# Reference outputs

These are the files produced by the run reported in the article, kept so that the published
numbers can be checked without re-running the whole pipeline. All of them come from
`code/4_statistics_NFFT_LSP.py`; `<m>` runs over the magnitude thresholds 4 to 8.

## Which file backs which table

| Article | File | Notes |
|---|---|---|
| **Table 5** — NFFT return periods per country and cluster | `NFFT_M<m>.csv`, collated in `Table5-NFFT.xlsx` | Column `return_P_nomes` is the estimated return period in years |
| **Table 6** — LSP return periods per country and cluster | `LSP-M<m>.csv`, collated in `Table6-LSP.xlsx` | Column `return_p_years` |
| **Table 7** — average return period per tectonic plate | `Table7-Table8.xlsx`, sheet `Table 7` | Averages of the per-cluster values across the countries on each plate |
| **Table 8** — alignment of the proposed methods with the statistical measures | `Table7-Table8.xlsx`, sheet `Table 8` | |
| **Table 9** — out-of-sample evaluation (80/20, three metrics) | not stored here | Re-run with `use_split = True`; see `docs/USER_GUIDE.md` |
| statistical mean / mode / median baselines | `statistics-M<m>.csv` | Columns `mean_gap`, `exact_mode`, `median_gap`, converted to years in `return_P` |
| **Figures 7 and 8** — example NFFT and LSP spectra | not stored here | Written to `graphs/` at run time; `docs/TUTORIAL.md` reproduces the Colombia cluster 3 pair |
| **Figures 9 and 10** | derived from the CSV files above | Estimated return period by method and threshold, and the average difference between the proposed estimators and the statistical measures |

The `.xlsx` files keep live formulas (`VLOOKUP`, `AVERAGE`) that pull from the per-threshold
sheets, so the collated tables recompute if the underlying sheets are replaced.

## Column reference

**`NFFT_M<m>.csv`** — `country`, `cluster`, `return_P_nomes` (years), `avg_gap` (days),
`Number of record`, `Number of the day`, `percent`, `highest_amplitude`, `highest_frequency`,
`highest_years_not_normalised`

**`LSP-M<m>.csv`** — `country`, `cluster`, `return_p_years`, `best_frequency`, `best_power`,
`num_records`, `Number of the day`, `time_span_days`

**`statistics-M<m>.csv`** — `country`, `cluster_id`, `return_P` (years), `total_earthquakes`,
`total_gaps`, `exact_mode`, `min_gap`, `max_gap`, `mean_gap`, `median_gap`, `std_gap`
(gap columns are in days)

An empty cell means the algorithm found no dominant spectral peak for that cluster and
magnitude threshold. This is why the M7+ and M8+ tables are sparser than M4+, and why the
NFFT has no M8+ row at all while the LSP does.

## Reproducing

The catalogue is fetched live from the USGS, so a rerun today may differ slightly from these
files if the catalogue has been revised since. See the repository `README.md` for the
parameter values used.
