# Запуск SRDetector

## 1. Сборка образа (один раз)

```bash
docker compose build srdet
```

Geant4 11.3.2 собирается из исходников внутри образа (многопоточный режим, GDML, offscreen-визуализация)
и скачивает только нужные датасеты: G4EMLOW, ENSDFSTATE, REALSURFACE, PhotonEvaporation,
RadioactiveDecay, PARTICLEXS, SAIDDATA. Первая сборка занимает ~15 минут на компиляцию плюс
время на скачивание ~650 МБ данных с CERN. Дальше слой кэшируется, и пересобирается только
приложение (~1 минута).

Другая версия Geant4: `docker compose build --build-arg GEANT4_VERSION=11.4.2 srdet`.

Компиляция и датасеты лежат в разных слоях. Скачанные архивы хранятся в кэше BuildKit, так что
повторная или упавшая сборка их не перекачивает. Версии и MD5 берутся из
`G4DatasetDefinitions.cmake` собранного Geant4 (`docker/fetch_datasets.py`). При медленном канале
датасеты можно заранее положить в `docker/g4data/` (распакованные папки `G4EMLOW8.6.1/` и т. п. или
исходные архивы) и собрать так:

```bash
docker build -f docker/Dockerfile --target srdet --build-context g4data=docker/g4data -t srdet:latest .
```

Образ с ROOT (TBrowser, PyROOT) собирается отдельно и нужен только для интерактивного просмотра:

```bash
docker compose --profile root build root
```

## 2. Веб-интерфейс

```bash
docker compose up web        # http://localhost:8080   (порт меняется: SRDET_WEB_PORT=9000)
```

В браузере доступно всё то же, что в CLI: форма конфигурации с предпросмотром геометрии, запуск
прогонов, исследований и оптимизаций, графики и метрики, 3D-картинки Geant4, ROOT-браузер,
сравнение прогонов и документация. Подробнее: [web.md](web.md).

## 3. Режимы запуска (CLI)

Все команды выполняются в контейнере, репозиторий примонтирован как `/work`:

```bash
docker compose run --rm srdet <команда>
```

Ниже для краткости префикс `docker compose run --rm srdet` опущен. Внутри контейнера
(`docker compose run --rm srdet bash`) команды те же, только без префикса.

### Кастомный режим: один прогон

```bash
srdet run full                                    # configs/detector/full.yaml
srdet run unit_optical --set optics.coating=Ag --set geometry.length="5 mm" --events 500
srdet run my_config.yaml --archive                # при успехе упаковать в results/
srdet macro full                                  # только показать сгенерированный макрос
```

Любой параметр меняется через `--set ключ=значение` или через собственный YAML с
`extends: full.yaml`. Список всех ключей с комментариями — `configs/defaults.yaml`.

### Автоматический режим: исследования (эксперименты по оптимизации)

```bash
srdet study --list                  # все исследования из configs/studies/
srdet study U01_coating             # одно исследование
srdet study U02 --quick             # малая статистика (smoke test)
srdet study all --archive           # все исследования, удачные — в results/
```

Каждое исследование — это YAML с базовой конфигурацией, сеткой значений (`scan`, режимы
`product`/`zip`) или списком вариантов (`variants`), метриками и подписями. Результат:
`runs/studies/<дата>_<имя>/` с `results.csv`, `report.md` и `plots/`.

| ID | Что изолируется |
|---|---|
| U01 | тип покрытия (оптическая пушка, один канал) |
| U02 | коэффициент отражения R, сравнение с `R^N` |
| U03 | глубина эмиссии (неоднородность светосбора) |
| U04 / U04b | длина канала / диаметр канала |
| U05 | шероховатость покрытия |
| U06 / U06b | оптическая связка / тип фотоприёмника (сигнал, шум, цена) |
| U07 | толщина стенки (кластер из 7 сот, кросс-ток) |
| U08 | материал стенок |
| U09 | сцинтиллятор в каналах |
| U10 | зависимость процессов от энергии (полный детектор, только EM) |
| B01 / B02 | типы пучков / радиоактивные источники и спектр трубки |
| F01 | полный детектор: базовый вариант против оптимизированных |

### Поиск оптимальных параметров

```bash
srdet optimize --list
srdet optimize O01_geometry_60keV --archive
srdet optimize O02 --quick
```

