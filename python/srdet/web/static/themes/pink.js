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
    names: ['Егор Крид', 'Екатерина Шульман', '💄', '🦋', '👛', '✨', '💋'],
    every: 2600,
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
    corner(pic) {
      return pic ? `<div class="heart-img" style="--k:1.2"><img src="${pic}"></div><div class="corner-cap">💖 glam mode</div>`
                 : `<div class="corner-cap">💄 glam mode 🦋</div>`;
    },
  },
};
