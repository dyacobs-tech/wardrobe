import sys, json, base64, io, time, hashlib, urllib.request, numpy as np
from PIL import Image
from skimage import color
from skimage.registration import phase_cross_correlation
from scipy.ndimage import shift as ndshift, gaussian_filter
base, item_photo, out_name, PROMPT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
import os
if os.path.exists('out/onbody-cut/' + out_name): print(out_name, 'ok | already done'); sys.exit(0)
def du(path):
    b = io.BytesIO(); Image.open(path).convert('RGB').save(b, 'JPEG', quality=95); return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None, headers={'content-type': 'application/json', 'authorization': 'Bearer proxy-injected'})
    with urllib.request.urlopen(req, timeout=120) as r: return json.load(r)
before = call('GET', 'https://api.fashn.ai/v1/credits')['credits']['total']
if before < 2: print('STOP: credits', before); sys.exit(2)
inputs = {'model_image': du(base), 'product_image': du(item_photo), 'resolution': '1k', 'generation_mode': 'balanced', 'num_images': 1, 'output_format': 'jpeg', 'return_base64': True, 'seed': int(os.environ.get('SEED', '42')), 'prompt': PROMPT}
pid = call('POST', 'https://api.fashn.ai/v1/run', {'model_name': 'tryon-max', 'inputs': inputs})['id']
for i in range(90):
    time.sleep(4); st = call('GET', 'https://api.fashn.ai/v1/status/' + pid)
    if st.get('status') in ('completed', 'failed', 'canceled'): break
if st.get('status') != 'completed': print('FAILED', st.get('error')); sys.exit(1)
out = st['output'][0]; raw = base64.b64decode(out.split(',', 1)[1]) if out.startswith('data:') else urllib.request.urlopen(out).read()
open('raw-' + out_name + '.jpg', 'wb').write(raw)
src = Image.open(io.BytesIO(raw)).convert('RGB'); W, H = src.size; cw = round(H * 386 / 1280); x0 = (W - cw) // 2
N = np.asarray(src.crop((x0, 0, x0 + cw, H)).resize((386, 1280), Image.LANCZOS)).astype(float) / 255
O = np.asarray(Image.open(base).convert('RGB')).astype(float) / 255
h, w = O.shape[:2]
g = lambda a: a[: int(h * .17), int(w * .25): int(w * .75)].mean(-1)
sh, _, _ = phase_cross_correlation(g(N), g(O), upsample_factor=10)
Os = np.stack([ndshift(O[..., c], sh, order=1, mode='nearest') for c in range(3)], -1)
lab = color.rgb2lab(Os); skin = (lab[..., 1] > 7) & (lab[..., 2] > 10) & (lab[..., 0] > 35)
cx0, cx1 = int(w * .44), int(w * .56); neck = int(h * .14)
for y in range(int(h * .10), int(h * .26)):
    if skin[y, cx0:cx1].mean() > 0.35: neck = y
chin = min(neck - 3, int(h * .158))   # head only: never the old collar
mask = np.zeros((h, w)); mask[: max(0, chin), int(w * .30): int(w * .70)] = 1
mask = gaussian_filter(mask, 2.5)
C = Os * mask[..., None] + N * (1 - mask[..., None])
Image.fromarray((np.clip(C, 0, 1) * 255).round().astype(np.uint8)).save('out/onbody/' + out_name, quality=92)
from rembg import remove, new_session
small = Image.open('out/onbody/' + out_name).convert('RGB').resize((362, 1200), Image.LANCZOS)
cut = remove(small, session=new_session('isnet-general-use'), post_process_mask=True)
ca = np.asarray(cut).astype(float) / 255; ca[..., :3] = np.asarray(small).astype(float) / 255
Image.fromarray((np.clip(ca, 0, 1) * 255).round().astype(np.uint8), 'RGBA').save('out/onbody-cut/' + out_name, quality=92)
after = call('GET', 'https://api.fashn.ai/v1/credits')['credits']['total']
print(out_name, 'ok | neck', neck, '| credits', before, '->', after, flush=True)
