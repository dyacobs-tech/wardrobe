"""Put finished outfit pictures into the app's assets.
usage: integrate.py S <list.json>   list = [{"f": "<hash>.webp", "k": "<composer key>"}]
Writes assets/onbody/<f> (386x1280), assets/onbody-cut/<f> (362x1200 cut-out), assets/onbody-cut-hq/<f> (386x1280 cut-out),
the placeholder in lq.json and the feet entry in feet.json. A key that is not in assets/onbody/manifest.json yet is added
there and to assets/onbody-cut/manifest.json. Existing files are replaced in place."""
import sys, os, io, json, base64, numpy as np
from PIL import Image
S = sys.argv[1]; N = S + '/navfix'; R = S + '/r2'; os.environ['U2NET_HOME'] = S + '/u2net'
from rembg import remove, new_session
jobs = json.load(open(sys.argv[2])); sess = new_session('isnet-general-use')
feet = json.load(open(N + '/assets/onbody-cut/feet.json')); lq = json.load(open(N + '/assets/onbody-cut/lq.json'))
man = json.load(open(N + '/assets/onbody/manifest.json')); cman = json.load(open(N + '/assets/onbody-cut/manifest.json')); known = {e['k']: e['f'] for e in man['r']}
def measure(path):
    a = np.asarray(Image.open(path).convert('RGBA'))[..., 3]; h, w = a.shape; op = a > 127
    rows = np.where(op.any(axis=1))[0]; cols = np.where(op.any(axis=0))[0]
    return [int(h - 1 - rows.max()), round(float((cols.min() + cols.max()) / 2.0 - (w - 1) / 2.0) * 2) / 2, int(rows.min())]
done = added = 0
for j in jobs:
    f = j['f']; k = f[:-5]; src = R + '/out/onbody/' + f; cut = R + '/out/onbody-cut/' + f
    if not (os.path.exists(src) and os.path.exists(cut)): print('MISSING', f); continue
    if j['k'] in known: assert known[j['k']] == f, (j['k'], known[j['k']], f)
    im = Image.open(src).convert('RGB'); assert im.size == (386, 1280), im.size
    im.save(N + '/assets/onbody/' + f, 'WEBP', quality=82, method=6)
    c = Image.open(cut).convert('RGBA'); assert c.size == (362, 1200), c.size
    c.save(N + '/assets/onbody-cut/' + f, 'WEBP', quality=84, method=6)
    hqfix = R + '/out/onbody-cut-hq/' + f                                 # a repaired zoom cut-out, when one was made
    if os.path.exists(hqfix): Image.open(hqfix).convert('RGBA').save(N + '/assets/onbody-cut-hq/' + f, 'WEBP', quality=80, method=6)
    else:
        hq = remove(im, session=sess, post_process_mask=True); ca = np.asarray(hq).astype(float) / 255; ca[..., :3] = np.asarray(im).astype(float) / 255
        Image.fromarray((np.clip(ca, 0, 1) * 255).round().astype(np.uint8), 'RGBA').save(N + '/assets/onbody-cut-hq/' + f, 'WEBP', quality=80, method=6)
    b = io.BytesIO(); Image.open(N + '/assets/onbody-cut/' + f).convert('RGBA').resize((lq['w'], lq['h']), Image.LANCZOS).save(b, 'WEBP', quality=60)
    lq['lq'][f if f in lq['lq'] else k] = 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
    fk = f if f in feet['feet'] else k; feet['feet'][fk] = measure(N + '/assets/onbody-cut/' + f); done += 1
    if j['k'] not in known:
        man['r'].append({'k': j['k'], 'f': f}); known[j['k']] = f; cman['map'][f] = 'assets/onbody-cut/' + f; added += 1
man['count'] = len(man['r'])
dump = lambda o, p: open(p, 'w').write(json.dumps(o, separators=(',', ':')))
dump(lq, N + '/assets/onbody-cut/lq.json'); dump(feet, N + '/assets/onbody-cut/feet.json'); dump(man, N + '/assets/onbody/manifest.json'); dump(cman, N + '/assets/onbody-cut/manifest.json')
print('integrated', done, 'of', len(jobs), '| new keys added', added, '| manifest now', man['count'], '| cut map', len(cman['map']))
