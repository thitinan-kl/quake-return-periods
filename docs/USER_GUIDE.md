# User guide

Inputs, outputs, options and expected behaviour of every script in `code/`.

All scripts resolve paths **relative to the current working directory**, so run them from
inside `code/`. Each script creates the folders it needs.

---

## 1. `1_fetch_data.py` — download the catalogue

| | |
|---|---|
| **Input** | None. Queries the USGS FDSN event service over the network. |
| **Output** | `Dataset/earthquake_global_data_combined.csv` (~91 MB) |
| **Options** | `start_year` (default 1900), `end_year` (default current year), `max_retries` (3), `retry_delay` (5 s), and the query parameters `minmagnitude` and `orderby` |
| **Behaviour** | Requests one calendar year at a time, retries a failed year up to three times with a delay, and concatenates the yearly CSV responses. Prints one line per year. A year that fails after all retries is skipped with a warning rather than aborting the run. |
| **Runtime** | 10–30 minutes, dominated by the network. |

Re-running overwrites the output file.

---

## 2. `2_preprocess_data.py` — clean and normalise

| | |
|---|---|
| **Input** | `Dataset/earthquake_global_data_combined.csv` |
| **Output** | `Dataset/Preprocessed_earthquake_data.csv` (~56 MB) |
| **Options** | The `us_states` mapping and the place-name rules inside the script |
| **Behaviour** | Parses `time` to datetime and derives `Date` and `Day_Number`; derives a `country` column from the free-text `place` field; converts latitude/longitude to Cartesian coordinates; sorts chronologically; normalises magnitude scales to moment magnitude. |

**Place-name normalisation matters.** The raw `place` field mixes regions, seas and US state
names, so a naive country match loses thousands of records. All fifty US state names and
entries such as `"Alaska Peninsula"` or `"Gulf of Alaska"` are mapped to `USA`; `"Banda Sea"`,
`"Flores Sea"` and similar are mapped to `Indonesia`. Ambiguous entries such as
`"Indian Ocean"` are excluded so that they are not misread as `India`.

**Magnitude normalisation.** Records reported on other scales are converted to moment
magnitude (Mw): Ms and mb with the relations of Scordilis (2006) and Ornthammarath et al.
(2011), ML with Li and Gao (2017), and duration magnitude with Sharon et al. (2022). A small
number of records carry uncommon magnitude units and are left unchanged.

---

## 3. `3_build_clusters_no_noise.py` — cluster and decluster

| | |
|---|---|
| **Input** | `Dataset/Preprocessed_earthquake_data.csv` and `countries.txt` |
| **Output** | `Dataset/clustering/clustered_earthquakes_<country>.csv`, one file per country |
| **Options** | `eps_km` (30), `min_samples` (4), `AFTERSHOCK_DAYS` (180), and the country list in `countries.txt` |
| **Behaviour** | For each country: removes aftershocks within the declustering window using a Gardner–Knopoff style distance criterion, then runs DBSCAN on the coordinates with the haversine metric. Points labelled `-1` (noise) are dropped. Countries with fewer than `min_samples` records are skipped with a warning. Prints the number of clusters and the elapsed time per country. |
| **Runtime** | A few minutes for the 28 countries. |

`countries.txt` holds one country per line, grouped in blocks of four by tectonic plate; blank
lines separate the plates and are ignored. Edit this file to analyse a different set.

---

## 4. `4_statistics_NFFT_LSP.py` — estimate return periods

| | |
|---|---|
| **Input** | `Dataset/clustering/clustered_earthquakes_<country>.csv` and `countries.txt` |
| **Output** | see the table below |
| **Options** | `use_split` (line ~1186), the magnitude range `range(4, 9)` (line ~1200), `AFTERSHOCK_DAYS` (180) |
| **Runtime** | Hours for a full run over 28 countries and five thresholds. |

### The `use_split` switch

* `use_split = False` (default) — uses the whole catalogue and reports return periods only.
  This is the setting behind Tables 5, 6 and 7 of the article.
* `use_split = True` — splits every cluster chronologically 80/20, fits on the first 80% and
  measures the error against the held-out 20%. This is the setting behind Table 9. It also
  writes the split data to `train/` and `test/` for inspection.

### Outputs

| File | Contents |
|---|---|
| `result/NFFT_M<m>.csv` | NFFT peak frequency and estimated return period per country and cluster |
| `result/LSP-M<m>.csv` | The same from the Lomb–Scargle periodogram |
| `result/statistics-M<m>.csv` | Inter-event gap statistics: mean, mode and median |
| `result/NFFT_validate_M<m>.csv`, `result/NFFT_vasummary_M<m>.csv` | Out-of-sample errors, only when `use_split = True` |
| `result/statistics_validate_M<m>.csv` | Baseline out-of-sample errors, only when `use_split = True` |
| `graphs/<country>_cluster_<id>.png` | Spectrum plots at 300 dpi |

`<m>` runs over the magnitude thresholds 4 to 8.

### Expected behaviour and known limits

* A cluster with fewer than five records after magnitude filtering is skipped and reported as
  such. This is why the M7+ and M8+ tables are sparser than M4+.
* The NFFT returns no estimate when the record is too short for a dominant peak to be
  resolved; the cell is left blank. The LSP resolves several of those clusters, which is the
  complementarity reported in the article.
* Return periods are computed as the reciprocal of the dominant frequency, converted from
  days to years.
* The estimate assumes the dominant cycle is stationary over the catalogue period.

---

## Web client (`web/`)

Static files, no build step. Open `index.html` in a browser, or serve the folder:

```bash
cd web && python -m http.server 8000     # then open http://localhost:8000
```

`data.js` and `clusters-data.js` hold the precomputed return periods that the map displays.
`build-data.js` regenerates them from the CSV files in `results/`.
