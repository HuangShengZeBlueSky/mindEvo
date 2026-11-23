import sys, shutil
from pathlib import Path
import experiment as e
if sys.argv[1:]==['--check']:
    assert len(e.dev)==665 and len(e.valid)==150 and len(e.test)==700
    assert not e.train & e.test
    for seed in e.SEEDS:
        records=e.baseline(seed,'PICTURE',e.train|e.test)
        assert {r['line'] for r in records}==e.train|e.test and len(records)==1515
    assert (e.PLUG/'round00.js').exists() and (e.ROOT/'固定搜索指导.txt').exists()
    w=e.rows(e.RESULT/'wiring.jsonl')[0]['calls']
    assert [c['request'] for c in w]==[c['request'] for c in e.read(e.DATA/'第1题-两阶段API对读.json')['calls']]
    assert e.reference.MODEL==e.read(e.ROOT/'settings.json')['model']
    print('数据、四个种子、初始插件、接线请求已核对')
else:
    assert not sys.argv[1:]
    e.NODE=Path(shutil.which('node') or sys.exit('请先将 Node 24 加入 PATH'))
    e.main()
