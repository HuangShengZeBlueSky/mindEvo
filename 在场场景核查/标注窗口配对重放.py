import sys,json,csv,tarfile,glob,random,concurrent.futures as cf,time
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parent
sys.path.insert(0,str(R/'PICTURE复现'))
from run_pair import query,score
def rows(p):
 import gzip
 with (gzip.open(p, 'rt') if str(p).endswith('.gz') else open(p)) as f:yield from map(json.loads,f)
labels={(int(r['line']),int(r['seed'])):r for r in csv.DictReader(open(D/'Round4-逐次错因.csv')) if r['scope']=='test' and r['compare'] in ('漏给','多给','多给且漏给')}
qs=list(rows(R/'PICTURE复现/fantom_bel.jsonl')); ids={r['short_context'].strip():r['part_id'] for r in json.load(tarfile.open(sys.argv[1]).extractfile('fantom_v1.json'))}
ann={r['part_id']:json.loads(r['conversation_with_perceivers']) for r in csv.DictReader(open(sys.argv[2]))}
opts={(r['line'],s):r['options'] for s in (0,111,222,333) for r in rows(R/f'PICTURE复现/paired-1515-seed{s}.jsonl.gz') if r['method']=='PICTURE' and (r['line'],s) in labels}
def norm(n):return {'makenzie':'mackenzie','everevt':'everett'}.get(n.lower(),n.lower())
def run(r,oracle):
 i,s=r['line'],r['seed'];q=qs[i-1];cs=r['calls'];p=cs[1]['request']['messages'][1]['content'];v=p.split('\n\nDialogue:\n')[1].split('\n\nQuestion:')[0];new=v
 if oracle:
  name=labels[i,s]['actor'];annrows=ann[ids[q['story']]];b=[name in set(map(norm,next(iter(k.values())))) for k in annrows];lines=q['story'].splitlines();assert len(b)==len(lines)
  gap=next(l for l in v.splitlines() if l.startswith('[Conversation occurred')) if '[Conversation occurred' in v else '[Conversation occurred while '+name+' was absent; its specific contents are unavailable.]'
  new='\n'.join((line if keep else gap) for j,(line,keep) in enumerate(zip(lines,b)) if keep or not j or b[j-1])
 a=query(p.replace(v,new,1),s)
 last=cs[2]['request']['messages'][1]['content'];sep='Earlier brief analysis (check it against the dialogue; it may contain errors):\n';left,right=last.split(sep,1);assert right.startswith(cs[1]['text'])
 z=query(left.replace(v,new,1)+sep+a['text']+right[len(cs[1]['text']):],s)
 ok=score(z['text'],opts[i,s],random.Random(s+i-1))[0]==q['answer']
 return dict(line=i,seed=s,oracle=oracle,correct=ok,calls=[a,z])
path=D/'窗口配对重放.jsonl';done={(v['line'],v['seed'],v['oracle']) for v in rows(path)} if path.exists() else set()
with cf.ThreadPoolExecutor(18) as pool:
 jobs=[pool.submit(run,r,oracle) for r in rows(R/'archive/solver/frozen-04.jsonl.gz') if (r['line'],r['seed']) in labels for oracle in (False,True) if (r['line'],r['seed'],oracle) not in done]
 for f in cf.as_completed(jobs):
  with path.open('a') as o:o.write(json.dumps(f.result(),ensure_ascii=False)+'\n')
