# U2 - light collection vs specular reflectivity R

Ideal specular mirror with constant R. Every photon needs about N reflections to leave the channel, so LCE should follow LCE(1)·R^N; the overlay uses the measured mean N at R = 1. Validates the reflection bookkeeping and shows how fast the light loss grows with 1 - R.

Base configuration: `unit_optical.yaml`; fixed overrides: `{'optics.coating': 'mirror', 'run.photon_fraction': 1.0}`

## Results

|   optics.coating_reflectivity |     lce |   coat_abs_prob |   mean_refl_det |
|------------------------------:|--------:|----------------:|----------------:|
|                         0.8   | 0.00953 |         0.1999  |           5.219 |
|                         0.85  | 0.01228 |         0.1503  |           6.394 |
|                         0.9   | 0.01905 |         0.09965 |           9.448 |
|                         0.93  | 0.02657 |         0.06993 |          13.44  |
|                         0.95  | 0.037   |         0.04975 |          17.68  |
|                         0.97  | 0.05647 |         0.02992 |          27.72  |
|                         0.98  | 0.07812 |         0.02    |          37.96  |
|                         0.99  | 0.1246  |         0.01005 |          57.75  |
|                         0.995 | 0.176   |         0.00499 |          80.91  |
|                         1     | 0.2899  |         0       |         133.7   |

![U02_reflectivity](plots/U02_reflectivity.png)

## Automatic observations

- **Light collection efficiency**: max 0.2899 at optics.coating_reflectivity = 1.0, min 0.00953 at optics.coating_reflectivity = 0.8 (ratio 30.4)
  - lce increases with optics.coating_reflectivity (Pearson r = 0.69)
- **coat_abs_prob**: max 0.1999 at optics.coating_reflectivity = 0.8, min 0 at optics.coating_reflectivity = 1.0
  - coat_abs_prob decreases with optics.coating_reflectivity (Pearson r = -1.00)
- **Mean reflections (detected)**: max 133.7 at optics.coating_reflectivity = 1.0, min 5.219 at optics.coating_reflectivity = 0.8 (ratio 25.6)
  - mean_refl_det increases with optics.coating_reflectivity (Pearson r = 0.69)
