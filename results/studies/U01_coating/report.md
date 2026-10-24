# U1 - light collection vs channel coating (single channel, optical gun)

One hexagonal cell, CsI(Tl) core D = 200 um, L = 30 mm, ideal sensor. Optical photons with the CsI(Tl) spectrum are emitted isotropically and uniformly inside the core, so only the light transport is tested: the coating model, its reflectivity and angular behaviour. For bare / thin-film channels part of the light leaves the core and is guided inside the glass wall to the sensor; `optical_crosstalk` shows that share - in the full detector it ends up in neighbouring pixels (see U07 / U08).

Base configuration: `unit_optical.yaml`; fixed overrides: `{}`

## Results

| optics.coating   |     lce |   lce_exit |   coat_abs_prob |   mean_refl_det |   t_det_median_ns |   optical_crosstalk |
|:-----------------|--------:|-----------:|----------------:|----------------:|------------------:|--------------------:|
| none             | 0.3261  |    0.2846  |         0       |         144.4   |           0.2133  |              0.275  |
| air_gap          | 0.2904  |    0.3539  |         0       |         133.7   |           0.2057  |              0      |
| MgF2_film        | 0.2009  |    0.2343  |         0       |         156.8   |           0.2271  |              0.1013 |
| black            | 0.00098 |    0.00108 |         1       |           2     |           0.015   |              0      |
| ideal            | 0.2899  |    0.3541  |         0       |         133.7   |           0.2058  |              0      |
| Al               | 0.01637 |    0.01748 |         0.1307  |           9.709 |           0.02111 |              0      |
| Al_simple        | 0.01834 |    0.01994 |         0.1017  |           9.272 |           0.01976 |              0      |
| Ag               | 0.0869  |    0.09434 |         0.02102 |          41.91  |           0.08612 |              0      |
| Au               | 0.01621 |    0.0169  |         0.1849  |          11.57  |           0.03031 |              0      |
| TiO2             | 0.00892 |    0.01017 |         0.06057 |          12.01  |           0.015   |              0      |
| BaSO4            | 0.01509 |    0.01752 |         0.0262  |          24.1   |           0.01882 |              0      |
| Teflon           | 0.0164  |    0.01906 |         0.02081 |          28.77  |           0.02166 |              0      |
| ESR_LUT          | 0.01297 |    0.01576 |         0       |           5.738 |           0.015   |              0      |
| Teflon_LUT       | 0.01284 |    0.01574 |         0       |           5.76  |           0.015   |              0      |
| ESR_LUT_BGO      | 0.229   |    0.2534  |         0       |         107     |           0.1477  |              0      |
| Tyvek_LUT        | 0.2282  |    0.2463  |         0       |          95.99  |           0.1377  |              0      |
| TiO2_LUT         | 0.1608  |    0.1832  |         0       |         283.1   |           0.2364  |              0      |

![U01_coating](plots/U01_coating.png)

## Automatic observations

- **Light collection efficiency (ideal sensor)**: max 0.3261 at optics.coating = none, min 0.00098 at optics.coating = black (ratio 333)
- **Fraction leaving the channel to the sensor**: max 0.3541 at optics.coating = ideal, min 0.00108 at optics.coating = black (ratio 328)
- **coat_abs_prob**: max 1 at optics.coating = black, min 0 at optics.coating = none
- **Mean reflections of detected photons**: max 283.1 at optics.coating = TiO2_LUT, min 2 at optics.coating = black (ratio 142)
- **Median arrival time [ns]**: max 0.2364 at optics.coating = TiO2_LUT, min 0.015 at optics.coating = black (ratio 15.8)
- **optical_crosstalk**: max 0.275 at optics.coating = none, min 0 at optics.coating = air_gap
