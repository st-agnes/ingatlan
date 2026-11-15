#!/usr/bin/env python3
"""Archive requested public evidence; use inherited proxy/CA and bounded reads."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib, json, urllib.request

HERE = Path(__file__).resolve().parent
DEST = HERE/'downloaded-sources'
DEST.mkdir(exist_ok=True)
STATUS = DEST/'acquisition-status.json'

def download(job):
    name, url = job['name'], job['url']
    target = DEST/name
    try:
        if not target.exists():
            request = urllib.request.Request(url, headers={'User-Agent':'Otthonra public neighborhood source archive'})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(90*1024**2+1)
            if len(data)>90*1024**2:
                raise ValueError('Source exceeds90MiB archive limit; preserve relevant pages separately')
            if name.endswith('.pdf') and not data.startswith(b'%PDF-'):
                raise ValueError('Reply is not a PDF')
            if name.endswith('.png') and not data.startswith(b'\x89PNG'):
                raise ValueError('Reply is not a PNG')
            temporary = target.with_suffix(target.suffix+'.part')
            temporary.write_bytes(data)
            temporary.replace(target)
        data=target.read_bytes()
        return {**job, 'path':str(target.relative_to(HERE.parents[2])), 'bytes':len(data),
                'sha256':hashlib.sha256(data).hexdigest(), 'status':'saved'}
    except Exception as error:
        return {**job, 'status':'failed', 'error':str(error)[:180]}

def main():
    jobs=json.loads((HERE/'download-jobs.json').read_text())['jobs']
    previous=json.loads(STATUS.read_text()) if STATUS.exists() else []
    records={row['name']:row for row in previous}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(download, job) for job in jobs]):
            row=future.result();records[row['name']]=row
            STATUS.write_text(json.dumps(sorted(records.values(), key=lambda x:x['name']),ensure_ascii=False,indent=2)+'\n')
            print(json.dumps(row,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
