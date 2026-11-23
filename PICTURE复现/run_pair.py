"""在作者公开题库上配对运行 Vanilla 和 PICTURE，记录两次调用的交接文本。"""
import argparse
import concurrent.futures as cf
import http.client
import json
import os
import random
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
import prompts_fantom as templates

ROOT = Path(__file__).resolve().parent
MODEL = 'meta-llama/llama-3.1-8b-instruct'


SYSTEM = 'You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.'


def query(prompt, seed):
    payload = dict(model=MODEL, messages=[dict(role='system', content=SYSTEM),dict(role='user', content=prompt)], temperature=0,
                   top_p=1, seed=seed, max_tokens=300, provider=dict(order=['Groq'], allow_fallbacks=False))
    req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',json.dumps(payload).encode(),
        headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY'],'Content-Type':'application/json'})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req,timeout=120) as response:
                result=json.load(response)
            choice=result['choices'][0]
            return dict(prompt=prompt,text=choice['message']['content'],provider=result['provider'],
                        model=result['model'],usage=result['usage'],finish=choice['finish_reason'])
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==5:raise
            time.sleep(max(2**attempt,float(e.headers.get('Retry-After','0') or 0)))
        except (urllib.error.URLError,TimeoutError,ConnectionError,http.client.IncompleteRead,json.JSONDecodeError,KeyError) as e:
            if attempt==5:raise
            time.sleep(2**attempt)


def similarity(pred, option):
    if pred==option:return 3
    def norm(s):
        return re.sub(r'[{}^\\`\u2047<]', ' ',s.replace('"','').replace("'",""))
    a,b=norm(pred),norm(option)
    if a==b:return 2
    if ' ' not in a and ' ' not in b:return 0
    return len(set(a.split(' ')) & set(b.split(' ')))/max(len(a.split(' ')),len(b.split(' ')))


def score(text, opts, rng):
    p=text.lower()
    last=p.split('\n')[-1].strip().replace('*','')
    for i,c in enumerate('ab'):
        if c+')' in p:return opts[i],'选项标记'
    if last in ('a','b'):return opts['ab'.index(last)],'单字母'
    if 'none' in p or 'both' in p:return 'None','放弃或两者'
    a,b=[similarity(p,s.lower()) for s in opts]
    if a==b:return rng.choice(opts),'相似度平局随机'
    return opts[int(b>a)],'文本相似度'


def run(row,idx,opts,method,seed):
    args=dict(story=row['story'],question=row['question'],containers_0=opts[0],containers_1=opts[1])
    question=templates.questionPrompt.format(**args)
    calls=[]
    if method=='Vanilla':
        prompt=templates.baselinePrompt.format(**args)
    else:
        name=row['target_character']
        calls.append(query(templates.PERSPECTIVE_PROMPT_OURS.format(story=row['story'],question=question,character=name),seed))
        prompt=templates.GPT_SIM_PROMPT_OURS.format(perspective=calls[0]['text'],name=name,question=question)
    calls.append(query(prompt,seed))
    prediction,rule=score(calls[-1]['text'],opts,random.Random(seed+idx))
    return dict(line=idx+1,seed=seed,method=method,story_type=row['story_type'],options=opts,
                gold=row['answer'],prediction=prediction,correct=prediction==row['answer'],rule=rule,calls=calls)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',type=int,default=48)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--workers',type=int,default=10)
    args=parser.parse_args()
    rows=list(map(json.loads,(ROOT/'fantom_bel.jsonl').read_text().splitlines()))
    selected=set(random.Random(2026).sample(range(len(rows)),args.size))
    out=ROOT/f'paired-{args.size}-seed{args.seed}.jsonl'
    done={(r['line'],r['method']) for r in map(json.loads,out.read_text().splitlines())} if out.exists() else set()
    rng=random.Random(args.seed)
    with cf.ThreadPoolExecutor(args.workers) as pool:
        jobs=[]
        for i,row in enumerate(rows):
            opts=list(row['containers']);rng.shuffle(opts)
            if i in selected:
                for method in ('Vanilla','PICTURE'):
                    if (i+1,method) not in done:jobs.append(pool.submit(run,row,i,opts,method,args.seed))
        errors=0
        for job in cf.as_completed(jobs):
            try: row=job.result()
            except Exception as exc:
                errors+=1
                print('请求失败', type(exc).__name__, str(exc)[:180],flush=True)
                continue
            with out.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        if errors:raise SystemExit(1)
