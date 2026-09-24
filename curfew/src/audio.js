// Procedural WebAudio: no sound files needed.
export class Sound {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.muted = false;
  }

  // Must be called from a user gesture (browsers block autoplay).
  start() {
    if (this.ctx) {
      this.ctx.resume();
      return;
    }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.master = this.ctx.createGain();
    this.master.gain.value = this.muted ? 0 : 0.8;
    this.master.connect(this.ctx.destination);
    this.noiseBuf = this.makeNoise(2);
    this.startAmbience();
    this.heart = { next: 0 };
  }

  suspend() { this.ctx?.suspend(); }

  setMuted(m) {
    this.muted = m;
    if (this.master) this.master.gain.value = m ? 0 : 0.8;
  }

  makeNoise(seconds) {
    const len = this.ctx.sampleRate * seconds;
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  startAmbience() {
    const c = this.ctx;
    const drone = c.createGain();
    drone.gain.value = 0.05;
    drone.connect(this.master);
    for (const f of [41, 41.7, 62]) {
      const o = c.createOscillator();
      o.type = 'sawtooth';
      o.frequency.value = f;
      const lp = c.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 180;
      o.connect(lp).connect(drone);
      o.start();
    }
    // Wind through broken windows.
    const n = c.createBufferSource();
    n.buffer = this.noiseBuf;
    n.loop = true;
    const bp = c.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = 400;
    bp.Q.value = 0.7;
    const wg = c.createGain();
    wg.gain.value = 0.035;
    const lfo = c.createOscillator();
    lfo.frequency.value = 0.07;
    const lfoGain = c.createGain();
    lfoGain.gain.value = 250;
    lfo.connect(lfoGain).connect(bp.frequency);
    lfo.start();
    n.connect(bp).connect(wg).connect(this.master);
    n.start();
  }

  // Volume/pan from a world position relative to the listener.
  spatial(pos, listener) {
    if (!pos || !listener) return { gain: 1, pan: 0 };
    const dx = pos.x - listener.pos.x;
    const dz = pos.z - listener.pos.z;
    const dist = Math.hypot(dx, dz);
    const gain = Math.max(0, 1 - dist / 22) ** 1.6;
    // Listener faces -Z rotated by yaw; right vector is (cos, -sin).
    const rx = Math.cos(listener.yaw);
    const rz = -Math.sin(listener.yaw);
    const pan = dist > 0.01 ? Math.max(-1, Math.min(1, (dx * rx + dz * rz) / dist)) : 0;
    return { gain, pan };
  }

  out(gain, pan) {
    const g = this.ctx.createGain();
    g.gain.value = gain;
    const p = this.ctx.createStereoPanner ? this.ctx.createStereoPanner() : null;
    if (p) {
      p.pan.value = pan;
      g.connect(p).connect(this.master);
    } else g.connect(this.master);
    return g;
  }

  noiseBurst({ dur = 0.08, freq = 900, q = 1, vol = 0.3, pos, listener, type = 'bandpass' }) {
    if (!this.ctx) return;
    const { gain, pan } = this.spatial(pos, listener);
    if (gain < 0.01) return;
    const c = this.ctx;
    const src = c.createBufferSource();
    src.buffer = this.noiseBuf;
    const f = c.createBiquadFilter();
    f.type = type;
    f.frequency.value = freq;
    f.Q.value = q;
    const env = c.createGain();
    const t = c.currentTime;
    env.gain.setValueAtTime(vol * gain, t);
    env.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f).connect(env).connect(this.out(1, pan));
    src.start(t, Math.random() * 1.5, dur + 0.05);
  }

  tone({ freq = 440, dur = 0.15, vol = 0.2, type = 'square', pos, listener, slide = 0 }) {
    if (!this.ctx) return;
    const { gain, pan } = this.spatial(pos, listener);
    if (gain < 0.01) return;
    const c = this.ctx;
    const o = c.createOscillator();
    o.type = type;
    const t = c.currentTime;
    o.frequency.setValueAtTime(freq, t);
    if (slide) o.frequency.linearRampToValueAtTime(freq + slide, t + dur);
    const env = c.createGain();
    env.gain.setValueAtTime(vol * gain, t);
    env.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(env).connect(this.out(1, pan));
    o.start(t);
    o.stop(t + dur + 0.02);
  }

  footstep(crouched) {
    this.noiseBurst({ dur: 0.07, freq: crouched ? 500 : 750, q: 1.2, vol: crouched ? 0.07 : 0.16, type: 'lowpass' });
  }

  enforcerStep(pos, listener) {
    this.noiseBurst({ dur: 0.09, freq: 300, q: 1, vol: 0.5, pos, listener, type: 'lowpass' });
    this.noiseBurst({ dur: 0.03, freq: 2400, q: 4, vol: 0.12, pos, listener }); // boot clink
  }

  radio(pos, listener) {
    if (!this.ctx) return;
    for (let i = 0; i < 6; i++) {
      setTimeout(() => this.noiseBurst({ dur: 0.09, freq: 1400 + Math.random() * 900, q: 6, vol: 0.35, pos, listener }), i * 85);
    }
    this.tone({ freq: 1250, dur: 0.06, vol: 0.12, type: 'sine', pos, listener });
  }

  alert(pos, listener) {
    this.tone({ freq: 660, dur: 0.18, vol: 0.25, type: 'square', pos, listener });
    setTimeout(() => this.tone({ freq: 880, dur: 0.28, vol: 0.25, type: 'square', pos, listener }), 170);
  }

  suspicious(pos, listener) {
    this.tone({ freq: 520, dur: 0.25, vol: 0.15, type: 'triangle', pos, listener, slide: 120 });
  }

  pickup() {
    this.tone({ freq: 700, dur: 0.12, vol: 0.2, type: 'sine' });
    setTimeout(() => this.tone({ freq: 1050, dur: 0.2, vol: 0.2, type: 'sine' }), 110);
  }

  locker() {
    this.noiseBurst({ dur: 0.25, freq: 1800, q: 8, vol: 0.2 });
    this.tone({ freq: 90, dur: 0.2, vol: 0.25, type: 'sine' });
  }

  caught() {
    this.tone({ freq: 220, dur: 1.2, vol: 0.35, type: 'sawtooth', slide: -150 });
    this.noiseBurst({ dur: 0.6, freq: 200, q: 0.5, vol: 0.6, type: 'lowpass' });
  }

  win() {
    [523, 659, 784, 1046].forEach((f, i) => setTimeout(() => this.tone({ freq: f, dur: 0.4, vol: 0.18, type: 'triangle' }), i * 150));
  }

  // Heartbeat whose rate follows how close you are to being spotted.
  updateHeart(level, now) {
    if (!this.ctx || level < 0.15) return;
    if (now < this.heart.next) return;
    const interval = 1.1 - level * 0.65;
    this.heart.next = now + interval;
    const vol = 0.15 + level * 0.35;
    this.tone({ freq: 55, dur: 0.12, vol, type: 'sine' });
    setTimeout(() => this.tone({ freq: 48, dur: 0.14, vol: vol * 0.8, type: 'sine' }), 140);
  }

  distantSiren() {
    if (!this.ctx) return;
    const c = this.ctx;
    const o = c.createOscillator();
    o.type = 'sine';
    const t = c.currentTime;
    o.frequency.setValueAtTime(500, t);
    for (let i = 0; i < 4; i++) {
      o.frequency.linearRampToValueAtTime(760, t + i * 2 + 1);
      o.frequency.linearRampToValueAtTime(500, t + i * 2 + 2);
    }
    const env = c.createGain();
    env.gain.setValueAtTime(0, t);
    env.gain.linearRampToValueAtTime(0.03, t + 1.5);
    env.gain.linearRampToValueAtTime(0, t + 8);
    const lp = c.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 900;
    o.connect(lp).connect(env).connect(this.master);
    o.start(t);
    o.stop(t + 8.1);
  }
}
