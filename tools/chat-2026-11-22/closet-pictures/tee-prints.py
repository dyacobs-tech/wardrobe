"""Put the real chest print back on the two printed tees: the print is lifted from a clean front-on picture made from
David's own photo and laid onto the redrawn tee at the same place and size relative to the body, keeping the cloth's shading."""
import os, json, numpy as np, cv2
S='/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; os.environ['U2NET_HOME']=S+'/u2net'
from rembg import new_session, remove
from PIL import Image
sess=new_session('isnet-general-use')
def gm(im): return np.array(remove(Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)),session=sess,only_mask=True))>127
def torso(m):
    ys,xs=np.where(m); top,bot=ys.min(),ys.max(); gh=bot-top+1; row=m[int(top+0.62*gh)]; c=np.where(row)[0]; return top,gh,c.min(),c.max()-c.min()+1,(c.min()+c.max())/2.0
def lift(src,kind):
    im=cv2.imread(src); m=gm(im); top,gh,tl,tw,cx=torso(m); lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB).astype(np.float32)
    core=cv2.erode(m.astype(np.uint8),np.ones((35,35),np.uint8))>0; core[:int(top+0.16*gh)]=False; core[int(top+0.62*gh):]=False     # chest only: below the neck label, above the waist
    cloth=np.median(lab[core],axis=0)
    if kind=='red': d=lab[...,1]-cloth[1]; hard=(d>22)&core; ink=np.median(lab[hard],axis=0); al=np.clip((d-8)/max(ink[1]-cloth[1]-8,1),0,1)
    else: d=cloth[0]-lab[...,0]; hard=(d>60)&core; ink=np.percentile(lab[hard],8,axis=0); ink[1:]=128; al=np.clip((d-18)/max(cloth[0]-np.median(lab[hard],axis=0)[0]-18,1),0,1)      # ink = the darkest of the print, neutral
    hard=cv2.morphologyEx(hard.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((25,25),np.uint8)); n,lb,st,_=cv2.connectedComponentsWithStats(hard,connectivity=8)
    k=1+int(np.argmax(st[1:,cv2.CC_STAT_AREA])); x,y,w,h=st[k,:4]; pad=10; x0,y0,x1,y1=max(0,x-pad),max(0,y-pad),x+w+pad,y+h+pad
    zone=cv2.dilate((lb==k).astype(np.uint8),np.ones((15,15),np.uint8))>0; al=al*zone*core.astype(np.float32) if kind!='red' else al*zone
    inkbgr=cv2.cvtColor(np.uint8([[ink]]),cv2.COLOR_LAB2BGR)[0,0].astype(np.float32)
    return {'alpha':al[y0:y1,x0:x1],'ink':inkbgr,'rw':(x1-x0)/float(tw),'rx':((x0+x1)/2.0-cx)/float(tw),'ry':((y0+y1)/2.0-top)/float(gh),'aspect':(y1-y0)/float(x1-x0)}
def lay(dst,p,out):
    im=cv2.imread(dst).astype(np.float32); m=gm(im.astype(np.uint8)); top,gh,tl,tw,cx=torso(m)
    pw=int(round(p['rw']*tw)); ph=int(round(pw*p['aspect'])); al=cv2.resize(p['alpha'],(pw,ph),interpolation=cv2.INTER_CUBIC); al=np.clip((al-0.22)/0.5,0,1); al=al*al*(3-2*al)      # crisper edges
    x0=int(round(cx+p['rx']*tw-pw/2.0)); y0=int(round(top+p['ry']*gh-ph/2.0)); reg=im[y0:y0+ph,x0:x0+pw]
    L=cv2.cvtColor(reg.astype(np.uint8),cv2.COLOR_BGR2LAB)[...,0].astype(np.float32); shade=np.clip(L/max(np.median(L),1),0.75,1.15)[...,None]
    im[y0:y0+ph,x0:x0+pw]=reg*(1-al[...,None])+p['ink'][None,None,:]*shade*al[...,None]
    cv2.imwrite(out,np.clip(im,0,255).astype(np.uint8),[cv2.IMWRITE_JPEG_QUALITY,90]); return (x0,y0,pw,ph)
F='item-1795301667680-803823'; E='item-1795301667671-850356'
for i,src,kind in ((F,S+'/tee2/raw/trial_fliks_photo.jpg','red'),(E,S+'/tee2/elcid-current.jpg','dark')):
    p=lift(src,kind); os.makedirs(S+'/tee2/plain',exist_ok=True)
    if not os.path.exists(S+'/tee2/plain/%s.jpg'%i): os.replace(S+'/tee2/final/%s.jpg'%i,S+'/tee2/plain/%s.jpg'%i)
    box=lay(S+'/tee2/plain/%s.jpg'%i,p,S+'/tee2/final/%s.jpg'%i); print(i[-10:],kind,'print width / body width %.2f'%p['rw'],'| placed at',box,'| ink BGR',np.round(p['ink']).astype(int).tolist(),'| KB',os.path.getsize(S+'/tee2/final/%s.jpg'%i)//1024)
a=cv2.imread(S+'/tee2/final/%s.jpg'%F); b=cv2.imread(S+'/tee2/final/%s.jpg'%E)
cv2.imwrite(S+'/tee2/prints-done.jpg',np.hstack([cv2.resize(a,(600,800)),cv2.resize(b,(600,800))]),[cv2.IMWRITE_JPEG_QUALITY,90])
