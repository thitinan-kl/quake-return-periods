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

## Clustered catalogues (`clustering/`)

`clustering/clustered_earthquakes_<country>.csv` — 28 files, about 31 MB in total — is the
output of `code/3_build_clusters_no_noise.py` for the run reported in the article: the
declustered catalogue of each country with a `cluster` label from DBSCAN.

These are committed on purpose. Steps 1 to 3 are reproducible in principle but not
bit-for-bit across machines, because DBSCAN assigns a border point reachable from two cores
according to processing order, so a few events can land in a different cluster under a
different operating system or library version. Copy this folder to `code/Dataset/clustering/`
and run step 4 to reproduce every cell of Tables 5 to 9 exactly.

Columns are those of the preprocessed catalogue (`time`, `latitude`, `longitude`, `depth`,
`mag`, `magType`, `place`, `Date`, `Day_Number`, `country`) plus `cluster`.

## Reference outputs

`../results/` holds the output files behind the tables and figures of the article, so the
numbers can be checked without re-running the full pipeline.
