// Rap skin: dark stage, neon, graffiti tags and stickers with names; battle vocabulary.
window.SKIN = {
  name: 'rap',
  brand: '<span class="skin-logo">SRDETECTOR</span><span class="skin-sub">// battle edition</span>',
  nav: { dashboard: 'Сцена', new: 'Новый раунд', runs: 'Раунды', studies: 'Разборы', optimize: 'Флекс-оптимизация',
         compare: 'Батл прогонов', jobs: 'Очередь на сцену', docs: 'Райдер' },
  icons: { dashboard: '🎤', new: '🔥', runs: '💿', studies: '📼', optimize: '💸', compare: '🥊', jobs: '⏱', docs: '📜' },
  text: {
    'Дашборд': 'Сцена 🎤', '＋ Новое моделирование': '🔥 Новый раунд', 'Новое моделирование': 'Новый раунд 🔥',
    '▶ Запустить': '🎤 На бит', '▶ + 3D-картинки': '🎤 На бит + 3D', 'Сбросить': 'Сбросить бит',
    'Показать макрос Geant4': 'Показать текст макроса 📜', 'Прогоны': 'Раунды 💿', 'Задачи': 'Очередь на сцену ⏱',
    'Лучшие найденные конфигурации': 'Лучшие панчи 💸', 'Последние прогоны': 'Последние раунды 💿',
    'Оптимизация параметров': 'Флекс-оптимизация 💸', 'Сравнение прогонов': 'Батл прогонов 🥊',
    'Предпросмотр геометрии': 'Превью сцены', '▶ Прогнать лучшую': '🎤 Выпустить лучший конфиг',
    'Проверка физики (quick)': 'Фактчек физики ✅',
  },
  slogans: [
    'панч по шуму: SNR растёт', 'биф с кросс-током закрыт', 'флексим светосбором', 'альтушечно, но строго по физике',
    'раунд за раундом — до оптимума', 'Geant4 на бите, фотоны на сцене', 'без фейков: всё сверено с XCOM',
    'микрофон — сенсору, слово — данным', 'серебро в покрытии, а не на шее',
  ],
  toastPrefix: '🎤 ',
  decor: {
    names: ['Замай', 'Слава КПСС', 'Oxxxymiron', 'Ежемесячные', 'альтушечно', '🔥', '💿'],
    every: 3000,
    render(it, r) {
      if (it.img) return `<div class="sticker-img" style="--s:${90 + r * 50}px"><img src="${it.img}"></div>`;
      if (it.text.length <= 2) return `<span class="sparkle" style="font-size:${24 + r * 18}px">${it.text}</span>`;
      const alt = it.text === 'альтушечно';
      return `<div class="tag ${alt ? 'tag-alt' : ''}" style="--hue:${Math.round(r * 360)}">${it.text}</div>`;
    },
    corner(pic) {
      return pic ? `<div class="sticker-img" style="--s:120px"><img src="${pic}"></div><div class="corner-cap">LIVE 🎤</div>`
                 : `<div class="corner-cap">● LIVE 🎤</div>`;
    },
  },
};
