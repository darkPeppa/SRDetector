# Архитектура

```
configs/*.yaml ──► python/srdet (config → macro) ──► srdet-sim run.mac ──► srdet.root + json
     ▲                    │                                                     │
     │                    ├── runner: папка прогона, бэкап конфига, статус      ▼
configs/history/          ├── analysis: метрики, sanity-проверки ◄──────── uproot
                          ├── plotting: подписанные графики
                          ├── studies: сетки параметров → отчёты
                          └── archive: results/*.tar.xz (≤ 45 МБ)
```

## Структура репозитория

| Путь | Содержимое |
|---|---|
| `app/` | C++ приложение Geant4 (`srdet-sim`) |
| `python/srdet/` | обёртка: CLI, конфиги, макросы, запуск, анализ, графики, исследования, архивы |
| `configs/defaults.yaml` | все параметры с комментариями |
| `configs/detector/` | готовые конфигурации (full, unit, cluster7, slab, legacy_like) |
| `configs/studies/` | автоматические эксперименты U01–U10, B01–B02, F01 |
| `configs/optimize/` | спецификации поиска оптимума O01–O03 |
| `configs/history/` | бэкапы всех запускавшихся конфигураций |
| `macros/` | vis-макросы и примеры ручных GPS-пучков |
| `tools/` | сопровождение данных: XCOM, конвертация, слияние, сравнение конфигов, сбор отчётов, очистка, скриншоты UI |
| `tests/` | `test_python.py` (без Geant4), `test_physics.py` (sanity), `data/` (NIST XCOM) |
| `docker/`, `docker-compose.yml` | сборка Geant4 из исходников и окружения |
| `results/` | архивы удачных прогонов и отчёты (в git) |
| `runs/` | рабочие прогоны (не в git) |
| `legacy/` | исходный код до рефакторинга, не собирается |

## C++ (`app/`)

| Файл | Роль |
|---|---|
| `srdet.cc` | `main`: RunManagerFactory (MT/Tasking), не вызывает `Initialize` — это делает макрос |
| `Config.hh/.cc` | `SRDetConfig` (все параметры) и `ConfigMessenger` (`/srdet/geom`, `/srdet/optics`, `/srdet/mat`, `/srdet/out`) |
| `Materials.hh/.cc` | каталог материалов с оптическими таблицами и источниками данных; переопределения из макросов; экспорт `materials.json` |
| `OpticalSurfaces.hh/.cc` | каталог покрытий (металлы n+ik, краски, LUT, плёнки), поверхность сенсора |
| `Sensors.hh/.cc` | каталог фотоприёмников (QE, fill factor, пиксель, шум, цена) |
| `DetectorConstruction.hh/.cc` | геометрия full / cluster7 / unit / slab, решётка сот, поверхности, регион `Detector`, `geometry.json`, GDML |
| `PhysicsList.hh/.cc` | модульный физ-лист: Livermore/option4/Penelope + Decay (+RDM) + Optical; `/srdet/phys/em` |
| `PrimaryGeneratorAction` | GPS (все пучки) или оптическая пушка внутри канала |
| `Actions.hh/.cc` | Stacking (учёт рождения фотонов и флуоресценции), Stepping (депозиты по типам объёмов, процессы, статусы границ, судьба фотонов) |
| `EventAction`, `RunAction` | накопители события; ntuple `events`/`photons`/`cells`, H1/H2 с подписями, `run_summary.json`; траектории первых N событий в `tracks.jsonl` для 3D |

Ключевые решения:

* **Конфигурация только через UI-команды.** Геометрия не захардкожена. Python пишет макрос, и тот
  же макрос можно запустить руками или в интерактивной сессии. В C++ нет парсера YAML и внешних
  зависимостей.
* **Одна логическая сота на все копии.** Ядро и покрытие — единственные физические объёмы внутри
  LV соты, поэтому одна `G4LogicalBorderSurface(Core → Coating)` обслуживает все ~10⁴ каналов.
* **Типы объёмов** (`VKind`) вычисляются по указателю LV. Номер соты берётся из touchable
  (глубина 0 для стенки, 1 для ядра/покрытия) и соответствует индексу в `geometry.json`.
