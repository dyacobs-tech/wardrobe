"""Run swap.py for the jobs in jobs.json (all, or the indices given), 3 at a time. Resumable: finished files are skipped."""
import sys, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; R = S + '/r2'
jobs = json.load(open(R + '/' + (os.environ.get('JOBS') or 'jobs.json'))); idx = [int(a) for a in sys.argv[1:]] or list(range(len(jobs)))
def one(i):
    j = jobs[i]; redrawn = R + '/out/onbody/' + j['base']; base = redrawn if os.path.exists(redrawn) else S + '/navfix/assets/onbody/' + j['base']
    try:
        p = subprocess.run(['python3', 'swap.py', base, 'photos/%s.jpg' % j['item'], j['f'], j['prompt']], cwd=R, capture_output=True, text=True, timeout=600)
        line = (p.stdout.strip().split('\n') or [''])[-1][:150]
        if p.returncode != 0: line = 'FAILED %s rc %d | %s | %s' % (j['f'], p.returncode, line, p.stderr.strip().split('\n')[-1][:160])
    except subprocess.TimeoutExpired: line = 'FAILED %s timeout' % j['f']
    print(i, line, flush=True)
with ThreadPoolExecutor(int(os.environ.get('PAR') or 3)) as ex: list(ex.map(one, idx))
