#!/usr/bin/env python3
"""MCP server for an AI agent on one case file, with memory and a grounded reasoning trail in the knowledge graph.

Use it instead of `relate serve --mcp` when the agent's answers must be traceable. Everything the agent does is written
into the case file, next to the client's graph:

  Session {by:'ai', agent}            short-term memory: one agent session, expires after 8 hours
    -[:ASKED]-> Ask {text}            a question the agent works on
       -[:RECALLED]-> Answer/Episode/Pattern     what it remembered before it started (earlier answers, decisions, lessons)
       -[:USED]-> ToolCall {ord, cypher, why, rows}
                    -[:READ]-> (any node)        every node that came back from that query
       -[:ANSWERED_BY]-> Answer {by:'ai', text, grounded, claims}
                    -[:HAS_CLAIM]-> Claim {text, status}
                                      -[:SUPPORTED_BY]-> (evidence node)
                    -[:REVISES]-> Answer          a corrected answer points to the one it replaces

A claim is "grounded" only if every node it cites was actually READ (or RECALLED) for this question. Claims that cite
nothing, or cite nodes the agent never read, are stored as "ungrounded" and reported back, so the agent must read the
evidence and answer again. The graph keeps the full trail: question -> what was remembered -> which queries -> which
nodes -> which claim -> the answer.

Tools:  recall(question)                 start a question; returns earlier AI answers, the latest decision and the approved patterns
        read_cypher(statement, why)      read-only Cypher on the case file; returned nodes carry their id, cite those ids
        answer(answer, claims[])         store the answer with its claims, each citing node ids; returns the grounding check

Configure (Cursor .cursor/mcp.json, Claude Desktop, ...):
  { "mcpServers": { "casefold-kalmora": { "command": "python3",
      "args": ["casefold/agent_mcp.py", "cases/nl-kalmora.rl"] } } }

Standard library only. Read queries run with `relate query --read-only`; only this server writes the memory nodes.
"""
import json, os, re, subprocess, sys, tempfile, uuid
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_case import find_relate, HERE
import clock

STORE = os.path.join(HERE, 'memory', 'longterm.rl')
ISO = lambda d: d.strftime('%Y-%m-%dT%H:%M:%SZ')
WRITE_WORDS = re.compile(r'\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|LOAD|CALL)\b', re.I)
MEMORY_LABELS = ['Session', 'Ask', 'Answer', 'Step', 'Episode', 'ToolCall', 'Claim']


