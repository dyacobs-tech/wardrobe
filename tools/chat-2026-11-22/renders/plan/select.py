"""Choose 3 outfits for each new piece from the app's own candidates (one swap from an existing picture each)."""
import json, hashlib, base64, os, re
from collections import Counter
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'
d=json.load(open(S+'/r2/plan/cands.json')); N=d['names']; PER=3
cat=lambda i: (N.get(i) or {}).get('category') or ''
nm=lambda i: (N.get(i) or {}).get('name') or '?'
fname=lambda ids: hashlib.sha256(("+".join(sorted(ids)) + "|").encode()).hexdigest()[:16] + ".webp"
full=json.load(open(S+'/sync/latest-dl.json')); items={r['id']:r['data'] for r in full['recs'] if r['coll']=='items' and isinstance(r.get('data'),dict)}
partner_use=Counter(); shoe_use=Counter(); base_use=Counter(); jobs=[]
def bottom_desc(it):
    n=it['name']; c=(it.get('colourName') or '').lower()
    if "Levi's 517 Mid Blue" in n: return "full-length vintage bootcut jeans in a mid-blue wash with whiskered fading, the hems turned up once at the ankle,"
    if "Levi's 517 Faded Grey-Blue" in n: return "full-length vintage bootcut jeans in a heavily faded grey-blue wash, the hems turned up once at the ankle,"
    if "Levi's 517 Light Blue Jeans" in n: return "full-length vintage bootcut jeans in a faded light-blue wash with pressed creases, hems not turned up,"
    if 'Patchwork' in n: return "full-length light-blue jeans with patchwork panels"
    if n.startswith('FRAME'): return "full-length slim straight jeans in a %s wash" % {'light blue':'light-blue','dark indigo':'dark indigo','mid blue':'mid-blue','black':'black','grey-blue':'faded grey-blue'}.get(c,c)
    if 'Grey Striped Drawstring' in n: return "full-length relaxed grey striped trousers with a drawstring waist"
    if 'Burgundy & White Striped' in n: return "full-length wide-leg burgundy and white striped trousers"
    if 'Seersucker' in n: return "full-length ivory seersucker trousers"
    if 'Isaia White' in n: return "full-length white trousers with a drawstring waist"
    if 'Isaia Navy' in n: return "full-length navy trousers with a drawstring waist"
    if 'Black Cotton Chinos' in n: return "full-length flat-front black cotton chinos"
    if 'Stone Grey Cotton Chinos' in n: return "full-length flat-front stone-grey cotton chinos"
    if 'Off-White Cotton Trousers' in n: return "full-length flat-front off-white cotton trousers"
    if 'Di Sondrio Beige Lightweight' in n: return "full-length flat-front khaki cotton chinos"
    if 'Stone Non-Iron' in n: return "full-length flat-front light stone cotton chinos"
    raise SystemExit('no description for '+n)
def tee_desc(it):
    n=it['name']; c=(it.get('colourName') or '').lower() or 'plain'
    kind='short-sleeve knit T-shirt' if 'Knit' in n else 'short-sleeve crew-neck T-shirt'
    extra=''
    if 'Red Collar' in n: extra=' with a thin red trim at the collar'
    if 'Pocket' in n: extra=' with a chest pocket'
    if 'Graphic' in n or 'Barbershop' in n: extra=' with the printed graphic'
    return "a %s %s%s" % (c, kind, extra)
order=sorted(d['news'], key=lambda x: (x['category']!='Tees', x['name']))
for it in order:
    cs=d['cands'].get(it['id']) or []; slot='t' if it['category']=='Tees' else 'b'; picked=[]; shoes=set(); partners=set()
    for rnd in range(PER):
        best=None
        for c in cs:
            if c['slot']!=slot: continue
            partner=c['b'] if slot=='t' else c['t']
            if c['s'] in shoes or partner in partners: continue
            # the picture it is made from: prefer one where the swapped-out garment is the same kind
            def bscore(b):
                rc=cat(b['rep']); s=0.0
                if slot=='t': s+= 0.6 if rc in ('Tees','Polos') else (0.2 if rc=='Shirts' else -0.4)
                else: s+= 0.6 if rc==it['category'] else (0.3 if rc in ('Trousers','Jeans') else -3.0)     # never from shorts
                return s-0.25*base_use[b['f']]
            b=max(c['bases'], key=bscore); bs=bscore(b)
            if bs<-1: continue
            v=c['score']+bs-0.35*partner_use[partner]-0.12*shoe_use[c['s']]-(0.6 if c['l'] else 0)+(0.15 if 2 in c['levels'] else 0)
            if best is None or v>best[0]: best=(v,c,b,partner)
        if not best: break
        v,c,b,partner=best; picked.append((c,b)); shoes.add(c['s']); partners.add(partner); partner_use[partner]+=1; shoe_use[c['s']]+=1; base_use[b['f']]+=1
    src=items[it['id']]; ph=src.get('photo') or ''
    if ph.startswith('data:'): open(S+'/r2/photos/%s.jpg'%it['id'],'wb').write(base64.b64decode(ph.split(',',1)[1]))
    elif os.path.exists(S+'/navfix/'+ph): import shutil; shutil.copy(S+'/navfix/'+ph, S+'/r2/photos/%s.jpg'%it['id']); print('photo from app file:', it['name'], ph)
    else: print('SKIP (photo is not a picture I can read):', it['name'], ph[:80]); continue
    for c,b in picked:
        ids=[x for x in (c['t'],c['b'],c['s'],c['l']) if x]; assert '|'.join(sorted(ids))==c['key'], (c['key'], ids)
        if slot=='t': prompt="%s exactly like the product photo, worn %s; keep the trousers, the shoes, the face, the pose and everything else exactly as they are" % (tee_desc(src), 'tucked into the trousers' if c['tuck'] else 'untucked over the waistband')
        else: prompt="%s exactly like the product photo, worn with the same top; keep the top, the shoes, the face, the pose and everything else exactly as they are" % bottom_desc(src)
        jobs.append({'item':it['id'],'itemName':it['name'],'slot':slot,'key':c['key'],'f':fname(ids),'base':b['f'],'baseKey':b['k'],'replaces':b['rep'],'replacesName':nm(b['rep']),'t':c['t'],'b':c['b'],'s':c['s'],'l':c['l'],'tuck':c['tuck'],'levels':c['levels'],'score':round(c['score'],2),'prompt':prompt})
assert len(set(j['f'] for j in jobs))==len(jobs)
json.dump(jobs,open(S+'/r2/jobs.json','w'),indent=1)
print('jobs', len(jobs), '| per piece', Counter(Counter(j['item'] for j in jobs).values()), '| credits', 2*len(jobs))
print('distinct pictures used as a start:', len(set(j['base'] for j in jobs)), '| most reused', Counter(j['base'] for j in jobs).most_common(3))
print('partners most used:', [(nm(k)[:28],v) for k,v in partner_use.most_common(6)]); print('shoes most used:', [(nm(k)[:28],v) for k,v in shoe_use.most_common(5)])
print('with a jacket:', sum(1 for j in jobs if j['l']), '| tucked:', sum(1 for j in jobs if j['tuck']), '| swapped-out kinds:', Counter(cat(j['replaces']) for j in jobs))
for j in jobs[:4]+jobs[60:64]: print(' ', j['itemName'][:30].ljust(30), '=', nm(j['t'])[:24], '+', nm(j['b'])[:24], '+', nm(j['s'])[:22], ('+ '+nm(j['l'])[:16]) if j['l'] else '', '| from', j['replacesName'][:24], '|', j['score'])
