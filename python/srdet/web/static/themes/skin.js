// Skin engine: applies window.SKIN (defined by themes/<name>.js) to the UI.
//  - text: exact-string replacements of labels and buttons (also for content rendered later)
//  - nav:  sidebar titles, brand, rotating slogan in the top bar
//  - decor: a non-interactive layer of floating items (hearts / stickers) with names and,
//           optionally, the user's own pictures from themes/<name>/user/ (served by /api/skin)
(() => {
  const S = window.SKIN;
  if (!S) return;
  document.documentElement.dataset.skin = S.name;
  document.title = S.brand.replace(/<[^>]+>/g, '');

  // ---------------- text replacement (exact text of an element's own text node)
  const map = new Map(Object.entries(S.text || {}));
  function patch(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const n of nodes) {
      const t = n.nodeValue.trim();
      if (t && map.has(t)) n.nodeValue = n.nodeValue.replace(t, map.get(t));
    }
  }
  const mo = new MutationObserver(muts => {
    for (const m of muts) {
      for (const n of m.addedNodes) if (n.nodeType === 1) patch(n); else if (n.nodeType === 3 && map.has(n.nodeValue.trim())) n.nodeValue = map.get(n.nodeValue.trim());
      if (m.type === 'characterData' && map.has(m.target.nodeValue.trim())) m.target.nodeValue = map.get(m.target.nodeValue.trim());
    }
  });

  // ---------------- Alpine hooks: nav titles, brand, slogans, toasts
  document.addEventListener('alpine:init', () => {
    Alpine.data('skinBar', () => ({ i: 0, get slogan() { return S.slogans[this.i % S.slogans.length]; },
      init() { setInterval(() => this.i++, S.sloganEvery || 6000); } }));
  });
  window.addEventListener('load', () => {
    const app = window.Alpine && Alpine.$data(document.querySelector('.layout'));
    if (app) {
      app.navItems = app.navItems.map(n => ({ ...n, title: (S.nav || {})[n.view] || n.title, icon: (S.icons || {})[n.view] || n.icon }));
      const notify = app.notify.bind(app);
      app.notify = html => notify(`${S.toastPrefix || ''}${html}`);
    }
    const brand = document.querySelector('.brand');
    if (brand) brand.innerHTML = S.brand;
    const bar = document.createElement('div');
    bar.className = 'skin-slogan';
    bar.setAttribute('x-data', 'skinBar');
    bar.innerHTML = '<span x-text="slogan"></span>';
    document.querySelector('.main').prepend(bar);
    if (window.Alpine) Alpine.initTree(bar);
    patch(document.body);
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
    decor();
  });

  // ---------------- decorative layer
  async function decor() {
    let pics = [];
    try { pics = (await (await fetch('/api/skin')).json()).images || []; } catch (e) { /* no pictures */ }
    const layer = document.createElement('div');
    layer.className = 'skin-decor';
    document.body.appendChild(layer);
    // pictures interleaved with the names, so they show up from the very start
    const items = [];
    const names = S.decor.names.map(n => ({ text: n }));
    for (let i = 0; i < Math.max(names.length, pics.length); i++) {
      if (pics.length) items.push({ img: pics[i % pics.length] });
      if (i < names.length) items.push(names[i]);
    }
    let k = 0;
    const spawn = () => {
      if (document.hidden) return;
      const it = items[k++ % items.length] || {};
      const el = document.createElement('div');
      el.className = 'skin-item';
      el.style.left = (4 + Math.random() * 88) + 'vw';
      el.style.setProperty('--dur', (14 + Math.random() * 10) + 's');
      el.style.setProperty('--rot', (Math.random() * 30 - 15) + 'deg');
      el.innerHTML = S.decor.render(it, Math.random());
      layer.appendChild(el);
      setTimeout(() => el.remove(), 26000);
    };
    for (let i = 0; i < 4; i++) setTimeout(spawn, i * 900);
    setInterval(spawn, S.decor.every || 3200);
    // a mascot frame at the bottom of the sidebar, cycling through the user's pictures
    const corner = document.createElement('div');
    corner.className = 'skin-corner';
    corner.innerHTML = S.decor.corner(pics[0]);
    (document.querySelector('.side') || document.body).appendChild(corner);
    const frame = corner.querySelector('img');
    if (frame && pics.length > 1) {
      let j = 0;
      setInterval(() => {
        if (document.hidden) return;
        frame.parentElement.style.opacity = 0;
        setTimeout(() => { frame.src = pics[++j % pics.length]; frame.parentElement.style.opacity = 1; }, 400);
      }, 5000);
    }
  }
})();
