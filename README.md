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
  `numpy`, `pandas`, `scipy`, `scikit-learn`, `matplotlib`, `astropy`, `nfft`, `requests`
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
| `data/sample/` | Small preprocessed sample (Colombia and Japan) so the pipeline can be run without the full download |
| `results/` | Output files behind the tables and figures of the article |
| `docs/USER_GUIDE.md` | Inputs, outputs, options and expected behaviour of every script |
| `docs/TUTORIAL.md` | Step-by-step walk-through on the bundled sample |
| `web/` | Interactive map client (plain JavaScript + Leaflet) |

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

To regenerate them, run the four scripts in order with the parameters above. Results are
deterministic apart from the ordering of ties in DBSCAN, which does not affect the reported
return periods.

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
