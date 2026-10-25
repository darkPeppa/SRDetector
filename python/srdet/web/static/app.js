// SRDetector web UI (Alpine.js component). Talks to the FastAPI backend in srdet/web/server.py.
const UNITS = { length: ['nm', 'um', 'mm', 'cm', 'm'], energy: ['eV', 'keV', 'MeV', 'GeV'], angle: ['deg', 'mrad', 'rad'] };
const TO_MM = { nm: 1e-6, um: 1e-3, mm: 1, cm: 10, m: 1000 };
const NO_LAYER = ['none', 'MgF2_film'];
const HIST_LABELS = {
  edep_core: 'Энергия в сцинтилляторе, кэВ', edep_total: 'Энергия во всём детекторе, кэВ',
  n_det: 'Детектированные фотоны на событие', n_scint: 'Рождённые фотоны на событие',
  nrefl_det: 'Отражений до детектирования', t_det: 'Время прихода фотонов, нс',
  lambda_det: 'Длина волны детектированных фотонов, нм', birthz_det: 'Глубина рождения детектированных фотонов, мм',
  first_z: 'Глубина первого взаимодействия, мм', fluo_energy: 'Энергии флуоресцентных квантов, кэВ',
  n_cells_hit: 'Число сработавших сот',
};
const JSROOT_URL = 'https://cdn.jsdelivr.net/npm/jsroot@7.7.4/modules/main.mjs';
const OBJECTIVE_PRESETS = [
  { title: 'свет × эффективность', expr: 'det_yield_per_keV * detection_efficiency', dir: 'maximize' },
  { title: 'свет в фотопике', expr: 'det_yield_per_keV * photopeak_fraction', dir: 'maximize' },
  { title: 'свет на цену', expr: 'det_yield_per_cost', dir: 'maximize' },
  { title: 'разрешение', expr: 'resolution_fwhm_poisson_limit', dir: 'minimize' },
];
const OP_TEXT = { '<=': '≤', '>=': '≥', '<': '<', '>': '>', '==': '=', '!=': '≠' };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// "60 keV" -> [60, 'keV']; numbers -> [n, '']
const splitQty = v => { const m = /^\s*([-+0-9.eE]+)\s*([A-Za-z]*)\s*$/.exec(String(v ?? '')); return m ? [m[1], m[2] || ''] : [String(v ?? ''), '']; };
function emptyOb() {
  return { preset: '', name: 'my_opt', title: '', description: '', base: 'full.yaml', fixed: [], params: [], derived: [],
           objective: 'det_yield_per_keV * detection_efficiency', direction: 'maximize', constraints: [],
           pareto: { on: false, x: 'psf_r50_um', x_dir: 'min', y: 'det_yield_per_keV', y_dir: 'max' }, report: [],
           search: { sampler: 'lhs', initial: 16, events: '300, 1200', eta: 3, seed: 1, refineOn: true,
                     refine: { iterations: 3, events: 1200, step: 0.15, min_gain: 0.03 }, finalOn: true,
                     final: { top: 2, events: 3000, repeats: 3 } },
           quickSpec: null, quick: false, archive: false };
}

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
    form: { base: 'full', name: '', values: {}, baseValues: {}, archive: false, tracks3d: false,
            spectrum: { kind: 'none', source: 'Am241', kvp: 80, filter: '2.5 mm', lines: '' } },
    run: null, runTab: 'обзор', runGeo: { cell: '', stack: '' }, geoInfo: '', runFilter: '',
    selected: [], compareRows: [], compareMetrics: ['det_yield_per_keV', 'detection_efficiency', 'psf_in_cell_fraction'],
    study: null, studyX: '', studyY: '', studySeries: '',
    HIST_LABELS, scanParam: '', scanHist: 'n_det', scanMetric: '', scanNorm: true, scanLog: false, scanNoZero: true, scanPoints: 6, scanNote: '', scanSummary: '',
    opt: null, optTab: 'метод и цель', optParam: '', onlyFeasible: false, trialSort: { col: 'trial', asc: true }, _optTick: 0,
    optimizeTab: 'constructor', ob: emptyOb(), obMeta: { metrics: [], fields: [], bases: [], samplers: {} }, obResult: null, obChecking: false,
    OBJECTIVE_PRESETS, studyEvents: {},
    showEst: true, runEst: null, optEst: null, studyEst: null, scanEstNote: '',
    optGeo: { cell: '', stack: '' }, optGeoInfo: '',
    job: null, docHtml: '', lightbox: null, modal: null, toast: '', _jobStatus: {},
    tracksN: 20, v3dAllCells: false, v3dCellInfo: {}, v3d: null, v3dEvents: [], v3dEvent: 'all', v3dParticles: {}, v3dCounts: {},
    rootKeys: [], rootSel: '', rootExpr: '', rootCut: '', rootMsg: '',

    // ------------------------------------------------------------ boot / routing
    async init() {
      this.theme = localStorage.getItem('srdet-theme') || 'auto';
      try { this.showEst = localStorage.getItem('srdet-est') !== '0'; } catch (e) { this.showEst = true; }
      this.applyTheme();
      try { this.selected = JSON.parse(localStorage.getItem('srdet-selected') || '[]'); } catch (e) { this.selected = []; }
      [this.info, this.schema, this.configs] = await Promise.all([api('/api/info'), api('/api/schema'), api('/api/configs')]);
      if (this.configs.length && !this.configs.find(c => c.name === this.form.base)) this.form.base = this.configs[0].name;
      await Promise.all([this.loadBase(), this.refresh(), this.loadObMeta()]);
      const first = this.opts.specs[0];
      if (first) this.obLoadPreset(first.name); else this.obCheck();
      window.addEventListener('hashchange', () => this.onRoute());
      this.onRoute();
      setInterval(() => this.poll(), 2000);
      if (new URLSearchParams(location.search).get('tour')) setTimeout(() => window.tourStart(this), 1200);
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
      if (view !== 'run' && this.v3d) { this.v3d.dispose(); this.v3d = null; }
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
        // a running optimisation: refresh its page every ~6 s
        if (this.route.view === 'opt' && this.opt && !this.opt.finished && ++this._optTick % 3 === 0) this.loadOpt(this.opt.path, true);
        if (this.route.view === 'optimize' && this.opts.results.some(r => !r.finished) && ++this._optTick % 3 === 0)
          this.opts = await api('/api/optimizations');
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
      const ov = this.overrides();
      if (this.form.tracks3d) ov['run.tracks'] = 20;
      const body = { kind: 'run', base: this.form.base, overrides: ov, name: this.form.name || this.form.base,
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
      this.runEst = null;
      try { this.run = await api('/api/run?path=' + encodeURIComponent(path)); } catch (e) { this.notify(e.message); return; }
      this.setRunTab(this.runTab);
      api('/api/estimates?path=' + encodeURIComponent(path)).then(r => { if (this.run && this.run.path === path) this.runEst = r; }).catch(() => {});
    },

    // ------------------------------------------------------------ analytic estimates (sanity checks)
    toggleEst(on) {
      this.showEst = on;
      try { localStorage.setItem('srdet-est', on ? '1' : '0'); } catch (e) { /* private mode */ }
      if (this.route.view === 'opt' && this.optTab === 'параметр → гистограммы') this.drawScan();
      if (this.route.view === 'study') this.drawStudy();
    },
    estFor(checks, metric) { return (checks || []).find(c => c.metric === metric); },
    estBadge(s) { return { ok: 'ok', warn: 'warn', bad: 'bad' }[s] || ''; },
    estStatusText(s) { return { ok: 'сходится', warn: 'проверить', bad: 'расходится' }[s] || s; },
    estRange(c) {
      const f = v => this.fmt(v);
      if (c.low === c.high) return '≈ ' + f(c.value);
      return c.low === 0 ? '≤ ' + f(c.high) : `${f(c.low)} … ${f(c.high)}`;
    },
    estTable(checks) {
      if (!checks || !checks.length) return '<div class="empty">Для этой конфигурации подходящих оценок нет (например, спектр вместо одной энергии или оптика выключена).</div>';
      const rows = checks.map(c => `<tr>
        <td><b>${esc(c.title)}</b><div class="small muted">${esc(c.law)}</div>
          <div class="small muted"><i>${esc(c.source)}</i>${c.note ? ' — ' + esc(c.note) : ''}</div></td>
        <td class="num">${esc(this.estRange(c))}</td>
        <td class="num">${esc(this.fmt(c.measured))}${c.err ? '<div class="small muted">± ' + esc(this.fmt(c.err)) + '</div>' : ''}</td>
        <td class="num small">${c.deviation && Math.abs(c.deviation) >= 5e-4 ? (c.deviation > 0 ? '+' : '') + (100 * c.deviation).toFixed(1) + ' %' : '—'}</td>
        <td><span class="badge ${this.estBadge(c.status)}">${this.estStatusText(c.status)}</span></td></tr>`).join('');
      return `<table class="t"><thead><tr><th>проверка и закон</th><th>оценка</th><th>Geant4</th><th>откл.</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
    },
    studyEstNote() {
      const pc = Object.values((this.studyEst && this.studyEst.per_check) || {}).filter(c => c.metric === this.studyY);
      if (!pc.length) return 'Для этой величины аналитической оценки нет (оценки есть для: ' +
        ([...new Set(Object.values((this.studyEst && this.studyEst.per_check) || {}).map(c => this.label(c.metric)))].join(', ') || '—') + ').';
      return pc.map(c => `Пунктир — оценка «${c.title}» для тех же конфигураций; по точкам: ${this.estSummaryText(c)}.`).join(' ');
    },
    estSummaryText(s) {
      if (!s) return '';
      return `сходится ${s.ok || 0}` + (s.warn ? `, проверить ${s.warn}` : '') + (s.bad ? `, расходится ${s.bad}` : '');
    },
    // dashed approximation (and its range as a band) over simulated points; rows need run_dir
    estTraces(rows, xKey, metric, points, name, color, group) {
      if (!this.showEst || !points) return [];
      const pts = rows.map(r => ({ x: r[xKey], e: (points[r.run_dir] || {})[metric] })).filter(p => p.e && p.x !== undefined && p.x !== null);
      if (!pts.length) return [];
      pts.sort((a, b) => (typeof a.x === 'number' && typeof b.x === 'number' ? a.x - b.x : 0));
      const line = { color: color || cssVar('--muted'), width: 1.6, dash: 'dash' };
      const bound = pts.every(p => p.e.low === 0 && p.e.high > 0);  // "not more than": draw the bound only
      if (bound) name += ' (верхняя граница)';
      const band = !bound && pts.some(p => p.e.low !== p.e.high);
      if (band) name += ' (середина диапазона)';
      const out = [];
      if (band) {
        out.push({ type: 'scatter', mode: 'lines', x: pts.map(p => p.x), y: pts.map(p => p.e.low), line: { width: 0 }, hoverinfo: 'skip',
                   showlegend: false, legendgroup: group });
        out.push({ type: 'scatter', mode: 'lines', x: pts.map(p => p.x), y: pts.map(p => p.e.high), fill: 'tonexty', line: { width: 0 },
                   fillcolor: 'rgba(128,128,128,0.18)', name: name + ' — диапазон оценки', hoverinfo: 'skip', legendgroup: group });
      }
      out.push({ type: 'scatter', mode: 'lines+markers', x: pts.map(p => p.x), y: pts.map(p => (p.e.low === 0 ? p.e.high : p.e.value)),
                 line, marker: { symbol: 'x', size: 7, color: line.color }, name: name, legendgroup: group,
                 hovertemplate: '%{y:.4g} (оценка)<extra></extra>' });
      return out;
    },
    async setRunTab(t) {
      if (t !== '3D' && this.v3d) { this.v3d.dispose(); this.v3d = null; }  // stop rendering off-screen
      this.runTab = t;
      if (!this.run) return;
      if (t === 'геометрия') {
        const g = await api('/api/run/geometry?path=' + encodeURIComponent(this.run.path)).catch(() => null);
        if (!g) { this.runGeo = { cell: '<div class="empty">нет geometry.json</div>', stack: '' }; return; }
        this.renderGeometry(g, this.$refs.lattice, 'runGeo', 'geoInfo');
      }
      if (t === 'ROOT' && this.run.has_root) await this.openRoot();
      if (t === '3D') await this.open3d();
    },
    async open3d() {
      if (this.v3d) { this.v3d.dispose(); this.v3d = null; }
      if (!this.run.tracks_run) return;
      const [g, text] = await Promise.all([
        api('/api/run/geometry?path=' + encodeURIComponent(this.run.tracks_run)),
        fetch('/files/' + this.run.tracks_run + '/tracks.jsonl').then(r => r.text())]);
      this.v3dEvents = text.split('\n').filter(Boolean).map(l => JSON.parse(l)).sort((a, b) => a.evt - b.evt);
      for (let i = 0; i < 50 && !window.Viewer3D; i++) await new Promise(r => setTimeout(r, 100));  // module loads async
      if (!window.Viewer3D) { this.notify('three.js не загрузился (нужен интернет для CDN)'); return; }
      this.v3dParticles = window.Viewer3D.PARTICLES;
      await this.$nextTick();
      this.v3d = window.Viewer3D.create(this.$refs.v3d, g, this.v3dEvents, { background: getComputedStyle(document.body).backgroundColor });
      this.v3dCellInfo = this.v3d.cellInfo();
      this.v3dAllCells = this.v3dCellInfo.shown === this.v3dCellInfo.total;
      // big detector: start with one event in close-up, the whole beam spot is mostly empty space
      this.v3dEvent = this.v3dCellInfo.total > 500 && this.v3dEvents.length ? String(this.v3dEvents[0].evt) : 'all';
      if (this.v3dEvent !== 'all') this.v3d.setEvent(+this.v3dEvent);
      this.v3dCounts = this.v3d.counts();
      this.v3d.animate();
    },
    saveShot() {
      if (!this.v3d) return;
      const a = document.createElement('a');
      a.href = this.v3d.screenshot();
      a.download = (this.run.name || 'srdet') + '_3d.png';
      a.click();
    },
    // Own small ROOT browser on top of JSROOT (its full GUI does not initialise inside our page).
    async openRoot() {
      this.rootKeys = [];
      this.rootMsg = 'загрузка JSROOT…';
      try {
        this._J = this._J || await import(JSROOT_URL);
        // one byte range per request: the server answers multi-range requests with multipart
        // bodies that JSROOT 7 cannot parse
        this._J.settings.MaxRanges = 1;
        this._rootFile = await this._J.openFile('/files/' + this.run.path + '/srdet.root');
        this.rootKeys = this._rootFile.fKeys.filter(k => k.fClassName !== 'TList')
          .map(k => ({ name: k.fName, cls: k.fClassName, title: k.fTitle }));
        this.rootMsg = '';
        const first = this.rootKeys.find(k => k.cls.startsWith('TH1'));
        if (first) await this.drawRoot(first.name);
      } catch (e) {
        this.rootMsg = `JSROOT: ${e.message}`;
      }
    },
    async drawRoot(name, expr) {
      const key = this.rootKeys.find(k => k.name === name);
      if (!key || !this._rootFile) return;
      this.rootSel = name;
      const el = this.$refs.jsroot;
      this._J.cleanup(el);
      el.innerHTML = '';
      try {
        const obj = await this._rootFile.readObject(name);
        if (key.cls === 'TTree') {
          this.rootExpr = expr || this.rootExpr || (name === 'events' ? 'n_det' : name === 'photons' ? 'lambda_nm' : 'edep_keV');
          await this._J.draw(el, obj, this.rootCut ? `${this.rootExpr}::${this.rootCut}` : this.rootExpr);
        } else {
          await this._J.draw(el, obj, key.cls.startsWith('TH2') ? 'colz' : 'hist');
        }
      } catch (e) { el.innerHTML = `<div class="empty">${e.message}</div>`; }
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
    fileHelp(path) {
      const n = path.split('/').pop();
      return { 'srdet.root': 'гистограммы и таблицы (ROOT / JSROOT / uproot)', 'config.yaml': 'полная конфигурация',
               'run.mac': 'макрос Geant4', 'metrics.json': 'метрики анализа', 'geometry.json': 'соты и размеры',
               'materials.json': 'оптические таблицы материалов', 'meta.json': 'версия, git, время', 'log.txt': 'вывод Geant4',
               'run_summary.json': 'быстрые итоги', 'STATUS': 'успешен ли прогон', 'tracks.jsonl': 'треки для 3D' }[n] || '';
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
      this.studyEst = null;
      this.study = await api('/api/study?path=' + encodeURIComponent(path));
      api('/api/estimates?path=' + encodeURIComponent(path)).then(r => {
        if (this.study && this.study.path === path) { this.studyEst = r; this.drawStudy(); }
      }).catch(() => {});
      const spec = this.study.spec || {};
      const scan = spec.variants ? ['variant'] : Object.keys(spec.scan || {});
      this.studyX = spec.x || scan[0] || '';
      this.studyY = (spec.metrics || [])[0] || '';
      this.studySeries = spec.series || '';
      this.$nextTick(() => this.drawStudy());
    },
    studyValue(s, key, v, i) {
      if (s.x_names && s.x_names[i] !== undefined && Object.keys(s.scan).length === 1) return s.x_names[i];
      return typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v);
    },
    // explanation of a study result: from its own study.yaml, else (older results) from the current spec
    studyExplain() {
      const spec = (this.study && this.study.spec) || {};
      if (spec.explain) return spec.explain;
      const cur = this.studies.specs.find(s => s.name === spec.name);
      return cur && cur.explain ? { ...cur.explain, stale: true } : {};
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
      const palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
      traces.forEach((t, i) => { t.marker = { color: palette[i % palette.length] }; t.line = { color: palette[i % palette.length] }; });
      if (!cat && this.studyEst) {
        groups.forEach((gv, i) => {
          const rr = rows.filter(r => gv === null || r[s] === gv);
          traces.push(...this.estTraces(rr, x, y, this.studyEst.points, 'оценка' + (gv === null ? '' : ` (${s} = ${gv})`),
                                        palette[i % palette.length], 'g' + i));
        });
      }
      const spec = this.study.spec || {};
      const logx = !cat && spec.logx && x === (spec.x || Object.keys(spec.scan || {})[0]) && rows.every(r => r[x] > 0);
      Plotly.react(el, traces, this.layout({ xaxis: { title: x, type: logx ? 'log' : 'linear' }, yaxis: { title: this.label(y) } }), { responsive: true });
    },

    // ------------------------------------------------------------ optimisation constructor
    async loadObMeta() {
      try { this.obMeta = await api('/api/optimize/meta'); } catch (e) { this.notify('meta: ' + e.message); }
    },
    obField(path) { return this.obMeta.fields.find(f => f.path === path) || {}; },
    obFieldHelp(path) {
      const f = this.obField(path);
      if (!f.path) return path ? '' : 'без ключа: параметр участвует только в вычисляемых формулах';
      return [f.help, f.default !== undefined && f.default !== null ? `по умолчанию ${f.default}` : ''].filter(Boolean).join(' · ');
    },
    obPlaceholder(path) { const f = this.obField(path); return f.default !== undefined && f.default !== null ? String(f.default) : 'значение'; },
    obUnits(p) { const f = this.obField(p.path); return f.unit_kind ? UNITS[f.unit_kind] : (p.unit ? [p.unit] : []); },
    obParamPath(p) {
      const f = this.obField(p.path);
      if (f.choices) { p.kind = 'choice'; p.values = []; }
      else if (f.kind === 'int') { p.kind = 'int'; p.unit = ''; }
      else if (p.kind === 'choice') p.kind = 'range';
      if (f.kind === 'quantity') p.unit = f.unit;
      if (f.key && /^p\d+$/.test(p.alias)) p.alias = f.key.replace(/[^A-Za-z0-9_]/g, '_').slice(0, 12);
    },
    obToggle(p, c, on) { p.values = on ? [...new Set([...p.values, c])] : p.values.filter(v => v !== c); this.obCheck(); },
    obLoadPreset(name) {
      const s = (this.opts.specs.find(x => x.name === name) || {}).spec;
      const ob = emptyOb();
      ob.preset = name || '';
      if (s) {
        ob.name = s.name + '_custom'; ob.title = s.title || ''; ob.description = String(s.description || '').trim();
        ob.base = typeof s.base === 'string' ? s.base : 'full.yaml';
        ob.fixed = Object.entries(s.set || {}).map(([path, value]) => ({ path, value: typeof value === 'object' ? JSON.stringify(value) : String(value) }));
        ob.params = Object.entries(s.space || {}).map(([alias, d]) => {
          if (d.values) return { alias, path: d.path || '', kind: 'choice', values: d.values.map(String), low: '', high: '', unit: '', log: false, steps: 3 };
          const [lo, u1] = splitQty(d.low), [hi, u2] = splitQty(d.high);
          return { alias, path: d.path || '', kind: d.type === 'int' ? 'int' : 'range', low: lo, high: hi, unit: u1 || u2, log: !!d.log, steps: d.steps || 3, values: [] };
        });
        ob.derived = Object.entries(s.derived || {}).map(([path, d]) => (typeof d === 'object' ? { path, expr: d.expr, unit: d.unit || '' } : { path, expr: String(d), unit: '' }));
        ob.objective = (s.objective || {}).expr || '';
        ob.direction = String((s.objective || {}).direction || 'maximize').startsWith('min') ? 'minimize' : 'maximize';
        ob.constraints = (s.constraints || []).map(c => {
          const m = /^(.*?)\s*(<=|>=|==|!=|<|>)\s*(.*)$/.exec(String(c));
          return m ? { left: m[1], op: m[2], right: m[3] } : { left: String(c), op: '', right: '' };
        });
        if (s.pareto) ob.pareto = { on: true, x_dir: 'min', y_dir: 'max', ...s.pareto };
        ob.report = [...(s.report_metrics || [])];
        const se = s.search || {};
        ob.search = { sampler: se.sampler || 'lhs', initial: se.initial ?? 12, events: (se.events || [300]).join(', '), eta: se.eta ?? 3, seed: se.seed ?? 1,
                      refineOn: !!se.refine, refine: { iterations: 4, events: (se.events || [300]).slice(-1)[0], step: 0.15, min_gain: 0.03, ...(se.refine || {}) },
                      finalOn: !!(se.final && se.final.top), final: { top: 3, events: 3000, repeats: 3, ...(se.final || {}) } };
        ob.quickSpec = s.quick || null;
      }
      this.ob = ob;
      this.obCheck();
    },
    // constructor state -> spec dictionary (the same format as configs/optimize/*.yaml)
    obValue(path, v) {
      const f = this.obField(path);
      if (f.kind === 'int' || f.kind === 'float') return v === '' || isNaN(+v) ? v : +v;
      if (f.kind === 'bool') return v === true || v === 'true';
      if (typeof v === 'string' && /^[\[{]/.test(v.trim())) { try { return JSON.parse(v); } catch (e) { /* keep text */ } }
      return v;
    },
    obSpec() {
      const o = this.ob, num = v => (v === '' || v === null || isNaN(+v) ? v : +v);
      const space = {};
      for (const p of o.params) {
        const d = p.path ? { path: p.path } : {};
        if (p.kind === 'choice') d.values = p.values.map(v => this.obValue(p.path, v));
        else {
          d.low = p.unit ? `${p.low} ${p.unit}` : num(p.low);
          d.high = p.unit ? `${p.high} ${p.unit}` : num(p.high);
          if (p.log) d.log = true;
          if (p.kind === 'int') d.type = 'int';
          if (o.search.sampler === 'grid' && p.steps) d.steps = +p.steps;
        }
        space[p.alias] = d;
      }
      const spec = { name: o.name, title: o.title || o.name, description: o.description, base: o.base,
                     set: Object.fromEntries(o.fixed.filter(r => r.path).map(r => [r.path, this.obValue(r.path, r.value)])), space };
      if (o.derived.length) spec.derived = Object.fromEntries(o.derived.filter(d => d.path).map(d => [d.path, d.unit ? { expr: d.expr, unit: d.unit } : { expr: d.expr }]));
      spec.objective = { expr: o.objective, direction: o.direction };
      spec.constraints = o.constraints.filter(c => String(c.left).trim()).map(c => (c.op ? `${c.left} ${c.op} ${c.right}` : c.left));
      if (o.pareto.on) spec.pareto = { x: o.pareto.x, x_dir: o.pareto.x_dir, y: o.pareto.y, y_dir: o.pareto.y_dir };
      if (o.report.length) spec.report_metrics = [...o.report];
      const s = o.search;
      spec.search = { sampler: s.sampler, events: String(s.events).split(/[,;\s]+/).filter(Boolean).map(Number), eta: +s.eta, seed: +s.seed };
      if (s.sampler !== 'grid') spec.search.initial = +s.initial;
      spec.search.refine = s.refineOn ? { iterations: +s.refine.iterations, events: +s.refine.events, step: +s.refine.step, min_gain: +s.refine.min_gain } : null;
      spec.search.final = s.finalOn ? { top: +s.final.top, events: +s.final.events, repeats: +s.final.repeats } : null;
      if (o.quickSpec) spec.quick = o.quickSpec;
      return spec;
    },
    async obCheck() {
      if (!this.obMeta.fields.length) return;
      const seq = (this._obSeq = (this._obSeq || 0) + 1);
      this.obChecking = true;
      try {
        const r = await post('/api/optimize/check', { spec: this.obSpec(), quick: this.ob.quick });
        if (seq === this._obSeq) this.obResult = r;
      } catch (e) {
        if (seq === this._obSeq) this.obResult = { ok: false, errors: [e.message], warnings: [], plan: { steps: [], sims: 0, events: 0 }, yaml: '' };
      } finally { if (seq === this._obSeq) this.obChecking = false; }
    },
    obMetric(name) { return this.obMeta.metrics.find(m => m.name === name); },
    obMetricsIn(expr) {
      const names = [...new Set((String(expr || '').match(/[A-Za-z_]\w*/g) || []))];
      return names.map(n => this.obMetric(n)).filter(Boolean);
    },
    // human-readable formula: metric names -> labels, aliases highlighted
    obPretty(expr, aliases = this.ob.params.map(p => p.alias)) {
      const ops = { '**': '^', '*': ' × ', '/': ' ÷ ', '<=': ' ≤ ', '>=': ' ≥ ', '!=': ' ≠ ', '==': ' = ' };
      // token by token, so operators inside the generated HTML are never touched
      return String(expr).replace(/([A-Za-z_]\w*)|(\*\*|<=|>=|!=|==|[*/])|([^A-Za-z_*/<>=!]+|[<>=!])/g, (all, name, op, other) => {
        if (op) return ops[op];
        if (other) return esc(other);
        const m = this.obMetric(name);
        if (m) return `<span title="${esc(name)}">${esc(m.label)}</span>`;
        return aliases.includes(name) ? `<i>${esc(name)}</i>` : esc(name);
      });
    },
    obFormula() {
      if (!this.ob.objective) return '<span class="muted">цель не задана</span>';
      return (this.ob.direction === 'maximize' ? 'Максимизируем: ' : 'Минимизируем: ') + this.obPretty(this.ob.objective) +
        (this.ob.constraints.length ? '<div class="small muted" style="font-weight:400;margin-top:4px">при условиях: ' +
          this.ob.constraints.filter(c => c.left).map(c => esc(this.obConstraintText(c))).join('; ') + '</div>' : '');
    },
    obConstraintText(c) {
      if (!c.left) return '';
      const m = this.obMetric(String(c.left).trim());
      return `${m ? m.label : c.left} ${OP_TEXT[c.op] || c.op} ${c.right}`;
    },
    obAddToObjective(name) {
      if (!name) return;
      this.ob.objective = this.ob.objective.trim() ? `${this.ob.objective.trim()} * ${name}` : name;
      const m = this.obMetric(name);
      if (m && m.better && this.ob.objective === name) this.ob.direction = m.better === 'max' ? 'maximize' : 'minimize';
      this.obCheck();
    },
    obEta() {
      if (!this.obResult || !this.obResult.plan.events) return '';
      return 'Ориентир по времени: полный детектор с оптикой — около 1 с на 1000 событий (8 потоков) плюс ~2 с на запуск ' +
        'каждой симуляции; точнее покажет quick (время каждого испытания видно в таблице испытаний).';
    },
    async obLaunch(quick) {
      await this.obCheck();
      if (!this.obResult || !this.obResult.ok) { this.notify('Исправьте ошибки спецификации'); return; }
      this.submit({ kind: 'optimize', spec: this.obSpec(), quick, archive: this.ob.archive && !quick });
    },
    async obSave() {
      const spec = this.obSpec();
      try {
        const r = await post('/api/optimize/save', { spec });
        this.notify(`Сохранено: <code>${esc(r.path)}</code>`);
      } catch (e) {
        if (/существует/.test(e.message) && confirm(`${e.message}. Перезаписать?`)) {
          try { const r = await post('/api/optimize/save', { spec, overwrite: true }); this.notify(`Перезаписано: <code>${esc(r.path)}</code>`); }
          catch (e2) { this.notify('Ошибка: ' + esc(e2.message)); return; }
        } else { this.notify('Ошибка: ' + esc(e.message)); return; }
      }
      this.opts = await api('/api/optimizations');
      this.ob.preset = spec.name;
    },
    obDownload() {
      const blob = new Blob([this.obResult ? this.obResult.yaml : ''], { type: 'text/yaml' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (this.ob.name || 'optimization') + '.yaml';
      a.click();
      URL.revokeObjectURL(a.href);
    },
    // a finished optimisation back into the constructor (change something, run again)
    optToConstructor() {
      const spec = JSON.parse(JSON.stringify(this.opt.spec));
      const tmp = '__from_run__';
      this.opts.specs = [...this.opts.specs.filter(s => s.name !== tmp), { name: tmp, title: 'из запуска', spec }];
      this.obLoadPreset(tmp);
      this.ob.preset = '';
      this.ob.name = String(spec.name || 'opt').replace(/_custom$/, '') + '_v2';
      this.optimizeTab = 'constructor';
      location.hash = '#/optimize';
    },

    // ------------------------------------------------------------ optimisation dashboard
    async loadOpt(path, quiet) {
      if (!quiet) this.opt = null;
      let o;
      try { o = await api('/api/optimization?path=' + encodeURIComponent(path)); } catch (e) { if (!quiet) this.notify(e.message); return; }
      if (quiet && this.opt && this.opt.path === path && this.opt.trials.length === o.trials.length && this.opt.finished === o.finished) {
        this.opt.progress = o.progress;
        return;
      }
      this.opt = o;
      api('/api/estimates?path=' + encodeURIComponent(path)).then(r => {
        if (!this.opt || this.opt.path !== path) return;
        this.optEst = r;
        if (this.optTab === 'параметр → гистограммы') this.drawScan();
      }).catch(() => {});
      const al = this.optAliases();
      if (!al.includes(this.optParam)) this.optParam = al[0] || '';
      if (!al.includes(this.scanParam)) this.scanParam = al[0] || '';
      if (!this.scanMetrics().includes(this.scanMetric)) this.scanMetric = this.scanMetrics()[0] || 'objective';
      this.setOptTab(this.optTab);
    },
    optFormula() {
      const o = this.opt.spec.objective || {}, al = this.optAliases();
      if (!o.expr) return '';
      const cons = (this.opt.spec.constraints || []).map(c => {
        const m = /^(.*?)\s*(<=|>=|==|!=|<|>)\s*(.*)$/.exec(String(c));
        return esc(m ? this.obConstraintText({ left: m[1], op: m[2], right: m[3] }) : c);
      });
      return (String(o.direction || 'max').startsWith('min') ? 'Минимизировали: ' : 'Максимизировали: ') + this.obPretty(o.expr, al) +
        (cons.length ? '<div class="small muted" style="font-weight:400;margin-top:4px">при условиях: ' + cons.join('; ') + '</div>' : '');
    },
    optMetricsUsed() {
      const s = this.opt.spec;
      return this.obMetricsIn([(s.objective || {}).expr, ...(s.constraints || [])].join(' '));
    },
    optRealSims() { return this.opt.trials.filter(t => t.run_dir).length; },
    optStageDone(step) {
      const T = this.opt.trials, st = t => String(t.stage);
      const match = { screen: t => st(t) === step.id, halving: t => st(t) === step.id, refine: t => /^r\d+$/.test(st(t)),
                      final: t => st(t).startsWith('final') }[step.kind];
      if (!match || !step.sims) return '';
      const rows = T.filter(match), ok = rows.filter(t => t.feasible).length;
      return `план: ${this.fmt(step.sims)} × ${this.fmt(step.events)} соб. · выполнено ${rows.length}, допустимых ${ok}`;
    },
    optProgress() {
      const p = (this.opt && this.opt.progress) || {};
      if (!p.planned) return 0;
      return Math.min(100, Math.round(100 * p.done / p.planned));
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
      const cmp = (x, y) => (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'ru', { numeric: true }));
      // empty values always last, whatever the direction
      return [...rows].sort((a, b) => {
        const x = a[col], y = b[col], ex = x === null || x === undefined || x === '', ey = y === null || y === undefined || y === '';
        if (ex || ey) return ex - ey;
        return cmp(x, y) * (asc ? 1 : -1);
      });
    },
    async setOptTab(t) {
      this.optTab = t;
      if (!this.opt) return;
      await this.$nextTick();
      if (t === 'параметр → гистограммы') this.drawScan();
      if (t === 'дашборд') { this.drawOptConv(); this.drawOptPareto(); this.drawOptPar(); this.drawOptSens(); }
      if (t === 'геометрия лучшей') {
        const best = this.opt.trials.find(r => String(r.stage).startsWith('final') && r.run_dir) ||
                     [...this.opt.trials].filter(r => r.feasible && r.run_dir).sort((a, b) => b.events - a.events)[0];
        if (!best) return;
        const g = await api('/api/run/geometry?path=' + encodeURIComponent(this.opt.path + '/' + best.run_dir)).catch(() => null);
        if (g) this.renderGeometry(g, this.$refs.optlattice, 'optGeo', 'optGeoInfo');
      }
    },
    scanMetrics() {
      if (!this.opt) return [];
      const rm = this.opt.spec.report_metrics || [];
      return ['objective', ...rm.filter(m => m !== 'objective')];
    },
    // Trials that differ from the best point only in `param` (others equal): a clean one-parameter scan.
    scanTrials(param) {
      const best = this.optBest();
      const others = this.optAliases().filter(a => a !== param);
      const same = (x, y) => (typeof x === 'number' && typeof y === 'number') ? Math.abs(x - y) <= 1e-6 * Math.max(1, Math.abs(y)) : String(x) === String(y);
      const ok = this.opt.trials.filter(t => t.run_dir && t.ok !== false && isFinite(t.objective));
      const pick = rows => {
        const by = new Map();
        for (const t of rows) {
          const key = String(typeof t[param] === 'number' ? +t[param].toPrecision(5) : t[param]);
          const cur = by.get(key);
          if (!cur || t.events > cur.events || (t.events === cur.events && t.feasible && !cur.feasible)) by.set(key, t);
        }
        return [...by.values()].sort((a, b) => (a[param] > b[param] ? 1 : -1));
      };
      let rows = best ? pick(ok.filter(t => others.every(o => same(t[o], best[o])))) : [];
      let note = '';
      if (rows.length < 2) {
        rows = pick(ok);
        note = 'Чистых одномерных точек мало: показаны симуляции, в которых другие параметры тоже отличались — сравнивайте осторожно.';
      }
      if (rows.length > 9) {  // keep the picture readable: evenly spaced subset
        const step = (rows.length - 1) / 8;
        rows = [...new Set(Array.from({ length: 9 }, (_, i) => rows[Math.round(i * step)]))];
      }
      return { rows, note };
    },
    async drawScan() {
      if (!this.opt || !this.scanParam) return;
      const { rows, note } = this.scanTrials(this.scanParam);
      this.scanNote = note;
      const p = this.scanParam, name = this.scanHist;
      const hists = await Promise.all(rows.map(t => api(`/api/run/hist?path=${encodeURIComponent(this.opt.path + '/' + t.run_dir)}&name=${name}`).catch(() => null)));
      const colors = ['#2a6fdb', '#e8743b', '#19a979', '#945ecf', '#ed4a7b', '#13a4b4', '#525df4', '#bf399e', '#6c8893'];
      const traces = [];
      hists.forEach((h, i) => {
        if (!h || !h.edges || h.edges.length !== 1 || !h.entries) return;
        let e = h.edges[0], v = [...h.values];
        if (this.scanNoZero && e[0] === 0) v[0] = 0;  // events without signal would dominate the shape
        // visible range, then merge bins so that ~60 remain (readable with modest statistics)
        let lo = v.findIndex(x => x > 0), hi = v.length - 1 - [...v].reverse().findIndex(x => x > 0);
        if (lo < 0) return;
        const k = Math.max(1, Math.ceil((hi - lo + 1) / 60));
        const ee = [], vv = [];
        for (let j = lo; j <= hi; j += k) { ee.push(e[j]); vv.push(v.slice(j, j + k).reduce((a, b) => a + b, 0)); }
        ee.push(e[Math.min(hi + 1, lo + vv.length * k)]);
        const total = vv.reduce((a, b) => a + b, 0) || 1;
        const xs = [], ys = [];
        vv.forEach((c, j) => { const y = this.scanNorm ? c / total / (ee[j + 1] - ee[j]) : c; xs.push(ee[j], ee[j + 1]); ys.push(y, y); });
        const t = rows[i];
        traces.push({ type: 'scatter', mode: 'lines', x: xs, y: ys, line: { color: colors[i % colors.length], width: 1.8 },
                      name: `${p} = ${this.fmt(t[p])}  (${t.events} соб.)` });
      });
      const xt = (hists.find(h => h && h.axes) || {}).axes;
      Plotly.react(this.$refs.scanhist, traces, this.layout({
        xaxis: { title: xt ? xt[0].replace(/[_^]\{([^}]*)\}/g, '$1').replace('#lambda', 'λ').replace('#gamma', 'γ') : '' },
        yaxis: { title: this.scanNorm ? 'плотность вероятности' : 'число', type: this.scanLog ? 'log' : 'linear' },
        legend: { orientation: 'v', x: 1.02, y: 1 }, margin: { l: 64, r: 10, t: 10, b: 56 } }), { responsive: true });
      // metric of the same runs
      const m = this.scanMetric;
      const cat = rows.some(t => typeof t[p] === 'string');
      const est = cat || !this.optEst ? [] : this.estTraces(rows, p, m, this.optEst.points, 'оценка', '#8a8f99', 'est');
      const dEst = (this.opt.spec.space || {})[p] || {};
      Plotly.react(this.$refs.scanmetric, [{ type: cat ? 'bar' : 'scatter', mode: 'lines+markers', x: rows.map(t => t[p]), y: rows.map(t => t[m]),
        marker: { color: rows.map(t => (t.feasible ? '#19a979' : '#d64545')), size: 10 }, hovertext: rows.map(t => this.hoverText(t)), hoverinfo: 'text+y',
        name: 'Geant4', line: { color: '#2a6fdb' } }, ...est],
        this.layout({ xaxis: { title: p, type: dEst.log && !cat ? 'log' : 'linear' }, yaxis: { title: this.label(m) }, showlegend: est.length > 0 }), { responsive: true });
      this.scanEstNote = !this.showEst ? '' : est.length ? 'Пунктир — аналитическая оценка для тех же конфигураций (NIST XCOM / простые законы), серая полоса — её диапазон.'
        : 'Для этой метрики аналитической оценки нет.';
      const vals = rows.map(t => t[m]).filter(isFinite);
      this.scanSummary = vals.length ? `${this.label(m)}: от ${this.fmt(Math.min(...vals))} до ${this.fmt(Math.max(...vals))}; зелёные точки удовлетворяют ограничениям, красные — нет.` : '';
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
