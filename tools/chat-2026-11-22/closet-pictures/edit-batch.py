"""Redo tee pictures in the look of the earlier (legacy) tees. FASHN edit, 1 credit per try.
usage: run.py jobs.json   jobs = [{"out": name, "image": path, "prompt": text}]   Resumable: finished outputs are skipped."""
import sys, json, base64, io, time, os, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'
jobs=json.load(open(sys.argv[1])); lock=threading.Lock()
def du(p):
    b=io.BytesIO(); Image.open(p).convert('RGB').save(b,'JPEG',quality=94); return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
def call(method,url,body=None):
    for t in range(4):
        req=urllib.request.Request(url,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer placeholder','Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=180) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            b=e.read().decode('utf-8','replace')[:300]
            if e.code in (429,500,502,503,504) and t<3: time.sleep(6*(t+1)); continue
            return {'_http':e.code,'_body':b}
        except Exception as e:
            if t<3: time.sleep(6*(t+1)); continue
            return {'_err':str(e)[:200]}
def one(j):
    out=S+'/tee2/raw/'+j['out']+'.jpg'
    if os.path.exists(out): return
    r=call('POST','https://api.fashn.ai/v1/run',{'model_name':'edit','inputs':{'image':du(j['image']),'prompt':j['prompt'],'return_base64':True,'output_format':'jpeg'}}); pid=r.get('id') if isinstance(r,dict) else None
    if not pid:
        with lock: print('RUN ERROR',j['out'],json.dumps(r)[:300],flush=True)
        return
    st={}
    for _ in range(100):
        time.sleep(3); st=call('GET','https://api.fashn.ai/v1/status/'+pid) or {}
        if st.get('status') in ('completed','failed','canceled'): break
    o=(st.get('output') or [None])[0]
    with lock:
        if st.get('status')=='completed' and o and o.startswith('data:'): open(out,'wb').write(base64.b64decode(o.split(',',1)[1])); print('ok',j['out'],flush=True)
        else: print('FAILED',j['out'],st.get('status'),json.dumps(st.get('error'))[:200],flush=True)
c0=(call('GET','https://api.fashn.ai/v1/credits') or {}).get('credits',{}).get('total')
with ThreadPoolExecutor(3) as ex: list(ex.map(one,jobs))
c1=(call('GET','https://api.fashn.ai/v1/credits') or {}).get('credits',{}).get('total'); print('credits',c0,'->',c1,flush=True)
