#!/usr/bin/env python3
"""Hand one client file over to an auditor, with Relate's own tools.

    python3 casefold/handover.py cases/nl-kalmora.rl            # -> handover/nl-kalmora/

Writes, next to a copy of the .rl file itself:
  snapshot/      `relate clone --to-snapshot-format json`: the whole graph as readable JSON (graph.json) plus its schema.cypher;
                 Relate opens it as a database too:  relate --database handover/nl-kalmora/snapshot --read-only "MATCH (n) RETURN count(n)"
  info.json      `relate info --json`: node and relationship counts, every constraint and index, format, commit
  manifest.json  sha256 of the .rl file, the counts, and the commands that made this hand-over
The source file is opened read-only; nothing in it changes.
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--out', default=os.path.join(HERE, 'handover'))
    ap.add_argument('--relate')
    a = ap.parse_args()
    relate = find_relate(a.relate)
    name = os.path.splitext(os.path.basename(a.file))[0]
    out = os.path.join(a.out, name)
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    shutil.copy2(a.file, os.path.join(out, name + '.rl'))
    cmds = [[relate, 'clone', '--to-snapshot-format', 'json', a.file, os.path.join(out, 'snapshot')],
            [relate, 'info', '--database', a.file, '--json']]
    subprocess.run(cmds[0], check=True, capture_output=True)
    info = json.loads(subprocess.run(cmds[1], check=True, capture_output=True, text=True).stdout)
    json.dump(info, open(os.path.join(out, 'info.json'), 'w'), indent=1)
    sha = hashlib.sha256(open(a.file, 'rb').read()).hexdigest()
    man = {'file': os.path.basename(a.file), 'sha256': sha, 'made': datetime.datetime.now().isoformat(timespec='seconds'),
           'nodes': info.get('node_count'), 'relationships': info.get('rel_count'),
           'constraints': len(info.get('constraints', [])), 'indexes': len(info.get('indexes', [])),
           'commands': [' '.join(['relate'] + c[1:]) for c in cmds]}
    json.dump(man, open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
    print(f"hand-over {os.path.relpath(out, HERE)}: {man['nodes']} nodes, {man['relationships']} relationships, "
          f"{man['constraints']} constraints, {man['indexes']} indexes, sha256 {sha[:12]}")


if __name__ == '__main__':
    main()
