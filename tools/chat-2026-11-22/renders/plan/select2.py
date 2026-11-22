"""Second pass: outfits that pair a new tee with new trousers or jeans, each made from a first-pass picture by one more swap."""
import json, hashlib, sys
from collections import Counter
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'
sys.path.insert(0, S+'/r2/plan')
J1=json.load(open(S+'/r2/jobs.json')); both=json.load(open(S+'/r2/plan/both.json'))['both']; N=json.load(open(S+'/r2/plan/cands.json'))['names']
full=json.load(open(S+'/sync/latest-dl.json')); items={r['id']:r['data'] for r in full['recs'] if r['coll']=='items' and isinstance(r.get('data'),dict)}
nm=lambda i: (N.get(i) or {}).get('name') or (items.get(i) or {}).get('name') or '?'
fname=lambda ids: hashlib.sha256(("+".join(sorted(ids)) + "|").encode()).hexdigest()[:16] + ".webp"
ALEX='item-1794868007730-581626'
def tee_desc(it):
    n=it['name']; c=(it.get('colourName') or '').lower() or 'plain'
    if it['id']==ALEX: return "a white short-sleeve crew-neck T-shirt with a chest pocket"
    kind='short-sleeve knit T-shirt' if 'Knit' in n else 'short-sleeve crew-neck T-shirt'; extra=''
    if 'Red Collar' in n: extra=' with a thin red trim at the collar'
    if 'Pocket' in n: extra=' with a chest pocket'
    if 'Graphic' in n or 'Barbershop' in n: extra=' with the printed graphic'
    return "a %s %s%s" % (c, kind, extra)
b1={}                                   # first-pass pictures of a new bottom, no jacket: (bottom, shoes) -> job
for j in J1:
    if j['slot']=='b' and not j['l']: b1.setdefault((j['b'],j['s']),j)
done={j['key'] for j in J1}; cands=[c for c in both if (c['b'],c['s']) in b1 and c['key'] not in done]
tees=sorted({c['t'] for c in cands}); bottoms=sorted({c['b'] for c in cands})
print('usable outfits', len(cands), '| tees', len(tees), '| bottoms', len(bottoms))
buse=Counter(); suse=Counter(); tuse=Counter(); jobs=[]; taken=set()
def pick(pool, n=1):
    out=[]
    for _ in range(n):
        best=None
        for c in pool:
            if c['key'] in taken: continue
            base=b1[(c['b'],c['s'])]; v=c['score']-0.6*buse[c['b']]-0.25*suse[c['s']]-0.6*tuse[c['t']]+(0.2 if base['tuck']==c['tuck'] else 0)
            if best is None or v>best[0]: best=(v,c)
        if not best: break
        c=best[1]; taken.add(c['key']); buse[c['b']]+=1; suse[c['s']]+=1; tuse[c['t']]+=1; out.append(c)
    return out
chosen=[]
for t in tees: chosen+=pick([c for c in cands if c['t']==t], 2 if t==ALEX else 1)
for b in bottoms:
    if not buse[b]: chosen+=pick([c for c in cands if c['b']==b], 1)
for c in chosen:
    base=b1[(c['b'],c['s'])]; ids=[c['t'],c['b'],c['s']]; assert '|'.join(sorted(ids))==c['key']
    it=dict(items[c['t']], id=c['t'])
    prompt="%s exactly like the product photo, worn %s; keep the trousers, the shoes, the face, the pose and everything else exactly as they are" % (tee_desc(it), 'tucked into the trousers' if c['tuck'] else 'untucked over the waistband')
    jobs.append({'item':c['t'],'itemName':it['name'],'slot':'t','key':c['key'],'f':fname(ids),'base':base['f'],'baseKey':base['key'],'replaces':base['t'],'replacesName':nm(base['t']),'t':c['t'],'b':c['b'],'s':c['s'],'l':None,'tuck':c['tuck'],'levels':c['levels'],'score':round(c['score'],2),'prompt':prompt})
assert len({j['f'] for j in jobs})==len(jobs) and not ({j['f'] for j in jobs} & {j['f'] for j in J1})
json.dump(jobs,open(S+'/r2/jobs2.json','w'),indent=1)
print('second-pass jobs', len(jobs), '| credits', 2*len(jobs), '| bottoms covered', len({j['b'] for j in jobs}), 'of', len(bottoms), '| tees covered', len({j['t'] for j in jobs}))
for j in jobs[:6]: print(' ', nm(j['t'])[:30].ljust(30), '+', nm(j['b'])[:30].ljust(30), '+', nm(j['s'])[:24], '| from', j['replacesName'][:22], '|', j['score'])
