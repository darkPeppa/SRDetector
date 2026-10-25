"""Human (Russian) labels of the analysis metrics, shared by the web UI and the exports."""

METRIC_LABELS = {
    "e0_keV": "Энергия пучка, кэВ", "detection_efficiency": "Эффективность регистрации",
    "photopeak_fraction": "Доля фотопика", "k_escape_fraction": "Вероятность K-escape",
    "lce": "Светосбор (с QE)", "lce_exit": "Доля света, вышедшего к сенсору",
    "det_yield_per_keV": "Фотоэлектронов на кэВ", "resolution_fwhm_poisson_limit": "FWHM, пуассоновский предел",
    "em_crosstalk": "ЭМ-кросс-ток", "optical_crosstalk": "Оптический кросс-ток", "psf_r50_um": "Пятно r50, мкм",
    "psf_in_cell_fraction": "Свет в своей соте", "mean_cells_hit": "Сработавших сот",
    "t_det_median_ns": "Медиана времени прихода, нс", "snr_60keV_per_channel": "SNR 60 кэВ / канал",
    "det_yield_per_cost": "pe/кэВ на единицу цены", "wall_time_s": "Время счёта, с",
    "interacting_fraction": "Доля провзаимодействовавших", "mean_n_det": "Детектированных фотонов",
    "mean_edep_core_keV": "Энергия в ядрах, кэВ", "scint_yield_per_keV": "Сцинтилляций на кэВ",
    "psf_r90_um": "Пятно r90, мкм", "relative_cost": "Относительная цена сенсора",
    "mean_edep_wall_keV": "Энергия в стенках, кэВ", "core_energy_fraction": "Доля энергии в ядрах",
    "geometry_fill_factor": "Доля площади сцинтиллятора", "mean_refl_det": "Отражений до детектирования",
    "n_cells": "Число сот", "mean_n_scint": "Рождённых фотонов", "objective": "Цель",
}

# what a metric means and which direction is "better" (max / min / None) - used by the optimisation
# constructor of the web UI and by the spec check (unknown names are reported as possible typos)
METRIC_HELP = {
    "det_yield_per_keV": ("Фотоэлектронов на кэВ, выделенный в сцинтилляторе: световыход × светосбор × QE", "max"),
    "scint_yield_per_keV": ("Рождённых сцинтилляционных фотонов на кэВ (контроль: ≈ каталожный выход)", "max"),
    "detection_efficiency": ("Доля событий, оставивших в сцинтилляторе > 0.5 кэВ (поглощение рентгена)", "max"),
    "interacting_fraction": ("Доля первичных частиц, провзаимодействовавших хоть где-то", "max"),
    "photopeak_fraction": ("Доля событий с полным поглощением энергии пучка (спектрометрия)", "max"),
    "k_escape_fraction": ("Доля фотопоглощений, после которых K-флуоресценция ушла из сцинтиллятора", "min"),
    "lce": ("Светосбор: доля рождённых фотонов, зарегистрированных сенсором (с QE)", "max"),
    "lce_exit": ("Доля рождённых фотонов, вышедших из канала к сенсору (без QE)", "max"),
    "resolution_fwhm_poisson_limit": ("Предел энергетического разрешения FWHM по фотостатистике, 2.355/√N", "min"),
    "em_crosstalk": ("Доля энергии, выделенной вне соты первого взаимодействия", "min"),
    "optical_crosstalk": ("Доля зарегистрированного света, пришедшего из чужих каналов", "min"),
    "psf_r50_um": ("Радиус, внутри которого 50 % света (пятно, пространственное разрешение), мкм", "min"),
    "psf_r90_um": ("Радиус, внутри которого 90 % света, мкм", "min"),
    "psf_in_cell_fraction": ("Доля света, попавшая в свою соту", "max"),
    "mean_cells_hit": ("Среднее число сот с энерговыделением", "min"),
    "t_det_median_ns": ("Медиана времени прихода фотонов (скорость), нс", "min"),
    "snr_60keV_per_channel": ("Сигнал/шум для фотона 60 кэВ в одном канале с учётом шума чтения", "max"),
    "det_yield_per_cost": ("Фотоэлектронов на кэВ на единицу относительной цены сенсора", "max"),
    "relative_cost": ("Относительная цена сенсора на см²", "min"),
    "mean_n_det": ("Детектированных фотонов на событие (в физическом выходе)", "max"),
    "mean_n_scint": ("Рождённых сцинтилляционных фотонов на событие", None),
    "mean_edep_core_keV": ("Средняя энергия в сцинтилляторе, кэВ", None),
    "mean_edep_wall_keV": ("Средняя энергия в стенках, кэВ", "min"),
    "core_energy_fraction": ("Доля выделенной энергии, пришедшаяся на сцинтиллятор", "max"),
    "geometry_fill_factor": ("Доля площади, занятая сцинтиллятором", "max"),
    "mean_refl_det": ("Среднее число отражений у зарегистрированных фотонов", None),
    "n_cells": ("Число сот в детекторе", None),
    "e0_keV": ("Энергия первичной частицы, кэВ", None),
    "wall_time_s": ("Время счёта прогона, с", "min"),
}

# order of the most important metrics in reports and exports
KEY_ORDER = ["e0_keV", "events", "detection_efficiency", "photopeak_fraction", "k_escape_fraction",
             "det_yield_per_keV", "lce", "lce_exit", "resolution_fwhm_poisson_limit", "em_crosstalk",
             "optical_crosstalk", "psf_r50_um", "psf_in_cell_fraction", "mean_cells_hit", "t_det_median_ns",
             "snr_60keV_per_channel", "det_yield_per_cost", "wall_time_s"]
