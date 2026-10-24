# F1 - full detector: baseline vs optimised variants (60 keV, parallel beam)

Candidate full-detector configurations built from the single-parameter studies, compared on the same beam: detection efficiency, light yield, resolution limit, cross-talk and cost figures.

Base configuration: `full.yaml`; fixed overrides: `{}`

## Results

| variant              |   detection_efficiency |   photopeak_fraction |   det_yield_per_keV |   resolution_fwhm_poisson_limit |   em_crosstalk |   optical_crosstalk |   snr_60keV_per_channel |   det_yield_per_cost |   psf_r50_um |   psf_in_cell_fraction |
|:---------------------|-----------------------:|---------------------:|--------------------:|--------------------------------:|---------------:|--------------------:|------------------------:|---------------------:|-------------:|-----------------------:|
| baseline_Al_L30      |                 0.9155 |               0.905  |            0.1226   |                         1.13    |         0.2175 |           0         |                0.003277 |             0.1226   |        78.94 |                0.7282  |
| legacy_materials_L30 |                 0.9315 |               0.8865 |            0.04296  |                       nan       |         0.2635 |           0         |                0.001148 |             0.04296  |        93.26 |                0.5455  |
| Ag_L30               |                 0.891  |               0.91   |            1.427    |                         0.3043  |         0.1745 |           0         |                0.03814  |             1.427    |        78.49 |                0.7287  |
| ESR_L30              |                 0.9055 |               0.875  |            0.008567 |                       nan       |         0.2154 |           0         |                0.000229 |             0.008567 |       nan    |              nan       |
| Al_L2                |                 0.888  |               0.858  |            3.216    |                         0.1866  |         0.2024 |           0         |                0.08596  |             3.216    |        89.51 |                0.5926  |
| Ag_L2                |                 0.887  |               0.892  |            8.244    |                         0.112   |         0.1738 |           0         |                0.2204   |             8.244    |        97.97 |                0.5378  |
| ESR_L2               |                 0.8875 |               0.8525 |            4.199    |                         0.1558  |         0.2011 |           0         |                0.1122   |             4.199    |        98.06 |                0.526   |
| Ag_L2_pitch220       |                 0.8035 |               0.897  |            8.207    |                         0.1275  |         0.1451 |           0         |                0.2074   |             8.207    |        95.98 |                0.5869  |
| Ag_L2_sCMOS          |                 0.8875 |               0.8975 |           14.45     |                         0.08338 |         0.1753 |           3.115e-05 |               15.4      |             0.4818   |       564.5  |                0.03053 |

![F01_full_comparison](plots/F01_full_comparison.png)

## Automatic observations

- **Events with core deposit**: max 0.9315 at variant = legacy_materials_L30, min 0.8035 at variant = Ag_L2_pitch220 (ratio 1.16)
- **Full-energy fraction**: max 0.91 at variant = Ag_L30, min 0.8525 at variant = ESR_L2 (ratio 1.07)
- **pe/keV**: max 14.45 at variant = Ag_L2_sCMOS, min 0.008567 at variant = ESR_L30 (ratio 1.69e+03)
- **FWHM Poisson limit**: max 1.13 at variant = baseline_Al_L30, min 0.08338 at variant = Ag_L2_sCMOS (ratio 13.5)
- **EM cross-talk**: max 0.2635 at variant = legacy_materials_L30, min 0.1451 at variant = Ag_L2_pitch220 (ratio 1.82)
- **optical_crosstalk**: max 3.115e-05 at variant = Ag_L2_sCMOS, min 0 at variant = baseline_Al_L30
- **SNR 60 keV / channel**: max 15.4 at variant = Ag_L2_sCMOS, min 0.000229 at variant = ESR_L30 (ratio 6.72e+04)
- **pe/keV per cost**: max 8.244 at variant = Ag_L2, min 0.008567 at variant = ESR_L30 (ratio 962)
- **Light spread r50 [um]**: max 564.5 at variant = Ag_L2_sCMOS, min 78.49 at variant = Ag_L30 (ratio 7.19)
- **Light inside own cell**: max 0.7287 at variant = Ag_L30, min 0.03053 at variant = Ag_L2_sCMOS (ratio 23.9)
