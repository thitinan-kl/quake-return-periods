"""
quick_test.py - quick test for QuakeReturnPeriods.

Run this straight after `pip install -r requirements.txt` to confirm that the
installation works and that the pipeline reproduces a known result. It takes
about a minute, needs no network access, and writes only inside a temporary
folder that is deleted afterwards - the repository is left untouched.

What it does:

  1. Checks that every required package imports, and reports the version of
     each against the pinned set in requirements.txt.
  2. Runs the real pipeline - 3_build_clusters_no_noise.py and
     4_statistics_NFFT_LSP.py, unmodified - on the bundled sample catalogue
     (Colombia and Japan, `data/sample/`), restricted to Colombia.
  3. Compares the return periods it produces at M4+ against the reference
     values below.

Usage:
    cd code
    python quick_test.py

Expected output: three clusters, a table of return periods, and the line
"All checks passed." The exit status is 0 on success and 1 on failure, so the
script can also be used in a continuous-integration job.

Determinism note
----------------
Every sort in steps 3 and 4 that decides which event is kept as a main shock
uses kind="mergesort" (a stable sort). This matters because convert_magnitude
rounds to two decimals, so a large share of events share a magnitude with
another event in the same 180-day declustering window - on the full catalogue
more than 80 per cent of them. With the default quicksort the winner of such a
tie depends on the platform and the library version, and the retained main
shocks drift by a few events between machines. With the stable sort the
pipeline produces byte-identical output across library versions; the reference
values below were confirmed on two independent stacks
(pandas 2.3.3 / scikit-learn 1.7.2 / astropy 7.2.2 and
 pandas 3.0.2 / scikit-learn 1.8.0 / astropy 8.0.1).

To go further, docs/TUTORIAL.md walks through the same sample step by step and
reproduces Figures 7 and 8 of the article; docs/USER_GUIDE.md documents the
inputs, outputs and options of every script.
"""

import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "data", "sample",
                      "preprocessed_sample_Colombia_Japan.csv")
STEP3 = os.path.join(HERE, "3_build_clusters_no_noise.py")
STEP4 = os.path.join(HERE, "4_statistics_NFFT_LSP.py")

COUNTRY = "Colombia"
TOLERANCE = 0.02          # 2 per cent; the pipeline is deterministic, so this
                          # only absorbs floating-point noise

# Versions the published results were produced with. A mismatch is reported but
# does not fail the test - the stable sorts make the pipeline reproducible
# across these versions.
PINNED = {
    "numpy": "2.3.3",
    "pandas": "2.3.3",
    "scipy": "1.16.3",
    "sklearn": "1.7.2",
    "matplotlib": "3.10.7",
    "astropy": "7.2.2",
}

# Reference return periods in years for the bundled sample at M4+.
# "" means the method reports no estimate for that cluster.
# Regenerate these numbers whenever the estimator in step 4 changes.
REFERENCE = {
    "NFFT_M4.csv":       {"1": 11.658, "2": 3.882, "3": 2.090},
    "LSP-M4.csv":        {"1": 11.528, "2": 3.901, "3": 20.869},
    "statistics-M4.csv": {"1": 1.877, "2": 1.271, "3": 1.467},
}
VALUE_COLUMN = {
    "NFFT_M4.csv": "return_P_nomes",
    "LSP-M4.csv": "return_p_years",
    "statistics-M4.csv": "return_P",
}
CLUSTER_COLUMN = {
    "NFFT_M4.csv": "cluster",
    "LSP-M4.csv": "cluster",
    "statistics-M4.csv": "cluster_id",
}
EXPECTED_FILES = [f"{stem}{m}.csv"
                  for stem in ("NFFT_M", "LSP-M", "statistics-M")
                  for m in range(4, 9)]


def check_imports():
    print("1. Checking the required packages")
    missing, drift = [], []
    for name in ("numpy", "pandas", "scipy", "sklearn", "matplotlib",
                 "astropy", "nfft"):
        try:
            module = __import__(name)
        except ImportError:
            missing.append(name)
            continue
        found = getattr(module, "__version__", "?")
        want = PINNED.get(name)
        if want and found != want:
            drift.append(f"{name} {found} (pinned {want})")
    if missing:
        print("   missing: " + ", ".join(missing))
        print("   install them with: pip install -r requirements.txt   FAIL")
        return False
    print("   all present                                              pass")
    if drift:
        print("   note: " + "; ".join(drift))
        print("   the stable sorts make this safe, but pinned versions are")
        print("   what the published tables were produced with")
    return True