Несколько параметров меняются одновременно, кандидаты сравниваются по целевой функции с
ограничениями, результат — `best.yaml` и отчёт. Подробнее: [optimization.md](optimization.md).

### Анализ, сравнение, архив

```bash
srdet analyze runs/<run>            # пересчитать metrics.json и графики
srdet analyze runs/studies/<study>  # пересобрать report.md
srdet compare runs/A runs/B         # таблица метрик
srdet archive runs/<run>            # results/<run>.tar.xz (≤ 45 МБ, проверка размера)
srdet list                          # последние прогоны и их статус
srdet catalog coatings              # что можно выбрать (materials | coatings | sensors)
```

### Визуализация и интерактив

```bash
srdet vis cluster7_xray --events 5    # PNG (TSG offscreen) + .wrl (VRML) в папке прогона
srdet shell                           # терминальная сессия Geant4 (macros/vis/interactive.mac)
srdet jsroot runs/<run>/srdet.root    # просмотр ROOT-файла в браузере (http://localhost:8090)
docker compose --profile root run --rm --service-ports root root -l runs/<run>/srdet.root
docker compose --profile lab up jupyter   # JupyterLab на :8888
```

Для `srdet jsroot` из контейнера пробросьте порт:
`docker compose run --rm -p 8090:8090 srdet jsroot runs/<run>/srdet.root`.

### Тесты

```bash
srdet validate --quick                # физические sanity-тесты, ~10 мин
pytest -q tests/test_python.py        # только Python-слой, без Geant4 (работает и на хосте)
```

## 4. Что лежит в папке прогона

```
runs/20261024-153000_full/
  config.yaml        полностью развёрнутая конфигурация
  run.mac            сгенерированный макрос (можно запустить вручную: srdet-sim run.mac)
  meta.json          git commit, версия Geant4, хост, время, ссылка на бэкап конфига
  srdet.root         гистограммы + ntuple events / photons / cells
  geometry.json      ячейки (q, r, x, y), производные размеры, QE сенсора
  materials.json     оптические таблицы, реально использованные в прогоне
  run_summary.json   быстрые итоги от Geant4
  metrics.json       метрики анализа (LCE, LY, кросс-ток, доли процессов, ...)
  plots/*.png        подписанные гистограммы
  log.txt            полный вывод Geant4
  STATUS             ok | failed: <причина>
```

Прогон считается удачным (`STATUS = ok`), если Geant4 завершился без фатальных исключений и
перекрытий, все файлы на месте, а sanity-проверки анализа прошли: сохранение энергии, LCE ≤ 1,
световыход близок к каталожному.

Каждая новая конфигурация одиночного прогона сохраняется один раз в
`configs/history/<дата>_<hash>_<имя>.yaml`, ссылка на бэкап записывается в `meta.json`. Для
исследования сохраняется одна запись `study_<имя>` с базовой конфигурацией и описанием сетки.
Конфиги отдельных точек лежат в их папках. Тесты бэкапов не создают (`SRDET_NO_HISTORY=1`).

## 5. Архивы для GitHub

`srdet archive` (или флаг `--archive`) кладёт в `results/<имя>.tar.xz`:
* конфиги, макросы, json, графики, таблицы, хвост лога;
* `histograms.root` — только гистограммы;
* `events.parquet` — ntuple событий в сжатом виде, если укладывается в бюджет.

Ntuple `photons`/`cells` отбрасываются. Архив больше 45 МБ не создаётся: GitHub отклоняет файлы
больше 100 МБ и предупреждает уже с 50 МБ. Для крупных данных используйте Git LFS. Индекс архивов
лежит в `results/INDEX.json`. `tools/collect_reports.py` собирает последние отчёты исследований в
`results/studies/`.

## 6. Без Docker

Понадобятся Geant4 ≥ 11.1 (MT, GDML), Python ≥ 3.10.

```bash
cmake -S . -B build && cmake --build build -j
pip install -r python/requirements.txt && pip install -e python
export SRDET_BIN=$PWD/build/srdet-sim
srdet run unit_optical
```

## 7. Переменные окружения

| Переменная | Назначение |
|---|---|
| `SRDET_THREADS` | число потоков (по умолчанию все ядра) |
| `SRDET_BIN` | путь к `srdet-sim` |
| `SRDET_RUNS` | куда писать прогоны (по умолчанию `runs/`) |
| `SRDET_QUICK=1` | тесты с уменьшенной статистикой |
