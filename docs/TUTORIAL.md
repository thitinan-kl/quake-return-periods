# Tutorial — a first run on the bundled sample

This walk-through reproduces one concrete result from the article without downloading the
full catalogue: the **NFFT and LSP spectra for Colombia, cluster 3, at M4+** — Figures 7 and 8
of the paper.

It takes a few minutes on a laptop.

## 0. Install

```bash
git clone https://github.com/thitinan-kl/quake-return-periods.git
cd quake-return-periods
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 1. Put the sample where the pipeline expects it

The sample is the preprocessed catalogue filtered to two countries, Colombia and Japan
(26,470 records). It is the output that step 2 would produce, so we can start at step 3.

```bash
cd code
mkdir -p Dataset
cp ../data/sample/preprocessed_sample_Colombia_Japan.csv Dataset/Preprocessed_earthquake_data.csv
```

## 2. Narrow the country list

```bash
printf 'Colombia\nJapan\n' > countries_sample.txt
cp countries.txt countries_full.txt      # keep the original
cp countries_sample.txt countries.txt
```

## 3. Cluster and decluster

```bash
python 3_build_clusters_no_noise.py
```

Expected output — one block per country, ending with something like:

```
[1/2] Processing: Colombia
  Clusters found: <n> (noise points removed)
  Saved to Dataset/clustering/clustered_earthquakes_Colombia.csv
```

The script removes aftershocks within 180 days, then runs DBSCAN with `eps = 30 km` and
`minPts = 4` on the haversine metric.

## 4. Estimate the return periods

```bash
python 4_statistics_NFFT_LSP.py
```

With the default `use_split = False` this writes, for each magnitude threshold M4+ … M8+:

```
result/NFFT_M4.csv          NFFT peak frequency and return period per cluster
result/LSP-M4.csv           the same from the Lomb-Scargle periodogram
result/statistics-M4.csv    mean / mode / median inter-event gaps
graphs/Colombia_cluster_3.png
```

## 5. Check the result

Open `result/NFFT_M4.csv` and find the row for Colombia, cluster 3. The return period should
be close to the value reported in Table 5 of the article. `graphs/Colombia_cluster_3.png` is
the spectrum shown as Figure 7; the LSP counterpart is Figure 8.

Small differences from the published numbers are expected if the USGS catalogue has been
revised since the run reported in the article — the reference outputs are kept in
`results/` for comparison.

## 6. Run the out-of-sample evaluation

To reproduce the error metrics of Table 9, edit `4_statistics_NFFT_LSP.py`:

```python
use_split = True    # around line 1186
```

and run it again. Each cluster is now split 80/20 chronologically, and the errors against the
held-out 20% are written to `result/NFFT_validate_M<m>.csv` and
`result/statistics_validate_M<m>.csv`.

## 7. Restore the full country list

```bash
cp countries_full.txt countries.txt
```

Then follow [`USER_GUIDE.md`](USER_GUIDE.md) to run the complete pipeline from step 1.
