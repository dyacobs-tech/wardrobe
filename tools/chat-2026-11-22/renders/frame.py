"""Flag pictures whose figure moved or changed size against the picture they were made from (a zoomed or cropped result)."""
import json, sys, os, numpy as np
from PIL import Image
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'
J=json.load(open(S+'/r2/'+sys.argv[1]))
def m(p):
    a=np.asarray(Image.open(p).convert('RGBA').resize((362,1200)))[...,3]>127; rows=np.where(a.any(axis=1))[0]; cols=np.where(a.any(axis=0))[0]
    return rows.min(), 1199-rows.max(), cols.min(), cols.max()
bad=[]
for n,j in enumerate(J):
    o=S+'/r2/out/onbody-cut/'+j['f']
    if not os.path.exists(o): continue
    rb=S+'/r2/out/onbody-cut/'+j['base']; b=rb if os.path.exists(rb) else S+'/navfix/assets/onbody-cut/'+j['base']
    t0,b0,l0,r0=m(b); t1,b1,l1,r1=m(o); h0=1200-t0-b0; h1=1200-t1-b1
    if b1<12 or abs(h1-h0)>0.04*h0 or abs(t1-t0)>30: bad.append(n); print('FRAME', n, j['f'], j['itemName'][:30], '| base top/bottom', t0, b0, '-> new', t1, b1, '| height', h0, '->', h1)
print('checked', sum(1 for j in J if os.path.exists(S+'/r2/out/onbody-cut/'+j['f'])), '| flagged', bad)
