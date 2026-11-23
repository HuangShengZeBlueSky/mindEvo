"""从真实回包重算配对表现，并以完整多人对话为单位估计测试差值的不确定性。"""
from collections import Counter,defaultdict
import json,random,sys
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'results'
src=root.parent/'PICTURE复现'
sys.path.insert(0,str(src))
from run_pair import score,SYSTEM,MODEL
def load(p):return json.loads(p.read_text())
def records(p):
    with p.open() as f:
        for line in f:yield json.loads(line)
frozen=load(out/'frozen.json')['round']
rounds=load(out/'rounds.json')
assert len(rounds)==10 and [r['round'] for r in rounds]==list(range(1,11))
parent=0
for r in rounds:
    assert r['parent']==parent
    assert 'model: gpt-6.1-terra' in (out/f'terra-{r["round"]:02d}.log').read_text()
    if r['kept']:parent=r['round']
assert frozen==parent
rows=list(records(src/'fantom_bel.jsonl'))
split=load(src/'DSH-故事划分-200-169.json')['splits']
group={i:x['conv_id'] for x in split['测试集'] for i in x['lines']}
assert not set(group)&{i for x in split['进化集'] for i in x['lines']}
picture={}
for s in (0,111,222,333):
    for r in records(src/f'paired-1515-seed{s}.jsonl'):
        if r['method']=='PICTURE':picture[s,r['line']]=r
seen=set();clusters=defaultdict(Counter);sums=defaultdict(Counter);counts=Counter()
for r in records(out/f'frozen-{frozen:02d}.jsonl'):
    key=(r['seed'],r['line']);assert key not in seen;seen.add(key)
    baseline=picture[key];calls=r['calls'];counts[len(calls)]+=1
    assert 1<=len(calls)<=3
    assert r['events']==['agent/pre-step','agent/turn-stopping']*len(calls)
    for c in calls:
        p=c['request'];assert c['model']==p['model']==MODEL and c['provider']=='Groq'
        assert p['messages'][0]=={'role':'system','content':SYSTEM} and p['messages'][1]['role']=='user' and len(p['messages'])==2
        assert (p['seed'],p['temperature'],p['top_p'],p['max_tokens'])==(key[0],0,1,300)
    q=rows[key[1]-1]
    pred=score(calls[-1]['text'],baseline['options'],random.Random(sum(key)-1))[0]
    correct=pred==q['answer']
    fb=q['story_type']=='false_belief'
    for g in ('all','test' if key[1] in group else 'train'):
        sums[g]['correct']+=correct;sums[g]['n']+=1
        sums[g]['fbcorrect']+=fb and correct;sums[g]['nfb']+=fb
    if key[1] in group:
        cl=clusters[group[key[1]]];delta=int(correct)-int(baseline['correct'])
        cl['all']+=delta;cl['n']+=1;cl['fb']+=delta*fb;cl['nf']+=fb
assert seen==set(picture) and len(seen)==6060
reported=load(out/'final.json')['DSH']
for g,c in sums.items():
    assert abs(100*c['correct']/c['n']-reported[g]['all'])<1e-8
    assert abs(100*c['fbcorrect']/c['nfb']-reported[g]['fb'])<1e-8
rng=random.Random(71);cs=list(clusters.values());dist={'all':[],'fb':[]}
for _ in range(5000):
    picks=rng.choices(cs,k=len(cs))
    for k,n in [('all','n'),('fb','nf')]:
        dist[k].append(100*sum(c[k] for c in picks)/sum(c[n] for c in picks))
intervals={k:[sorted(v)[125],sorted(v)[4874]] for k,v in dist.items()}
(out/'audit.json').write_text(json.dumps(dict(frozen=frozen,rounds=10,unique_runs=len(seen),call_distribution=counts,
    counts=sums,test_difference_vs_picture_cluster_bootstrap_95=intervals),indent=2))
print('PASS',frozen,dict(counts),intervals)
