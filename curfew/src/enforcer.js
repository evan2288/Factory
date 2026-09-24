import * as THREE from 'three';
import { isSolid, toCell, toWorld } from './level-data.js';
import { findPath, hasLineOfSight, openCells } from './grid.js';

const VIEW_DIST = 17;
const FOV = 0.62; // half-angle of the flashlight beam (radians)
const CATCH_DIST = 1.1;
const STATE_COLORS = { patrol: 0xfff0d0, suspicious: 0xffb030, search: 0xffb030, chase: 0xff2a1a, check: 0xff2a1a };

export class Enforcer {
  constructor(scene, level, cell, difficulty = 1) {
    this.level = level;
    this.difficulty = difficulty;
    this.pos = new THREE.Vector3(toWorld(cell.x), 0, toWorld(cell.z));
    this.yaw = Math.random() * Math.PI * 2;
    this.state = 'patrol';
    this.detection = 0;
    this.path = [];
    this.pathIdx = 0;
    this.wait = 1 + Math.random() * 2;
    this.lookTimer = 0;
    this.lookBase = this.yaw;
    this.lastKnown = null;
    this.lostTimer = 0;
    this.repathTimer = 0;
    this.stepTimer = 0;
    this.targetLocker = null;
    this.sawPlayer = false;
    this.open = openCells(level);
    this.build(scene);
  }

