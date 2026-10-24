// SRDetector web UI (Alpine.js component). Talks to the FastAPI backend in srdet/web/server.py.
const UNITS = { length: ['nm', 'um', 'mm', 'cm', 'm'], energy: ['eV', 'keV', 'MeV', 'GeV'], angle: ['deg', 'mrad', 'rad'] };
const TO_MM = { nm: 1e-6, um: 1e-3, mm: 1, cm: 10, m: 1000 };
const NO_LAYER = ['none', 'MgF2_film'];
const JSROOT_URL = 'https://cdn.jsdelivr.net/npm/jsroot@7.7.4/modules/gui.mjs';

async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) { /* not json */ }
    throw new Error(msg);
  }
  return r.json();
}
const post = (url, body) => api(url, { method: 'POST', body: JSON.stringify(body) });
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const mmOf = s => { if (typeof s === 'number') return s; const m = /^\s*([-+0-9.eE]+)\s*([a-z]+)?/.exec(String(s || '')); return m ? +m[1] * (TO_MM[m[2]] ?? 1) : NaN; };

function flatten(o, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(o || {})) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v) && p !== 'beam.spectrum') flatten(v, p, out);
    else out[p] = v;
  }
  return out;
}
function resolvePath(dir, rel) {
  const parts = (dir ? dir.split('/') : []).concat(rel.split('/'));
  const out = [];
  for (const p of parts) { if (p === '..') out.pop(); else if (p && p !== '.') out.push(p); }
  return out.join('/');
}

