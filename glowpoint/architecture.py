"""Ceiling and wall elements that change the model: coves and slatted ceilings.
Each type has prepare(model, feature), which runs before ray casting, and draw(canvas, feature, base),
which returns the new base image. (The waffle is in features.py.)"""
import numpy as np
import cv2
from .features import GLOW

SIDE_TONE = (200, 200, 200)


def _edges(cv, base, idset, dark=40, extra=None):
    """Draw lines where the visible surface changes, around the given surfaces."""
    ids = cv.ids if extra is None else extra
    near = np.isin(ids, list(idset))
    e = np.zeros(ids.shape, bool)
    e[:, 1:] |= (ids[:, 1:] != ids[:, :-1]) & (near[:, 1:] | near[:, :-1])
    e[1:, :] |= (ids[1:, :] != ids[:-1, :]) & (near[1:, :] | near[:-1, :])
    base[e] = dark
    return base


def _add(m, s):
    m.surfaces.append(s); m.by_name[s["name"]] = s


def _blend(img, mask, col, g):
    g = np.broadcast_to(g, mask.shape)
    for ch, val in enumerate(col):
        img[..., ch][mask] = (img[..., ch][mask]*(1-g[mask]) + val*g[mask]).astype(np.uint8)


# ---------------------------------------------------------------- cove
def cove_prepare(m, f):
    name = f.get("name", "Cove"); kind = f.get("kind", "recess")
    if kind == "recess":
        ceil = m.surface(f.get("plane", "Ceiling"))
        (x0, x1), (z0, z1) = f["X"], f["Z"]; y0 = ceil["at"]; y1 = y0 + f["depth"]
        ceil.setdefault("holes", []).append({"X": [x0, x1], "Z": [z0, z1]})
        for s in (dict(name=name+" top", axis=1, at=y1, X=[x0, x1], Z=[z0, z1], cove="top"),
                  dict(name=name+" left", axis=0, at=x0, Y=[y0, y1], Z=[z0, z1], cove="side"),
                  dict(name=name+" right", axis=0, at=x1, Y=[y0, y1], Z=[z0, z1], cove="side"),
                  dict(name=name+" front", axis=2, at=z0, X=[x0, x1], Y=[y0, y1], cove="side"),
                  dict(name=name+" back", axis=2, at=z1, X=[x0, x1], Y=[y0, y1], cove="side")):
            _add(m, s)
    elif kind == "wall":
        wall = m.surface(f["plane"]); a = wall["axis"]
        if a == 1: raise ValueError("a wall cove needs a wall (a surface at constant X or Z)")
        u0, u1 = f["range"]; y = f["y"]; dep = f.get("depth", 1.0); h = f.get("h", 0.5)
        # the ledge projects from the wall towards the room: towards the camera side of the wall
        side = 1 if m.C[a] > wall["at"] else -1                     # +1: the room is on the high side of the wall
        w0, w1 = sorted([wall["at"], wall["at"] + side*dep])
        hk = 2 if a == 0 else 0
        rng = {("X" if a == 0 else "Z"): [w0, w1], ("Z" if a == 0 else "X"): [u0, u1], "Y": [y-h, y]}
        fx = w1 if side > 0 else w0                                  # fascia (the face toward the room)
        for s in (dict(name=name+" fascia", axis=a, at=fx, **{k: v for k, v in rng.items() if k != "XYZ"[a]}, cove="side"),
                  dict(name=name+" bottom", axis=1, at=y-h, **{k: v for k, v in rng.items() if k != "Y"}, cove="side"),
                  dict(name=name+" top", axis=1, at=y, **{k: v for k, v in rng.items() if k != "Y"}, cove="side")):
            _add(m, s)
        for end, uu in (("end A", u0), ("end B", u1)):
            _add(m, dict(name=name+" "+end, axis=hk, at=uu, **{"XYZ"[a]: [w0, w1]}, Y=[y-h, y], cove="side"))
    else:
        raise ValueError("cove kind must be 'recess' or 'wall'")


