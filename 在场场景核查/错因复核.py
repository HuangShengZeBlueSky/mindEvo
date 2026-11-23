from pathlib import Path
import collections as C,csv,json,glob,itertools,re,sys,tarfile,random
R=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(R/'PICTURE复现'))
from run_pair import score
def rows(p):
 import gzip
 with (gzip.open(p, 'rt') if str(p).endswith('.gz') else open(p)) as f:yield from map(json.loads,f)
def norm(n):
 n=n.strip().strip('."\'').lower()
 return {'makenzie':'mackenzie','everevt':'everett'}.get(n,n)
data=list(rows(R/'PICTURE复现/fantom_bel.jsonl'))
src=json.load(tarfile.open(sys.argv[1]).extractfile('fantom_v1.json'))
ids={r['short_context'].strip():r['part_id'] for r in src}
a={r['part_id']:json.loads(r['conversation_with_perceivers']) for r in csv.DictReader(open(sys.argv[2]))}
test=set(json.load(open(R/'archive/partition.json'))['test'])
opts={(s,r['line']):r['options'] for s in (0,111,222,333) for r in rows(R/f'PICTURE复现/paired-1515-seed{s}.jsonl.gz') if r['method']=='PICTURE'}
out=[]
for r in rows(R/'archive/solver/frozen-04.jsonl.gz'):
 i=r['line'];q=data[i-1];s=r['seed'];c=r['calls'];p=c[1]['request']['messages'][1]['content'];story=q['story'];lines=story.splitlines();pid=ids[story];ann=a.get(pid);name=norm(c[0]['text']);mode='过滤' if '\n\nDialogue:\n' in p else '回退'
 opt=opts[s,i];gold='ab'[opt.index(q['answer'])];pred,rule=score(c[-1]['text'],opt,random.Random(s+i-1));ok=pred==q['answer'];pat='';miss=[];extra=[];tag='未对齐听众';strict=False
 if ann and len(ann)==len(lines) and all(norm(l.split(':')[0])==norm(next(iter(e)).split(':')[0]) for l,e in zip(lines,ann)):
  masks=[name in set(map(norm,next(iter(e.values())))) for e in ann]
  if any(masks):
   pat=''.join(str(int(k)) for k,g in itertools.groupby(masks))
   if mode=='回退':tag='回退'
   else:
    view=p.split('\n\nDialogue:\n')[1].split('\n\nQuestion:')[0].splitlines()
    kept=[l for l in view if not l.startswith('[Conversation occurred while ')]
    if len(set(lines))!=len(lines):tag='重复原句待核'
    else:
     assert set(kept)<=set(lines)
     miss=[j for j,(l,heard) in enumerate(zip(lines,masks),1) if heard and l not in kept]
     extra=[j for j,(l,heard) in enumerate(zip(lines,masks),1) if not heard and l in kept]
     tag='多给且漏给' if miss and extra else '漏给' if miss else '多给' if extra else '可见原句一致'
     strict=tag=='可见原句一致' and q['question_type']=='first-order' and name==norm(q['target_character'])
 step=c[1]['text']
 # 只对明确表示偏向某个字母的句式编码；不以提到某个选项本身判定其立场。
 votes=set(re.findall(r'(?:option|choice|answer)\s*\(([ab])\)\s+(?:is|seems|appears)\s+(?:the\s+)?(?:better|best|correct|more (?:likely|supported))|(?:better[- ]supported (?:option|choice)|(?:correct|best) (?:option|answer|choice))\s*(?:is|:)\s*(?:option\s*)?\(([ab])\)',step.lower()))
 letters={x for g in votes for x in g if x};mid=next(iter(letters)) if len(letters)==1 else ''
 out.append(dict(line=i,seed=s,scope='test' if i in test else 'train',actor=name,story_pattern=pat,mode=mode,compare=tag,missing=miss,extra=extra,strict=strict,gold=gold,correct=ok,parse=rule,mid=mid,mid_finish=c[1]['finish'],final=c[2]['text'][:160]))
with open(Path(__file__).with_name('Round4-逐次错因.csv'),'w') as f:
 w=csv.DictWriter(f,fieldnames=out[0]);w.writeheader();w.writerows(out)
for desc,v in [('test',[r for r in out if r['scope']=='test']),('exit',[r for r in out if r['story_pattern']=='10']),('exitTest',[r for r in out if r['story_pattern']=='10' and r['scope']=='test'])]:
 print(desc,'#q',len(set(r['line'] for r in v)),C.Counter((r['compare'],r['correct']) for r in v));t=[r for r in v if r['strict'] and not r['correct']];print('strict',sum(r['strict'] for r in v),len(t),C.Counter('unknown' if not r['mid'] else 'flip' if r['mid']==r['gold'] else 'wrong' for r in t),C.Counter(r['parse'] for r in t))
 if desc=='test':
  for group in ['flip','wrong','unknown']:
   el=[r for r in t if ('unknown' if not r['mid'] else 'flip' if r['mid']==r['gold'] else 'wrong')==group];print(group,[(r['line'],r['seed']) for r in el[:6]])
