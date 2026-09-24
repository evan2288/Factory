import * as THREE from 'three';
import { CELL, isSolid, toCell, toWorld } from './level-data.js';

const RADIUS = 0.35;
const EYE = 1.62;
const EYE_CROUCH = 0.9;
const SPEED = { walk: 3.0, sprint: 5.4, crouch: 1.5 };
// How far footsteps carry (metres) - enforcers within this radius hear you.
const NOISE = { walk: 5, sprint: 13, crouch: 0 };

export class Player {
  constructor(camera, level) {
    this.camera = camera;
    this.level = level;
    this.pos = new THREE.Vector3(toWorld(level.spawns.player.x), 0, toWorld(level.spawns.player.z));
    this.yaw = Math.PI; // face +Z into the level
    this.pitch = 0;
    this.eye = EYE;
    this.crouched = false;
    this.sprinting = false;
    this.moving = false;
    this.stamina = 1;
    this.exhausted = false;
    this.hidden = null; // locker object while hiding
    this.stepDist = 0;
    this.bob = 0;
    this.keys = new Set();

    this.flashlight = new THREE.SpotLight(0xfff1d6, 0, 22, 0.42, 0.55, 1.2);
    this.flashlight.position.set(0.25, -0.25, 0);
    this.flashlight.target.position.set(0, 0, -1);
    camera.add(this.flashlight);
    camera.add(this.flashlight.target);
    this.flashOn = false;
  }

  setFlashlight(on) {
    this.flashOn = on;
    this.flashlight.intensity = on ? 38 : 0;
  }

  look(dx, dy, sensitivity) {
    this.yaw -= dx * sensitivity;
    this.pitch -= dy * sensitivity;
    this.pitch = Math.max(-1.35, Math.min(1.35, this.pitch));
    if (this.hidden) {
      const base = Math.atan2(-this.hidden.facing.x, -this.hidden.facing.z);
      let d = this.yaw - base;
      d = Math.atan2(Math.sin(d), Math.cos(d));
      this.yaw = base + Math.max(-0.9, Math.min(0.9, d));
      this.pitch = Math.max(-0.5, Math.min(0.4, this.pitch));
    }
  }

  forward() {
    return new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
  }

  enterLocker(locker) {
    this.hidden = locker;
    this.preHide = this.pos.clone();
    // Peek out through the vents, facing the way the locker opens.
    this.yaw = Math.atan2(-locker.facing.x, -locker.facing.z);
    this.pitch = 0;
    this.pos.set(locker.pos.x + locker.facing.x * 0.55, 0, locker.pos.z + locker.facing.z * 0.55);
  }

  exitLocker() {
    const l = this.hidden;
    this.hidden = null;
    this.pos.copy(l.exit);
  }

  // Returns the noise radius emitted by a footstep this frame (0 if none).
  update(dt) {
    let noise = 0;
    this.crouched = this.keys.has('KeyC');
    const targetEye = this.hidden ? 1.55 : this.crouched ? EYE_CROUCH : EYE;
    this.eye += (targetEye - this.eye) * Math.min(1, dt * 10);

    if (this.hidden) {
      this.moving = false;
      this.sprinting = false;
      this.stamina = Math.min(1, this.stamina + dt * 0.2);
      this.applyCamera(0);
      return 0;
    }

    const f = this.forward();
    const r = new THREE.Vector3(-f.z, 0, f.x);
    const move = new THREE.Vector3();
    if (this.keys.has('KeyW') || this.keys.has('ArrowUp')) move.add(f);
    if (this.keys.has('KeyS') || this.keys.has('ArrowDown')) move.sub(f);
    if (this.keys.has('KeyD') || this.keys.has('ArrowRight')) move.add(r);
    if (this.keys.has('KeyA') || this.keys.has('ArrowLeft')) move.sub(r);
    this.moving = move.lengthSq() > 0;

    const wantSprint = (this.keys.has('ShiftLeft') || this.keys.has('ShiftRight')) && !this.crouched;
    this.sprinting = wantSprint && this.moving && !this.exhausted;
    if (this.sprinting) {
      this.stamina -= dt * 0.22;
      if (this.stamina <= 0) {
        this.stamina = 0;
        this.exhausted = true;
      }
    } else {
      this.stamina = Math.min(1, this.stamina + dt * (this.moving ? 0.1 : 0.18));
      if (this.exhausted && this.stamina > 0.35) this.exhausted = false;
    }

    const mode = this.crouched ? 'crouch' : this.sprinting ? 'sprint' : 'walk';
    if (this.moving) {
      move.normalize().multiplyScalar(SPEED[mode] * dt);
      const before = this.pos.clone();
      this.moveAxis(move.x, 0);
      this.moveAxis(0, move.z);
      const d = before.distanceTo(this.pos);
      this.stepDist += d;
      this.bob += d * (mode === 'sprint' ? 2.4 : 3);
      const stride = mode === 'sprint' ? 2.2 : mode === 'crouch' ? 1.3 : 1.8;
      if (this.stepDist > stride) {
        this.stepDist = 0;
        noise = NOISE[mode] || -1; // -1: a step happened but made no enforcer-audible noise
      }
    }
    this.applyCamera(this.moving ? (mode === 'sprint' ? 0.06 : 0.035) : 0);
    return noise;
  }

  moveAxis(dx, dz) {
    this.pos.x += dx;
    this.pos.z += dz;
    const minX = toCell(this.pos.x - RADIUS);
    const maxX = toCell(this.pos.x + RADIUS);
    const minZ = toCell(this.pos.z - RADIUS);
    const maxZ = toCell(this.pos.z + RADIUS);
    for (let z = minZ; z <= maxZ; z++) {
      for (let x = minX; x <= maxX; x++) {
        if (!isSolid(this.level, x, z)) continue;
        const cx0 = x * CELL;
        const cz0 = z * CELL;
        if (dx > 0) this.pos.x = Math.min(this.pos.x, cx0 - RADIUS - 0.001);
        else if (dx < 0) this.pos.x = Math.max(this.pos.x, cx0 + CELL + RADIUS + 0.001);
        if (dz > 0) this.pos.z = Math.min(this.pos.z, cz0 - RADIUS - 0.001);
        else if (dz < 0) this.pos.z = Math.max(this.pos.z, cz0 + CELL + RADIUS + 0.001);
      }
    }
  }

  applyCamera(bobAmt) {
    const bobY = Math.sin(this.bob) * bobAmt;
    this.camera.position.set(this.pos.x, this.eye + bobY, this.pos.z);
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }

  // World position of the head, used for enforcer line-of-sight.
  head() {
    return new THREE.Vector3(this.pos.x, this.eye, this.pos.z);
  }
}