def cove_draw(cv, f, base):
    m = cv.m; name = f.get("name", "Cove"); kind = f.get("kind", "recess")
    mine = {i: s for i, s in enumerate(m.surfaces) if s["name"].startswith(name+" ") and "cove" in s}
    over = base.copy(); strength = f.get("strength", 0.85)
    if kind == "recess":
        (x0, x1), (z0, z1) = f["X"], f["Z"]
        xc, zc, hw, hd = (x0+x1)/2, (z0+z1)/2, (x1-x0)/2, (z1-z0)/2
        for i, s in mine.items():
            k = cv.ids == i
            if not k.any(): continue
            if s["cove"] == "top":
                # the light comes from the ledge at the edges: brightest near the edges
                P = cv.P
                e = np.maximum(np.abs(P[..., 0]-xc)/hw, np.abs(P[..., 2]-zc)/hd)
                g = strength*(0.45 + 0.55*np.clip(e, 0, 1)**2)
                _blend(over, k, GLOW, g)
            else:
                _blend(over, k, (40, 150, 230), np.full(k.shape, 0.8*strength))
    else:
        wall = m.surface(f["plane"]); a = wall["axis"]; iw = [j for j, s in enumerate(m.surfaces) if s is wall][0]
        u0, u1 = f["range"]; y = f["y"]; hk = 2 if a == 0 else 0
        P = cv.P; U = P[..., hk]
        ends = np.clip(np.minimum(U-u0, u1-U)/1.0, 0, 1)
        k = (cv.ids == iw) & (P[..., 1] >= y)
        g = strength*np.exp(-np.clip(P[..., 1]-y, 0, None)/f.get("fade", 4.0))*ends
        _blend(over, k, GLOW, g)
        # spill onto the ceiling near the wall
        cname = f.get("ceiling")
        if cname:
            ic = [j for j, s in enumerate(m.surfaces) if s["name"] == cname][0]
            kc = cv.ids == ic
            dist = np.abs(P[..., a] - wall["at"])
            gc = 0.7*strength*np.exp(-dist/f.get("spread", 4.0))*ends
            _blend(over, kc, GLOW, gc)
        for i, s in mine.items():
            kk = cv.ids == i
            _blend(over, kk, SIDE_TONE, np.full(kk.shape, 0.6))
    res = np.minimum(cv2.addWeighted(over, 0.6, base, 0.4, 0), base)
    res = _edges(cv, res, list(mine))
    cv.report.append(dict(layer=f.get("layer", ""), type="cove", surface=name, x=0, y=0, z=0,
                          note=f"{kind} cove" + (f", X {f['X'][0]:.2f}..{f['X'][1]:.2f}, Z {f['Z'][0]:.2f}..{f['Z'][1]:.2f}, depth {f['depth']*12:.1f} in"
                                                 if kind == "recess" else f" on {f['plane']}, range {f['range'][0]:.2f}..{f['range'][1]:.2f}, top at {f['y']:.2f} ft")))
    return res


# ---------------------------------------------------------------- slats
def slats_prepare(m, f):
    """A layer of parallel slats below a ceiling. A flat 'bottom' surface marks where rays enter the layer."""
    name = f.get("name", "Slats")
    (x0, x1), (z0, z1) = f["X"], f["Z"]
    yb = f["y"]                                                  # bottom of the slats
    s = dict(name=name, axis=1, at=yb, X=[x0, x1], Z=[z0, z1], slats=True)
    _add(m, s)


