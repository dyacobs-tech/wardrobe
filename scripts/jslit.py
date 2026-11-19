"""A JavaScript data literal (objects, arrays, strings, numbers, true/false/null,
unquoted keys, single quotes, trailing commas, comments) -> JSON text, and
finding where a top-level `var NAME = <literal>;` ends."""
import json, re
_WS = re.compile(r"(?:\s+|//[^\n]*|/\*.*?\*/)+", re.S)
_NUM = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")
_ID = re.compile(r"[A-Za-z_$][\w$]*")
_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}

def _string(s, i):
    q = s[i]; i += 1; out = []
    while True:
        c = s[i]
        if c == q: return "".join(out), i + 1
        if c == "\\":
            d = s[i + 1]
            if d == "u":
                if s[i + 2] == "{":
                    j = s.index("}", i); out.append(chr(int(s[i + 3:j], 16))); i = j + 1; continue
                out.append(chr(int(s[i + 2:i + 6], 16))); i += 6; continue
            if d == "x": out.append(chr(int(s[i + 2:i + 4], 16))); i += 4; continue
            if d == "\n": i += 2; continue
            out.append(_ESC.get(d, d)); i += 2; continue
        if c == "\n": raise ValueError("newline in string at %d" % i)
        out.append(c); i += 1

def parse(s, i=0):
    """-> (value, end index)"""
    m = _WS.match(s, i)
    if m: i = m.end()
    c = s[i]
    if c in "[{":
        close = "]" if c == "[" else "}"; i += 1
        res = [] if c == "[" else {}
        while True:
            m = _WS.match(s, i)
            if m: i = m.end()
            if s[i] == close: return res, i + 1
            if c == "[":
                v, i = parse(s, i); res.append(v)
            else:
                if s[i] in "'\"": k, i = _string(s, i)
                else:
                    m = _ID.match(s, i) or _NUM.match(s, i)
                    if not m: raise ValueError("bad key at %d: %r" % (i, s[i:i + 30]))
                    k = m.group(0); i = m.end()
                    if _NUM.fullmatch(k): k = str(json.loads(k)) if not k.lower().startswith(("0x", "-0x")) else str(int(k, 16))
                m = _WS.match(s, i)
                if m: i = m.end()
                if s[i] != ":": raise ValueError("expected : at %d" % i)
                v, i = parse(s, i + 1); res[k] = v
            m = _WS.match(s, i)
            if m: i = m.end()
            if s[i] == ",": i += 1
            elif s[i] != close: raise ValueError("expected , at %d: %r" % (i, s[i:i + 30]))
    if c in "'\"": return _string(s, i)
    if c == "-" or c == "." or c.isdigit():
        m = _NUM.match(s, i)
        t = m.group(0)
        if "x" in t.lower(): return int(t, 16), m.end()
        if t.startswith((".", "-.")): t = t.replace(".", "0.", 1)
        if re.search(r"\.(?![0-9])", t): t = t.replace(".", ".0", 1)
        return json.loads(t), m.end()
    m = _ID.match(s, i)
    if m and m.group(0) in ("true", "false", "null"):
        return {"true": True, "false": False, "null": None}[m.group(0)], m.end()
    raise ValueError("not a data literal at %d: %r" % (i, s[i:i + 40]))

def take_var(code, name):
    """Find `var NAME = <literal>;` at the start of a line -> (start, end, value) or None."""
    m = re.search(r"^var %s = " % re.escape(name), code, re.M)
    if not m: return None
    v, j = parse(code, m.end())
    k = _WS.match(code, j)
    if k: j = k.end()
    if code[j] != ";": raise ValueError("%s: expected ; after the literal" % name)
    return m.start(), j + 1, v
