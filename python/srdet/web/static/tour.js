// Guided tour: highlights elements of the current page one by one and explains what to press.
// Started from the "❓ Как пользоваться" link in the sidebar (or ?tour=1 in the URL).
const TOUR = {
  dashboard: [
    ['.nav', 'Меню разделов', 'Отсюда попадаете в любой раздел: моделирование, прогоны, исследования, оптимизацию, документацию.'],
    ['.topbar .btn.primary', 'Новое моделирование', 'Начните отсюда: откроется форма, где задаются детектор, материалы и пучок.'],
    ['.grid.g4', 'Счётчики', 'Сколько прогонов готово, сколько исследований и оптимизаций, и что сейчас считается.'],
    ['.grid.g2 .card', 'Лучшие конфигурации', 'Итоги оптимизаций: лучшая цель ± погрешность и параметры. Клик по названию открывает дашборд.'],
    ['.main > section > .card:last-child', 'Последние прогоны', 'Клик по имени — страница прогона с графиками, 3D, ROOT и скачиванием.'],
  ],
  new: [
    ['.main select', 'Базовая конфигурация', 'Выберите готовую заготовку (весь детектор, одна сота, кластер из 7 сот…). Все поля ниже заполнятся.'],
    ['details.sec > summary', 'Параметры', 'Меняйте что угодно: длину канала, шаг, покрытие, материалы, пучок. Изменённые поля подсвечиваются оранжевым.'],
    ['.sticky .card', 'Предпросмотр', 'Сразу видно соту с размерами и разрез детектора. Красная рамка — геометрия невозможна, запуск заблокирован.'],
    ['.sticky .btn.primary', 'Запуск', '«Запустить» ставит задачу в очередь и открывает её живой лог. «+ 3D-картинки» дополнительно рисует сцену Geant4.'],
  ],
  runs: [
    ['.topbar input', 'Фильтр', 'Наберите часть имени, покрытия или режима, чтобы найти прогон.'],
    ['table.t', 'Таблица прогонов', 'Ключевые цифры каждого прогона. Галочки слева — выбрать для сравнения, имя — открыть.'],
  ],
  run: [
    ['.tabs', 'Вкладки прогона', 'обзор — метрики; графики — все гистограммы; 3D — частицы в детекторе; геометрия — соты; ROOT — интерактивный браузер; файлы — скачать.'],
    ['.topbar', 'Действия', 'Excel и ZIP — красиво оформленные данные; «Повторить с изменениями» переносит этот прогон в форму.'],
  ],
  studies: [
    ['.grid.g3 .card', 'Исследование', 'Готовый эксперимент: меняется один параметр. quick — быстро прикинуть, полный — с хорошей статистикой и архивом.'],
  ],
  study: [
    ['.main .plot', 'Интерактивный график', 'Выберите ось x, величину y и серии — график перестроится.'],
  ],
  optimize: [
    ['.main .tabs', 'Конструктор и результаты', 'В конструкторе собирается своя оптимизация; во вкладке «Результаты» — все запуски.'],
    ['.ob-param', 'Что меняем', 'Свободные параметры: ключ конфигурации, диапазон с единицами (log — для величин, меняющихся в разы) или список вариантов.'],
    ['.ob-formula', 'Цель и ограничения', 'Формула цели расшифрована словами; ограничения — требования, нарушение которых делает кандидата недопустимым.'],
    ['.ob-steps', 'План поиска', 'Что именно будет посчитано: ступени, число симуляций и событий. Меняется сразу при правке настроек.'],
    ['.sticky .btn.primary', 'Запуск', 'Сначала quick — проверка за минуту, затем полный поиск. Спецификацию можно сохранить как пресет.'],
  ],
  opt: [
    ['.tabs', 'Вкладки', '«параметр → гистограммы» — самое наглядное: как меняется спектр при изменении одного параметра.'],
    ['.main select', 'Параметр и величина', 'Выберите параметр (например, длину канала L) и гистограмму — линии покажут разные значения параметра.'],
    ['.main .btn.sm.primary', 'Досчитать скан', 'Если точек мало — нажмите: будет посчитано N значений параметра по всему диапазону, остальное как в лучшей точке.'],
  ],
  jobs: [['table.t', 'Очередь', 'Все задачи и их статус; «стоп» прерывает. Клик по задаче — живой лог.']],
  job: [['.log', 'Живой лог', 'Здесь видно, что делает Geant4. Когда задача закончится, появится кнопка «Открыть результат».']],
  docs: [['.md', 'Документация', 'Слева — разделы: инструкция пользователя, физика, запуск, оптимизация, эксперименты.']],
  compare: [['.main .plot', 'Сравнение', 'Отметьте метрики — столбцы покажут их для всех выбранных прогонов.']],
};

function tourStart(app) {
  const steps = (TOUR[app.route.view] || []).filter(([sel]) => [...document.querySelectorAll(sel)].some(e => e.offsetParent));
  if (!steps.length) { app.notify('Для этой страницы подсказок нет — откройте «Документация → Инструкция».'); return; }
  let i = 0;
  const layer = document.createElement('div');
  layer.className = 'tour-layer';
  layer.innerHTML = '<div class="tour-box"></div><div class="tour-tip card"><div class="tour-n"></div><h2></h2><p></p>' +
    '<div class="row"><button class="btn sm" data-a="prev">← назад</button><button class="btn sm primary" data-a="next">далее →</button>' +
    '<button class="btn sm right" data-a="close">закрыть</button></div></div>';
  document.body.appendChild(layer);
  const box = layer.querySelector('.tour-box'), tip = layer.querySelector('.tour-tip');
  function show() {
    const [sel, title, text] = steps[i];
    const el = [...document.querySelectorAll(sel)].find(e => e.offsetParent);
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setTimeout(() => {
      const r = el.getBoundingClientRect();
      Object.assign(box.style, { left: r.left - 6 + 'px', top: r.top - 6 + 'px', width: r.width + 12 + 'px', height: r.height + 12 + 'px' });
      const below = r.bottom + 230 < innerHeight;
      Object.assign(tip.style, { left: Math.min(Math.max(12, r.left), innerWidth - 380) + 'px',
                                 top: (below ? r.bottom + 14 : Math.max(12, r.top - 214)) + 'px' });
      tip.querySelector('.tour-n').textContent = `шаг ${i + 1} из ${steps.length}`;
      tip.querySelector('h2').textContent = title;
      tip.querySelector('p').textContent = text;
      tip.querySelector('[data-a=prev]').disabled = i === 0;
      tip.querySelector('[data-a=next]').textContent = i === steps.length - 1 ? 'готово ✓' : 'далее →';
    }, 280);
  }
  layer.addEventListener('click', e => {
    const a = e.target.dataset.a;
    if (a === 'next') { if (++i >= steps.length) layer.remove(); else show(); }
    if (a === 'prev' && i > 0) { i--; show(); }
    if (a === 'close' || e.target === layer) layer.remove();
  });
  show();
}
window.tourStart = tourStart;
