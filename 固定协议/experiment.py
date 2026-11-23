"""十轮 DSH 插件进化；开发、选型、最终测试由固定控制器分开执行。"""
import collections
import json
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT.parent/'PICTURE复现'
sys.path.insert(0,str(DATA))
import run_pair as reference

RESULT=ROOT/'results'
PLUG=ROOT/'plugins'
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
SEEDS=[0,111,222,333]

def read(p):return json.loads(p.read_text())
def save(p,v):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2));tmp.replace(p)
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
data=rows(DATA/'fantom_bel.jsonl')
split=read(DATA/'DSH-故事划分-200-169.json')['splits']
groups=collections.defaultdict(list)
for r in split['进化集']:groups[r['conv_id']].append(r['lines'])
order=sorted(groups);random.Random(12345).shuffle(order)
val_groups=[];size=0
for g in order:
    if g!=0 and size+len(groups[g])<=40:
        val_groups.append(g);size+=len(groups[g])
assert size==40
valid={i for g in val_groups for ls in groups[g] for i in ls}
train={i for r in split['进化集'] for i in r['lines']}
dev=train-valid
test={i for r in split['测试集'] for i in r['lines']}
assert not train&test and len(train)==815 and len(test)==700
opts={}
for seed in SEEDS:
    rng=random.Random(seed)
    for i,q in enumerate(data,1):
        o=list(q['containers']);rng.shuffle(o);opts[seed,i]=o

def task(seed,i):
    q=data[i-1];o=opts[seed,i]
    question=reference.templates.questionPrompt.format(question=q['question'],containers_0=o[0],containers_1=o[1])
    target=q['target_character']
    return dict(key=f'{seed}-{i}',line=i,seed=seed,input=dict(story=q['story'],question=q['question'],target=target,options=o,
        pictureFirst=reference.templates.PERSPECTIVE_PROMPT_OURS.format(story=q['story'],question=question,character=target),
        pictureLast=reference.templates.GPT_SIM_PROMPT_OURS.format(perspective='{perspective}',name=target,question=question)))

def baseline(seed,method,ids):
    out=[]
    for r in rows(DATA/f'paired-1515-seed{seed}.jsonl'):
        if r['method']==method and r['line'] in ids:
            out.append(dict(line=r['line'],seed=seed,calls=r['calls'],correct=r['correct']))
    return out

def evaluate(n,ids,seeds,phase):
    path=RESULT/f'{phase}-{n:02d}.jsonl'
    tasks=[task(seed,i) for seed in seeds for i in sorted(ids)]
    tmp=RESULT/'active-input.json';save(tmp,tasks)
    for attempt in range(4):
        with (RESULT/'runtime.log').open('a') as log:
            proc=subprocess.run([str(NODE),str(ROOT/'runtime.mjs'),str(PLUG/f'round{n:02d}.js'),str(tmp),str(path)],stdout=log,stderr=log)
        if not proc.returncode:break
        if attempt<3:time.sleep(2)
    records=rows(path) if path.exists() else []
    if {r['key'] for r in records}!={t['key'] for t in tasks} or len(records)!=len(tasks):raise RuntimeError(f'incomplete {path}: {len(records)}/{len(tasks)}')
    for r in records:
        i=r['line'];s=r['seed'];calls=r['calls'];assert 1<=len(calls)<=3
        assert r['events'].count('agent/pre-step')==len(calls)
        for c in calls:
            req=c['request']
            assert req['messages'][0]['content']==reference.SYSTEM and len(req['messages'])==2
            assert req['model']==reference.MODEL and req['seed']==s and c['provider']=='Groq'
        pred,_=reference.score(calls[-1]['text'],opts[s,i],random.Random(s+i-1))
        r['correct']=pred==data[i-1]['answer']
    return records

def metrics(records,ids):
    a=[r for r in records if r['line'] in ids]
    f=[r for r in a if data[r['line']-1]['story_type']=='false_belief']
    return dict(n=len(a),all=sum(r['correct'] for r in a),fb=sum(r['correct'] for r in f),nfb=len(f),
                calls=sum(len(r['calls']) for r in a),tokens=sum(c['usage']['total_tokens'] for r in a for c in r['calls']))

