"""离线展开原控制器所需的基线输入。"""
import gzip
import os
import shutil
import tempfile
from pathlib import Path

data = Path(__file__).resolve().parents[1] / 'PICTURE复现'
for source in sorted(data.glob('paired-1515-seed*.jsonl.gz')):
    target = source.with_suffix('')
    if target.exists():
        continue
    with gzip.open(source, 'rb') as inp, tempfile.NamedTemporaryFile(dir=data, delete=False) as out:
        try:
            shutil.copyfileobj(inp, out)
            out.close()
            os.replace(out.name, target)
        finally:
            Path(out.name).unlink(missing_ok=True)
