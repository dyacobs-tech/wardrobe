"""Old library pictures and their high-res redraws (.87.27).

David, 27 Nov 2026, on the published site being over GitHub's 1 GB limit: "Do 2" (the second
option offered: remove the old pictures that have a high-res replacement).

Since .87.27 an old picture (assets/onbody/<id>.webp, with its cut-outs in assets/onbody-cut/ and
assets/onbody-cut-hq/) is kept only for an outfit that has no high-res redraw. The app shows the
redraw wherever one exists, so the checks written for the old drawings (belt colour, both shoes,
whole arms, holes, one build) now run on the old pictures that are still shown. The redraws are
checked by tests/test_hires8714.py and tests/test_hiresqa8715.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD_DIRS = ("assets/onbody", "assets/onbody-cut", "assets/onbody-cut-hq")
_redrawn = None


def redrawn():
    """{old picture id: its high-res entry} for every old library picture that has a redraw."""
    global _redrawn
    if _redrawn is None:
        j = json.loads((ROOT / "assets/onbody-hires/manifest.json").read_text())
        _redrawn = {Path(e["onbody"]).stem: e for e in j["r"] if e.get("onbody")}
    return _redrawn


def stem_of(name):
    name = str(name)
    return name[:-5] if name.endswith(".webp") else name


def is_redrawn(name):
    """True when this old picture has a high-res redraw whose two copies are in the repo."""
    e = redrawn().get(stem_of(name))
    return bool(e) and (ROOT / e["full"]).is_file() and (ROOT / e["card"]).is_file()


def old_files(name):
    return [ROOT / d / (stem_of(name) + ".webp") for d in OLD_DIRS]


def kept(names):
    """The pictures in `names` that are still old drawings (no redraw)."""
    return [n for n in names if not is_redrawn(n)]
