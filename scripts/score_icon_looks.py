#!/usr/bin/env python3
"""Score closet looks against the nine style-icon lenses and tag manifests.

Used to bias future render queues toward looks that match the current
per-level icon weights, and to tag the public on-body hires manifest
with the driving icons. Never writes closet photos, names, or secrets
into the repo: tags are only icon ids and numeric lens scores.

Closet pieces (id, name, category, colour) are read from --closet or
$DONNA_CLOSET_JSON, which must stay off the public tree.

    python3 scripts/score_icon_looks.py tag-manifest [--closet PATH]
    python3 scripts/score_icon_looks.py bias-queue QUEUE.json [--closet PATH] [--weights WEIGHTS.json]

Does not call FASHN or spend credits.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LENS_WORDS = [
    "double-breasted", "blazer", "suit", "polo", "loafer", "linen", "knit",
    "sweater", "cardigan", "chino", "jean", "denim", "tee", "t-shirt", "shirt",
    "oxford", "trouser", "shorts", "suede", "boot", "sneaker", "overshirt",
    "jacket", "coat", "turtleneck", "roll-neck", "rollneck", "cashmere",
    "gurkha", "pleat", "leather", "tweed", "flannel", "corduroy", "camp collar",
    "henley", "espadrille", "driver", "derby", "chelsea", "field jacket",
    "safari", "bomber", "peacoat", "trench", "waistcoat", "cable",
]
GROUPS = {"casual": (1, 2), "smart": (3, 4), "business": (5,), "formal": (6, 7)}


def _first(glob):
    hits = sorted(ROOT.joinpath("app").glob(glob))
    if not hits:
        sys.exit("missing " + glob)
    return hits[0]


def load_icons():
    icons = json.loads(_first("style-icons.*.json").read_text())
    if isinstance(icons, dict):
        icons = icons.get("icons") or icons.get("STYLE_ICONS") or list(icons.values())[0]
    specs = json.loads(_first("icon-specs.*.json").read_text())
    return icons, specs


def hex_rgb(h):
    m = re.match(r"^#?([0-9a-f]{6})$", str(h or ""), re.I)
    if not m:
        return None
    n = int(m.group(1), 16)
    return (n >> 16 & 255, n >> 8 & 255, n & 255)


def hex_dist(a, b):
    x, y = hex_rgb(a), hex_rgb(b)
    if not x or not y:
        return 999
    dr, dg, db = x[0] - y[0], x[1] - y[1], x[2] - y[2]
    return math.sqrt(0.3 * dr * dr + 0.59 * dg * dg + 0.11 * db * db)


def icon_lens(ic, specs):
    hexes = list(ic.get("palette") or [])
    cnt, txt = {}, []
    for rows in (specs.get(ic["id"]) or {}).values():
        for row in rows or []:
            if len(row) > 2 and row[2]:
                hexes.append(row[2])
            txt.append(str(row[0] or "") + " " + (str(row[3]) if len(row) > 3 else ""))
    for t in ic.get("signatures") or []:
        txt.append(t)
        txt.append(t)
    if ic.get("shoeLabel"):
        txt.append(ic["shoeLabel"] + " " + (ic.get("shoeDetail") or ""))
    if ic.get("shoeHex"):
        hexes.append(ic["shoeHex"])
    for look in ic.get("looks") or []:
        if look and look.get("desc"):
            txt.append(look["desc"])
    all_ = " | ".join(txt).lower()
    for w in LENS_WORDS:
        n = all_.count(w)
        if n:
            cnt[w] = n
    mx = max(cnt.values()) if cnt else 0
    words = {w: round((0.3 + 1.2 * cnt[w] / mx), 2) for w in cnt} if mx else {}
    hc = collections.Counter()
    for h in hexes:
        h = str(h).lower()
        if re.match(r"^#[0-9a-f]{6}$", h):
            hc[h] += 1
    return {"id": ic["id"], "name": ic["name"], "hex": [h for h, _ in hc.most_common(48)], "words": words}


def lens_piece(p, lens):
    sc = 0
    if p.get("hex") and lens["hex"]:
        best = min(hex_dist(h, p["hex"]) for h in lens["hex"])
        sc += 4 if best < 22 else 2.2 if best < 45 else 0.25 if best < 75 else -2.2
    nm = p.get("nm") or ""
    if nm and lens["words"]:
        for w, wv in lens["words"].items():
            if w in nm:
                sc += wv * 2
    return sc


def load_closet(path: Path) -> dict:
    raw = json.loads(path.read_text())
    byid = {}

    def ingest(it, fallback_id=None):
        if not isinstance(it, dict):
            return
        iid = it.get("id") or fallback_id
        if not iid:
            return
        nm = ((it.get("name") or "") + " " + (it.get("category") or it.get("garment") or it.get("cat") or "") + " " + (it.get("detail") or it.get("colour") or it.get("colourName") or "")).lower()
        byid[iid] = {
            "hex": it.get("colourHex") or it.get("hex") or "",
            "nm": nm,
            "category": it.get("category") or it.get("cat") or "",
        }

    # A bare items list, a {items: [...]} dump, or a sync snapshot with recs[].coll == items
    if isinstance(raw, list):
        for it in raw:
            ingest(it)
    elif isinstance(raw, dict):
        if isinstance(raw.get("items"), list):
            for it in raw["items"]:
                ingest(it)
        elif isinstance(raw.get("items"), dict):
            for k, it in raw["items"].items():
                ingest(it, k)
        recs = raw.get("recs") or ((raw.get("meta") or {}).get("data") or {}).get("recs")
        if not recs and isinstance(raw.get("meta"), dict) and "data" in raw["meta"]:
            recs = None  # items may be elsewhere
        # official sync snapshot
        if isinstance(raw.get("recs"), list):
            for rec in raw["recs"]:
                if rec.get("coll") in ("items", "item", "closet"):
                    ingest(rec.get("data") or {}, rec.get("id"))
        data = raw.get("meta", {}).get("data") if isinstance(raw.get("meta"), dict) else raw.get("data")
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            if isinstance(items, list):
                for it in items:
                    ingest(it)
            elif isinstance(items, dict):
                for k, it in items.items():
                    ingest(it, k)
        # flat {id: item} closet dumps
        if not byid:
            for k, it in raw.items():
                if isinstance(it, dict) and (it.get("name") or it.get("category") or it.get("id")):
                    ingest(it, k)
    return byid


def pieces_from_key(key: str, closet: dict, garments=None):
    if garments:
        out = []
        for g in garments:
            iid = g.get("id")
            p = dict(closet.get(iid) or {})
            nm = ((g.get("name") or p.get("nm") or "") + " " + (g.get("category") or p.get("category") or "")).lower()
            if not p.get("nm"):
                p["nm"] = nm
            if not p.get("hex"):
                p["hex"] = g.get("colourHex") or g.get("hex") or ""
            out.append(p)
        return out
    out = []
    for iid in str(key or "").split("|"):
        if not iid:
            continue
        p = closet.get(iid)
        if p:
            out.append(p)
        else:
            out.append({"hex": "", "nm": iid.lower(), "category": ""})
    return out


def per_icon_scores(pieces, lenses):
    scores = {}
    for icid, lens in lenses.items():
        scores[icid] = round(sum(lens_piece(p, lens) for p in pieces), 3)
    return scores


def driving_icons(scores, n=2):
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [i for i, sc in ranked[:n] if sc > 0]


def group_for(level):
    n = int(level or 0)
    for g, lv in GROUPS.items():
        if n in lv:
            return g
    return "smart"


def share_norm(mp, ids):
    pos, tot, out = [], 0, {}
    for i in ids:
        v = max(0, int(round(float(mp.get(i) or 0))))
        if v <= 0:
            out[i] = 0
            continue
        out[i] = v
        pos.append(i)
        tot += v
    if not pos or tot == 100:
        return out
    if max(out[i] for i in pos) <= 10 and tot <= 40:
        for i in pos:
            out[i] *= 10
        tot *= 10
    exact = {i: out[i] * 100 / tot for i in pos}
    used = 0
    for i in pos:
        out[i] = int(exact[i] // 1)
        used += out[i]
    rem = 100 - used
    for i in sorted(pos, key=lambda i: (-(exact[i] - out[i]), ids.index(i) if i in ids else 0)):
        if rem <= 0:
            break
        out[i] += 1
        rem -= 1
    return out


def default_weights(ids):
    mid = {i: 20 for i in ids}
    by = {g: dict(mid) for g in GROUPS}
    if "squarzi" in mid:
        by["casual"]["squarzi"] = 80
        by["smart"]["squarzi"] = 80
    if "kraft" in mid:
        by["business"]["kraft"] = 80
        by["formal"]["kraft"] = 80
    if "beckham" in mid:
        by["business"]["beckham"] = 80
        by["formal"]["beckham"] = 80
    return {g: share_norm(mp, ids) for g, mp in by.items()}


def load_weights(path, ids):
    if not path:
        return default_weights(ids)
    raw = json.loads(Path(path).read_text())
    # accept a full iconWeights state, or a sync snippet {iconWeights: ...}
    w = raw.get("iconWeights") or raw
    if "byLevel" in w or "all" in w:
        mode = w.get("mode") or "per"
        by = {}
        for g in GROUPS:
            src = (w.get("all") if mode == "all" else (w.get("byLevel") or {}).get(g)) or w.get("all") or {}
            by[g] = share_norm(src, ids)
        return by
    return default_weights(ids)


def weighted_score(scores, wt):
    tot = acc = 0
    for i, sc in scores.items():
        wv = float(wt.get(i) or 0)
        if wv <= 0:
            continue
        pw = math.pow(wv / 100, 2.5)
        acc += sc * pw
        tot += pw
    return acc / tot if tot else 0


def closet_path(args_closet):
    p = args_closet or os.environ.get("DONNA_CLOSET_JSON")
    if not p:
        sys.exit("need --closet or DONNA_CLOSET_JSON (local only; not committed)")
    path = Path(p)
    if not path.exists():
        sys.exit("closet not found: " + str(path))
    # refuse obvious in-repo paths
    try:
        path.resolve().relative_to(ROOT.resolve())
        # allowed only under tests/ fixtures
        if "tests" not in path.parts:
            sys.exit("refusing a closet path inside the public repo (except tests/ fixtures)")
    except ValueError:
        pass
    return path


def find_queue_level(look_n, key, queues):
    for q in queues:
        for row in q.get("looks") or []:
            if row.get("n") == look_n or row.get("id") == key or row.get("core_key") == key:
                return row.get("primary_level") or 0
    return 0


def load_queues():
    out = []
    for p in (
        Path("/workspace/donna-originals/agent-run/queue.json"),
        Path("/workspace/donna-originals/agent-run/formal-queue.json"),
    ):
        if p.exists():
            try:
                out.append(json.loads(p.read_text()))
            except Exception:
                pass
    return out


def cmd_tag_manifest(args):
    closet = load_closet(closet_path(args.closet))
    icons, specs = load_icons()
    lenses = {ic["id"]: icon_lens(ic, specs) for ic in icons}
    man_path = ROOT / "assets/onbody-hires/manifest.json"
    man = json.loads(man_path.read_text())
    queues = load_queues()
    tagged = 0
    for row in man.get("r") or []:
        key = row.get("k") or ""
        # join garments from queues when present (names only used in memory)
        garments = None
        level = 0
        for q in queues:
            for look in q.get("looks") or []:
                if look.get("id") == key or look.get("core_key") == key or (look.get("n") and look.get("n") == row.get("look_n")):
                    garments = look.get("garments")
                    level = look.get("primary_level") or 0
                    break
            if garments is not None:
                break
        pieces = pieces_from_key(key, closet, garments)
        scores = per_icon_scores(pieces, lenses)
        row["icons"] = driving_icons(scores)
        row["iconScores"] = {k: v for k, v in scores.items() if v}
        if level:
            row["iconLevel"] = level
        tagged += 1
    man["iconTag"] = "per-icon lens scores; driving icons are the top two with a positive score"
    man_path.write_text(json.dumps(man, separators=(",", ":")) + "\n")
    print("tagged", tagged, "hires looks in", man_path.relative_to(ROOT))


def cmd_bias_queue(args):
    closet = load_closet(closet_path(args.closet))
    icons, specs = load_icons()
    lenses = {ic["id"]: icon_lens(ic, specs) for ic in icons}
    ids = [ic["id"] for ic in icons]
    by = load_weights(args.weights, ids)
    qpath = Path(args.queue)
    q = json.loads(qpath.read_text())
    looks = q.get("looks") or []
    for row in looks:
        pieces = pieces_from_key(row.get("id") or row.get("core_key") or "", closet, row.get("garments"))
        scores = per_icon_scores(pieces, lenses)
        level = row.get("primary_level") or 4
        wt = by[group_for(level)]
        row["icons"] = driving_icons(scores)
        row["iconScore"] = round(weighted_score(scores, wt), 3)
    # High scorers first within each dress level, stable otherwise
    order = {id(row): i for i, row in enumerate(looks)}
    looks.sort(key=lambda r: (-(r.get("primary_level") or 0), -(r.get("iconScore") or 0), order[id(r)]))
    q["looks"] = looks
    qpath.write_text(json.dumps(q, indent=2) + "\n")
    print("biased", len(looks), "looks in", qpath, "by current per-level icon weights")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tag-manifest")
    t.add_argument("--closet")
    b = sub.add_parser("bias-queue")
    b.add_argument("queue")
    b.add_argument("--closet")
    b.add_argument("--weights", help="optional iconWeights JSON (otherwise seeded defaults)")
    args = ap.parse_args()
    if args.cmd == "tag-manifest":
        cmd_tag_manifest(args)
    else:
        cmd_bias_queue(args)


if __name__ == "__main__":
    main()
