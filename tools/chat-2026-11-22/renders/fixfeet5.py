"""Put back the shoe a matte dropped: its place is the mirror image of the shoe that is there; SAM selects the object in that box."""
import sys, io, json, base64, numpy as np, cv2, onnxruntime as ort
from PIL import Image
from scipy import ndimage as ndi
S = sys.argv[1]; N = S + '/navfix'; files = sys.argv[2].split(',')
MD = S + '/u2net/models/sam/sam_vit_b_01ec64.'; enc = ort.InferenceSession(MD + 'encoder.onnx', providers=['CPUExecutionProvider']); dec = ort.InferenceSession(MD + 'decoder.onnx', providers=['CPUExecutionProvider'])
feet = json.load(open(N + '/assets/onbody-cut/feet.json')); lq = json.load(open(N + '/assets/onbody-cut/lq.json')); tiles = []
def measure(a):
    h, w = a.shape; op = a > 127; rows = np.where(op.any(axis=1))[0]; cols = np.where(op.any(axis=0))[0]
    return [int(h - 1 - rows.max()), round(float((cols.min() + cols.max()) / 2.0 - (w - 1) / 2.0) * 2) / 2, int(rows.min())]
def sam(img, pts, labs):
    H, W = img.shape[:2]; emb = enc.run(None, {'input_image': img.astype(np.float32)})[0]
    c = np.concatenate([np.array(pts, np.float32), np.zeros((1, 2), np.float32)], 0)[None]; l = np.concatenate([np.array(labs, np.float32), np.array([-1], np.float32)], 0)[None]
    mi = np.zeros((1, 1, 256, 256), np.float32)
    for it in range(2):
        _, iou, lr = dec.run(None, {'image_embeddings': emb, 'point_coords': c, 'point_labels': l, 'mask_input': mi, 'has_mask_input': np.array([float(it)], np.float32), 'orig_im_size': np.array([684, 1024], np.float32)}); mi = lr.astype(np.float32)
    return cv2.resize(lr[0, 0], (1024, 1024), interpolation=cv2.INTER_LINEAR)[:H, :W] > 0
for f in files:
    rgb = np.array(Image.open(N + '/assets/onbody/' + f + '.webp').convert('RGB')); h, w = rgb.shape[:2]
    a = np.array(Image.open(N + '/assets/onbody-cut-hq/' + f + '.webp').convert('RGBA'))[..., 3]; fig = a > 127
    y_feet = np.where(fig.any(axis=1))[0].max(); legs = np.where(fig[y_feet - 400:y_feet - 200].any(axis=0))[0]; cx = (legs.min() + legs.max()) / 2.0
    band = fig[y_feet - 60:y_feet + 1]; cols = np.where(band.any(axis=0))[0]; sx0, sx1 = cols.min(), cols.max()            # the shoe that is there
    col_rows = np.where(fig[:, sx0:sx1 + 1].any(axis=1))[0]
    # top of that shoe: where the figure below the cuff gets wider than the leg; a fixed 95 px above the sole is close enough for the box
    sy0 = y_feet - 95; mx0, mx1 = int(round(2 * cx - sx1)) - 8, int(round(2 * cx - sx0)) + 8; mx0 = max(2, mx0); mx1 = min(w - 3, mx1)
    BOX = {k: tuple(v) for k, v in json.loads(sys.argv[3]).items()} if len(sys.argv) > 3 else {}          # read off the pictures: where the missing shoe is
    if f in BOX: mx0, sy0, mx1, yb = BOX[f]; y_feet = yb - 8
    Y0 = max(0, y_feet - 330); Y1 = min(h, y_feet + 60); crop = rgb[Y0:Y1]; sc = 1024.0 / max(crop.shape[:2]); up = cv2.resize(crop, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)[:1024, :1024]
    P = lambda x, y: [x * sc, (y - Y0) * sc]
    pts = [P(mx0, sy0), P(mx1, y_feet + 10), P((mx0 + mx1) / 2.0, y_feet - 38), P((mx0 + mx1) / 2.0 - 14, y_feet - 26), P(cx, y_feet - 20), P((mx0 + mx1) / 2.0, min(h - 2, y_feet + 34))]
    m = sam(up, pts, [2, 3, 1, 1, 0, 0]); m = cv2.resize(m.astype(np.uint8), (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_NEAREST)
    lim = np.zeros_like(m); lim[max(0, sy0 - Y0):min(Y1 - Y0, y_feet + 12 - Y0), mx0:mx1 + 1] = 1; m &= lim
    n, lb, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n > 1: m = (lb == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)); m = ndi.binary_fill_holes(m).astype(np.uint8)
    newa = a.copy(); newa[Y0:Y1] = np.maximum(a[Y0:Y1], (cv2.GaussianBlur(m.astype(np.float32), (0, 0), 0.8) * 255).clip(0, 255).astype(np.uint8))
    hq = np.dstack([rgb, newa]); Image.fromarray(hq, 'RGBA').save(N + '/assets/onbody-cut-hq/' + f + '.webp', 'WEBP', quality=80, method=6)
    small = Image.fromarray(hq, 'RGBA').resize((362, 1200), Image.LANCZOS); small.save(N + '/assets/onbody-cut/' + f + '.webp', 'WEBP', quality=84, method=6)
    b = io.BytesIO(); small.resize((lq['w'], lq['h']), Image.LANCZOS).save(b, 'WEBP', quality=60); lq['lq'][f] = 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
    fk = f + '.webp' if f + '.webp' in feet['feet'] else f; feet['feet'][fk] = measure(np.array(small)[..., 3])
    al = newa[..., None].astype(np.float32) / 255; cmp_ = (rgb * al + np.full(rgb.shape, (120, 160, 120), np.float32) * (1 - al)).astype(np.uint8)
    tiles.append(np.hstack([cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)[1000:], cv2.cvtColor(cmp_, cv2.COLOR_RGB2BGR)[1000:]])); print(f, 'box', (mx0, sy0, mx1, y_feet), 'shoe mask', int(m.sum()), 'px; feet', feet['feet'][fk], flush=True)
json.dump(lq, open(N + '/assets/onbody-cut/lq.json', 'w'), separators=(',', ':')); json.dump(feet, open(N + '/assets/onbody-cut/feet.json', 'w'), separators=(',', ':'))
cv2.imwrite(S + '/r2/feet-fixed-c.jpg', np.vstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 90])
