// Rap skin, antihype cut: xerox black/white/red, caution tape, crossed-out hype; battle vocabulary.
window.SKIN = {
  name: 'rap',
  brand: '<span class="skin-logo">SRDETECTOR</span><span class="skin-sub">антихайп edition</span>',
  nav: { dashboard: 'Сцена', new: 'Новый раунд', runs: 'Раунды', studies: 'Разборы', optimize: 'Флекс-оптимизация',
         compare: 'Батл прогонов', jobs: 'Очередь на сцену', docs: 'Райдер' },
  icons: { dashboard: '⚡', new: '💥', runs: '📼', studies: '🗞', optimize: '⛓', compare: '🥊', jobs: '⏱', docs: '📜' },
  text: {
    'Дашборд': 'Сцена', '＋ Новое моделирование': '💥 Новый раунд', 'Новое моделирование': 'Новый раунд',
    '▶ Запустить': '💥 На бит', '▶ + 3D-картинки': '💥 На бит + 3D', 'Сбросить': 'Снести бит',
    'Показать макрос Geant4': 'Текст макроса без цензуры', 'Прогоны': 'Раунды', 'Задачи': 'Очередь на сцену',
    'Лучшие найденные конфигурации': 'Лучшие панчи', 'Последние прогоны': 'Последние раунды',
    'Оптимизация параметров': 'Флекс-оптимизация', 'Сравнение прогонов': 'Батл прогонов',
    'Предпросмотр геометрии': 'Превью сцены', '▶ Прогнать лучшую': '💥 Выпустить лучший конфиг',
    'Проверка физики (quick)': 'Фактчек физики',
  },
  slogans: [
    'хайп — это шум, сигнал — это данные', 'никакого фейкового светосбора', 'XCOM не врёт, а ты?',
    'SNR или уходи со сцены', 'кросс-ток — в бан навсегда', 'сначала валидация, потом панчи',
    'мейнстрим считает на глаз, мы — на Geant4', 'без автотюна: сырые фотоэлектроны', 'серебро в покрытии, а не на шее',
    'альтушечно, но строго по физике',
  ],
  sloganEvery: 14000,  // one slogan per pass of the marquee (see .skin-slogan in rap.css)
  toastPrefix: '✖ ',
  decor: {
    names: ['АНТИХАЙП', 'Замай', 'ХАЙП', 'Слава КПСС', 'Oxxxymiron', 'Ежемесячные', 'альтушечно', '💥', '📼'],
    every: 2600,
    render(it, r) {
      if (it.img) return `<div class="sticker-img" style="--s:${100 + r * 60}px;transform:rotate(${(r * 16 - 8).toFixed(1)}deg)"><img src="${it.img}"><span class="sticker-cap">${r > .5 ? 'no hype' : 'антихайп'}</span></div>`;
      if (it.text.length <= 2) return `<span class="sparkle" style="font-size:${24 + r * 18}px">${it.text}</span>`;
      const cls = it.text === 'альтушечно' || it.text === 'АНТИХАЙП' ? 'tag-alt' : it.text === 'ХАЙП' ? 'tag-x' : '';
      return `<div class="tag ${cls}">${it.text}</div>`;
    },
    corner(pic) {
      return pic ? `<div class="sticker-img" style="--s:150px"><img src="${pic}"></div><div class="corner-cap">● LIVE</div>`
                 : `<div class="corner-cap">● LIVE</div>`;
    },
  },
};
