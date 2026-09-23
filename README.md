# QuakeReturnPeriods

Estimating earthquake return periods from irregularly sampled catalogues with the
**Non-Uniform Fast Fourier Transform (NFFT)** and the **Lomb–Scargle Periodogram (LSP)**.

This repository contains the complete analysis pipeline and the interactive web client for
the article *"Evaluating Earthquake Return Period Reliability Across Seismic Scales Using
NFFT and LSP Algorithms"* (Heednacram, Kliangsuwan and Boonsat), submitted to
*Computers & Geosciences*.

Live web application: **https://quake-return-periods.vercel.app/**

---

## Why this code exists

Earthquake catalogues are irregularly sampled by nature: events do not occur on a uniform
time grid. The classical Fast Fourier Transform assumes uniform spacing, so applying it to a
catalogue requires binning or interpolation, both of which distort the recurrence structure
the analysis is trying to recover. This pipeline instead applies the NFFT directly to the raw
event times, cross-verifies the result with the Lomb–Scargle periodogram, and compares both
against statistical mean / mode / median baselines on a held-out 20% of the catalogue.

The pipeline is fault-line independent: events are grouped spatially with DBSCAN rather than
assigned to mapped faults, so seismicity away from known faults is not discarded.

---

## Requirements

* Python **3.10 or later**
* Any standard x86-64 personal computer. No GPU or specialised hardware is required.
* Packages listed in [`requirements.txt`](requirements.txt):
  `numpy`, `pandas`, `scipy`, `scikit-learn`, `matplotlib`, `astropy`, `nfft`, `requests`.
  The versions there are **exact pins, not minimums**. The Lomb-Scargle power values
  astropy returns shift slightly between major versions, which is enough to change which
  of two close spectral peaks wins: under astropy 8 two of the published cells change.
  astropy 6.1.7 and 7.2.2 both reproduce the article exactly; astropy 8 does not.
* Disk: the full USGS catalogue is roughly 91 MB raw and 56 MB after preprocessing.
* Runtime: a full run over the 28 countries and five magnitude thresholds takes on the order
  of a few hours on a laptop; the tutorial run over two countries takes a few minutes.
* The web client needs only a modern web browser — no build step, no package manager.

## Installation

```bash
git clone https://github.com/thitinan-kl/quake-return-periods.git
cd quake-return-periods
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quick test

A single command checks that the installation works and that the pipeline
reproduces a known result. It runs the real scripts on the bundled sample
(Colombia), takes well under a minute, needs no network access and writes
only inside a temporary folder:

```bash
cd code
python quick_test.py
```

Expected output:

```
1. Checking the required packages
   all present                                              pass

2. Checking that the declustering sorts are stable
   every sort_values uses kind='mergesort'                  pass

3. Running the pipeline on the bundled sample (Colombia only)
   both scripts finished                                    pass

4. Comparing the result with the reference values
   15 output files written               pass

   method       cluster   expected   obtained   verdict
   NFFT               1     11.658     11.658   pass
   NFFT               2      3.882      3.882   pass
   NFFT               3      2.090      2.090   pass
   LSP                1     11.528     11.528   pass
   LSP                2      3.901      3.901   pass
   LSP                3     20.869     20.869   pass
   statistics         1      1.877      1.877   pass
   statistics         2      1.271      1.271   pass
   statistics         3      1.467      1.467   pass
