"""从归档记录重算选拔和冻结成绩。只用 Python 标准库，无模型请求。"""
import gzip
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'PICTURE复现'
ARCHIVE = ROOT / 'archive'
sys.path.insert(0, str(DATA))
from run_pair import score

def rows(path):
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
        yield from map(json.loads, f)

def load(path):
    return json.loads(path.read_text())

questions = list(rows(DATA / 'fantom_bel.jsonl'))
split = load(ARCHIVE / 'partition.json')
dev, select, test = (set(split[k]) for k in ('develop', 'select', 'test'))
train = dev | select
all_ids = set(range(1, len(questions) + 1))
assert (len(dev), len(select), len(test)) == (665, 150, 700)
assert dev.isdisjoint(select) and train.isdisjoint(test) and train | test == all_ids
options = {}
base = {}
for seed in (0, 111, 222, 333):
    for r in rows(DATA / f'paired-1515-seed{seed}.jsonl.gz'):
        if r['method'] == 'PICTURE':
            key = (seed, r['line'])
            assert key not in options
            options[key] = r['options']
            base[key] = score(r['calls'][-1]['text'], r['options'], random.Random(sum(key)-1))[0] == questions[key[1]-1]['answer']
            assert base[key] == r['correct']
assert len(base) == 6060

def scored(r):
    s, i = r['seed'], r['line']
    pred, _ = score(r['calls'][-1]['text'], options[s, i], random.Random(s+i-1))
    return pred == questions[i-1]['answer']

def filtered(r):
    return '[Conversation occurred while ' in r['calls'][1]['request']['messages'][1]['content'] and 'The following is a sequence of utterances' not in r['calls'][1]['request']['messages'][1]['content']

parent = 0
parent_scores = {i: base[0,i] for i in train}
trace = load(ARCHIVE / 'rounds.json')
parent_routes = {}
routes = defaultdict(Counter)
assert [x['round'] for x in trace] == list(range(1, 11))
for item in trace:
    n = item['round']
    assert parent == item['parent']
    proposal = load(ARCHIVE / f'terra/proposal-{n:02d}.json')
    assert proposal['source'] == (ARCHIVE / f'plugins/round{n:02d}.js').read_text()
    assert (ARCHIVE / f'terra/input-{n:02d}.txt').is_file()
    scores, flags = {}, {}
    for r in rows(ARCHIVE / f'solver/training-{n:02d}.jsonl.gz'):
        i = r['line']
        assert r['seed'] == 0 and i not in scores
        scores[i] = scored(r)
        if n in (2, 4):
            flags[i] = filtered(r)
    assert set(scores) == train
    fixes = sum(scores[i] and not parent_scores[i] for i in dev)
    losses = sum(parent_scores[i] and not scores[i] for i in dev)
    assert (fixes, losses) == (item['dev_repairs'], item['dev_regressions'])
    a, b = item['parent_selection'], item['selection']
    for label, ids in [('all', select), ('fb', [i for i in select if questions[i-1]['story_type']=='false_belief'])]:
        assert a[label] == sum(parent_scores[i] for i in ids)
        assert b[label] == sum(scores[i] for i in ids)
    keep = (b['all'] > a['all'] and b['fb'] >= a['fb']) or (
        (a['all'], a['fb']) == (b['all'], b['fb']) and (b['calls'], b['tokens']) < (a['calls'], a['tokens']))
    assert keep == item['kept']
    if n == 4:
        for i in dev:
            group = ('过滤' if parent_routes[i] else '回退', '过滤' if flags[i] else '回退')
            outcome = '修好' if scores[i] and not parent_scores[i] else '改坏' if parent_scores[i] and not scores[i] else '两版均对' if scores[i] else '两版均错'
            routes[group][outcome] += 1
    if keep:
        parent, parent_scores, parent_routes = n, scores, flags
assert parent == load(ARCHIVE / 'frozen.json')['round'] == 4
totals = defaultdict(Counter)
seen = set()
for r in rows(ARCHIVE / 'solver/frozen-04.jsonl.gz'):
    s, i = key = (r['seed'], r['line'])
    assert key not in seen and len(r['calls']) == 3
    seen.add(key)
    hit = scored(r)
    for group in ('all', 'test' if i in test else 'train'):
        for method, correct in [('DSH', hit), ('PICTURE', base[key])]:
            c = totals[method, group, s]
            c['n'] += 1
            c['all'] += correct
            if questions[i-1]['story_type'] == 'false_belief':
                c['nfb'] += 1
                c['fb'] += correct
assert seen == set(base)
for method, groups in load(ARCHIVE / 'final.json').items():
    if method not in ('DSH','PICTURE'):
        continue
    for group, report in groups.items():
        for seed, original in zip((0,111,222,333), report['by_seed']):
            for field in ('n','all','nfb','fb'):
                assert totals[method, group, seed][field] == original[field]
print('核验通过：10 轮 × 815 道候选作答；保留 0 → 2 → 4；冻结 6,060 次作答；两个方法各范围、各种子正确数与归档一致。')
for (before, after), counts in sorted(routes.items()):
    print(before, '→', after, sum(counts.values()), dict(counts))