* **Статусы границ** читаются у `G4OpBoundaryProcess` на шагах с `fGeomBoundary` и сводятся
  в 9 классов. Каждый оптический фотон попадает ровно в один исход (это проверяется тестом).
* **Вывод** — `G4AnalysisManager` (ROOT, слияние потоков). Гистограммы уже подписаны (title, оси).
  Диапазоны выставляются из макроса (`/analysis/h1/set`) по энергии пучка и размерам.

## Python (`python/srdet`)

| Модуль | Роль |
|---|---|
| `config.py` | YAML с `extends`, `--set` по точечным путям, величины с единицами |
| `macro.py` | генерация макроса (порядок: геометрия → физика → `/run/initialize` → пороги региона → гистограммы → пучок → `beamOn`) |
| `spectra.py` | линии нуклидов, приближённый спектр трубки, файлы, μ/ρ по XCOM |
| `runner.py` | папка прогона, `meta.json`, бэкап конфига, запуск, проверка, `STATUS` |
| `analysis.py` | загрузка (uproot), метрики, sanity-проверки |
| `plotting.py` | стиль, графики прогона и исследований |
| `studies.py` | развёртка сеток и вариантов, отчёты с автоматическими наблюдениями |
| `optimize.py`, `optimize_plots.py` | поиск оптимума: пространство параметров, LHS/grid, successive halving, уточнение, проверка с повторами, Парето, `best.yaml` |
| `archive.py` | упаковка в `results/` с контролем размера |
| `catalog.py` | зеркало C++ каталогов (синхронность проверяет тест) |
| `cli.py` | команда `srdet` |
| `web/server.py` | FastAPI: каталоги, схема формы, задачи, прогоны, исследования, оптимизации, документы, файлы |
| `web/jobs.py` | очередь задач (`srdet ...` в подпроцессах, по одной), журнал `runs/web_jobs/` |
| `web/schema.py` | схема формы из `configs/defaults.yaml` (тип, единицы, подсказка, варианты из каталогов) |
| `web/static/` | одностраничный UI: `index.html` (Alpine.js), `app.js`, `geometry.js` (SVG-геометрия), `viewer3d.js` (three.js: геометрия + треки), `tour.js` (подсказки по шагам), `style.css`, `themes/` (скины pink / rap) |
| `export.py` | Excel (openpyxl, оформление, графики) и ZIP-пакеты для прогонов, исследований, оптимизаций |
| `labels.py` | русские подписи метрик и порядок важных величин (веб и экспорт) |

## Ntuple `events` (одна строка на событие)

`evt, e0_keV, pdg, x0_mm, y0_mm, first_proc (0 нет, 1 phot, 2 compt, 3 Rayl, 4 conv, 5 other),
first_z_mm, first_kind, first_cell, edep_{total,core,wall,coating,matrix,window,housing,coupling,sensor,slab,world}_keV,
e_escape_keV, n_cells_hit, edep_first_cell_keV, edep_max_cell_keV, n_{phot,compt,rayl,conv,eioni,ebrem,annihil,msc},
n_fluo, n_fluo_escape, n_scint, n_cher, n_cher_primary, op_{fresnel_refl,tir,lambert,spike_lobe,lut_refl,refraction,surf_abs,detection,norindex},
n_det, n_abs_bulk, n_abs_surface, n_norindex, n_escaped, n_lost_other, abs_bulk_{core,wall,coupling,other},
coat_{refl,abs,trans}, n_exit, det_same_cell, det_other_cell, n_op_rayleigh, first_boundary_status`

Коды `first_kind`: 0 world, 1 housing, 2 window, 3 matrix, 4 wall, 5 coating, 6 core,
7 coupling, 8 sensor_window, 9 sensor_active, 10 slab.

## CI (`.github/workflows/ci.yml`)

1. `python`: тесты Python-слоя без Geant4 (секунды).
2. `geant4`: сборка образа (слой Geant4 кэшируется в GitHub Actions cache), физические
   sanity-тесты с малой статистикой, smoke-тест исследования, загрузка отчётов как артефактов.