All checks passed. The installation is working.
```

If the installed versions differ from the pins the test still runs and says so; it fails
only if a package is missing, if a sort has lost its `kind='mergesort'`, or if a return
period has moved.

The script exits with status 0 when every check passes and 1 otherwise, so it
can also be run in a continuous-integration job. A difference of a few per cent
in the return periods can come from a different version of numpy, scipy or
astropy; a large difference means something is wrong.

## Quick start

All scripts use paths relative to the working directory, so run them from inside `code/`.

```bash
cd code
python 1_fetch_data.py                 # download the USGS catalogue (1900 - present)
python 2_preprocess_data.py            # clean, normalise place names and magnitudes
python 3_build_clusters_no_noise.py    # DBSCAN clustering + 180-day declustering
python 4_statistics_NFFT_LSP.py        # NFFT, LSP and statistical baselines
```

To try the pipeline without downloading anything, start from the bundled sample instead —
see [`docs/TUTORIAL.md`](docs/TUTORIAL.md).

---

## Repository layout

| Path | Contents |
|---|---|
| `code/1_fetch_data.py` | Downloads the global USGS catalogue year by year from the FDSN event service |
| `code/2_preprocess_data.py` | Cleans records, resolves inconsistent place names to countries, normalises magnitude scales to moment magnitude |
| `code/3_build_clusters_no_noise.py` | DBSCAN clustering per country (haversine, eps = 30 km, minPts = 4) and 180-day aftershock removal |
| `code/4_statistics_NFFT_LSP.py` | NFFT and LSP return-period estimation, statistical baselines, optional 80/20 out-of-sample evaluation |
| `code/countries.txt` | The 28 countries analysed, four per tectonic plate |
| `code/quick_test.py` | Quick test: runs the pipeline on the bundled sample and checks the result |
| `data/sample/` | Small preprocessed sample (Colombia and Japan) so the pipeline can be run without the full download |
| `data/clustering/` | The 28 clustered catalogues behind the published tables — the output of step 3, shipped so step 4 can be reproduced exactly (see below) |
| `results/` | Output files behind the tables and figures of the article |
| `docs/USER_GUIDE.md` | Inputs, outputs, options and expected behaviour of every script |
| `docs/TUTORIAL.md` | Step-by-step walk-through on the bundled sample |
| `web/` | Interactive map client (plain JavaScript + Leaflet) |
| `web/update-from-results.py` | Rewrites the client's numbers from `results/`; run `node web/build-data.js clusters-data.js .` afterwards |

## Key parameters

| Parameter | Value | Where |
|---|---|---|
| Catalogue period | 1 January 1900 to present | `1_fetch_data.py` |
| Minimum magnitude of the raw catalogue | 4.0 | USGS query |
| DBSCAN `eps` | 30 km (haversine) | `3_build_clusters_no_noise.py` |
| DBSCAN `min_samples` | 4 | `3_build_clusters_no_noise.py` |
| Declustering window | 180 days | `3_build_clusters_no_noise.py`, `4_statistics_NFFT_LSP.py` |
| Magnitude thresholds | M4+, M5+, M6+, M7+, M8+ | `4_statistics_NFFT_LSP.py` |
| Train / test split | 80 / 20, chronological per cluster | `4_statistics_NFFT_LSP.py` |
| Clusters kept per country | three largest | `3_build_clusters_no_noise.py` |

## Reproducing the results in the article

`results/` already holds the output of the run reported in the article:

* `NFFT_M{4..8}.csv`, `LSP-M{4..8}.csv` — estimated return periods per country and cluster (Tables 5 and 6)
* `statistics-M{4..8}.csv` — statistical mean / mode / median baselines
* `Table5-NFFT.xlsx`, `Table6-LSP.xlsx`, `Table7-Table8.xlsx` — the collated tables as published
* Out-of-sample errors (Table 9) come from the same script with `use_split = True`

To regenerate them, run the four scripts in order with the parameters above.

**Start from `data/clustering/` if you want the published numbers exactly.** Steps 1 to 3
are reproducible in principle but not bit-for-bit across machines: DBSCAN assigns a border
point that is reachable from two cores according to processing order, so a handful of
events can land in a different cluster on a different operating system. The 28
`clustered_earthquakes_<country>.csv` files in `data/clustering/` are the step-3 output the
article was computed from; copying them to `code/Dataset/clustering/` and running step 4
reproduces every cell of Tables 5 to 9.

Step 4 itself is deterministic: every sort that decides which event is kept as a main shock
uses a stable sort (`kind='mergesort'`), which matters because magnitudes are rounded to two
decimals and a large share of events tie with another event inside the same 180-day window.
`code/quick_test.py` checks this.

## Data

The earthquake catalogue is the public USGS FDSN event service:
<https://earthquake.usgs.gov/fdsnws/event/1/query>. It is **not** redistributed here — the
raw file is roughly 91 MB and is reproducible in one command with `code/1_fetch_data.py`.
See [`data/README.md`](data/README.md) for the fields used and for a description of the
bundled sample.

## Citation

If you use this software, please cite the accompanying article; see [`CITATION.cff`](CITATION.cff).

## License

Released under the [MIT License](LICENSE).

## Contact

Thitinan Kliangsuwan — thitinan.kl@phuket.psu.ac.th
College of Computing, Prince of Songkla University, Phuket 83120, Thailand
