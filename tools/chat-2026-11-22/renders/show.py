"""A sheet for David: new outfit pictures on the app's cream, with the new piece named under each."""
import json, sys, os, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; N=S+'/navfix'
idx=json.load(open(sys.argv[1])); out=sys.argv[2]; cols=int(sys.argv[3]) if len(sys.argv)>3 else 8
W,H=250,829; CREAM=(241,233,218)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
except Exception: font=ImageFont.load_default()
tiles=[]
for j in idx:
    t=Image.new('RGB',(W,H+58),CREAM); c=Image.open(N+'/assets/onbody-cut-hq/'+j['f']).convert('RGBA').resize((W,H),Image.LANCZOS); t.paste(c,(0,0),c)
    d=ImageDraw.Draw(t); name=j['label']; words=name.split(); l1=''; l2=''
    if '|' in name: l1,l2=[x.strip() for x in name.split('|',1)]; words=[]
    for w in words:
        if d.textlength((l1+' '+w).strip(),font=font)<=W-12 and not l2: l1=(l1+' '+w).strip()
        else: l2=(l2+' '+w).strip()
    while l2 and d.textlength(l2,font=font)>W-12: l2=l2[:-2]
    d.text((W/2-d.textlength(l1,font=font)/2,H+6),l1,fill=(40,34,28),font=font)
    if l2: d.text((W/2-d.textlength(l2,font=font)/2,H+30),l2,fill=(40,34,28),font=font)
    tiles.append(np.asarray(t))
rows=[]
for s in range(0,len(tiles),cols):
    r=tiles[s:s+cols]
    while len(r)<cols: r.append(np.full_like(tiles[0],0)+np.array(CREAM,np.uint8))
    rows.append(np.hstack(r))
Image.fromarray(np.vstack(rows)).save(out,quality=88); print('sheet', out, len(tiles))