def compact(r):
    q=data[r['line']-1];seed=r['seed'];i=r['line']
    return dict(story=q['story'],question=q['question'],options=opts[seed,i],target=q['target_character'],
        label=q['answer'],correct=r['correct'],trace=[{'input_end':(c.get('prompt') or c['request']['messages'][-1]['content'])[-380:],
            'output':c['text'][:1700],'finish':c['finish']} for c in r['calls']])

def propose(n,parent,evidence,rounds):
    out=PLUG/f'round{n:02d}.js'
    if out.exists():return
    rng=random.Random(800+n);dev_rows=[r for r in evidence if r['line'] in dev]
    examples=[]
    for belief in ('false_belief','true_belief'):
        for correct,count in [(False,5),(True,2)]:
            pool=[r for r in dev_rows if r['correct']==correct and data[r['line']-1]['story_type']==belief]
            examples.extend(compact(r) for r in rng.sample(pool,min(count,len(pool))))
    transitions=[]
    if rounds:
        prev=rounds[-1];last=prev['round'];origin=prev['parent']
        path=RESULT/f'training-{last:02d}.jsonl'
        if path.exists():
            parent_rows=baseline(0,'PICTURE',dev) if origin==0 else rows(RESULT/f'training-{origin:02d}.jsonl')
            by_id={r['line']:r for r in parent_rows if r['line'] in dev}
            buckets=collections.defaultdict(list)
            def judged(r):
                i=r['line'];last_text=r['calls'][-1]['text']
                return reference.score(last_text,opts[0,i],random.Random(i-1))[0]==data[i-1]['answer']
            for after in rows(path):
                i=after['line']
                if i not in by_id:continue
                before=by_id[i];a,b=judged(before),judged(after)
                if a!=b:buckets[(a,b)].append((before,after))
            for direction,pool in buckets.items():
                for before,after in rng.sample(pool,min(2,len(pool))):
                    i=before['line']
                    transitions.append(dict(kind='repair' if direction[1] else 'regression',story=data[i-1]['story'],question=data[i-1]['question'],options=opts[0,i],gold=data[i-1]['answer'],before=[c['text'][:650] for c in before['calls']],after=[c['text'][:650] for c in after['calls']]))
    history=[{k:r[k] for k in ('round','parent','kept','diagnosis','change','selection','dev_repairs','dev_regressions') if k in r} for r in rounds]
    adaptive=(ROOT/'固定搜索指导.txt').read_text()
    prompt=f"""你是本实验唯一的进化器。第 {n}/10 轮。目标是提高冻结 Llama 3.1 8B 的 FANToM 信念二选一 All 准确率，同时错误信念不得退步。看下面训练侧真实轨迹，给出一个可执行候选。只根据本消息工作，不调用工具。返回符合 schema 的 JSON，diagnosis、change 用中文，source 是完整普通 JavaScript（无 import/export，无 markdown），定义 function next(q,h,s)。会真实执行。每个题独立隔离，无网络文件或系统 API，无标签。q.story, q.question, q.target, q.options[0:2]；q.pictureFirst 和 q.pictureLast 是作者原提示，后者含 {{perspective}} 占位符。h 是已返回的数组，每项 {{text,finish}}；s 是本题可写的空对象，跨步保留。每次 next 返回一个完整英文 user prompt 就触发 Llama 一次，返回 null 就采用最后一次模型原答。1–3 次调用，第 3 次系统直接采纳该输出。不能在插件里返回选择作为最终答案，不能记忆人名、题号、题或选项标答。DSH pre-step 注入本步提示，turn-stopping 作继续判断。每次模型只能看到该次 prompt 以及固定 system，上步输出必须自行放回。模型温度0，上限300 tokens；避免冗长分析遮蔽作答。最终提示要求只输出 (a) 或 (b)。可用 JS 先识别发言行/目标的进出场、逐段原句/嵌套人物证据和有条件路由。注意 true belief 尤其二阶题也可能询问在场人物；不要一概选更无知的选项。要从证据提出能泛化的代码修复；不必受限于上轮机制。试验拒绝时可以跨方向。{adaptive} 父版本 {parent} 源码：\n{(PLUG/f'round{parent:02d}.js').read_text()}\n历史：{json.dumps(history,ensure_ascii=False)}\n开发轨迹：{json.dumps(examples,ensure_ascii=False)}\n上一候选的开发配对修复和退步：{json.dumps(transitions,ensure_ascii=False)}"""
    (RESULT/f'input-{n:02d}.txt').write_text(prompt)
    with tempfile.TemporaryDirectory(prefix='fantom-terra-training-') as folder:
        w=Path(folder);schema={'type':'object','properties':{k:{'type':'string'} for k in ('diagnosis','change','source')},'required':['diagnosis','change','source'],'additionalProperties':False}
        save(w/'schema.json',schema)
        env={k:v for k,v in os.environ.items() if k!='OPENROUTER_API_KEY'}
        cmd=['codex','exec','--ephemeral','--skip-git-repo-check','--disable','shell_tool','--disable','unified_exec','--disable','plugins','-s','read-only','-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema','schema.json','-o','answer.json','-']
        with (RESULT/f'terra-{n:02d}.log').open('a') as log:
            p=subprocess.run(cmd,input=prompt,text=True,cwd=w,env=env,stdout=log,stderr=log,timeout=1400)
        if p.returncode or not (w/'answer.json').exists():raise RuntimeError(f'Terra round {n} failed')
        ans=read(w/'answer.json')
    save(RESULT/f'proposal-{n:02d}.json',ans)
    out.write_text(ans['source'])

