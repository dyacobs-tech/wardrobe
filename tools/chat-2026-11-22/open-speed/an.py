import json, collections, sys
p=json.load(open(sys.argv[1])); nodes={n['id']:n for n in p['nodes']}; dt=p['timeDeltas']; samples=p['samples']
self_t=collections.Counter()
for s,d in zip(samples,dt): self_t[s]+=d
parent={}
for n in p['nodes']:
    for c in n.get('children',[]): parent[c]=n['id']
def name(n):
    cf=n['callFrame']; u=cf['url'].split('/')[-1][:26]; return f"{cf['functionName'] or '(anon)'} {u}:{cf['lineNumber']+1}"
total=sum(dt)/1000; incl=collections.Counter(); selfn=collections.Counter()
for nid,t in self_t.items():
    selfn[name(nodes[nid])]+=t; seen=set(); x=nid
    while x is not None:
        nm=name(nodes[x])
        if nm not in seen: incl[nm]+=t; seen.add(nm)
        x=parent.get(x)
idle=sum(t for n,t in selfn.items() if n.startswith('(idle)'))
print(f'profile span {total:.0f} ms | busy {(total-idle/1000):.0f} ms | gc {selfn.get("(garbage collector) :0",0)/1000:.0f} ms')
# busy per second
ts=0; buckets=collections.Counter()
for s,d in zip(samples,dt):
    ts+=d
    if not name(nodes[s]).startswith('(idle)'): buckets[int(ts/1e6)]+=d
print('busy ms by second:', ' '.join(f"{k}s:{v/1000:.0f}" for k,v in sorted(buckets.items())))
N=int(sys.argv[2]) if len(sys.argv)>2 else 28
print('--- top inclusive')
for n,t in [x for x in incl.most_common(200) if not x[0].startswith(('(root)','(idle)','(program)'))][:N]: print(f'  {t/1000:7.0f} ms  {n}')
print('--- top self')
for n,t in selfn.most_common(14): print(f'  {t/1000:7.0f} ms  {n}')
