"""Fit each redrawn tee to the closet card exactly as the earlier tees sit (same picture geometry as its base), set the
cloth to the target colour, and normalise the backdrop to the closet cream."""
import sys, os, json, numpy as np, cv2
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; os.environ['U2NET_HOME']=S+'/u2net'
from rembg import new_session, remove
from PIL import Image
sess=new_session('isnet-general-use'); plan=json.load(open(S+'/tee2/plan.json')); CREAM=np.array([218,233.5,241],np.float32); W,H=900,1200
only=set(sys.argv[1:]); rep={}
def hex2lab(h):
    h=h.lstrip('#'); bgr=np.uint8([[[int(h[4:6],16),int(h[2:4],16),int(h[0:2],16)]]]); return cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB)[0,0].astype(np.float32)
for i,p in plan.items():
    if only and i not in only: continue
    src=S+'/tee2/raw/%s.jpg'%i
    if not os.path.exists(src): print('MISSING',i); continue
    im=cv2.imread(src); h,w=im.shape[:2]; f=W/float(w); r=cv2.resize(im,(W,int(round(h*f))),interpolation=cv2.INTER_LANCZOS4); y0=(r.shape[0]-H)//2; im=r[y0:y0+H].astype(np.float32)
    a=np.array(remove(Image.fromarray(cv2.cvtColor(im.astype(np.uint8),cv2.COLOR_BGR2RGB)),session=sess,only_mask=True)).astype(np.float32)/255
    # cloth colour -> target (hue and chroma shifted, lightness scaled), shading kept
    lab=cv2.cvtColor(im.astype(np.uint8),cv2.COLOR_BGR2LAB).astype(np.float32); core=cv2.erode((a>0.6).astype(np.uint8),np.ones((25,25),np.uint8))>0; px=lab[core]
    L=px[:,0]; lo,hi=np.percentile(L,20),np.percentile(L,80); cur=np.median(px[(L>=lo)&(L<=hi)],axis=0); tgt=hex2lab(p['target'])
    if not p.get('nocolour'):
        g=cv2.GaussianBlur((a>0.5).astype(np.float32),(0,0),1.5)
        out=lab.copy(); k=tgt[0]/max(cur[0],1.0); k=float(np.clip(k,0.6,1.6))
        out[...,0]=np.clip(lab[...,0]*k,0,255) if tgt[0]<200 else np.clip(255-(255-lab[...,0])*((255-tgt[0])/max(255-cur[0],1.0)),0,255)
        out[...,1]=np.clip(lab[...,1]+(tgt[1]-cur[1]),0,255); out[...,2]=np.clip(lab[...,2]+(tgt[2]-cur[2]),0,255)
        lab=lab*(1-g[...,None])+out*g[...,None]; im=cv2.cvtColor(np.clip(lab,0,255).astype(np.uint8),cv2.COLOR_LAB2BGR).astype(np.float32)
    # backdrop -> closet cream (the garment and its soft shadow untouched in shape)
    far=cv2.dilate((a>0.2).astype(np.uint8),np.ones((61,61),np.uint8))==0; bg=np.median(im[far],axis=0) if far.sum()>2000 else np.median(np.vstack([im[:12].reshape(-1,3),im[:,:12].reshape(-1,3)]),axis=0)
    gain=CREAM/np.maximum(bg,1); wgt=1-cv2.GaussianBlur(cv2.dilate((a>0.3).astype(np.float32),np.ones((9,9),np.uint8)),(0,0),5)[...,None]
    im=np.clip(im*(1+(gain-1)*wgt),0,255)
    ys,xs=np.where(a>0.5); rep[i]={'w':round((xs.max()-xs.min()+1)/W,3),'h':round((ys.max()-ys.min()+1)/H,3),'top':round(ys.min()/H,3),'from':'#%02x%02x%02x'%tuple(int(v) for v in cv2.cvtColor(np.uint8([[cur]]),cv2.COLOR_LAB2BGR)[0,0][::-1]),'to':p['target']}
    pth=S+'/tee2/final/%s.jpg'%i; q=88
    while True:
        cv2.imwrite(pth,im.astype(np.uint8),[cv2.IMWRITE_JPEG_QUALITY,q])
        if os.path.getsize(pth)<=125*1024 or q<=72: break
        q-=4
    rep[i]['kb']=os.path.getsize(pth)//1024
json.dump(rep,open(S+'/tee2/finish.json','w'),indent=1)
for i,v in rep.items(): print(i[-10:], plan[i]['name'][:36].ljust(36), v)
