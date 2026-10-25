// Pink skin: glossy pink, glitter, hearts with names, Bratz-doll-style vibe (no brand assets).
window.SKIN = {
  name: 'pink',
  brand: '<span class="skin-logo">💖 SRDetector</span><span class="skin-sub">glam edition</span>',
  nav: { dashboard: 'Главная, зай', new: 'Замутить симуляцию', runs: 'Мои прогоны', studies: 'Исследования',
         optimize: 'Сделать имбово', compare: 'Кто краше?', jobs: 'Что в работе', docs: 'Гайд для зай' },
  icons: { dashboard: '💖', new: '✨', runs: '💄', studies: '🦋', optimize: '💎', compare: '👛', jobs: '⏳', docs: '📖' },
  text: {
    'Дашборд': 'Главная 💖', '＋ Новое моделирование': '✨ Замутить симуляцию', 'Новое моделирование': 'Новая симуляция ✨',
    '▶ Запустить': '💖 Погнали', '▶ + 3D-картинки': '💖 Погнали + 3D', 'Сбросить': 'Всё сначала',
    'Показать макрос Geant4': 'Подсмотреть макрос 👀', 'Прогоны': 'Мои прогоны 💄', 'Задачи': 'Что в работе ⏳',
    'Лучшие найденные конфигурации': 'Самые имбовые конфиги 💎', 'Последние прогоны': 'Свеженькое 💅',
    'Оптимизация параметров': 'Сделать имбово 💎', 'Сравнение прогонов': 'Кто краше? 👛',
    'Предпросмотр геометрии': 'Как это будет выглядеть 🪞', '▶ Прогнать лучшую': '💎 Прогнать самую имбовую',
    'Проверка физики (quick)': 'Проверить физику 🧪',
  },
  slogans: [
    'вайб детектора: розовый и сияющий ✨', 'краш недели — серебряное покрытие 💎', 'фотоэлектроны любят тебя 💖',
    'сцинтиллятор светится — и ты сияй ✨', 'кросс-ток? не, не слышали 💅', 'оптическая смазка обязательна, как блеск для губ 💋',
    'канал 1 мм — это новый маст-хэв 👛', 'на чиле считаем Geant4 🦋', 'энергия сохраняется, а настроение растёт 💖',
  ],
  toastPrefix: '💖 Зай, ',
  decor: {
    names: ['Егор Крид', '💖', 'Екатерина Шульман', '💄', '✨', '🦋', 'Егор Крид', '💗', '👛', '🌸', 'Екатерина Шульман', '✨', '💋', '💕'],
    every: 1300,
    initial: 9,
    render(it, r) {
      if (it.img) return `<div class="heart-img" style="--k:${(0.8 + r * 0.5).toFixed(2)}"><img src="${it.img}"></div>`;
      if (it.text.length <= 2) return `<span class="sparkle" style="font-size:${22 + r * 20}px">${it.text}</span>`;
      const w = 150 + r * 40;
      return `<svg width="${w}" height="${w * 0.92}" viewBox="0 0 100 92"><defs><linearGradient id="g${Math.round(r * 1e6)}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#ff7ac6"/><stop offset="1" stop-color="#ff2f92"/></linearGradient></defs>
        <path d="M50 88 C20 66 2 50 2 28 C2 13 14 2 28 2 C38 2 46 8 50 16 C54 8 62 2 72 2 C86 2 98 13 98 28 C98 50 80 66 50 88Z"
          fill="url(#g${Math.round(r * 1e6)})" stroke="#fff" stroke-width="2.5"/>
        <text x="50" y="44" text-anchor="middle" font-family="Lobster, cursive" font-size="${it.text.length > 12 ? 8.5 : 10.5}" fill="#fff">${it.text.split(' ')[0]}</text>
        <text x="50" y="58" text-anchor="middle" font-family="Lobster, cursive" font-size="${it.text.length > 12 ? 8.5 : 10.5}" fill="#fff">${it.text.split(' ').slice(1).join(' ')}</text></svg>`;
    },
    // about half of the name hearts pop mid-flight into a spray of tiny hearts
    onSpawn(el, it, layer) {
      if (!it.text || it.text.length <= 2 || Math.random() > .5) return;
      setTimeout(() => {
        if (!el.isConnected) return;
        const b = el.getBoundingClientRect();
        if (b.bottom < 0 || b.top > innerHeight) return;
        el.classList.add('popping');
        pinkBurst(layer, b.left + b.width / 2, b.top + b.height / 2, 10);
        setTimeout(() => el.remove(), 260);
      }, 3500 + Math.random() * 7000);
    },
    corner(pic) {
      return pic ? `<div class="heart-img" style="--k:1.2"><img src="${pic}"></div><div class="corner-cap">💖 glam mode</div>`
                 : `<div class="corner-cap">💄 glam mode 🦋</div>`;
    },
  },
  extras(layer) {
    const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
    // glitter twinkling behind the panels
    for (let i = 0; i < 28; i++) {
      const g = document.createElement('span');
      g.className = 'glitter';
      g.textContent = Math.random() < .7 ? '✦' : '✧';
      g.style.cssText = `left:${Math.random() * 100}vw;top:${Math.random() * 100}vh;font-size:${8 + Math.random() * 16}px;` +
                        `animation-delay:${(-Math.random() * 3).toFixed(2)}s;animation-duration:${(1.6 + Math.random() * 2).toFixed(2)}s`;
      layer.appendChild(g);
    }
    if (calm) return;
    // effects above the UI (never catch clicks)
    const fx = document.createElement('div');
    fx.className = 'pink-fx';
    document.body.appendChild(fx);
    addEventListener('pointerdown', e => pinkBurst(fx, e.clientX, e.clientY, 8), { passive: true });
    let lastTrail = 0;
    addEventListener('pointermove', e => {
      if (e.pointerType !== 'mouse' || e.timeStamp - lastTrail < 45) return;
      lastTrail = e.timeStamp;
      const t = document.createElement('span');
      t.className = 'trail';
      t.textContent = Math.random() < .5 ? '✦' : '♡';
      t.style.cssText = `left:${e.clientX + (Math.random() * 16 - 8)}px;top:${e.clientY + (Math.random() * 16 - 8)}px`;
      fx.appendChild(t);
      setTimeout(() => t.remove(), 700);
    }, { passive: true });
    if (matchMedia('(hover: hover)').matches) pinkCat(fx);
  },
};