def slats_draw(cv, f, base):
    m = cv.m; name = f.get("name", "Slats")
    iS = [j for j, s in enumerate(m.surfaces) if s["name"] == name][0]
    (x0, x1), (z0, z1) = f["X"], f["Z"]
    yb = f["y"]; h = f["h"]; w = f["w"]; pitch = f["pitch"]
    along = f.get("direction", "z")                              # slats run along Z (default) or X
    ak = 0 if along == "z" else 2                                 # the axis ACROSS the slats
    lo = x0 if ak == 0 else z0
    mask = cv.ids == iS
    if not mask.any(): return base
    # what is behind the slat layer (for rays that pass between slats)
    s_ = m.surfaces.pop(iS)
    ids_b, P_b, dep_b = m.raycast(cv.ids.shape)
    m.surfaces.insert(iS, s_)
    D = m.rays(cv.ids.shape)[mask]; Q = cv.P[mask]
    t_ = (Q[:, ak] - lo) / pitch; cell = np.floor(t_); fr = (t_ - cell)*pitch   # position across, in this cell
    on_bottom = fr < w                                             # slat from lo+cell*pitch to +w
    with np.errstate(divide="ignore", invalid="ignore"):
        tt = h / D[:, 1]                                           # to the top of the layer
        da = D[:, ak]
        gap0 = lo + cell*pitch + w; gap1 = lo + (cell+1)*pitch    # the gap between this slat and the next
        tside = np.where(da > 0, (gap1 - Q[:, ak])/da, np.where(da < 0, (gap0 - Q[:, ak])/da, np.inf))
    tside = np.where(tside > 0, tside, np.inf)
    hits_side = (~on_bottom) & (tside < tt)
    through = (~on_bottom) & ~hits_side
    hit = Q + np.where(hits_side, tside, 0)[:, None]*D
    face = np.where(on_bottom, 1, np.where(hits_side, 2, 0))       # 1 slat bottom, 2 slat side, 0 between
    # update the canvas: slat pixels keep the slat; pixels between slats see what is behind
    sub_ids = cv.ids[mask].copy(); sub_P = cv.P[mask].copy(); sub_dep = cv.dep[mask].copy()
    sub_P[~through] = hit[~through]; sub_dep[~through] = m.depth(hit[~through])
    sub_ids[through] = ids_b[mask][through]; sub_P[through] = P_b[mask][through]; sub_dep[through] = dep_b[mask][through]
    cv.ids[mask] = sub_ids; cv.P[mask] = sub_P; cv.dep[mask] = sub_dep
    # draw
    col = f.get("color", "wood")
    tone = {"wood": (120, 170, 215), "white": (245, 245, 245), "dark": (70, 70, 70)}.get(col) if isinstance(col, str) else tuple(col[::-1])
    side = tuple(int(v*0.75) for v in tone)
    over = base.copy(); sub = over[mask]
    for k, c in ((face == 1, tone), (face == 2, side)):
        sub[k] = (sub[k]*0.25 + np.array(c)*0.75).astype(np.uint8)
    if f.get("backlit"):
        sub[through] = (sub[through]*0.4 + np.array(GLOW)*0.6).astype(np.uint8)
    over[mask] = sub
    res = np.minimum(cv2.addWeighted(over, 0.7, base, 0.3, 0), base) if not f.get("backlit") else over
    # slat outlines
    lab = np.full(cv.ids.shape, -1, np.int64)
    lab[mask] = np.where(face == 0, -2, face + 3*(cell.astype(np.int64) % 100000))
    e = np.zeros(lab.shape, bool)
    e[:, 1:] |= (lab[:, 1:] != lab[:, :-1]) & ((lab[:, 1:] >= 0) | (lab[:, :-1] >= 0))
    e[1:, :] |= (lab[1:, :] != lab[:-1, :]) & ((lab[1:, :] >= 0) | (lab[:-1, :] >= 0))
    res[e] = (res[e]*0.3).astype(np.uint8)
    n = int(((x1-x0) if ak == 0 else (z1-z0))/pitch + 1e-6) + 1
    cv.report.append(dict(layer=f.get("layer", ""), type="slats", surface=name, x=round(x0, 2), y=round(yb, 2), z=round(z0, 2),
                          note=f"{n} slats along {along.upper()}, {w*12:.1f} in wide, {h*12:.1f} in high, {pitch*12:.1f} in on centre, bottom at {yb:.2f} ft"))
    return res


GEOMETRY = {"cove": (cove_prepare, cove_draw), "slats": (slats_prepare, slats_draw)}
