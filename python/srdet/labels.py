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
}

# order of the most important metrics in reports and exports
KEY_ORDER = ["e0_keV", "events", "detection_efficiency", "photopeak_fraction", "k_escape_fraction",
             "det_yield_per_keV", "lce", "lce_exit", "resolution_fwhm_poisson_limit", "em_crosstalk",
             "optical_crosstalk", "psf_r50_um", "psf_in_cell_fraction", "mean_cells_hit", "t_det_median_ns",
             "snr_60keV_per_channel", "det_yield_per_cost", "wall_time_s"]
