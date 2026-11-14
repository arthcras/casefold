#!/usr/bin/env python3
"""Replay of an agent session over MCP, to show the AI memory without a language model.

This script plays the agent's side with fixed steps (it is not an AI) and talks to casefold/agent_mcp.py over stdio,
exactly as Cursor or Claude would. It shows:
  1. recall      what the case already remembers
  2. read_cypher the ownership chain and the UBO declaration, returned as nodes, so they are recorded as READ
  3. answer      three claims; one cites a legal ground and article that were not read, so the server marks it "ungrounded"
  4. read_cypher the law article, then answer again: all claims grounded, stored as a revision of the first answer
  5. a new session: recall now returns the grounded answer from step 4 as memory

usage:  python3 casefold/agent_demo.py cases/nl-kalmora.rl
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


class Client:
    def __init__(self, case, name):
        self.p = subprocess.Popen([sys.executable, os.path.join(HERE, 'agent_mcp.py'), case], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.n = 0
        self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': name, 'version': '1'}})
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')

    def rpc(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params}) + '\n'); self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline())
        if 'error' in r:
            sys.exit(r['error']['message'])
        return r['result']

    def call(self, tool, **args):
        r = self.rpc('tools/call', {'name': tool, 'arguments': args})
        text = r['content'][0]['text']
        if r.get('isError'):
            sys.exit(text)
        return json.loads(text)

    def close(self):
        self.p.stdin.close(); self.p.wait()


def ids(rows, col):
    return [r[col]['id'] for r in rows if isinstance(r.get(col), dict)]


def show_check(res):
    print(f"   answer {res['answer_id']}: grounded={res['grounded']}")
    for c in res['claims']:
        print(f"     claim {c['claim']}: {c['status']:<10} {c['reason']}")


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else 'cases/nl-kalmora.rl'
    Q = 'Is the UBO declaration complete?'
    print(f'Session 1 (replayed agent, no language model): "{Q}"')
    a = Client(case, 'replay-agent')
    m = a.call('recall', question=Q)
    print(f"1. recall: {len(m['earlier_answers'])} earlier answers, latest decision: {(m['latest_decision'] or {}).get('decision')}, "
          f"{len(m['approved_patterns_long_term'])} approved patterns in long-term memory")

    ctl = a.call('read_cypher', why='who controls the client by other means than shares or votes',
                 statement="MATCH (o:Person)-[r:CONTROLS]->(x) WHERE x:Client OR EXISTS { (x)-[:OWNS]->{1,4}(:Client) } "
                           "MATCH (d:Document {id: r.source}) RETURN o, r.basis AS basis, x, d")
    decl = a.call('read_cypher', why='the UBO declaration in the file and the persons it names',
                  statement="MATCH (d:Document)-[:OF_TYPE]->(t:DocumentType {key:'ubo_declaration'}) RETURN d, t")
    print(f"2. read_cypher x2: {ctl['nodes_recorded_as_read']} + {decl['nodes_recorded_as_read']} nodes recorded as read")
    top = ctl['rows'][0]
    who, holding, d8 = top['o'], top['x']['id'], top['d']['id']
    d6 = ids(decl['rows'], 'd')[0]
    # the replayed agent "knows" the id of the legal ground without having read it through the server (as a model might guess one);
    # the first answer cites it anyway, and the server catches that
    import agent_mcp
    r = agent_mcp.Relate(case).read("MATCH (:Client)-[:CLIENT_OF]->(:Institution)-[:FOLLOWS]->(:UboRule)-[:HAS_GROUND]->"
                                    "(g:UboGround {entity_type:'corporate', ground:'control_other_means'})-[:DEFINED_IN]->(a:Article) RETURN id(g) AS g, id(a) AS a")
    ground, article = r[0]['g'], r[0]['a']
    name = who['properties']['name']
    claims = [
        {'text': f"{name} holds a veto ({top['basis']}) over the holding that owns the client, according to the shareholders agreement", 'cites': [who['id'], holding, d8]},
        {'text': f'The signed UBO declaration does not name {name}', 'cites': [d6, who['id']]},
        {'text': 'Under Dutch law control by other means makes a person a UBO of a B.V., without any percentage, so the declaration is incomplete', 'cites': [ground, article]},
    ]
    res = a.call('answer', answer=f'No. The declaration misses {name}, who controls the client by other means.', claims=claims, confidence=0.8)
    print('3. answer (first try):'); show_check(res)

    a.call('read_cypher', why='the ground in the rule of the serving office, and the article that defines it',
           statement="MATCH (:Client)-[:CLIENT_OF]->(i:Institution)-[:FOLLOWS]->(u:UboRule)-[:HAS_GROUND]->"
                     "(g:UboGround {entity_type:'corporate', ground:'control_other_means'})-[:DEFINED_IN]->(a:Article) RETURN i, u, g, a")
    res = a.call('answer', answer=f'No. {name} is missing from the UBO declaration: through a veto in the shareholders agreement she controls the holding '
                                  'and so the client by other means, which under art. 3(1)(a) Uitvoeringsbesluit Wwft 2018 makes her a UBO without any percentage. '
                                  'Request a corrected, signed declaration.',
                 claims=claims, confidence=0.9)
    print('4. read the ground and the article, answer again:'); show_check(res)
    a.close()

    print('\nSession 2 (later): recall')
    b = Client(case, 'replay-agent')
    m = b.call('recall', question='What did we conclude about the UBO declaration?')
    for e in m['earlier_answers'][:3]:
        print(f"   [{e['by']}] {e['question']} -> {e['answer'][:110]}  (grounded={e['grounded']})")
    b.close()


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    main()
