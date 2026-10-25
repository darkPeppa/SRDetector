// SVG drawings of the honeycomb detector (same conventions as DetectorConstruction:
// flat-top hexagons with corners on +-x, axial lattice x = sqrt(3)/2 p q, y = p (r + q/2)).
const Geo = (() => {
  const S3 = Math.sqrt(3);
  const f = (v, d = 4) => +v.toFixed(d);

  function hex(cx, cy, apothem) {
    const rc = 2 * apothem / S3;
    let s = '';
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 3 * i;
      s += (i ? 'L' : 'M') + f(cx + rc * Math.cos(a)) + ' ' + f(cy + rc * Math.sin(a));
    }
    return s + 'Z';
  }
  function circle(cx, cy, r) {
    return `M${f(cx - r)} ${f(cy)}a${f(r)} ${f(r)} 0 1 0 ${f(2 * r)} 0a${f(r)} ${f(r)} 0 1 0 ${f(-2 * r)} 0Z`;
  }
  function channel(cx, cy, r, shape) { return shape === 'hex' ? hex(cx, cy, r) : circle(cx, cy, r); }

  // Cell centres for the geometry modes (used for the preview before a run exists).
  function cells(mode, pitch, radius) {
    const rc = pitch / S3;
    if (mode === 'unit') return { cells: [[0, 0, 0, 0]], R: rc * 1.001 };
    if (mode === 'cluster7') {
      const qr = [[0, 0], [1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, -1]];
      return { cells: qr.map(([q, r]) => [q, r, S3 / 2 * pitch * q, pitch * (r + q / 2)]), R: pitch + rc };
    }
    const out = [];
    const n = Math.floor(2 * radius / pitch) + 2;
    for (let q = -n; q <= n; q++) for (let r = -n; r <= n; r++) {
      const x = S3 / 2 * pitch * q, y = pitch * (r + q / 2);
      if (Math.hypot(x, y) + rc <= radius - 0.0005) out.push([q, r, x, y]);
    }
    return { cells: out, R: radius };
  }

  // Full lattice: one path per material keeps 1e5 cells fast.
  function lattice(g) {
    const p = g.pitch, rCore = g.D / 2, t = g.t || 0, R = g.R, shape = g.shape || 'circle';
    let walls = '', coat = '', core = '';
    for (const c of g.cells) {
      walls += hex(c[2], c[3], p / 2);
      if (t > 0) coat += channel(c[2], c[3], rCore + t, shape);
      core += channel(c[2], c[3], rCore, shape);
    }
    const m = R * 1.08, hous = g.housing || 0;
    return `<svg viewBox="${f(-m)} ${f(-m)} ${f(2 * m)} ${f(2 * m)}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
      ${hous > 0 ? `<circle r="${f(R + hous)}" fill="#9aa3b1" opacity=".5"/>` : ''}
      <circle r="${f(R)}" fill="var(--rim)" stroke="var(--muted)" stroke-width="${f(R / 400)}"/>
      <path d="${walls}" fill="var(--wall)" stroke="var(--panel)" stroke-width="${f(p / 60)}"/>
      ${t > 0 ? `<path d="${coat}" fill="var(--coat)"/>` : ''}
      <path d="${core}" fill="var(--core)"/>
    </svg>`;
  }

  // Close-up of the central cell and its neighbours with dimension labels (lengths in mm).
  function closeup(g) {
    const p = g.pitch, rCore = g.D / 2, t = g.t || 0, shape = g.shape || 'circle';
    const wall = p - g.D - 2 * t;
    const m = p * 1.7, fs = p / 11, sw = p / 200;
    let walls = '', coat = '', core = '';
    const qr = [[0, 0], [1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, -1]];
    for (const [q, r] of qr) {
      const x = S3 / 2 * p * q, y = p * (r + q / 2);
      walls += hex(x, y, p / 2);
      if (t > 0) coat += channel(x, y, rCore + t, shape);
      core += channel(x, y, rCore, shape);
    }
    const um = v => (v * 1000).toFixed(v * 1000 < 10 ? 1 : 0) + ' мкм';
    const ax = S3 / 2 * p, ay = p / 2;
    return `<svg viewBox="${f(-m)} ${f(-m)} ${f(2 * m)} ${f(2 * m)}" xmlns="http://www.w3.org/2000/svg">
      <defs><marker id="ar" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--text)"/></marker></defs>
      <path d="${walls}" fill="var(--wall)" stroke="var(--panel)" stroke-width="${f(p / 80)}"/>
      ${t > 0 ? `<path d="${coat}" fill="var(--coat)"/>` : ''}
      <path d="${core}" fill="var(--core)" opacity=".92"/>
      <g stroke="var(--text)" stroke-width="${f(sw)}" fill="none">
        <line x1="0" y1="0" x2="${f(ax)}" y2="${f(ay)}" marker-start="url(#ar)" marker-end="url(#ar)"/>
        <line x1="${f(-rCore)}" y1="${f(-p * 0.62)}" x2="${f(rCore)}" y2="${f(-p * 0.62)}" marker-start="url(#ar)" marker-end="url(#ar)"/>
        <line x1="${f(-rCore)}" y1="${f(-p * 0.55)}" x2="${f(-rCore)}" y2="${f(-p * 0.1)}" stroke-dasharray="${f(sw * 4)}"/>
        <line x1="${f(rCore)}" y1="${f(-p * 0.55)}" x2="${f(rCore)}" y2="${f(-p * 0.1)}" stroke-dasharray="${f(sw * 4)}"/>
      </g>
      <g fill="var(--text)" font-size="${f(fs)}" font-family="sans-serif" paint-order="stroke" stroke="var(--panel)" stroke-width="${f(fs / 4)}" stroke-linejoin="round">
        <text x="${f(ax * 0.55)}" y="${f(ay * 0.5 - fs * 0.4)}">шаг ${um(p)}</text>
        <text x="${f(-rCore)}" y="${f(-p * 0.67)}">D = ${um(g.D)}</text>
        <text x="${f(-m * 0.96)}" y="${f(m * 0.86)}">стенка (мин.) ${um(Math.max(wall, 0))}${t > 0 ? ', покрытие ' + um(t) : ''}</text>
        <text x="${f(-m * 0.96)}" y="${f(m * 0.96)}">доля сцинтиллятора ${(g.fill * 100).toFixed(1)} %</text>
      </g>
    </svg>`;
  }

  // Beam-axis cross-section; thin layers get a minimum drawn width, labels show the real values.
  function stack(g) {
    const layers = [
      ['окно', g.window, '#9fb3d9', g.windowMat],
      ['матрица (каналы)', g.L, 'var(--core)', g.core],
      ['смазка', g.coupling, '#e5d36b', g.couplingMat],
      ['окно сенсора', g.sensorWindow, '#b9c6e6', ''],
      ['Si сенсор', g.active, '#3a4fa8', g.sensor],
    ].filter(l => l[1] > 1e-6);
    const W = 560, H = 150, x0 = 28, avail = W - 2 * x0;
    const minw = 26, total = layers.reduce((s, l) => s + l[1], 0);
    let widths = layers.map(l => Math.max(minw, l[1] / total * avail));
    const scale = avail / widths.reduce((a, b) => a + b, 0);
    widths = widths.map(w => w * scale);
    let x = x0, out = '';
    const mm = v => v >= 1 ? v.toFixed(v >= 10 ? 0 : 1) + ' мм' : (v * 1000).toFixed(0) + ' мкм';
    layers.forEach((l, i) => {
      out += `<rect x="${f(x)}" y="40" width="${f(widths[i])}" height="62" fill="${l[2]}" stroke="var(--panel)"/>`;
      out += `<text x="${f(x + widths[i] / 2)}" y="${i % 2 ? 122 : 134}" text-anchor="middle" font-size="11" fill="var(--text)">${l[0]}</text>`;
      out += `<text x="${f(x + widths[i] / 2)}" y="${i % 2 ? 30 : 20}" text-anchor="middle" font-size="10.5" fill="var(--muted)">${mm(l[1])}${l[3] ? ' · ' + l[3] : ''}</text>`;
      x += widths[i];
    });
    return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
      <defs><marker id="beam" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--accent-2)"/></marker></defs>
      <line x1="2" y1="71" x2="${x0 - 3}" y2="71" stroke="var(--accent-2)" stroke-width="2" marker-end="url(#beam)"/>
      <text x="2" y="62" font-size="10" fill="var(--accent-2)">пучок</text>${out}</svg>`;
  }

  // Wheel zoom + drag pan on an <svg> inside `host`.
  function interactive(host) {
    const svg = host.querySelector('svg');
    if (!svg) return;
    const vb0 = svg.getAttribute('viewBox').split(' ').map(Number);
    let vb = [...vb0], drag = null;
    const set = () => svg.setAttribute('viewBox', vb.map(v => +v.toFixed(5)).join(' '));
    svg.addEventListener('wheel', e => {
      e.preventDefault();
      const r = svg.getBoundingClientRect(), k = e.deltaY > 0 ? 1.25 : 0.8;
      const px = vb[0] + (e.clientX - r.left) / r.width * vb[2], py = vb[1] + (e.clientY - r.top) / r.height * vb[3];
      vb = [px - (px - vb[0]) * k, py - (py - vb[1]) * k, vb[2] * k, vb[3] * k];
      set();
    }, { passive: false });
    svg.addEventListener('mousedown', e => { drag = [e.clientX, e.clientY, [...vb]]; svg.style.cursor = 'grabbing'; });
    window.addEventListener('mouseup', () => { drag = null; svg.style.cursor = ''; });
    svg.addEventListener('mousemove', e => {
      if (!drag) return;
      const r = svg.getBoundingClientRect();
      vb = [drag[2][0] - (e.clientX - drag[0]) / r.width * vb[2], drag[2][1] - (e.clientY - drag[1]) / r.height * vb[3], vb[2], vb[3]];
      set();
    });
    svg.addEventListener('dblclick', () => { vb = [...vb0]; set(); });
  }

  return { cells, lattice, closeup, stack, interactive, S3 };
})();
