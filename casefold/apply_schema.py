#!/usr/bin/env python3
"""Apply schema/<kind>.cypher to built Relate files and check that every constraint holds.

    python3 casefold/apply_schema.py register/sectors.rl offices/*.rl cases/*.rl tests/offices/*.rl tests/cases/*.rl

The kind follows from the folder: register/, offices/ or cases/. Relate checks each constraint against the data
already in the file, so a duplicate key or a wrong type is reported here; the script then exits with 1.
"""
import os, subprocess, sys
from build_case import find_relate, HERE

ROOT = HERE if os.path.isdir(os.path.join(HERE, "schema")) else os.path.dirname(HERE)


def kind_of(path):
    parts = os.path.normpath(path).split(os.sep)
    for folder, kind in (('register', 'register'), ('offices', 'office'), ('cases', 'case'), ('reviews', 'case'), ('laws', 'law')):
        if folder in parts:
            return kind
    sys.exit(f'{path}: not in register/, offices/, cases/ or laws/')


def statements(kind):
    text = open(os.path.join(ROOT, 'schema', kind + '.cypher'), encoding='utf-8').read()
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith('//')]
    return [s.strip() for s in '\n'.join(lines).split(';') if s.strip()]


def main(files):
    relate = find_relate(None)
    bad = 0
    for f in files:
        sts = statements(kind_of(f))
        # one call per file; only when that fails, run the statements one by one to name the constraint that does not hold
        r = subprocess.run([relate, 'query', '--database', f], input=';\n'.join(sts) + ';\n', capture_output=True, text=True)
        out = (r.stdout + r.stderr)
        if r.returncode == 0 and 'error' not in out.lower():
            continue
        for st in sts:
            r = subprocess.run([relate, '--database', f, st], capture_output=True, text=True)
            o = (r.stdout + r.stderr).strip()
            if r.returncode != 0 or 'error' in o.lower():
                bad += 1
                print(f'{f}: {st.split(" IF NOT")[0]}\n  {o.splitlines()[-1] if o else r.returncode}')
    print(f'schema: {len(files)} files, {"all constraints hold" if not bad else str(bad) + " failed"}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