def main():
    save(RESULT/'partition.json',dict(develop=sorted(dev),select=sorted(valid),test=sorted(test),develop_stories=160,select_stories=40,test_stories=169))
    wiring=rows(RESULT/'wiring.jsonl')[0];ref=read(DATA/'第1题-两阶段API对读.json')['calls']
    assert [c['request'] for c in wiring['calls']]==[c['request'] for c in ref]
    parent=0;current=baseline(0,'PICTURE',train);rounds=[]
    for n in range(1,11):
        print(time.strftime('%H:%M:%S'),f'round {n} parent {parent}',flush=True)
        propose(n,parent,current,rounds)
        ans=read(RESULT/f'proposal-{n:02d}.json')
        rec={'round':n,'parent':parent,'diagnosis':ans['diagnosis'],'change':ans['change']}
        try:
            candidate=evaluate(n,train,[0],'training')
        except RuntimeError:
            log=(RESULT/'runtime.log').read_text()[-5000:]
            if any(x in log for x in ('Invalid plugin output','SyntaxError','ReferenceError','Script execution timed out')):candidate=None
            else:raise
        if candidate is None:
            rec.update(kept=False,selection='候选执行失败',dev_repairs=0,dev_regressions=0)
        else:
            a=metrics(current,valid);b=metrics(candidate,valid)
            kept=b['all']>a['all'] and b['fb']>=a['fb'] or (b['all'],b['fb'])==(a['all'],a['fb']) and (b['calls'],b['tokens'])<(a['calls'],a['tokens'])
            before={r['line']:r['correct'] for r in current};changes=collections.Counter((before[r['line']],r['correct']) for r in candidate if r['line'] in dev)
            rec.update(kept=kept,selection=b,parent_selection=a,development=metrics(candidate,dev),dev_repairs=changes[False,True],dev_regressions=changes[True,False])
            if kept:parent=n;current=candidate
        rounds.append(rec);save(RESULT/'rounds.json',rounds)
        print('retained',parent,'selection',rec['selection'],flush=True)
    save(RESULT/'frozen.json',dict(round=parent,model=reference.MODEL,seeds=SEEDS))
    final=evaluate(parent,train|test,SEEDS,'frozen')
    reports={}
    for method in ('DSH','PICTURE','Vanilla'):
        r=final if method=='DSH' else sum([baseline(s,method,train|test) for s in SEEDS],[])
        reports[method]={}
        for group,ids in [('test',test),('train',train),('all',train|test)]:
            v=[metrics([x for x in r if x['seed']==s],ids) for s in SEEDS]
            reports[method][group]=dict(by_seed=v,all=statistics.mean(100*m['all']/m['n'] for m in v),fb=statistics.mean(100*m['fb']/m['nfb'] for m in v),calls=sum(m['calls'] for m in v)/sum(m['n'] for m in v),tokens=sum(m['tokens'] for m in v)/sum(m['n'] for m in v))
    save(RESULT/'final.json',reports)
    print('COMPLETE',parent,flush=True)

if __name__=='__main__':main()
