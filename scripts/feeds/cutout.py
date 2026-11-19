#!/usr/bin/env python3
"""Cut a product photo out and composite it on off-white #F6F2EA.

Uses rembg when ``rembg[cpu]`` is installed; otherwise falls back to the
local IS-Net general model via onnxruntime (same family rembg uses).
Never leaves a grey studio backdrop in the saved file.

    python3 scripts/feeds/cutout.py --in img.jpg --out assets/editimg/xxx.webp
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from PIL import Image

OFFWHITE = (0xF6, 0xF2, 0xEA)  # #F6F2EA
MAX_PX = 640
QUALITY = 80

# rembg's default cache; also the models already on this box
MODEL_CANDIDATES = [
    Path(os.environ["REMBG_MODEL"]) if os.environ.get("REMBG_MODEL") else None,
    Path.home() / ".rembg" / "models" / "isnet-general-use" / "isnet-general-use.onnx",
    Path.home() / ".u2net" / "isnet-general-use.onnx",
]


def _session_rembg():
    try:
        from rembg import new_session, remove  # type: ignore
        session = new_session("isnet-general-use")
        def run(im: Image.Image) -> Image.Image:
            return remove(im, session=session)
        return run
    except Exception:
        return None


_ORT_SESSION = None


def _session_onnx():
    global _ORT_SESSION
    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError:
        return None
    model = next((p for p in MODEL_CANDIDATES if p is not None and p.exists()), None)
    if not model:
        return None
    if _ORT_SESSION is None:
        _ORT_SESSION = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])

    def run(im: Image.Image) -> Image.Image:
        sess = _ORT_SESSION
        inp = sess.get_inputs()[0]
        name, shape = inp.name, inp.shape
        # expected [1, 3, 1024, 1024]
        h = int(shape[2] or 1024)
        w = int(shape[3] or 1024)
        rgb = im.convert("RGB")
        resized = rgb.resize((w, h), Image.Resampling.LANCZOS)
        arr = np.asarray(resized).astype("float32") / 255.0
        # rembg IS-Net normalization: mean 0.5, std 0.5
        arr = (arr - 0.5) / 0.5
        arr = arr.transpose(2, 0, 1)[None, ...]
        pred = sess.run(None, {name: arr})[0]
        mask = pred[0, 0]
        # squash to 0..1
        mask = (mask - mask.min()) / (mask.max() - mask.min() + 1e-6)
        mask_im = Image.fromarray((mask * 255).astype("uint8"), "L").resize(rgb.size, Image.Resampling.LANCZOS)
        cut = Image.new("RGBA", rgb.size)
        cut.paste(rgb, mask=mask_im)
        cut.putalpha(mask_im)
        return cut

    return run


def cutter():
    fn = _session_rembg() or _session_onnx()
    if not fn:
        raise RuntimeError(
            "No rembg/onnxruntime cut-out backend. Install rembg[cpu] or place "
            "isnet-general-use.onnx under ~/.rembg/models/."
        )
    return fn


def composite_offwhite(cut: Image.Image, bg=OFFWHITE) -> Image.Image:
    if cut.mode != "RGBA":
        cut = cut.convert("RGBA")
    canvas = Image.new("RGB", cut.size, bg)
    canvas.paste(cut, mask=cut.split()[-1])
    return canvas


def process_image(src: Path | Image.Image, dest: Path | None = None) -> Image.Image:
    im = src if isinstance(src, Image.Image) else Image.open(src)
    cut = cutter()(im)
    out = composite_offwhite(cut)
    out.thumbnail((MAX_PX, MAX_PX), Image.Resampling.LANCZOS)
    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, "WEBP", quality=QUALITY, method=6)
    return out


def hash_save(im: Image.Image, folder: Path) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "_tmp.webp"
    im.save(tmp, "WEBP", quality=QUALITY, method=6)
    h = hashlib.sha256(tmp.read_bytes()).hexdigest()[:16]
    dest = folder / f"{h}.webp"
    if dest.exists():
        tmp.unlink(missing_ok=True)
    else:
        tmp.rename(dest)
    return f"assets/editimg/{h}.webp"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", type=Path, required=True)
    ap.add_argument("--out", dest="dest", type=Path, required=True)
    args = ap.parse_args(argv)
    process_image(args.src, args.dest)
    print(args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
