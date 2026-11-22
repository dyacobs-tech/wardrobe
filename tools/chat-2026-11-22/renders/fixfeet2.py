"""Repair cut-outs whose matte dropped a shoe: the lower legs and feet are cut out again on their own, zoomed in
(the matting model keeps both shoes when they fill the frame), and joined to the rest of the figure's matte."""
import sys, os, io, json, base64, numpy as np, cv2
from PIL import Image
S = sys.argv[1]; N = S + '/navfix'; files = sys.argv[2].split(','); os.environ['U2NET_HOME'] = S + '/u2net'
from rembg import remove, new_session
sess = new_session('isnet-general-use'); tiles = []
feet = json.load(open(N + '/assets/onbody-cut/feet.json')); lq = json.load(open(N + '/assets/onbody-cut/lq.json'))
def measure(a):
    h, w = a.shape; op = a > 127; rows = np.where(op.any(axis=1))[0]; cols = np.where(op.any(axis=0))[0]
    return [int(h - 1 - rows.max()), round(float((cols.min() + cols.max()) / 2.0 - (w - 1) / 2.0) * 2) / 2, int(rows.min())]
for f in files:
    rgb = np.array(Image.open(N + '/assets/onbody/' + f + '.webp').convert('RGB')); h, w = rgb.shape[:2]
    full = np.array(remove(Image.fromarray(rgb), session=sess, only_mask=True, post_process_mask=True))            # the whole-figure matte, as before
    fig = full > 127; y_feet = np.where(fig.any(axis=1))[0].max(); y0 = max(0, y_feet - 330); y1 = min(h, y_feet + 60)
    crop = rgb[y0:y1]; up = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    m = np.array(remove(Image.fromarray(up), session=sess, only_mask=True, post_process_mask=True)); m = cv2.resize(m, (w, y1 - y0), interpolation=cv2.INTER_AREA)
    newa = full.copy(); band = 40                                                   # blend the two mattes over a short band so no seam shows
    wgt = np.clip((np.arange(y0, y1) - (y0 + 30)) / float(band), 0, 1)[:, None]
    newa[y0:y1] = np.maximum(full[y0:y1], (m * wgt).astype(np.uint8))
    hq = np.dstack([rgb, newa]); Image.fromarray(hq, 'RGBA').save(N + '/assets/onbody-cut-hq/' + f + '.webp', 'WEBP', quality=80, method=6)
    small = Image.fromarray(hq, 'RGBA').resize((362, 1200), Image.LANCZOS); small.save(N + '/assets/onbody-cut/' + f + '.webp', 'WEBP', quality=84, method=6)
    b = io.BytesIO(); small.resize((lq['w'], lq['h']), Image.LANCZOS).save(b, 'WEBP', quality=60); lq['lq'][f] = 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
    fk = f + '.webp' if f + '.webp' in feet['feet'] else f; feet['feet'][fk] = measure(np.array(small)[..., 3])
    al = newa[..., None].astype(np.float32) / 255; comp = (rgb * al + np.full(rgb.shape, (120, 160, 120), np.float32) * (1 - al)).astype(np.uint8)
    tiles.append(np.hstack([cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)[1000:], cv2.cvtColor(comp, cv2.COLOR_RGB2BGR)[1000:]])); print(f, 'feet', feet['feet'][fk], flush=True)
json.dump(lq, open(N + '/assets/onbody-cut/lq.json', 'w'), separators=(',', ':')); json.dump(feet, open(N + '/assets/onbody-cut/feet.json', 'w'), separators=(',', ':'))
while len(tiles) % 2: tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(S + '/relevi/feet-fixed.jpg', np.vstack([np.hstack(tiles[k:k + 2]) for k in range(0, len(tiles), 2)]), [cv2.IMWRITE_JPEG_QUALITY, 90])
