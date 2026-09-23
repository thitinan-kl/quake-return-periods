#!/usr/bin/env python3
"""
update-from-results.py — refresh the web client's numbers from the pipeline output.

Reads the authoritative result files and rewrites the two data files the site is
built from:

    Results_v2/NFFT_M4..M8.csv   -> data.js         DATA.countries[].nfft   (Table 5)
    Results_v2/LSP-M4..M8.csv    -> data.js         DATA.countries[].lsp    (Table 6)
    Table 7 of the manuscript    -> clusters-data.js PAVG                   (Table 7,
                                                     NFFT and LSP rows only)

Everything else in those files is left untouched: coordinates, plate names, the
Table 3 record counts, the Table 4 main-shock counts and every cluster polygon.

After running this, run

    node build-data.js clusters-data.js .

to regenerate clusters-core.js and pts/, or the site keeps showing the old numbers.

Usage:
    python3 update-from-results.py [--results DIR] [--table7 FILE.csv] [--dry-run]
"""
import argparse, csv, json, os, re, sys

MAGS = ['M4', 'M5', 'M6', 'M7', 'M8']
# the result files name this country differently from the web client
COUNTRY_ALIAS = {'Dominican': 'Dominican Republic'}
HERE = os.path.dirname(os.path.abspath(__file__))


def fmt(value):
    """Three decimals, the precision the published tables use. None stays None."""
    if value in (None, '', 'nan', 'None'):
        return None
    return f'{float(value):.3f}'


def load_results(results_dir):
    """(country, cluster) -> {'nfft': [...5 values...], 'lsp': [...]} , None where blank."""
    out = {}
    for method, stem, col in (('nfft', 'NFFT_M', 'return_P_nomes'),
                              ('lsp', 'LSP-M', 'return_p_years')):
        for i, m in enumerate(MAGS):
            path = os.path.join(results_dir, f'{stem}{m[1]}.csv')
            with open(path, encoding='utf-8') as fh:
                for row in csv.DictReader(fh):
                    country = COUNTRY_ALIAS.get(row['country'].strip(), row['country'].strip())
                    key = (country, str(row['cluster']).strip())
                    rec = out.setdefault(key, {'nfft': [None] * 5, 'lsp': [None] * 5})
                    rec[method][i] = fmt((row.get(col) or '').strip())
    return out


def load_table7(path):
    """plate -> {'NFFT': [...], 'LSP': [...]}, None where blank."""
    out = {}
    with open(path, encoding='utf-8') as fh:
        for row in csv.reader(fh):
            row = [c.strip() for c in row]
            if len(row) < 7 or row[1] not in ('NFFT', 'LSP'):
                continue
            out.setdefault(row[0], {})[row[1]] = [fmt(c) for c in row[2:7]]
    return out


def read_js_object(text, name):
    """Return (start, end, parsed) for `const <name> = {...}` in a JS file."""
    m = re.search(r'\b' + re.escape(name) + r'\s*=\s*\{', text)
    if not m:
        raise SystemExit(f'{name} not found')
    start = text.index('{', m.start())
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1, json.loads(text[start:i + 1])
    raise SystemExit(f'unbalanced braces in {name}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default=os.path.join(HERE, '..', '..', 'Results_v2'))
    ap.add_argument('--table7', default=os.path.join(HERE, 'table7_plate_averages.csv'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    results = load_results(args.results)
    table7 = load_table7(args.table7)

    # ---------- data.js ----------
    path = os.path.join(HERE, 'data.js')
    text = open(path, encoding='utf-8').read()
    start, end, data = read_js_object(text, 'DATA')

    changed = kept = dropped = added = 0
    for country in data['countries']:
        name, plate = country['name'], country['plate']
        clusters = sorted({c for (cn, c) in results if cn == name}, key=lambda s: (len(s), s))
        for method in ('nfft', 'lsp'):
            old = {str(r['cluster']): r for r in country[method]}
            new = []
            for cl in clusters:
                vals = results[(name, cl)][method]
                if all(v is None for v in vals):          # nothing resolved: not shown
                    if cl in old: dropped += 1
                    continue
                row = {'country': name, 'cluster': cl, 'plate': plate}
                row.update({m: vals[i] for i, m in enumerate(MAGS)})
                if cl not in old: added += 1
                elif any(old[cl].get(m) != row[m] for m in MAGS): changed += 1
                else: kept += 1
                new.append(row)
            country[method] = new

    new_text = text[:start] + json.dumps(data, ensure_ascii=False) + text[end:]
    print(f'data.js   : {changed} cluster rows updated, {kept} unchanged, '
          f'{added} added, {dropped} removed')
    if not args.dry_run:
        open(path, 'w', encoding='utf-8').write(new_text)

    # ---------- clusters-data.js ----------
    path = os.path.join(HERE, 'clusters-data.js')
    text = open(path, encoding='utf-8').read()
    start, end, pavg = read_js_object(text, 'PAVG')
    n = 0
    for plate, methods in pavg.items():
        if plate not in table7:
            print(f'  warning: {plate} missing from Table 7', file=sys.stderr); continue
        for method in ('NFFT', 'LSP'):
            for i, m in enumerate(MAGS):
                v = table7[plate][method][i]
                if methods[method].get(m) != v:
                    methods[method][m] = v; n += 1
    new_text = text[:start] + json.dumps(pavg, ensure_ascii=False) + text[end:]
    print(f'clusters-data.js: {n} PAVG cells updated')
    if not args.dry_run:
        open(path, 'w', encoding='utf-8').write(new_text)
        print('\nnow run:  node build-data.js clusters-data.js .')
    else:
        print('\n(dry run - nothing written)')


if __name__ == '__main__':
    main()