function app() {
  return {
    route: { view: 'dashboard', params: {} },
    navItems: [
      { view: 'dashboard', title: 'Дашборд', icon: '◧' },
      { view: 'new', title: 'Моделирование', icon: '＋' },
      { view: 'runs', title: 'Прогоны', icon: '☰', alt: ['run'] },
      { view: 'studies', title: 'Исследования', icon: '∿', alt: ['study'] },
      { view: 'optimize', title: 'Оптимизация', icon: '◎', alt: ['opt'] },
      { view: 'compare', title: 'Сравнение', icon: '⇄' },
      { view: 'jobs', title: 'Задачи', icon: '⏱', alt: ['job'] },
      { view: 'docs', title: 'Документация', icon: '📖' },
    ],
    info: { key_metrics: [], metric_labels: {} }, theme: 'auto',
    configs: [], schema: { sections: [], spectra: { sources: [] } },
    runs: [], studies: { specs: [], results: [] }, opts: { specs: [], results: [] },
    jobs: [], docs: [], archives: [],
    form: { base: 'full', name: '', values: {}, baseValues: {}, archive: false,
            spectrum: { kind: 'none', source: 'Am241', kvp: 80, filter: '2.5 mm', lines: '' } },
    run: null, runTab: 'обзор', runGeo: { cell: '', stack: '' }, geoInfo: '', runFilter: '',
    selected: [], compareRows: [], compareMetrics: ['det_yield_per_keV', 'detection_efficiency', 'psf_in_cell_fraction'],
    study: null, studyX: '', studyY: '', studySeries: '',
    opt: null, optTab: 'дашборд', optParam: '', onlyFeasible: false, trialSort: { col: 'trial', asc: true },
    optGeo: { cell: '', stack: '' }, optGeoInfo: '',
    job: null, docHtml: '', lightbox: null, modal: null, toast: '', _jobStatus: {},

    // ------------------------------------------------------------ boot / routing
    async init() {
      this.theme = localStorage.getItem('srdet-theme') || 'auto';
      this.applyTheme();
      try { this.selected = JSON.parse(localStorage.getItem('srdet-selected') || '[]'); } catch (e) { this.selected = []; }
      [this.info, this.schema, this.configs] = await Promise.all([api('/api/info'), api('/api/schema'), api('/api/configs')]);
      if (this.configs.length && !this.configs.find(c => c.name === this.form.base)) this.form.base = this.configs[0].name;
      await Promise.all([this.loadBase(), this.refresh()]);
      window.addEventListener('hashchange', () => this.onRoute());
      this.onRoute();
      setInterval(() => this.poll(), 2000);
    },
    async refresh() {
      [this.runs, this.studies, this.opts, this.jobs, this.docs, this.archives] = await Promise.all([
        api('/api/runs'), api('/api/studies'), api('/api/optimizations'), api('/api/jobs'), api('/api/docs'), api('/api/archives')]);
      for (const j of this.jobs) this._jobStatus[j.id] = j.status;
    },
    onRoute() {
      const h = location.hash.replace(/^#\/?/, '') || 'dashboard';
      const [view, q] = h.split('?');
      this.route = { view, params: Object.fromEntries(new URLSearchParams(q || '')) };
      const p = this.route.params;
      if (view === 'run') this.loadRun(p.path);
      if (view === 'study') this.loadStudy(p.path);
      if (view === 'opt') this.loadOpt(p.path);
      if (view === 'job') this.loadJob(p.id);
      if (view === 'docs') this.loadDoc(p.path || 'README.md');
      if (view === 'compare') this.loadCompare();
      window.scrollTo(0, 0);
    },
    latestOpts() {
      // newest finished result of every optimisation spec (folder name: <stamp>_<spec name>)
      const seen = new Set(), out = [];
      for (const o of this.opts.results) {
        const spec = o.name.replace(/^\d{8}-\d{6}_/, '').replace(/_quick$/, '');
        if (!seen.has(spec) && o.finished) { seen.add(spec); out.push(o); }
      }
      return out;
    },
    get activeJobs() { return this.jobs.filter(j => ['queued', 'running'].includes(j.status)).length; },
    async poll() {
      try {
        const jobs = await api('/api/jobs');
        let finished = null;
        for (const j of jobs) {
          const before = this._jobStatus[j.id];
          if (before && ['queued', 'running'].includes(before) && !['queued', 'running'].includes(j.status)) finished = j;
          this._jobStatus[j.id] = j.status;
        }
        this.jobs = jobs;
        if (this.route.view === 'job' && this.job) this.loadJob(this.job.id, true);
        if (finished) {
          this.notify(`Задача <b>${finished.title}</b>: ${finished.status}` +
            (finished.result ? ` — <a href="${this.resultLink(finished)}">открыть</a>` : ''));
          await this.refresh();
        }
      } catch (e) { /* server restarting */ }
    },
    notify(html) { this.toast = html; clearTimeout(this._t); this._t = setTimeout(() => (this.toast = ''), 7000); },

    // ------------------------------------------------------------ formatting
    fmt(v) {
      if (v === null || v === undefined || v === '') return '—';
      if (typeof v === 'boolean') return v ? '✓' : '✗';
      if (typeof v !== 'number') return String(v);
      if (!isFinite(v)) return '—';
      if (Number.isInteger(v)) return v.toLocaleString('ru-RU');
      const a = Math.abs(v);
      if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(2);
      return (+v.toPrecision(4)).toString();
    },
    label(k) { return this.info.metric_labels[k] || k; },
    jobBadge(s) { return { done: 'ok', failed: 'bad', running: 'run', queued: 'warn', cancelled: '', interrupted: 'bad' }[s] || ''; },
    resultLink(j) {
      const r = j.result || '';
      if (r.includes('/optimize/')) return '#/opt?path=' + r;
      if (r.includes('/studies/')) return '#/study?path=' + r;
      return '#/run?path=' + r;
    },
    toggleTheme() {
      this.theme = { auto: 'light', light: 'dark', dark: 'auto' }[this.theme];
      localStorage.setItem('srdet-theme', this.theme);
      this.applyTheme();
    },
    applyTheme() {
      if (this.theme === 'auto') document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', this.theme);
    },
    layout(extra = {}) {
      const grid = cssVar('--border') || '#ddd', text = cssVar('--text') || '#222';
      const { xaxis = {}, yaxis = {}, ...rest } = extra;
      return { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: text, size: 12 },
               margin: { l: 64, r: 20, t: 16, b: 90 }, legend: { orientation: 'h', y: -0.32 },
               xaxis: { gridcolor: grid, zerolinecolor: grid, automargin: true, ...xaxis },
               yaxis: { gridcolor: grid, zerolinecolor: grid, automargin: true, ...yaxis }, ...rest };
    },

    // ------------------------------------------------------------ jobs
    async submit(body) {
      try {
        const j = await post('/api/jobs', body);
        this.jobs.unshift(j);
        this._jobStatus[j.id] = j.status;
        location.hash = '#/job?id=' + j.id;
      } catch (e) { this.notify('Ошибка: ' + e.message); }
    },
    async loadJob(id, quiet) {
      try {
        this.job = await api('/api/jobs/' + id);
        this.$nextTick(() => { const el = this.$refs.joblog; if (el) el.scrollTop = el.scrollHeight; });
      } catch (e) { if (!quiet) this.notify(e.message); }
    },
    async cancel(id) { await post(`/api/jobs/${id}/cancel`, {}); this.poll(); },

    // ------------------------------------------------------------ simulation form
    async loadBase() {
      const cfg = await api('/api/configs/' + this.form.base);
      const flat = flatten(cfg);
      delete flat.name; delete flat.description;
      this.form.values = JSON.parse(JSON.stringify(flat));
      this.form.baseValues = JSON.parse(JSON.stringify(flat));
      this.readSpectrum();
    },
    resetForm() { this.form.values = JSON.parse(JSON.stringify(this.form.baseValues)); this.readSpectrum(); },
    readSpectrum() {
      const s = this.form.values['beam.spectrum'];
      const sp = this.form.spectrum;
      if (!s) sp.kind = 'none';
      else if (s.source) { sp.kind = 'source'; sp.source = s.source; }
      else if (s.xray_tube) { sp.kind = 'xray_tube'; sp.kvp = s.xray_tube.kvp ?? 80; sp.filter = s.xray_tube.filter ?? '2.5 mm'; }
      else if (s.lines) { sp.kind = 'lines'; sp.lines = s.lines.map(l => l.join(', ')).join('\n'); }
    },
    syncSpectrum() {
      const sp = this.form.spectrum;
      let v = null;
      if (sp.kind === 'source') v = { source: sp.source };
      if (sp.kind === 'xray_tube') v = { xray_tube: { kvp: +sp.kvp, filter: sp.filter } };
      if (sp.kind === 'lines') v = { lines: sp.lines.split('\n').map(l => l.split(/[,;\s]+/).filter(Boolean).map(Number)).filter(l => l.length === 2) };
      this.form.values['beam.spectrum'] = v;
    },
    isChanged(p) { return JSON.stringify(this.form.values[p]) !== JSON.stringify(this.form.baseValues[p]); },
    changedIn(sec) { return Object.keys(this.form.values).filter(p => p.startsWith(sec + '.') && this.isChanged(p)).length; },
    overrides() {
      const o = {};
      for (const p of Object.keys(this.form.values)) if (this.isChanged(p)) o[p] = this.form.values[p];
      return o;
    },
    unitsFor(kind) { return UNITS[kind] || []; },
    qtyNum(p) { const m = /^\s*([-+0-9.eE]+)/.exec(String(this.form.values[p] ?? '')); return m ? +m[1] : ''; },
    qtyUnit(p) { const m = /([a-zA-Z]+)\s*$/.exec(String(this.form.values[p] ?? '')); return m ? m[1] : ''; },
    setQty(p, num, unit) {
      const n = num !== null ? num : this.qtyNum(p);
      const u = unit !== null ? unit : this.qtyUnit(p);
      this.form.values[p] = `${n} ${u}`;
    },
    fieldVisible(f) {
      const v = this.form.values, p = f.path, type = v['beam.type'], mode = v['geometry.mode'], coat = v['optics.coating'];
      if (p === 'run.events') return false;  // shown at the top
      if (p.startsWith('geometry.slab_')) return mode === 'slab';
      if (p.startsWith('beam.optical.')) return type === 'optical';
      if (p === 'beam.radius') return type === 'parallel';
      if (p === 'beam.sigma') return type === 'gauss';
      if (p === 'beam.half_angle') return type === 'divergent';
      if (p === 'beam.distance') return ['divergent', 'isotropic'].includes(type);
      if (p === 'beam.macro') return type === 'macro';
      if (['beam.energy', 'beam.spectrum', 'beam.particle', 'beam.position'].includes(p)) return type !== 'optical';
      if (p === 'optics.coating_reflectivity') return ['mirror', 'diffuse'].includes(coat);
      if (p === 'optics.film_thickness') return coat === 'MgF2_film';
      if (p === 'geometry.detector_radius' || p.startsWith('geometry.housing_')) return mode === 'full';
      return true;
    },
    geoPreview() {
      const v = this.form.values;
      const pitch = mmOf(v['geometry.pitch']), D = mmOf(v['geometry.channel_diameter']);
      const t = NO_LAYER.includes(v['optics.coating']) ? 0 : mmOf(v['geometry.coating_thickness']);
      const mode = v['geometry.mode'], R = mmOf(v['geometry.detector_radius']);
      if (!(pitch > 0 && D > 0)) return { summary: '', problem: 'укажите шаг и диаметр канала', cell: '', stack: '' };
      const wall = pitch - D - 2 * t;
      const shape = v['geometry.channel_shape'];
      const coreA = shape === 'hex' ? Geo.S3 / 2 * D * D : Math.PI * D * D / 4;
      const fill = coreA / (Geo.S3 / 2 * pitch * pitch);
      const n = mode === 'unit' ? 1 : mode === 'cluster7' ? 7 : Math.round(Math.PI * (R - pitch / Geo.S3) ** 2 / (Geo.S3 / 2 * pitch * pitch));
      let problem = '';
      if (mode !== 'slab' && wall < 0.001) problem = `Сота не помещается: стенка ${(wall * 1000).toFixed(2)} мкм < 1 мкм (шаг ≥ D + 2·покрытие + 1 мкм)`;
      if (mode === 'full' && n > 3e5) problem = `${n.toLocaleString('ru-RU')} сот — слишком много для полного детектора`;
      const g = { pitch, D, t, shape, fill };
      return {
        problem,
        summary: mode === 'slab' ? `блок ${v['geometry.slab_material']}, ${v['geometry.slab_thickness']}` :
          `${mode}: ~${n.toLocaleString('ru-RU')} сот, стенка ${(wall * 1000).toFixed(1)} мкм, сцинтиллятор ${(fill * 100).toFixed(1)} % площади`,
        cell: mode === 'slab' ? '' : Geo.closeup(g),
        stack: Geo.stack({ window: mmOf(v['geometry.window_thickness']), L: mode === 'slab' ? mmOf(v['geometry.slab_thickness']) : mmOf(v['geometry.length']),
          coupling: mmOf(v['geometry.coupling_thickness']), sensorWindow: Math.max(0, mmOf(v['geometry.sensor_window_thickness']) || 0),
          active: mmOf(v['geometry.sensor_active_thickness']), windowMat: v['geometry.window_material'],
          core: mode === 'slab' ? v['geometry.slab_material'] : v['geometry.core_material'], couplingMat: v['geometry.coupling_material'],
          sensor: v['geometry.sensor'] }),
      };
    },
    async showMacro() {
      try {
        const r = await post('/api/macro', { base: this.form.base, overrides: this.overrides() });
        this.modal = { title: 'Макрос Geant4 для текущих параметров', text: r.macro };
      } catch (e) { this.notify('Ошибка конфигурации: ' + e.message); }
    },
    async launchRun(withVis) {
      const body = { kind: 'run', base: this.form.base, overrides: this.overrides(), name: this.form.name || this.form.base,
                     events: this.form.values['run.events'], archive: this.form.archive };
      if (withVis) {
        try { await post('/api/jobs', { ...body, kind: 'vis', events: 5, name: body.name + '_vis' }); } catch (e) { this.notify(e.message); }
      }
      this.submit(body);
    },
    async rerunInForm(run) {
      const base = this.configs.find(c => (run.config_sources || []).some(s => s.endsWith(`/${c.name}.yaml`)));
      this.form.base = base ? base.name : 'full';
      await this.loadBase();
      const flat = flatten(run.config || {});
      for (const k of Object.keys(this.form.values)) if (k in flat) this.form.values[k] = flat[k];
      this.readSpectrum();
      this.form.name = (run.config && run.config.name) || run.name;
      location.hash = '#/new';
    },

    // ------------------------------------------------------------ runs
    filteredRuns() {
      const q = this.runFilter.toLowerCase();
      return q ? this.runs.filter(r => JSON.stringify([r.name, r.mode, r.coating, r.core, r.sensor, r.status]).toLowerCase().includes(q)) : this.runs;
    },
    runsTable(rows, selectable) {
      if (!rows.length) return '<div class="empty">Прогонов пока нет — <a href="#/new">запустить моделирование</a></div>';
      const f = v => this.fmt(v);
      const head = `<tr>${selectable ? '<th></th>' : ''}<th>прогон</th><th>статус</th><th>режим</th><th>L</th><th>ядро</th><th>покрытие</th><th>пучок</th><th>pe/кэВ</th><th>эфф.</th><th>LCE</th><th>r50, мкм</th><th>с</th></tr>`;
      const body = rows.map(r => `<tr>${selectable ? `<td><input type="checkbox" data-path="${r.path}" ${this.selected.includes(r.path) ? 'checked' : ''}></td>` : ''}
        <td><a href="#/run?path=${encodeURIComponent(r.path)}">${r.name}</a></td>
        <td><span class="badge ${r.status.startsWith('ok') ? 'ok' : 'bad'}">${r.status.slice(0, 40)}</span></td>
        <td>${r.mode || ''}</td><td>${r.length || ''}</td><td>${r.core || ''}</td><td>${r.coating || ''}</td><td class="small">${r.beam}</td>
        <td class="num">${f(r.metrics.det_yield_per_keV)}</td><td class="num">${f(r.metrics.detection_efficiency)}</td>
        <td class="num">${f(r.metrics.lce)}</td><td class="num">${f(r.metrics.psf_r50_um)}</td><td class="num">${f(r.wall_time_s)}</td></tr>`).join('');
      return `<table class="t"><thead>${head}</thead><tbody>${body}</tbody></table>`;
    },
    onSelect(e) {
      const p = e.target.dataset.path;
      if (!p) return;
      this.selected = e.target.checked ? [...new Set([...this.selected, p])] : this.selected.filter(x => x !== p);
      this.saveSel();
    },
    saveSel() { localStorage.setItem('srdet-selected', JSON.stringify(this.selected)); },
    async loadRun(path) {
      this.run = null;
      try { this.run = await api('/api/run?path=' + encodeURIComponent(path)); } catch (e) { this.notify(e.message); return; }
      this.setRunTab(this.runTab);
    },
    async setRunTab(t) {
      this.runTab = t;
      if (!this.run) return;
      if (t === 'геометрия') {
        const g = await api('/api/run/geometry?path=' + encodeURIComponent(this.run.path)).catch(() => null);
        if (!g) { this.runGeo = { cell: '<div class="empty">нет geometry.json</div>', stack: '' }; return; }
        this.renderGeometry(g, this.$refs.lattice, 'runGeo', 'geoInfo');
      }
      if (t === 'ROOT' && this.run.has_root) {
        const el = this.$refs.jsroot;
        el.innerHTML = '';
        try {
          const { buildGUI } = await import(JSROOT_URL);
          const h = await buildGUI(el);
          await h.openRootFile('/files/' + this.run.path + '/srdet.root');
        } catch (e) { el.innerHTML = `<div class="empty">JSROOT не загрузился (${e.message}); <a href="/files/${this.run.path}/srdet.root">скачать srdet.root</a></div>`; }
      }
    },
    renderGeometry(g, host, target, infoKey) {
      const cg = g.config_geometry || {}, co = g.config_optics || {};
      const t = NO_LAYER.includes(co.coating) ? 0 : mmOf(cg.coating_thickness);
      const geo = { cells: g.cells || [], pitch: g.pitch_mm, D: g.channel_diameter_mm, t, R: g.matrix_radius_mm,
                    shape: g.channel_shape, housing: g.mode === 'full' ? mmOf(cg.housing_thickness) : 0, fill: g.core_fill_factor };
      this[infoKey] = `${g.mode}: ${(g.n_cells || 0).toLocaleString('ru-RU')} сот, R матрицы ${this.fmt(g.matrix_radius_mm)} мм`;
      this[target] = {
        cell: g.mode === 'slab' ? '' : Geo.closeup(geo),
        stack: Geo.stack({ window: mmOf(cg.window_thickness), L: g.length_mm, coupling: mmOf(cg.coupling_thickness),
                           sensorWindow: Math.max(0, g.z_sensor_mm - g.length_mm / 2 - mmOf(cg.coupling_thickness)),
                           active: g.z_back_mm - g.z_sensor_mm, windowMat: cg.window_material, core: g.core_material,
                           couplingMat: cg.coupling_material, sensor: g.sensor }),
      };
      this.$nextTick(() => {
        if (!host) return;
        host.innerHTML = g.mode === 'slab' ? '<div class="empty">режим slab: блок материала</div>' : Geo.lattice(geo);
        Geo.interactive(host);
      });
    },
    visFor(configPath, sourceRun) { this.submit({ kind: 'vis', config_path: configPath, events: 5 }); },

    // ------------------------------------------------------------ compare
    async loadCompare() {
      if (!this.selected.length) { this.compareRows = []; return; }
      this.compareRows = await post('/api/compare', { paths: this.selected });
      this.$nextTick(() => this.drawCompare());
    },
    drawCompare() {
      const el = this.$refs.compareplot;
      if (!el || !this.compareRows.length) return;
      const traces = this.compareMetrics.map(k => ({ type: 'bar', name: this.label(k), x: this.compareRows.map(r => r.name), y: this.compareRows.map(r => r[k]) }));
      Plotly.react(el, traces, this.layout({ barmode: 'group', yaxis: { type: 'log', title: 'значение (лог. шкала)' } }), { responsive: true });
    },

    // ------------------------------------------------------------ studies
    async loadStudy(path) {
      this.study = null;
      this.study = await api('/api/study?path=' + encodeURIComponent(path));
      const spec = this.study.spec || {};
      const scan = spec.variants ? ['variant'] : Object.keys(spec.scan || {});
      this.studyX = spec.x || scan[0] || '';
      this.studyY = (spec.metrics || [])[0] || '';
      this.studySeries = spec.series || '';
      this.$nextTick(() => this.drawStudy());
    },
    studyCols() {
      if (!this.study || !this.study.rows.length) return [];
      return Object.keys(this.study.rows[0]).filter(c => !c.endsWith('_err') && !['run_dir', 'name', 'ok'].includes(c));
    },
    drawStudy() {
      const el = this.$refs.studyplot;
      if (!el || !this.study || !this.study.rows.length) return;
      const rows = this.study.rows.filter(r => r.ok !== false);
      const x = this.studyX, y = this.studyY, s = this.studySeries;
      const cat = rows.some(r => typeof r[x] === 'string');
      const groups = s ? [...new Set(rows.map(r => r[s]))] : [null];
      const traces = groups.map(gv => {
        const rr = rows.filter(r => gv === null || r[s] === gv);
        return { type: cat && !s ? 'bar' : 'scatter', mode: 'lines+markers', name: gv === null ? this.label(y) : `${s} = ${gv}`,
                 x: rr.map(r => r[x]), y: rr.map(r => r[y]),
                 error_y: rr[0] && rr[0][y + '_err'] !== undefined ? { type: 'data', array: rr.map(r => r[y + '_err']), visible: true } : undefined };
      });
      Plotly.react(el, traces, this.layout({ xaxis: { title: x }, yaxis: { title: this.label(y) } }), { responsive: true });
    },

    // ------------------------------------------------------------ optimisation dashboard
    async loadOpt(path) {
      this.opt = null;
      this.opt = await api('/api/optimization?path=' + encodeURIComponent(path));
      this.optParam = this.optAliases()[0] || '';
      this.setOptTab(this.optTab);
    },
    optAliases() { return this.opt ? Object.keys(this.opt.spec.space || {}) : []; },
    optBest() {
      if (!this.opt) return null;
      if (this.opt.final.length) return this.opt.final[0];
      const max = (this.opt.spec.objective || {}).direction !== 'minimize';
      const f = this.opt.trials.filter(t => t.feasible);
      return f.sort((a, b) => (max ? b.objective - a.objective : a.objective - b.objective))[0] || null;
    },
    finalCols() {
      const keys = this.opt && this.opt.final[0] ? Object.keys(this.opt.final[0]) : [];
      return keys.filter(k => !k.endsWith('_std') && !['n', 'feasible_all', 'trial', 'events', 'seed'].includes(k)).slice(0, 14);
    },
    trialCols() {
      const rm = (this.opt.spec.report_metrics || []);
      return ['trial', 'stage', 'events', ...this.optAliases(), 'objective', 'feasible', ...rm, 'violations', 'run_dir'];
    },
    sortTrials(c) { this.trialSort = { col: c, asc: this.trialSort.col === c ? !this.trialSort.asc : true }; },
    sortedTrials() {
      const { col, asc } = this.trialSort;
      const rows = this.opt.trials.filter(t => !this.onlyFeasible || t.feasible);
      return [...rows].sort((a, b) => ((a[col] ?? -Infinity) > (b[col] ?? -Infinity) ? 1 : -1) * (asc ? 1 : -1));
    },
    async setOptTab(t) {
      this.optTab = t;
      if (!this.opt) return;
      await this.$nextTick();
      if (t === 'дашборд') { this.drawOptConv(); this.drawOptPareto(); this.drawOptPar(); this.drawOptSens(); }
      if (t === 'геометрия лучшей') {
        const best = this.opt.trials.find(r => String(r.stage).startsWith('final') && r.run_dir) ||
                     [...this.opt.trials].filter(r => r.feasible && r.run_dir).sort((a, b) => b.events - a.events)[0];
        if (!best) return;
        const g = await api('/api/run/geometry?path=' + encodeURIComponent(this.opt.path + '/' + best.run_dir)).catch(() => null);
        if (g) this.renderGeometry(g, this.$refs.optlattice, 'optGeo', 'optGeoInfo');
      }
    },
    hoverText(t) { return this.optAliases().map(a => `${a} = ${this.fmt(t[a])}`).join('<br>') + `<br>events ${t.events}` + (t.violations ? `<br><i>${t.violations}</i>` : ''); },
    drawOptConv() {
      const el = this.$refs.optconv, T = this.opt.trials;
      const grp = s => (String(s).startsWith('r') ? 'уточнение' : String(s).startsWith('final') ? 'проверка' : 'отбор ' + s);
      const groups = [...new Set(T.map(t => grp(t.stage)))];
      const traces = groups.map(g => {
        const rr = T.filter(t => grp(t.stage) === g);
        return { type: 'scatter', mode: 'markers', name: g, x: rr.map(t => t.trial), y: rr.map(t => t.objective),
                 marker: { symbol: rr.map(t => (t.feasible ? 'circle' : 'x')), size: 8 }, text: rr.map(t => this.hoverText(t)), hoverinfo: 'text+y' };
      });
      const max = (this.opt.spec.objective || {}).direction !== 'minimize';
      let best = null;
      const line = T.map(t => { if (t.feasible && isFinite(t.objective) && (best === null || (max ? t.objective > best : t.objective < best))) best = t.objective; return best; });
      traces.push({ type: 'scatter', mode: 'lines', name: 'лучший допустимый', x: T.map(t => t.trial), y: line, line: { color: cssVar('--text'), width: 1.5 } });
      Plotly.react(el, traces, this.layout({ xaxis: { title: 'испытание' }, yaxis: { title: 'цель' } }), { responsive: true });
    },
    drawOptPareto() {
      const el = this.$refs.optpareto, par = this.opt.spec.pareto;
      if (!par) { Plotly.purge(el); el.innerHTML = '<div class="empty">Pareto не задан</div>'; return; }
      const pts = this.opt.trials.filter(t => t.feasible && isFinite(t[par.x]) && isFinite(t[par.y]));
      const sx = par.x_dir === 'max' ? -1 : 1, sy = par.y_dir === 'min' ? 1 : -1;
      const front = pts.filter(p => !pts.some(q => sx * q[par.x] <= sx * p[par.x] && sy * q[par.y] <= sy * p[par.y] &&
                                                   (sx * q[par.x] < sx * p[par.x] || sy * q[par.y] < sy * p[par.y]))).sort((a, b) => a[par.x] - b[par.x]);
      Plotly.react(el, [
        { type: 'scatter', mode: 'markers', name: 'допустимые', x: pts.map(p => p[par.x]), y: pts.map(p => p[par.y]), text: pts.map(t => this.hoverText(t)), hoverinfo: 'text', marker: { color: cssVar('--muted'), size: 7 } },
        { type: 'scatter', mode: 'lines+markers', name: 'фронт Парето', x: front.map(p => p[par.x]), y: front.map(p => p[par.y]), text: front.map(t => this.hoverText(t)), hoverinfo: 'text', marker: { color: '#d62728', size: 9 } },
      ], this.layout({ xaxis: { title: `${this.label(par.x)} (${par.x_dir === 'max' ? '↑' : '↓'} лучше)` }, yaxis: { title: `${this.label(par.y)} (${par.y_dir === 'min' ? '↓' : '↑'} лучше)` } }), { responsive: true });
    },
    drawOptPar() {
      const el = this.$refs.optpar, space = this.opt.spec.space || {};
      const T = this.opt.trials.filter(t => t.feasible && isFinite(t.objective));
      if (!T.length) { el.innerHTML = '<div class="empty">нет допустимых испытаний</div>'; return; }
      const dims = Object.entries(space).map(([a, d]) => {
        if (d.values) {
          const vals = d.values.map(String);
          return { label: a, values: T.map(t => vals.indexOf(String(t[a]))), tickvals: vals.map((_, i) => i), ticktext: vals };
        }
        if (!d.log) return { label: a, values: T.map(t => t[a]) };
        // log axis: plot log10, label with the real values
        const lv = T.map(t => Math.log10(t[a])), lo = Math.min(...lv), hi = Math.max(...lv);
        const ticks = [0, 0.25, 0.5, 0.75, 1].map(u => lo + u * (hi - lo));
        return { label: a + ' (log)', values: lv, tickvals: ticks, ticktext: ticks.map(v => (+(10 ** v).toPrecision(3)).toString()) };
      });
      dims.push({ label: 'цель', values: T.map(t => t.objective) });
      Plotly.react(el, [{ type: 'parcoords', dimensions: dims, line: { color: T.map(t => t.objective), colorscale: 'Viridis', showscale: true } }],
        this.layout({ margin: { l: 70, r: 70, t: 40, b: 30 } }), { responsive: true });
    },
    drawOptSens() {
      const el = this.$refs.optsens, a = this.optParam, d = (this.opt.spec.space || {})[a];
      if (!el || !d) return;
      const T = this.opt.trials.filter(t => t.feasible && isFinite(t.objective) && !String(t.stage).startsWith('final'));
      const trace = d.values
        ? d.values.map(v => ({ type: 'box', name: String(v), y: T.filter(t => String(t[a]) === String(v)).map(t => t.objective), boxpoints: 'all', jitter: 0.4 }))
        : [{ type: 'scatter', mode: 'markers', x: T.map(t => t[a]), y: T.map(t => t.objective), text: T.map(t => this.hoverText(t)), hoverinfo: 'text+y',
             marker: { color: T.map(t => Math.log10(t.events)), colorscale: 'Viridis', showscale: true, colorbar: { title: 'log10 событий' }, size: 8 } }];
      Plotly.react(el, trace, this.layout({ showlegend: false, xaxis: { title: a, type: d.log ? 'log' : 'linear' }, yaxis: { title: 'цель' } }), { responsive: true });
    },

    // ------------------------------------------------------------ docs / markdown
    async loadDoc(path) {
      try { const d = await api('/api/doc?path=' + encodeURIComponent(path)); this.docHtml = this.renderMd(d.markdown, path); }
      catch (e) { this.docHtml = `<div class="empty">${e.message}</div>`; }
    },
    renderMd(md, path) {
      if (!md) return '';
      const dir = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
      const tmp = document.createElement('div');
      tmp.innerHTML = marked.parse(md);
      tmp.querySelectorAll('img').forEach(img => {
        const src = img.getAttribute('src');
        if (src && !/^(https?:|\/|data:)/.test(src)) img.src = '/files/' + resolvePath(dir, src);
      });
      tmp.querySelectorAll('a').forEach(a => {
        const href = a.getAttribute('href');
        if (!href || /^(https?:|#|\/|mailto:)/.test(href)) return;
        const target = resolvePath(dir, href.split('#')[0]);
        if (target.endsWith('.md')) a.setAttribute('href', '#/docs?path=' + target);
        else { a.setAttribute('href', '/files/' + target); a.setAttribute('target', '_blank'); }
      });
      return tmp.innerHTML;
    },
  };
}
