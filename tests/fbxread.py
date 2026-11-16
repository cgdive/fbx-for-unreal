import math
# ---- FBX reading ------------------------------------------------------------------------------
from io_scene_fbx import parse_fbx

SKIP = {b"CreationTime", b"FileId", b"CreationTimeStamp", b"FBXHeaderExtension", b"SceneInfo",
        b"Creator", b"Documents"}


def tree(path):
    root, _ = parse_fbx.parse(path)
    def conv(e):
        if e.id in SKIP: return None
        props = []
        for p in e.props:
            if hasattr(p, "tolist"): p = p.tolist()
            elif isinstance(p, (bytes, bytearray)): p = p.decode("utf-8", "replace")
            elif hasattr(p, "__len__") and not isinstance(p, str): p = list(p)
            props.append(p)
        return [e.id.decode() if e.id else "", props, [c for c in map(conv, e.elems) if c is not None]]
    return [c for c in map(conv, root.elems) if c is not None]


def models(t):
    objs = next(e for e in t if e[0] == "Objects")
    out = {}
    for e in objs[2]:
        if e[0] == "Model":
            name = e[1][1].split("\x00")[0]
            p70 = next((c for c in e[2] if c[0] == "Properties70"), None)
            props = {c[1][0]: c[1][4:] for c in (p70[2] if p70 else [])}
            out[name] = {"type": e[1][2], "props": props, "uid": e[1][0]}
    return out


def anim_curves(t):
    """{(model_name, 'Lcl Translation', 'd|Y'): [values]} via Connections."""
    objs = next(e for e in t if e[0] == "Objects")[2]
    conns = next(e for e in t if e[0] == "Connections")[2]
    by_uid = {e[1][0]: e for e in objs}
    name = lambda e: e[1][1].split("\x00")[0]
    curve_vals = {}
    for c in conns:
        kind, src, dst = c[1][0], c[1][1], c[1][2]
        if kind == "OP" and src in by_uid and by_uid[src][0] == "AnimationCurve":
            vals = next(x for x in by_uid[src][2] if x[0] == "KeyValueFloat")[1][0]
            node = by_uid[dst]; channel = c[1][3]
            # node -> model
            for c2 in conns:
                if c2[1][1] == dst and c2[1][0] == "OP" and by_uid.get(c2[1][2], [None])[0] == "Model":
                    curve_vals[(name(by_uid[c2[1][2]]), c2[1][3], channel)] = vals
    return curve_vals


def poses(t):
    objs = next(e for e in t if e[0] == "Objects")[2]
    by_uid = {e[1][0]: e for e in objs}
    out = {}
    for e in objs:
        if e[0] == "Pose":
            for pn in e[2]:
                if pn[0] == "PoseNode":
                    uid = next(x for x in pn[2] if x[0] == "Node")[1][0]
                    m = next(x for x in pn[2] if x[0] == "Matrix")[1][0]
                    out[by_uid[uid][1][1].split("\x00")[0]] = m
    return out


def col_scale(m):  # column-major 4x4 -> scale of first axis
    return math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2)


def diff(a, b, path="", out=None, tol=1e-4):
    if out is None: out = []
    if len(out) > 15: return out
    if isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= tol * max(1, abs(a))):
            out.append(f"{path}: {a!r} != {b!r}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}/{a[0] if isinstance(a[0], str) and i else i}", out, tol)
    elif a != b:
        out.append(f"{path}: {str(a)[:80]!r} != {str(b)[:80]!r}")
    return out