  build(scene) {
    const g = new THREE.Group();
    const uniform = new THREE.MeshStandardMaterial({ color: 0x1b1e22, roughness: 0.7 });
    const armor = new THREE.MeshStandardMaterial({ color: 0x2a2f35, roughness: 0.4, metalness: 0.5 });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.33, 0.95, 4, 10), uniform);
    body.position.y = 0.95;
    g.add(body);
    const vest = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.55, 0.42), armor);
    vest.position.y = 1.2;
    g.add(vest);
    const helmet = new THREE.Mesh(new THREE.SphereGeometry(0.24, 14, 10), armor);
    helmet.position.y = 1.78;
    helmet.scale.set(1, 1.05, 1.1);
    g.add(helmet);
    this.visorMat = new THREE.MeshBasicMaterial({ color: STATE_COLORS.patrol });
    const visor = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.07, 0.05), this.visorMat);
    visor.position.set(0, 1.78, 0.25);
    g.add(visor);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.1, 10), new THREE.MeshBasicMaterial({ color: 0x8a1010 }));
    band.position.set(0.38, 1.3, 0);
    band.rotation.z = Math.PI / 2;
    g.add(band);

    // Flashlight held at chest height, plus a faint visible beam.
    this.light = new THREE.SpotLight(STATE_COLORS.patrol, 55, VIEW_DIST + 3, FOV, 0.45, 1.25);
    this.light.position.set(0.2, 1.35, 0.3);
    this.light.target.position.set(0.2, 0.6, 6);
    g.add(this.light);
    g.add(this.light.target);

    const len = 7;
    const coneGeo = new THREE.ConeGeometry(Math.tan(FOV) * len * 0.8, len, 24, 1, true);
    coneGeo.translate(0, -len / 2, 0);
    coneGeo.rotateX(-Math.PI / 2 + 0.12);
    this.beamMat = new THREE.MeshBasicMaterial({
      color: STATE_COLORS.patrol, transparent: true, opacity: 0.045,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
    });
    const beam = new THREE.Mesh(coneGeo, this.beamMat);
    beam.position.copy(this.light.position);
    g.add(beam);

    this.group = g;
    scene.add(g);
    this.sync();
  }

  sync() {
    this.group.position.copy(this.pos);
    this.group.rotation.y = this.yaw;
  }

  setState(s, ctx) {
    if (this.state === s) return;
    const prev = this.state;
    this.state = s;
    const col = STATE_COLORS[s];
    this.light.color.setHex(col);
    this.visorMat.color.setHex(col);
    this.beamMat.color.setHex(col);
    this.beamMat.opacity = s === 'chase' ? 0.08 : 0.045;
    if (s === 'chase' && prev !== 'check') ctx.sound.alert(this.pos, ctx.listener);
    else if (s === 'suspicious' || s === 'search') ctx.sound.suspicious(this.pos, ctx.listener);
    if (s === 'patrol' && prev !== 'patrol') ctx.sound.radio(this.pos, ctx.listener);
  }

  cell() {
    return { x: toCell(this.pos.x), z: toCell(this.pos.z) };
  }

  goTo(worldPos) {
    let tx = toCell(worldPos.x);
    let tz = toCell(worldPos.z);
    if (isSolid(this.level, tx, tz)) {
      const n = [[1, 0], [-1, 0], [0, 1], [0, -1]].find(([dx, dz]) => !isSolid(this.level, tx + dx, tz + dz));
      if (!n) return false;
      tx += n[0];
      tz += n[1];
    }
    const c = this.cell();
    const p = findPath(this.level, c.x, c.z, tx, tz);
    if (!p) return false;
    this.path = p.map((q) => new THREE.Vector3(toWorld(q.x), 0, toWorld(q.z)));
    // Final waypoint goes to the exact spot, not the cell centre.
    if (!isSolid(this.level, toCell(worldPos.x), toCell(worldPos.z))) this.path[this.path.length - 1] = worldPos.clone().setY(0);
    // Skip the cell we're standing in, unless the target is inside it.
    this.pathIdx = this.path.length > 1 ? 1 : 0;
    return true;
  }

  pickPatrolTarget() {
    for (let i = 0; i < 8; i++) {
      const c = this.open[Math.floor(Math.random() * this.open.length)];
      const d = Math.hypot(c.x - toCell(this.pos.x), c.z - toCell(this.pos.z));
      if (d > 4 && d < 16 && this.goTo(new THREE.Vector3(toWorld(c.x), 0, toWorld(c.z)))) return;
    }
  }

  // Walk along the current path. Returns true when the path is done.
  follow(dt, speed) {
    if (this.pathIdx >= this.path.length) return true;
    const t = this.path[this.pathIdx];
    const dx = t.x - this.pos.x;
    const dz = t.z - this.pos.z;
    const d = Math.hypot(dx, dz);
    if (d < 0.15) {
      this.pathIdx++;
      return this.pathIdx >= this.path.length;
    }
    const step = Math.min(d, speed * dt);
    this.pos.x += (dx / d) * step;
    this.pos.z += (dz / d) * step;
    this.turnTo(Math.atan2(dx, dz), dt * 7);
    return false;
  }

  turnTo(target, rate) {
    let diff = target - this.yaw;
    diff = Math.atan2(Math.sin(diff), Math.cos(diff));
    this.yaw += Math.max(-rate, Math.min(rate, diff));
  }

  lookAround(dt) {
    this.lookTimer += dt;
    this.yaw = this.lookBase + Math.sin(this.lookTimer * 1.3) * 1.1;
  }

  // How visible the player is to this enforcer right now (0 = not at all).
  visibility(ctx) {
    const { player, lights } = ctx;
    if (player.hidden) return 0;
    const head = player.head();
    const dx = head.x - this.pos.x;
    const dz = head.z - this.pos.z;
    const dist = Math.hypot(dx, dz);
    if (dist > VIEW_DIST) return 0;
    let ang = Math.atan2(dx, dz) - this.yaw;
    ang = Math.abs(Math.atan2(Math.sin(ang), Math.cos(ang)));
    const inBeam = ang < FOV;
    const peripheral = dist < 3 && ang < 1.9;
    if (!inBeam && !peripheral && !(player.flashOn && ang < 1.3)) return 0;
    if (!hasLineOfSight(this.level, this.pos.x, this.pos.z, head.x, head.z, player.crouched)) return 0;

    let v = Math.max(0.12, 1 - dist / VIEW_DIST);
    if (inBeam && ang < FOV * 0.5) v *= 1.3;
    if (player.crouched) v *= 0.5;
    if (player.sprinting) v *= 1.4;
    else if (!player.moving) v *= 0.6;
    if (player.flashOn) v *= 1.9;
    const lit = lights.some((l) => l.light.intensity > 1 && l.pos.distanceTo(head) < 4.5);
    v *= lit ? 1.35 : 0.75;
    return v;
  }

  hear(pos, radius, ctx) {
    if (this.state === 'chase' || this.state === 'check') return;
    if (this.pos.distanceTo(pos) > radius) return;
    this.lastKnown = pos.clone();
    this.lookTimer = 0;
    this.goTo(pos);
    this.setState('suspicious', ctx);
  }

  update(dt, ctx) {
    const { player } = ctx;
    const vis = this.visibility(ctx);
    const seen = vis > 0;
    const d = this.difficulty;
    if (seen) {
      this.detection = Math.min(1, this.detection + vis * 1.5 * d * dt);
      this.lastKnown = player.pos.clone();
    } else if (this.state !== 'chase') {
      this.detection = Math.max(0, this.detection - 0.22 * dt);
    }

    // Seen climbing into a locker: he'll check it.
    if (player.hidden && !this.targetLocker && this.state === 'chase' && this.sawPlayer && this.lostTimer < 0.6) {
      const l = player.hidden;
      if (hasLineOfSight(this.level, this.pos.x, this.pos.z, l.exit.x, l.exit.z)) {
        this.targetLocker = l;
        l.compromised = true;
        this.goTo(l.exit);
        this.setState('check', ctx);
      }
    }
    this.sawPlayer = seen;

    let speed = 0;
    switch (this.state) {
      case 'patrol': {
        speed = 1.5 * d;
        if (this.detection >= 1) { this.setState('chase', ctx); break; }
        if (this.detection > 0.4 && this.lastKnown) {
          this.goTo(this.lastKnown);
          this.lookTimer = 0;
          this.setState('suspicious', ctx);
          break;
        }
        if (this.pathIdx >= this.path.length) {
          speed = 0;
          this.wait -= dt;
          this.lookAround(dt);
          if (this.wait <= 0) {
            this.pickPatrolTarget();
            this.wait = 1.5 + Math.random() * 2.5;
            this.lookTimer = 0;
          }
        } else if (this.follow(dt, speed)) {
          this.lookBase = this.yaw;
        }
        break;
      }
      case 'suspicious':
      case 'search': {
        speed = 2.3 * d;
        if (this.detection >= 1) { this.setState('chase', ctx); break; }
        if (seen && this.lastKnown) {
          // Face toward the movement he glimpsed.
          this.turnTo(Math.atan2(player.pos.x - this.pos.x, player.pos.z - this.pos.z), dt * 4);
          speed = 0.8;
        }
        if (this.pathIdx >= this.path.length) {
          speed = 0;
          if (this.lookTimer === 0) this.lookBase = this.yaw;
          this.lookAround(dt);
          const limit = this.state === 'search' ? 6 : 3.5;
          if (this.lookTimer > limit) {
            this.detection = Math.min(this.detection, 0.2);
            this.setState('patrol', ctx);
            this.wait = 0.5;
          }
        } else {
          this.follow(dt, speed);
        }
        break;
      }
      case 'chase': {
        speed = 4.5 * d;
        this.repathTimer -= dt;
        if (seen) {
          this.lostTimer = 0;
          if (this.repathTimer <= 0) {
            this.goTo(player.pos);
            this.repathTimer = 0.35;
          }
        } else {
          this.lostTimer += dt;
          if (this.pathIdx >= this.path.length || this.lostTimer > 4) {
            this.detection = 0.6;
            if (this.lastKnown) this.goTo(this.lastKnown);
            this.lookTimer = 0;
            this.setState('search', ctx);
            break;
          }
        }
        this.follow(dt, speed);
        if (!player.hidden && this.pos.distanceTo(player.pos) < CATCH_DIST) ctx.onCaught(this);
        break;
      }
      case 'check': {
        speed = 3.8 * d;
        const done = this.follow(dt, speed);
        const l = this.targetLocker;
        this.turnTo(Math.atan2(l.pos.x - this.pos.x, l.pos.z - this.pos.z), dt * 5);
        if (done || this.pos.distanceTo(l.exit) < 0.7) {
          if (player.hidden === l) ctx.onCaught(this, true);
          this.targetLocker = null;
          l.compromised = false;
          this.lookTimer = 0;
          this.setState('search', ctx);
        }
        break;
      }
    }

    if (speed > 0.1 && this.pathIdx < this.path.length) {
      this.stepTimer -= dt;
      if (this.stepTimer <= 0) {
        this.stepTimer = speed > 3 ? 0.3 : 0.55;
        ctx.sound.enforcerStep(this.pos, ctx.listener);
      }
    }
    this.sync();
  }
}
