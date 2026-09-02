# Data

## Source

All earthquake records come from the **United States Geological Survey** FDSN event service:

<https://earthquake.usgs.gov/fdsnws/event/1/query>

The catalogue covers 1 January 1900 to the present with a minimum magnitude of 4.0, which is
roughly 545,000 events worldwide. The USGS catalogue is in the public domain.

The raw and preprocessed files are **not** committed to this repository: the raw download is
about 91 MB and the preprocessed file about 56 MB, and both are reproducible in one command.
Run `code/1_fetch_data.py` followed by `code/2_preprocess_data.py` to regenerate them at
`code/Dataset/`.

## Fields used by the pipeline

| Column | Use |
|---|---|
| `time` | Event origin time; parsed to `Date` and `Day_Number` |
| `latitude`, `longitude` | DBSCAN clustering (haversine metric) |
| `depth` | Reported but not used in the return-period estimation |
| `mag`, `magType` | Magnitude and its scale; normalised to moment magnitude |
| `place` | Free-text location, resolved to a `country` column |

Columns added by `2_preprocess_data.py`: `Date`, `Day_Number`, `country`.

## Bundled sample

`sample/preprocessed_sample_Colombia_Japan.csv` (5.3 MB, 26,470 records) is the preprocessed
catalogue filtered to Colombia and Japan. It is the output of `2_preprocess_data.py`, so the
pipeline can be started at step 3 with no network access. It is used by
[`../docs/TUTORIAL.md`](../docs/TUTORIAL.md) to reproduce the Colombia cluster 3 spectra
(Figures 7 and 8 of the article).

## Reference outputs

`../results/` holds the output files behind the tables and figures of the article, so the
numbers can be checked without re-running the full pipeline.
