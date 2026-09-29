import * as THREE from 'three';
import { WALL_HEIGHT, toWorld } from './level-data.js';
import { hasLineOfSight } from './grid.js';
import { isLit } from './world.js';

const RANGE = 11;
const HALF_FOV = 0.42;
const SWEEP = 0.75; // radians either side of the mounted direction
const COOLDOWN = 9; // seconds before the same camera can raise another alarm

// A ceiling camera that sweeps a cone of light. If it sees you for long enough
// it raises an alarm: every patrol on the floor is sent to where you were.
export class SecurityCamera {
  constructor(scene, level, spec) {
    this.level = level;
    this.pos = new THREE.Vector3(toWorld(spec.x), WALL_HEIGHT - 0.35, toWorld(spec.z));
    this.baseYaw = Math.atan2(spec.dir[0], spec.dir[1]);
    this.yaw = this.baseYaw;
    this.phase = Math.random() * Math.PI * 2;
    this.detection = 0;
    this.cooldown = 0;
    this.alarm = 0;
    this.build(scene);
  }

  build(scene) {
    const g = new THREE.Group();
    const mount = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.3, 8), new THREE.MeshStandardMaterial({ color: 0x222426, metalness: 0.6 }));
    mount.position.y = 0.2;
    g.add(mount);
    this.head = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.16, 0.42), new THREE.MeshStandardMaterial({ color: 0x2a2d30, metalness: 0.7, roughness: 0.4 }));
    body.position.z = 0.1;
    this.head.add(body);
    this.lensMat = new THREE.MeshBasicMaterial({ color: 0xff2a1a });
    const lens = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), this.lensMat);
    lens.position.set(0, 0, 0.32);
    this.head.add(lens);
    this.beam = { on: true, pos: this.pos.clone(), target: new THREE.Vector3(), color: 0xff3a2a, intensity: 18, angle: HALF_FOV, distance: RANGE + 2, penumbra: 0.5 };
    const len = 6;
    const coneGeo = new THREE.ConeGeometry(Math.tan(HALF_FOV) * len * 0.7, len, 18, 1, true);
    coneGeo.translate(0, -len / 2, 0);
    coneGeo.rotateX(-Math.PI / 2 - 0.42);
    this.beamMat = new THREE.MeshBasicMaterial({ color: 0xff3a2a, transparent: true, opacity: 0.035, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const beam = new THREE.Mesh(coneGeo, this.beamMat);
    beam.position.set(0, 0, 0.2);
    this.head.add(beam);
    g.add(this.head);
    g.position.copy(this.pos);
    this.group = g;
    scene.add(g);
  }

  sees(player, world) {
    if (player.hidden) return 0;
    const head = player.head();
    const dx = head.x - this.pos.x;
    const dz = head.z - this.pos.z;
    const dist = Math.hypot(dx, dz);
    if (dist > RANGE || dist < 0.6) return 0;
    let ang = Math.atan2(dx, dz) - this.yaw;
    ang = Math.abs(Math.atan2(Math.sin(ang), Math.cos(ang)));
    if (ang > HALF_FOV) return 0;
    if (!hasLineOfSight(this.level, this.pos.x, this.pos.z, head.x, head.z, player.crouched)) return 0;
    let v = Math.max(0.2, 1 - dist / RANGE);
    if (player.crouched) v *= 0.55;
    if (!player.moving) v *= 0.7;
    if (player.flashOn) v *= 1.6;
    v *= isLit(world, head) ? 1.3 : 0.85;
    return v;
  }

  update(dt, t, ctx) {
    this.cooldown = Math.max(0, this.cooldown - dt);
    this.alarm = Math.max(0, this.alarm - dt);
    if (!this.registered && ctx.world) { ctx.world.beams.push(this.beam); this.registered = true; }
    this.yaw = this.baseYaw + Math.sin(t * 0.55 + this.phase) * SWEEP;
    this.head.rotation.y = this.yaw;
    this.beam.target.set(this.pos.x + Math.sin(this.yaw) * 6, this.pos.y - 2.6, this.pos.z + Math.cos(this.yaw) * 6);

    const v = this.cooldown > 0 ? 0 : this.sees(ctx.player, ctx.world);
    if (v > 0) this.detection = Math.min(1, this.detection + v * 1.1 * dt);
    else this.detection = Math.max(0, this.detection - 0.5 * dt);

    if (this.detection >= 1) {
      this.detection = 0;
      this.cooldown = COOLDOWN;
      this.alarm = 3;
      ctx.onAlarm(this);
    }
    const hot = this.alarm > 0;
    const col = hot ? 0xffffff : this.detection > 0.3 ? 0xff8a1a : 0xff3a2a;
    this.lensMat.color.setHex(col);
    this.beam.color = col;
    this.beam.intensity = hot ? 40 + Math.sin(t * 30) * 20 : 18;
    this.beamMat.opacity = hot ? 0.09 : 0.035;
  }
}
