import * as THREE from 'three';

// All textures are painted onto canvases at startup: no image downloads,
// which keeps the build tiny for web portals.

function rand(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function canvasTexture(size, paint, repeat = [1, 1]) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  paint(g, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = 4;
  return t;
}

function speckle(g, size, r, count, colors, maxR = 2) {
  for (let i = 0; i < count; i++) {
    g.fillStyle = colors[Math.floor(r() * colors.length)];
    const rad = r() * maxR + 0.3;
    g.fillRect(r() * size, r() * size, rad, rad);
  }
}

function blotches(g, size, r, count, color, maxRad) {
  for (let i = 0; i < count; i++) {
    const x = r() * size;
    const y = r() * size;
    const rad = r() * maxRad + 8;
    const grd = g.createRadialGradient(x, y, 0, x, y, rad);
    grd.addColorStop(0, color);
    grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd;
    g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
  }
}

export function wallTexture() {
  return canvasTexture(512, (g, s) => {
    const r = rand(7);
    g.fillStyle = '#6b6e63';
    g.fillRect(0, 0, s, s);
    blotches(g, s, r, 40, 'rgba(40,44,36,0.35)', 70);
    speckle(g, s, r, 9000, ['#5c5f55', '#7a7c70', '#4d5048', '#83857a']);
    // Water streaks running down from the top.
    for (let i = 0; i < 26; i++) {
      const x = r() * s;
      const len = r() * s * 0.7 + 40;
      const grd = g.createLinearGradient(0, 0, 0, len);
      grd.addColorStop(0, 'rgba(35,32,24,0.55)');
      grd.addColorStop(1, 'rgba(35,32,24,0)');
      g.fillStyle = grd;
      g.fillRect(x, 0, r() * 7 + 2, len);
    }
    // Grime band along the floor and a faded paint line.
    const band = g.createLinearGradient(0, s * 0.72, 0, s);
    band.addColorStop(0, 'rgba(25,24,20,0)');
    band.addColorStop(1, 'rgba(25,24,20,0.75)');
    g.fillStyle = band;
    g.fillRect(0, s * 0.72, s, s * 0.28);
    g.fillStyle = 'rgba(70,90,80,0.45)';
    g.fillRect(0, s * 0.6, s, 10);
    // Cracks.
    g.strokeStyle = 'rgba(20,20,18,0.6)';
    for (let i = 0; i < 6; i++) {
      g.lineWidth = r() * 1.5 + 0.5;
      g.beginPath();
      let x = r() * s;
      let y = r() * s;
      g.moveTo(x, y);
      for (let j = 0; j < 8; j++) {
        x += (r() - 0.5) * 40;
        y += r() * 30;
        g.lineTo(x, y);
      }
      g.stroke();
    }
  });
}

export function floorTexture(repeat) {
  return canvasTexture(512, (g, s) => {
    const r = rand(21);
    g.fillStyle = '#4a4740';
    g.fillRect(0, 0, s, s);
    const n = 4;
    const t = s / n;
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < n; x++) {
        const v = 60 + Math.floor(r() * 25);
        g.fillStyle = `rgb(${v + 8},${v + 4},${v - 4})`;
        g.fillRect(x * t + 2, y * t + 2, t - 4, t - 4);
        if (r() < 0.18) {
          g.fillStyle = 'rgba(15,14,12,0.7)';
          g.fillRect(x * t + 2, y * t + 2, t - 4, t - 4);
        }
      }
    }
    blotches(g, s, r, 30, 'rgba(20,18,12,0.5)', 80);
    speckle(g, s, r, 6000, ['#3a3832', '#5e5a50', '#2d2b26']);
  }, repeat);
}

export function ceilingTexture(repeat) {
  return canvasTexture(256, (g, s) => {
    const r = rand(33);
    g.fillStyle = '#34342f';
    g.fillRect(0, 0, s, s);
    blotches(g, s, r, 14, 'rgba(60,50,30,0.45)', 60);
    speckle(g, s, r, 2500, ['#2a2a26', '#3e3e38']);
    g.strokeStyle = 'rgba(0,0,0,0.5)';
    g.lineWidth = 3;
    g.strokeRect(0, 0, s, s);
  }, repeat);
}

export function crateTexture() {
  return canvasTexture(256, (g, s) => {
    const r = rand(44);
    g.fillStyle = '#5d4a33';
    g.fillRect(0, 0, s, s);
    for (let i = 0; i < 6; i++) {
      const y = (i * s) / 6;
      g.fillStyle = i % 2 ? '#56432d' : '#634f37';
      g.fillRect(0, y + 2, s, s / 6 - 4);
    }
    speckle(g, s, r, 3000, ['#3f3121', '#6f5a40', '#4a3a28'], 3);
    g.strokeStyle = '#2b2116';
    g.lineWidth = 10;
    g.strokeRect(5, 5, s - 10, s - 10);
    g.beginPath();
    g.moveTo(5, 5);
    g.lineTo(s - 5, s - 5);
    g.stroke();
  });
}

export function lockerTexture() {
  return canvasTexture(256, (g, s) => {
    const r = rand(55);
    g.fillStyle = '#4b5a5c';
    g.fillRect(0, 0, s, s);
    blotches(g, s, r, 16, 'rgba(110,60,25,0.55)', 40); // rust
    speckle(g, s, r, 2500, ['#3d4a4c', '#5b6a6c', '#6b4a30']);
    g.fillStyle = '#1b2021';
    for (let i = 0; i < 6; i++) g.fillRect(s * 0.3, s * 0.12 + i * 12, s * 0.4, 5); // vents
    g.fillRect(s * 0.8, s * 0.45, 10, 34); // handle
    g.strokeStyle = '#23292a';
    g.lineWidth = 6;
    g.strokeRect(3, 3, s - 6, s - 6);
  });
}

export function posterTexture(seed) {
  return canvasTexture(256, (g, s) => {
    const r = rand(seed);
    g.fillStyle = '#b8ae94';
    g.fillRect(0, 0, s, s);
    g.fillStyle = '#7d1414';
    g.fillRect(0, 0, s, s * 0.22);
    g.fillStyle = '#e8e0cc';
    g.font = 'bold 30px Impact, sans-serif';
    g.textAlign = 'center';
    g.fillText('THE ORDER', s / 2, s * 0.16);
    // Stylised eye emblem.
    g.fillStyle = '#1a1a1a';
    g.beginPath();
    g.ellipse(s / 2, s * 0.52, s * 0.3, s * 0.15, 0, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#b8ae94';
    g.beginPath();
    g.arc(s / 2, s * 0.52, s * 0.1, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#1a1a1a';
    g.beginPath();
    g.arc(s / 2, s * 0.52, s * 0.05, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#1a1a1a';
    g.font = 'bold 24px Impact, sans-serif';
    const lines = ['OBEDIENCE IS SAFETY', 'CURFEW IS PROTECTION', 'REPORT THE HIDDEN'];
    g.fillText(lines[Math.floor(r() * lines.length)], s / 2, s * 0.86);
    // Age and tears.
    blotches(g, s, r, 12, 'rgba(60,45,20,0.45)', 50);
    speckle(g, s, r, 1500, ['#8f866d', '#6d654f']);
    g.fillStyle = 'rgba(0,0,0,0.85)';
    for (let i = 0; i < 3; i++) {
      g.beginPath();
      const x = r() * s;
      g.moveTo(x, s);
      g.lineTo(x + 20 + r() * 30, s - 30 - r() * 40);
      g.lineTo(x + 50, s);
      g.fill();
    }
  });
}