def check_stable_sorts():
    """Every sort that picks a main shock must be stable, or results drift."""
    print("\n2. Checking that the declustering sorts are stable")
    ok = True
    for path in (STEP3, STEP4):
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            print(f"   cannot read {os.path.basename(path)}                    FAIL")
            return False
        bare = []
        for match in re.finditer(r"sort_values\s*\(", text):
            i = text.index("(", match.start())
            depth = 0
            for j in range(i, len(text)):
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
            call = text[match.start():j + 1]
            if "mergesort" not in call:
                bare.append(" ".join(call.split())[:72])
        if bare:
            ok = False
            print(f"   {os.path.basename(path)}: {len(bare)} sort(s) without "
                  f"kind='mergesort'                FAIL")
            for line in bare[:3]:
                print(f"      {line}")
    if ok:
        print("   every sort_values uses kind='mergesort'                  pass")
    return ok


def run_pipeline(workdir):
    print(f"\n3. Running the pipeline on the bundled sample ({COUNTRY} only)")
    if not os.path.exists(SAMPLE):
        print(f"   sample not found at {SAMPLE}                        FAIL")
        return False

    os.makedirs(os.path.join(workdir, "Dataset"), exist_ok=True)
    shutil.copy(SAMPLE, os.path.join(workdir, "Dataset",
                                     "Preprocessed_earthquake_data.csv"))
    with open(os.path.join(workdir, "countries.txt"), "w") as handle:
        handle.write(COUNTRY + "\n")

    env = dict(os.environ, MPLBACKEND="Agg")
    for step, script in (("3 - clustering and declustering", STEP3),
                         ("4 - NFFT, LSP and statistical baselines", STEP4)):
        print(f"   step {step} ...")
        done = subprocess.run([sys.executable, script], cwd=workdir, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True)
        if done.returncode != 0:
            print("   the script stopped with an error:                 FAIL")
            print("   " + "\n   ".join(done.stdout.strip().splitlines()[-12:]))
            return False
    print("   both scripts finished                                    pass")
    return True


def read_values(path, cluster_column, value_column):
    values = {}
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            cluster = str(row[cluster_column]).strip()
            raw = row[value_column].strip()
            values[cluster] = float(raw) if raw not in ("", "nan") else ""
    return values


def check_results(workdir):
    print("\n4. Comparing the result with the reference values")
    result_dir = os.path.join(workdir, "result")

    absent = [name for name in EXPECTED_FILES
              if not os.path.exists(os.path.join(result_dir, name))]
    if absent:
        print(f"   missing output files: {', '.join(absent)}           FAIL")
        return False
    print(f"   {len(EXPECTED_FILES)} output files written               pass")

    print(f"\n   {'method':<12}{'cluster':>8}{'expected':>11}{'obtained':>11}   verdict")
    ok = True
    for name, expected in REFERENCE.items():
        produced = read_values(os.path.join(result_dir, name),
                               CLUSTER_COLUMN[name], VALUE_COLUMN[name])
        label = name.split("_M")[0].split("-M")[0]
        for cluster, want in expected.items():
            got = produced.get(cluster, "missing")
            if want == "":
                good = got in ("", "missing")
                shown_want, shown_got = "none", ("none" if good else f"{got}")
            elif isinstance(got, float):
                good = abs(got - want) <= TOLERANCE * want
                shown_want, shown_got = f"{want:.3f}", f"{got:.3f}"
            else:
                good = False
                shown_want, shown_got = f"{want:.3f}", str(got)
            ok = ok and good
            print(f"   {label:<12}{cluster:>8}{shown_want:>11}{shown_got:>11}"
                  f"   {'pass' if good else 'FAIL'}")
    if not ok:
        print("\n   A difference here means the estimator or the declustering "
              "has changed.\n   Check that the stable sorts are in place and "
              "that the installed\n   versions match requirements.txt.")
    return ok


def main():
    print("QuakeReturnPeriods - quick test\n" + "-" * 56)
    if not check_imports():
        print("-" * 56)
        print("Install the dependencies first: pip install -r requirements.txt")
        return 1
    if not check_stable_sorts():
        print("-" * 56)
        print("The declustering sorts are not stable; results will not be "
              "reproducible.")
        return 1

    workdir = tempfile.mkdtemp(prefix="quake_quick_test_")
    try:
        ok = run_pipeline(workdir) and check_results(workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print("-" * 56)
    if ok:
        print("All checks passed. The installation is working.")
        return 0
    print("At least one check failed. See the output above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
