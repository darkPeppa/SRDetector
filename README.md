# SRDetector — моделирование микроканального сцинтилляционного детектора (Geant4)

Цилиндрический детектор: гексагональные соты из стекла, в каждой канал со сцинтиллятором
(CsI(Tl) по умолчанию) и отражающим покрытием, свет читается фотоприёмником с торца.
Всё (геометрия, материалы, покрытия, сенсор, физика, пучок) задаётся в YAML или макросах,
запуск идёт из Docker, где Geant4 собирается из исходников.

```bash
docker compose build srdet                          # Geant4 11.3.2 + приложение + Python
docker compose run --rm srdet run full              # один прогон (кастомный режим)
docker compose run --rm srdet study U01_coating     # автоматическое исследование
docker compose run --rm srdet study --list
docker compose run --rm srdet validate --quick      # физические sanity-тесты
```

| Документ | О чём |
|---|---|
| [docs/running.md](docs/running.md) | сборка, режимы запуска, вывод, бэкапы и архивы |
| [docs/physics.md](docs/physics.md) | физ-лист, сцинтилляция, оптика, покрытия, сенсоры, проверки, ошибки legacy |
| [docs/architecture.md](docs/architecture.md) | структура кода, поток данных, формат ntuple |
| [docs/experiments.md](docs/experiments.md) | проведённые эксперименты и выводы |

Структура: `app/` (C++ Geant4) · `python/srdet/` (CLI и анализ) · `configs/` (детектор,
исследования, история конфигов) · `macros/` · `tools/` (сопровождение данных) · `tests/` ·
`results/` (архивы удачных прогонов) · `legacy/` (старый код).