class Relate:
    def __init__(self, db):
        self.bin, self.db = find_relate(os.environ.get('RELATE_BIN')), db

    def read(self, cypher, db=None):
        r = subprocess.run([self.bin, 'query', '--database', db or self.db, '--read-only', '--mode', 'json', '--max-rows', '0', '-c', cypher],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip()[-600:])
        i = r.stdout.find('{"data"')
        return json.loads(r.stdout[i:])['data'] if i >= 0 else []

    def explain(self, cypher):
        """Plan the statement without running it (EXPLAIN): a syntax error is raised, and Relate's warnings
        (an unknown label, relationship type or property key) are returned, so an empty result is not read as 'not in the file'."""
        r = subprocess.run([self.bin, 'query', '--database', self.db, '--read-only', '--mode', 'json', '-c', 'EXPLAIN ' + cypher],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip()[-600:])
        i = r.stdout.find('{')
        try:
            notes = json.loads(r.stdout[i:]).get('notifications', []) if i >= 0 else []
        except ValueError:
            notes = []
        return [f"{n.get('title')}: {n.get('description')}" for n in notes if n.get('severity') == 'WARNING']

    def write(self, script, params):
        args, tmp = [self.bin, 'query', '--database', self.db], []
        try:
            for k, v in params.items():
                fd, p = tempfile.mkstemp(suffix='.json'); os.close(fd); tmp.append(p)
                json.dump(v, open(p, 'w', encoding='utf-8'), ensure_ascii=False); args += ['--fetch-params', f'{k}={p}']
            r = subprocess.run(args, input=script, capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError((r.stderr or r.stdout).strip()[-600:])
        finally:
            for p in tmp:
                os.remove(p)


def nodes_in(value, found):
    """Collect node ids (and relationship end points) anywhere in a query result."""
    if isinstance(value, dict):
        if value.get('kind') == 'node' and 'id' in value:
            found[value['id']] = value.get('labels', [])
        elif value.get('kind') == 'relationship':
            for k in ('start_node', 'end_node'):
                found.setdefault(value[k], [])
        for v in value.values():
            nodes_in(v, found)
    elif isinstance(value, list):
        for v in value:
            nodes_in(v, found)
    return found


def name_of(props):
    return str(props.get('title') or props.get('name') or props.get('ref') or props.get('text') or props.get('id') or props.get('key') or '')[:120]


class Agent:
    def __init__(self, db, agent='agent'):
        self.r, self.agent = Relate(db), agent
        now, self.offset = clock.now(), timedelta(0)
        if os.environ.get('CASEFOLD_ON'):
            # a fixed clock (run.sh): every session in this file starts one second after the previous one, with a reproducible id
            n = self.r.read("MATCH (s:Session) RETURN count(s) AS n")[0]['n']
            self.offset = timedelta(seconds=n); now += self.offset
            tail = uuid.uuid5(uuid.NAMESPACE_URL, f'{os.path.basename(db)}#{agent}#{n}').hex[:6]
        else:
            tail = uuid.uuid4().hex[:6]     # two agents can start in the same second
        self.sid = 'S-ai-' + now.strftime('%Y%m%d%H%M%S') + '-' + tail
        self.q = 0          # question number in this session
        self.calls = 0      # tool call number for the current question
        self.seen = {}      # node id -> labels, read or recalled for the current question
        self.last_answer = None
        self.r.write("""MATCH (k:Case) MERGE (s:Session {id:$sid}) SET s.started=$now, s.expires=$exp, s.kind='short-term', s.by='ai', s.agent=$agent
MERGE (k)-[:HAS_SESSION]->(s)""", {'sid': self.sid, 'now': ISO(now), 'exp': ISO(now + timedelta(hours=8)), 'agent': agent})

    @property
    def qid(self):
        return f'{self.sid}-Q{self.q}'

    # ---- recall: start a question and bring back what the case remembers ----
    def recall(self, question):
        self.q += 1; self.calls = 0; self.seen = {}; self.last_answer = None
        self.r.write("MATCH (s:Session {id:$sid}) CREATE (q:Ask {id:$qid, text:$text, at:$now, by:'ai'}) CREATE (s)-[:ASKED]->(q)",
                     {'sid': self.sid, 'qid': self.qid, 'text': question, 'now': ISO(clock.now() + self.offset)})
        earlier = self.r.read("""
MATCH (s:Session)-[:ASKED]->(q:Ask)-[:ANSWERED_BY]->(a:Answer) WHERE NOT EXISTS { (:Answer)-[:REVISES]->(a) }
OPTIONAL MATCH (a)-[:HAS_CLAIM]->(c:Claim)
WITH s, q, a, collect(c.text + ' [' + c.status + ']') AS claims
RETURN id(a) AS node, coalesce(s.by, 'rules') AS by, q.text AS question, a.text AS answer, a.at AS at, coalesce(a.grounded, true) AS grounded, claims
ORDER BY at DESC LIMIT 12""")
        episode = self.r.read("MATCH (k:Case)-[:HAS_EPISODE]->(e:Episode) RETURN id(e) AS node, e.decision AS decision, e.open_items AS open_items, e.created AS at ORDER BY at DESC LIMIT 1")
        in_case = self.r.read("MATCH (k:Case)-[:PROPOSED]->(p:Pattern) RETURN id(p) AS node, p.id AS id, p.status AS status, p.title AS title, p.action AS action")
        shared = []
        if os.path.exists(STORE):
            shared = self.r.read("MATCH (p:Pattern {status:'approved'}) RETURN p.id AS id, p.title AS title, p.action AS action, p.seen AS seen_in_cases", STORE)
        ids = [x['node'] for x in earlier + episode + in_case]
        for x in ids:
            self.seen[x] = ['memory']
        if ids:
            self.r.write("MATCH (q:Ask {id:$qid}) MATCH (n) WHERE id(n) IN $ids MERGE (q)-[:RECALLED]->(n)", {'qid': self.qid, 'ids': ids})
        return {
            'question_id': self.qid,
            'earlier_answers': earlier,
            'latest_decision': episode[0] if episode else None,
            'patterns_in_this_case': in_case,
            'approved_patterns_long_term': shared,
            'how_to_answer': 'Read the evidence with read_cypher and RETURN the nodes themselves (not only properties), so they are recorded '
                             'as read. Then call answer with one claim per statement; each claim cites the ids of the nodes it rests on. '
                             'Earlier answers are memory, not evidence: re-read the nodes if you rely on them.',
        }

    # ---- read_cypher: read-only query, every returned node is recorded as READ ----
    def read_cypher(self, statement, why=''):
        if not self.q:
            self.recall('(question not stated)')
        if WRITE_WORDS.search(re.sub(r"'[^']*'|\"[^\"]*\"", '', statement)):
            raise RuntimeError('read_cypher is read-only: CREATE, MERGE, SET, DELETE, REMOVE, DROP, LOAD and CALL are not allowed')
        warnings = self.r.explain(statement)      # checked before it runs, as the Relate docs advise for generated Cypher
        rows = self.r.read(statement)
        found = nodes_in(rows, {})
        found = {k: v for k, v in found.items() if not (set(v) & set(MEMORY_LABELS))}
        self.calls += 1
        self.seen.update(found)
        self.r.write("""MATCH (q:Ask {id:$qid}) CREATE (t:ToolCall {id:$tid, ord:$ord, tool:'read_cypher', cypher:$cy, why:$why, rows:$rows, at:$now})
CREATE (q)-[:USED]->(t) WITH t MATCH (n) WHERE id(n) IN $ids CREATE (t)-[:READ]->(n)""",
                     {'qid': self.qid, 'tid': f'{self.qid}-T{self.calls}', 'ord': self.calls, 'cy': statement, 'why': why, 'rows': len(rows),
                      'now': ISO(clock.now() + self.offset), 'ids': list(found)})
        res = {'rows': rows, 'nodes_recorded_as_read': len(found)}
        if warnings:
            res['warnings'] = warnings + ['These names do not exist in this file, so an empty or short result says nothing about the client: '
                                          'check the labels and relationship types (CALL db.labels() is not available here: MATCH (n) RETURN DISTINCT labels(n)) and query again.']
        return res

    # ---- answer: store the answer and its claims, check that every claim rests on nodes that were read ----
    def answer(self, answer, claims, confidence=None):
        if not self.q:
            raise RuntimeError('call recall(question) first')
        cited = sorted({i for c in claims for i in c.get('cites', [])})
        exist = {r['i']: r for r in self.r.read(f"MATCH (n) WHERE id(n) IN {json.dumps(cited)} RETURN id(n) AS i, labels(n) AS l, properties(n) AS p")} if cited else {}
        n_ans = 1 + (int(self.last_answer.rsplit('A', 1)[1]) if self.last_answer else 0)
        aid = f'{self.qid}-A{n_ans}'
        report, out = [], []
        for n, c in enumerate(claims, 1):
            ids = [i for i in c.get('cites', []) if isinstance(i, int)]
            unknown = [i for i in ids if i not in exist]
            not_read = [i for i in ids if i in exist and i not in self.seen]
            status = 'grounded' if ids and not unknown and not not_read else 'ungrounded'
            reason = ('cites no evidence' if not ids else
                      f'cites nodes that do not exist: {unknown}' if unknown else
                      f'cites nodes that were not read for this question: {not_read}' if not_read else 'all cited nodes were read')
            evidence = [f"{(exist[i]['l'] or ['?'])[0]}: {name_of(exist[i]['p'])}" for i in ids if i in exist]
            out.append({'id': f'{aid}-C{n}', 'ord': n, 'text': c.get('text', ''), 'status': status, 'reason': reason,
                        'evidence': evidence, 'ids': [i for i in ids if i in exist]})
            report.append({'claim': n, 'status': status, 'reason': reason, 'evidence': evidence})
        grounded = all(c['status'] == 'grounded' for c in out) and bool(out)
        self.r.write("""MATCH (q:Ask {id:$qid})
CREATE (a:Answer {id:$aid, by:'ai', agent:$agent, text:$text, confidence:$conf, grounded:$grounded, claims:size($claims),
                  grounded_claims:size([c IN $claims WHERE c.status='grounded']), at:$now}) CREATE (q)-[:ANSWERED_BY]->(a)
WITH a UNWIND $claims AS c CREATE (x:Claim {id:c.id, ord:c.ord, text:c.text, status:c.status, reason:c.reason, evidence:c.evidence}) CREATE (a)-[:HAS_CLAIM]->(x)
WITH x, c UNWIND c.ids AS i MATCH (n) WHERE id(n) = i CREATE (x)-[:SUPPORTED_BY]->(n)""",
                     {'qid': self.qid, 'aid': aid, 'agent': self.agent, 'text': answer, 'conf': confidence, 'grounded': grounded, 'claims': out,
                      'now': ISO(clock.now() + self.offset)})
        if self.last_answer:
            self.r.write("MATCH (a:Answer {id:$a}), (b:Answer {id:$b}) CREATE (a)-[:REVISES]->(b)", {'a': aid, 'b': self.last_answer})
        self.last_answer = aid
        return {'answer_id': aid, 'grounded': grounded, 'claims': report,
                'next': 'Stored. Every claim is grounded.' if grounded else
                        'Some claims are not grounded. Read the evidence with read_cypher (return the nodes) and call answer again; '
                        'the new answer will be stored as a revision of this one.'}


TOOLS = [
    {'name': 'recall', 'description': 'Start working on a question. Returns what this case remembers: earlier answers (by the AI and by the rule-based checks) with their claims, the latest decision, and the approved patterns from long-term memory. Always call this first.',
     'inputSchema': {'type': 'object', 'properties': {'question': {'type': 'string'}}, 'required': ['question']}},
    {'name': 'read_cypher', 'description': 'Run a read-only Cypher query on this client\'s case file (a Relate graph). RETURN the nodes you rely on (e.g. RETURN d, a), not only their properties: every returned node is recorded as read, and its "id" is what you cite in answer. Schema: Client, Document, Chunk (OCR text), Question, Person, Company, Signal, Law, Article, Obligation, DocumentType, LegalForm, RiskTrigger, Counterparty, Country, ScreeningHit, Institution (the office that renders the service), Regulator, UboRule; Client-[:CLIENT_OF]->Institution-[:FOLLOWS]->UboRule-[:HAS_GROUND]->UboGround (per legal-entity type: ownership_interest, voting_rights with threshold and op; control_other_means; listed_exemption; fallback), (Person)-[:OWNS {pct, votes}|BOARD_OF {votes}|CONTROLS {basis}]->, Client-[:REQUIRES {by_law,by_legal_form,by_risk}]->DocumentType, Document-[:OF_TYPE]->DocumentType, Article-[:IMPOSES]->Obligation-[:PROVEN_BY]->DocumentType, (Person|Company)-[:OWNS {pct}]->(Company|Client). OWNS, CONTROLS and BOARD_OF carry source (the Document id) and, when read from a structure chart, evidence (the Chunk id). Facts read from a structure chart are Proposal nodes -[:STATED_IN]-> Chunk {page, bbox, text}, with status proposed / confirmed / rejected; only confirmed ones are part of the structure.',
     'inputSchema': {'type': 'object', 'properties': {'statement': {'type': 'string'}, 'why': {'type': 'string', 'description': 'what you want to find out with this query'}}, 'required': ['statement']}},
    {'name': 'answer', 'description': 'Store your answer to the current question, split into claims. Each claim cites the ids of the nodes it rests on; those nodes must have been returned by read_cypher (or recall) for this question. Returns the grounding check per claim. If a claim is ungrounded, read the evidence and answer again.',
     'inputSchema': {'type': 'object', 'properties': {
         'answer': {'type': 'string'}, 'confidence': {'type': 'number'},
         'claims': {'type': 'array', 'items': {'type': 'object', 'properties': {'text': {'type': 'string'}, 'cites': {'type': 'array', 'items': {'type': 'integer'}}}, 'required': ['text', 'cites']}}},
         'required': ['answer', 'claims']}},
]


PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')
PROMPTS = [
    {'name': 'review_file', 'title': 'Review this client file',
     'description': 'The compliance officer\'s file review: required documents against the documents present, beneficial owners against the '
                    'UBO declaration, contradictions, PEPs and signals, KYCC; then a request to the client and a proposal. '
                    'Uses only this graph file; every claim cites the nodes it rests on.',
     'arguments': [{'name': 'on', 'description': 'review date, YYYY-MM-DD (default today)', 'required': False},
                   {'name': 'language', 'description': 'language of the review (default English; e.g. Dutch)', 'required': False}]},
]


def get_prompt(name, args):
    if name not in {p['name'] for p in PROMPTS}:
        raise ValueError(f'unknown prompt {name}')
    text = open(os.path.join(PROMPT_DIR, name + '.md'), encoding='utf-8').read()
    text = text.replace('{on}', (args or {}).get('on') or clock.today().isoformat()).replace('{language}', (args or {}).get('language') or 'English')
    return {'description': PROMPTS[0]['description'], 'messages': [{'role': 'user', 'content': {'type': 'text', 'text': text}}]}


def serve(db):
    agent = None
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        mid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
        if mid is None:
            continue    # notification
        try:
            if method == 'initialize':
                name = (params.get('clientInfo') or {}).get('name', 'agent')
                agent = Agent(db, name)
                result = {'protocolVersion': params.get('protocolVersion', '2025-06-18'), 'capabilities': {'tools': {}, 'prompts': {}},
                          'serverInfo': {'name': 'casefold-agent-memory', 'version': '1.0.0'},
                          'instructions': 'Use only this graph file as evidence. Call recall first, read evidence with read_cypher (return nodes), then answer with claims that cite node ids. For a file review, use the prompt review_file.'}
            elif method == 'tools/list':
                result = {'tools': TOOLS}
            elif method == 'tools/call':
                agent = agent or Agent(db)
                a = params.get('arguments') or {}
                fn = {'recall': lambda: agent.recall(a['question']),
                      'read_cypher': lambda: agent.read_cypher(a['statement'], a.get('why', '')),
                      'answer': lambda: agent.answer(a['answer'], a.get('claims', []), a.get('confidence'))}[params['name']]
                try:
                    result = {'content': [{'type': 'text', 'text': json.dumps(fn(), ensure_ascii=False, default=str)}]}
                except Exception as e:
                    result = {'content': [{'type': 'text', 'text': f'error: {e}'}], 'isError': True}
            elif method == 'prompts/list':
                result = {'prompts': PROMPTS}
            elif method == 'prompts/get':
                result = get_prompt(params.get('name'), params.get('arguments'))
            elif method == 'ping':
                result = {}
            else:
                print(json.dumps({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'unknown method {method}'}}), flush=True)
                continue
            print(json.dumps({'jsonrpc': '2.0', 'id': mid, 'result': result}, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32000, 'message': str(e)}}), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1].startswith('-'):
        sys.exit(__doc__)
    serve(sys.argv[1])
