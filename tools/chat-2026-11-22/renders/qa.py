"""Review sheets: for each new outfit picture, the picture it was made from, the result and its cut-out on green."""
import json, sys, os, cv2, numpy as np
from PIL import Image
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'
J=json.load(open(S+'/r2/'+sys.argv[1])); tag=sys.argv[2]; per=int(sys.argv[3]) if len(sys.argv)>3 else 19
def rd(p,size): return cv2.cvtColor(np.asarray(Image.open(p).convert('RGB').resize(size, Image.LANCZOS)), cv2.COLOR_RGB2BGR)
def cut(p,size):
    im=Image.open(p).convert('RGBA').resize(size, Image.LANCZOS); bg=Image.new('RGBA',size,(60,120,60,255)); bg.alpha_composite(im); return cv2.cvtColor(np.asarray(bg.convert('RGB')), cv2.COLOR_RGB2BGR)
W,H=104,345; tiles=[]
for n,j in enumerate(J):
    o=S+'/r2/out/onbody/'+j['f']
    if not (os.path.exists(o) and os.path.exists(S+'/r2/out/onbody-cut/'+j['f'])): tiles.append(np.full((H*2+18,W*2,3),(0,0,255),np.uint8)); continue
    rb=S+'/r2/out/onbody/'+j['base']; base=rb if os.path.exists(rb) else S+'/navfix/assets/onbody/'+j['base']
    top=np.hstack([rd(base,(W,H)), rd(o,(W,H))]); ph=cv2.resize(cv2.imread(S+'/r2/photos/%s.jpg'%j['item']),(W,int(W*4/3)))
    pc=np.full((H,W,3),255,np.uint8); pc[:ph.shape[0]]=ph; bot=np.hstack([pc, cut(S+'/r2/out/onbody-cut/'+j['f'],(W,H))])
    bar=np.full((18,W*2,3),255,np.uint8); cv2.putText(bar,'%d %s'%(n,j['itemName'][:24]),(2,13),cv2.FONT_HERSHEY_SIMPLEX,0.36,(30,30,30),1,cv2.LINE_AA)
    tiles.append(np.vstack([top,bar,bot]))
for s in range(0,len(tiles),per):
    row=tiles[s:s+per]
    while len(row)<per: row.append(np.full_like(tiles[0],255))
    cv2.imwrite(S+'/r2/qa-%s-%d.jpg'%(tag,s//per), np.hstack([np.hstack([x,np.full((x.shape[0],6,3),255,np.uint8)]) for x in row]), [cv2.IMWRITE_JPEG_QUALITY,84])
print('sheets', (len(tiles)+per-1)//per)
