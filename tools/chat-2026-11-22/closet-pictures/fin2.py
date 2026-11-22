"""Fit a chosen studio render to the closet card (900x1200, closet cream), scaled by the item's outline.
usage: fin2.py S jobs.json   jobs = [{"id":..., "raw": path, "fit":[fw,fh,cy]}]"""
import sys, os, json, numpy as np, cv2
S = sys.argv[1]; os.environ['U2NET_HOME'] = S + '/u2net'
from rembg import new_session, remove
from PIL import Image
sess = new_session('isnet-general-use'); jobs = json.load(open(sys.argv[2]))
CREAM = np.array([218, 233.5, 241], np.float32); W, H = 900, 1200; out = {}
for j in jobs:
    im = cv2.imread(j['raw']); h, w = im.shape[:2]
    a = np.array(remove(Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)), session=sess, only_mask=True)).astype(np.float32) / 255
    far = cv2.dilate((a > 0.2).astype(np.uint8), np.ones((61, 61), np.uint8)) == 0
    bg = np.median(im[far], axis=0) if far.sum() > 2000 else np.median(np.vstack([im[:12].reshape(-1, 3), im[:, :12].reshape(-1, 3)]), axis=0)
    gain = CREAM / np.maximum(bg, 1); wgt = 1 - cv2.GaussianBlur(cv2.dilate((a > 0.3).astype(np.float32), np.ones((9, 9), np.uint8)), (0, 0), 5)[..., None]
    im2 = np.clip(im.astype(np.float32) * (1 + (gain - 1) * wgt), 0, 255)
    ys, xs = np.where(a > 0.5); bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max(); bw, bh = bx1 - bx0 + 1, by1 - by0 + 1
    fw, fh, cy = j['fit']; f = min(fw * W / bw, fh * H / bh, 1.9)
    canvas = np.empty((H, W, 3), np.float32); canvas[:] = CREAM
    r = cv2.resize(im2, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4 if f > 1 else cv2.INTER_AREA)
    ox = int(round(W / 2 - (bx0 + bw / 2.0) * f)); oy = int(round(H * cy - (by0 + bh / 2.0) * f))
    fe = np.ones(r.shape[:2], np.float32); k = 28
    for i in range(k): v = (i + 1) / float(k + 1); fe[i, :] = np.minimum(fe[i, :], v); fe[-1 - i, :] = np.minimum(fe[-1 - i, :], v); fe[:, i] = np.minimum(fe[:, i], v); fe[:, -1 - i] = np.minimum(fe[:, -1 - i], v)
    X0, Y0 = max(0, ox), max(0, oy); X1, Y1 = min(W, ox + r.shape[1]), min(H, oy + r.shape[0])
    sub = r[Y0 - oy:Y1 - oy, X0 - ox:X1 - ox]; fs = fe[Y0 - oy:Y1 - oy, X0 - ox:X1 - ox][..., None]
    canvas[Y0:Y1, X0:X1] = sub * fs + canvas[Y0:Y1, X0:X1] * (1 - fs); c = np.clip(canvas, 0, 255).astype(np.uint8)
    # the item's own middle colour, for the colour chip
    core = cv2.erode((a > 0.6).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    med = np.median(im[core], axis=0) if core.sum() > 500 else np.median(im[a > 0.6], axis=0)
    p = S + '/fin2/final/%s.jpg' % j['id']; q = 86
    while True:
        cv2.imwrite(p, c, [cv2.IMWRITE_JPEG_QUALITY, q])
        if os.path.getsize(p) <= 120 * 1024 or q <= 70: break
        q -= 4
    out[j['id']] = {'kb': os.path.getsize(p) // 1024, 'hex': '#%02x%02x%02x' % (int(med[2]), int(med[1]), int(med[0])), 'f': round(float(f), 2)}
json.dump(out, open(S + '/fin2/out.json', 'w'), indent=1); print(len(out), 'done; largest KB', max(v['kb'] for v in out.values()))
