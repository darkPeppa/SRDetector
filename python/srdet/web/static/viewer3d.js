// 3D viewer of a simulated run: honeycomb geometry from geometry.json + Geant4 trajectories
// from tracks.jsonl. Loaded as an ES module; exposes window.Viewer3D.create(host, geo, events).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export const PARTICLES = {
  gamma: { color: 0xf4c430, label: 'γ (фотоны)' },
  'e-': { color: 0xe74c3c, label: 'e⁻' },
  'e+': { color: 0x3498db, label: 'e⁺' },
  opticalphoton: { color: 0xff9f43, label: 'оптические фотоны', opacity: 0.35 },
  other: { color: 0x9aa3b1, label: 'прочие' },
};
const kind = n => (PARTICLES[n] ? n : 'other');

function create(host, geo, events, opts = {}) {
  host.innerHTML = '';
  const W = host.clientWidth || 900, H = host.clientHeight || 560;
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(W, H);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(opts.background || 0x10141b);
  const camera = new THREE.PerspectiveCamera(40, W / H, 0.001, 5000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.AmbientLight(0xffffff, 0.65));
  const sun = new THREE.DirectionalLight(0xffffff, 0.9);
  sun.position.set(30, 40, -60);
  scene.add(sun);

  const R = geo.matrix_radius_mm, L = geo.length_mm, pitch = geo.pitch_mm || 0.2;
  const zAxis = g => { g.rotateX(Math.PI / 2); return g; };  // three cylinders run along y; ours along z
  const world = new THREE.Group();
  scene.add(world);

  // ---- matrix shell, window, coupling, sensor
  const shell = new THREE.Mesh(zAxis(new THREE.CylinderGeometry(R, R, L, 96, 1, true)),
    new THREE.MeshPhongMaterial({ color: 0x8fa3bf, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false }));
  world.add(shell);
  const disc = (z0, z1, color, opacity) => {
    if (!(z1 > z0)) return;
    const m = new THREE.Mesh(zAxis(new THREE.CylinderGeometry(R, R, z1 - z0, 96)),
      new THREE.MeshPhongMaterial({ color, transparent: true, opacity, depthWrite: false }));
    m.position.z = (z0 + z1) / 2;
    world.add(m);
  };
  disc(geo.z_front_mm, -L / 2, 0x9fb3d9, 0.10);          // entrance window
  disc(L / 2, geo.z_sensor_mm, 0xe5d36b, 0.15);          // coupling (+ sensor window)
  disc(geo.z_sensor_mm, geo.z_back_mm, 0x3a4fa8, 0.30);  // Si sensor

  const state = { visible: Object.fromEntries(Object.keys(PARTICLES).map(k => [k, true])), event: null, lines: {},
                  allCells: (geo.cells || []).length <= 500, cellsShown: 0 };
  // ---- cells (instanced): hex walls + channel cores
  const cells = geo.cells || [];
  const rc = pitch / Math.sqrt(3), rCore = (geo.channel_diameter_mm || pitch * 0.9) / 2;
  const hexGeo = zAxis(new THREE.CylinderGeometry(rc * 0.995, rc * 0.995, L, 6, 1));
  hexGeo.rotateZ(Math.PI / 6);  // corners on +-x (flat-top) like DetectorConstruction
  const coreGeo = zAxis(new THREE.CylinderGeometry(rCore, rCore, L, cells.length > 3000 ? 10 : 24, 1));
  const wallMat = new THREE.MeshPhongMaterial({ color: 0x9aa3b1, transparent: true, opacity: 0.18, depthWrite: false });
  const coreMat = new THREE.MeshPhongMaterial({ color: 0x4caf7a, transparent: true, opacity: 0.22, depthWrite: false });
  // cells touched by any track (within one pitch in x-y): with thousands of cells only these are
  // drawn by default, otherwise the stacked transparent prisms hide the tracks
  const pts = events.flatMap(e => e.tracks.flatMap(t => t.pts));
  const touched = new Set();
  if (pts.length) {
    const bin = new Map();
    pts.forEach(p => { const k = Math.round(p[0] / pitch) + ',' + Math.round(p[1] / pitch); bin.set(k, true); });
    cells.forEach((c, i) => {
      const bx = Math.round(c[2] / pitch), by = Math.round(c[3] / pitch);
      for (let dx = -1; dx <= 1 && !touched.has(i); dx++)
        for (let dy = -1; dy <= 1; dy++) if (bin.has((bx + dx) + ',' + (by + dy))) { touched.add(i); break; }
    });
  }
  const walls = new THREE.InstancedMesh(hexGeo, wallMat, Math.max(cells.length, 1));
  const cores = new THREE.InstancedMesh(coreGeo, coreMat, Math.max(cells.length, 1));
  const m4 = new THREE.Matrix4();
  function placeCells(all) {
    let n = 0;
    cells.forEach((c, i) => {
      if (!all && !touched.has(i)) return;
      m4.makeTranslation(c[2], c[3], 0);
      walls.setMatrixAt(n, m4);
      cores.setMatrixAt(n, m4);
      n++;
    });
    walls.count = cores.count = n;
    walls.instanceMatrix.needsUpdate = cores.instanceMatrix.needsUpdate = true;
    state.cellsShown = n;
  }
  placeCells(state.allCells);
  world.add(walls, cores);

  // ---- tracks: one LineSegments object per particle kind
  const trackGroup = new THREE.Group();
  scene.add(trackGroup);

  function buildTracks() {
    trackGroup.clear();
    state.lines = {};
    const seg = Object.fromEntries(Object.keys(PARTICLES).map(k => [k, []]));
    const evs = state.event === null ? events : events.filter(e => e.evt === state.event);
    for (const ev of evs) {
      for (const t of ev.tracks) {
        const k = kind(t.name), p = t.pts;
        for (let i = 1; i < p.length; i++) seg[k].push(...p[i - 1], ...p[i]);
      }
    }
    for (const [k, arr] of Object.entries(seg)) {
      if (!arr.length) continue;
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3));
      const mat = new THREE.LineBasicMaterial({ color: PARTICLES[k].color, transparent: true,
                                                opacity: PARTICLES[k].opacity ?? 0.95, depthWrite: false });
      const line = new THREE.LineSegments(g, mat);
      line.visible = state.visible[k];
      trackGroup.add(line);
      state.lines[k] = line;
    }
  }
  buildTracks();

  // ---- camera framing
  // frame the tracks (the beam region) if there are any, else the whole detector
  function frameBox(sel) {
    const b = new THREE.Box3();
    sel.forEach(p => b.expandByPoint(new THREE.Vector3(p[0], p[1], Math.max(Math.min(p[2], geo.z_back_mm + 1), geo.z_front_mm - 2))));
    return b;
  }
  let box = frameBox(pts);
  function resetCamera() {
    const c = pts.length ? box.getCenter(new THREE.Vector3()) : new THREE.Vector3();
    const size = pts.length ? box.getSize(new THREE.Vector3()) : new THREE.Vector3(R * 2, R * 2, L);
    const span = Math.max(size.x, size.y, size.z, L, pitch * 6) * 1.5;
    camera.position.set(c.x + span * 0.9, c.y + span * 0.55, c.z - span * 0.9);
    controls.target.copy(c);
    camera.near = span / 2000;
    camera.far = span * 50;
    camera.updateProjectionMatrix();
    controls.update();
  }
  resetCamera();

  let raf = 0, anim = null;
  function loop() {
    raf = requestAnimationFrame(loop);
    if (anim) {
      const f = Math.min(1, (performance.now() - anim.t0) / anim.ms);
      for (const line of Object.values(state.lines)) {
        const n = line.geometry.attributes.position.count;
        line.geometry.setDrawRange(0, Math.floor(f * n / 2) * 2);
      }
      if (f >= 1) anim = null;
    }
    controls.update();
    renderer.render(scene, camera);
  }
  loop();
  const ro = new ResizeObserver(() => {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  ro.observe(host);

  return {
    setVisible(k, v) { state.visible[k] = v; if (state.lines[k]) state.lines[k].visible = v; },
    setEvent(e) {
      state.event = e;
      buildTracks();
      const sel = (e === null ? events : events.filter(x => x.evt === e)).flatMap(x => x.tracks.flatMap(t => t.pts));
      box = frameBox(sel.length ? sel : pts);
      resetCamera();
    },
    setAllCells(v) { state.allCells = v; placeCells(v); },
    cellInfo() { return { shown: state.cellsShown, total: cells.length, touched: touched.size }; },
    setCellOpacity(o) { wallMat.opacity = o * 0.8; coreMat.opacity = o; walls.visible = cores.visible = o > 0.001; },
    animate(ms = 3500) { anim = { t0: performance.now(), ms }; },
    resetCamera,
    view(dir) {  // 'front' | 'side' | 'iso'
      const span = Math.max(R * 2.4, L * 1.4, 1);
      if (dir === 'front') camera.position.set(0, 0, -span * 1.6);
      if (dir === 'side') camera.position.set(span * 1.6, 0, 0);
      if (dir === 'iso') { resetCamera(); return; }
      controls.target.set(0, 0, 0);
      controls.update();
    },
    screenshot() { return renderer.domElement.toDataURL('image/png'); },
    counts() {
      const c = {};
      for (const ev of (state.event === null ? events : events.filter(e => e.evt === state.event)))
        for (const t of ev.tracks) c[kind(t.name)] = (c[kind(t.name)] || 0) + 1;
      return c;
    },
    dispose() { cancelAnimationFrame(raf); ro.disconnect(); renderer.dispose(); host.innerHTML = ''; },
  };
}

window.Viewer3D = { create, PARTICLES };
