"""用冻结的 DSH 插件回答一个新问题；从 stdin 读 JSON，输出答案与实际调用次数。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parent
config=json.loads((root/'settings.json').read_text())
frozen=json.loads((root.parent/'archive/frozen.json').read_text())['round']
x=json.load(sys.stdin)
story,question,target=x['story'],x['question'],x['target']
choices=x['options']
if not all(isinstance(s,str) and s.strip() for s in (story,question,target)) or len(choices)!=2 or not all(isinstance(s,str) and s.strip() for s in choices):
    sys.exit('输入需要 story、question、target 和两个非空字符串选项。')
prompt=config['q'].format(question=question,containers_0=choices[0],containers_1=choices[1])
inputs=dict(story=story,question=question,target=target,options=choices,
            pictureFirst=config['first'].format(story=story,question=prompt,character=target),
            pictureLast=config['last'].format(perspective='{perspective}',name=target,question=prompt))
node=shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
with tempfile.TemporaryDirectory() as d:
    batch=Path(d)/'request.json';log=Path(d)/'reply.jsonl'
    batch.write_text(json.dumps([dict(key='prediction',line=1,seed=int(x.get('seed',0)),input=inputs)]))
    subprocess.run([node,str(root/'runtime.mjs'),str(root.parent/'archive/plugins'/f'round{frozen:02d}.js'),str(batch),str(log)],check=True)
    record=json.loads(log.read_text())
    print(json.dumps(dict(answer=record['calls'][-1]['text'],calls=len(record['calls']),plugin=frozen),ensure_ascii=False))