// a burst of tiny hearts flying out from (x, y), with a ring "pop"
function pinkBurst(layer, x, y, n) {
  const ring = document.createElement('span');
  ring.className = 'pop-ring';
  ring.style.cssText = `left:${x}px;top:${y}px`;
  layer.appendChild(ring);
  setTimeout(() => ring.remove(), 500);
  for (let i = 0; i < n; i++) {
    const h = document.createElement('span');
    const a = (i / n) * 2 * Math.PI + Math.random() * .5, d = 40 + Math.random() * 50;
    h.className = 'pop-heart';
    h.textContent = ['💖', '💗', '💕', '✨'][i % 4];
    h.style.cssText = `left:${x}px;top:${y}px;--dx:${(Math.cos(a) * d).toFixed(1)}px;--dy:${(Math.sin(a) * d).toFixed(1)}px;font-size:${12 + Math.random() * 10}px`;
    layer.appendChild(h);
    setTimeout(() => h.remove(), 800);
  }
}

// a little cat that runs after the mouse pointer, sits down when it catches up and naps after a while
function pinkCat(fx) {
  const cat = document.createElement('div');
  cat.className = 'pink-cat sit';
  cat.innerHTML = `<div class="cat-body"><svg viewBox="0 0 64 48" width="84" height="63">
    <path class="cat-tail" d="M12 30 Q2 22 5 10" fill="none" stroke="#4a1035" stroke-width="5" stroke-linecap="round"/>
    <path class="cat-tail" d="M12 30 Q2 22 5 10" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>
    <g class="leg l1"><rect x="16" y="33" width="5" height="10" rx="2.5"/></g><g class="leg l2"><rect x="23" y="33" width="5" height="10" rx="2.5"/></g>
    <g class="leg l3"><rect x="34" y="33" width="5" height="10" rx="2.5"/></g><g class="leg l4"><rect x="41" y="33" width="5" height="10" rx="2.5"/></g>
    <ellipse cx="29" cy="30" rx="18" ry="10" fill="#fff" stroke="#4a1035" stroke-width="1.6"/>
    <path d="M40 15 L42 3 L48 11 Z M51 11 L57 3 L58 15 Z" fill="#fff" stroke="#4a1035" stroke-width="1.6" stroke-linejoin="round"/>
    <path d="M42.5 12 L43 6.5 L46 10.5 Z M53 10.5 L56 6.5 L56.5 12 Z" fill="#ff9ccf"/>
    <circle cx="49" cy="20" r="10.5" fill="#fff" stroke="#4a1035" stroke-width="1.6"/>
    <g class="cat-eyes" fill="#4a1035"><ellipse cx="46" cy="19" rx="1.5" ry="2"/><ellipse cx="53.5" cy="19" rx="1.5" ry="2"/></g>
    <path d="M49 22.5 l1.4 1.4 l1.4 -1.4 Z" fill="#ff3d9a"/><circle cx="43.5" cy="23.5" r="2" fill="#ffb3d9"/><circle cx="56" cy="23.5" r="2" fill="#ffb3d9"/>
    <path d="M40 9 l4 3 l-4 3 Z M48 9 l-4 3 l4 3 Z" fill="#ff3d9a"/><circle cx="44" cy="12" r="1.4" fill="#ff7ac6"/>
  </svg></div><span class="cat-zzz">z<small>z</small></span>`;
  fx.appendChild(cat);
  let x = innerWidth - 120, y = innerHeight - 70, tx = x, ty = y, dir = 1, idle = 0, last = performance.now();
  addEventListener('pointermove', e => { if (e.pointerType === 'mouse') { tx = e.clientX; ty = e.clientY; } }, { passive: true });
  addEventListener('pointerdown', () => { cat.classList.remove('jump'); void cat.offsetWidth; cat.classList.add('jump'); }, { passive: true });
  function tick(now) {
    const dt = Math.min(now - last, 50); last = now;
    // stop beside the pointer, slightly below it, so the cat never sits under the cursor
    const gx = tx - dir * 58 - 42, gy = ty + 8;
    const dx = gx - x, dy = gy - y, dist = Math.hypot(dx, dy);
    if (dist > 6) {
      const step = Math.min(dist, (0.2 + Math.min(dist, 600) / 900) * dt);
      x += dx / dist * step; y += dy / dist * step;
      if (Math.abs(dx) > 8) dir = dx > 0 ? 1 : -1;
      idle = 0;
    } else idle += dt;
    cat.classList.toggle('sit', dist <= 6);
    cat.classList.toggle('nap', idle > 7000);
    cat.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scaleX(${dir})`;
    cat.style.setProperty('--flip', dir);  // keeps the 'zz' readable when the cat faces left
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
