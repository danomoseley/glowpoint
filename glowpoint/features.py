"""Light and ceiling types. Each type reads its settings (already evaluated) and draws on the canvas.

Positions on a surface:
  horizontal surfaces (floor, ceiling, soffit, box tops):  x, z
  walls at constant X (left/right walls, box left/right):   along (= Z), y
  walls at constant Z (back wall, box front/back):          along (= X), y
A position can be one number or a list; lists make one light for each combination.
"""
import itertools
import numpy as np
import cv2

GLOW = (70, 215, 255)       # BGR, warm light
BEAM = (150, 235, 255)


def as_list(v):
    return list(v) if isinstance(v, (list, tuple)) else [v]


class Canvas:
    def __init__(self, model, base):
        self.m = model
        self.img = base.copy()        # linework and outlines
        self.over = base.copy()       # light, blended in at the end
        self.report = []

    def raycast(self):
        self.ids, self.P, self.dep = self.m.raycast(self.img.shape[:2])

    def visible(self, pts3, pix):
        H, W = self.dep.shape; ok = []
        dz = self.m.depth(pts3) if len(pts3) else []
        for P, (x, y), z in zip(pts3, pix, dz):
            if not (np.isfinite(x) and np.isfinite(y)) or z <= 0: ok.append(False); continue
            xi, yi = int(round(x)), int(round(y))
            ok.append(0 <= xi < W and 0 <= yi < H and z <= self.dep[yi, xi] + 0.3)
        return np.array(ok)

    def glow(self, mask, g, col=GLOW):
        k = mask & (g > 0.03)
        for ch, val in enumerate(col):
            self.over[..., ch][k] = (self.over[..., ch][k]*(1-g[k]) + val*g[k]).astype(np.uint8)

    def seg(self, A, B, th=1, n=200):
        pts = [list(np.array(A)+(np.array(B)-np.array(A))*s) for s in np.linspace(0, 1, n)]
        pix = self.m.project(pts); vis = self.visible(pts, pix)
        for q in range(len(pts)-1):
            if vis[q] and vis[q+1]:
                cv2.line(self.img, tuple(np.int32(pix[q])), tuple(np.int32(pix[q+1])), (0, 0, 0), th, cv2.LINE_AA)

    def sid(self, name):
        return [i for i, s in enumerate(self.m.surfaces) if s["name"] == name][0]

    def add(self, f, kind, plane, P, **extra):
        self.report.append(dict(layer=f.get("layer", ""), type=kind, surface=plane,
                                x=round(P[0], 2), y=round(P[1], 2), z=round(P[2], 2), **extra))

    def finish(self):
        res = cv2.addWeighted(self.over, 0.55, self.img, 0.45, 0)
        return np.minimum(res, self.img)


# ---------------------------------------------------------------- ceiling geometry
def waffle_prepare(m, f):
    ceil = m.surface(f.get("plane", "Ceiling"))
    (x0, x1), (z0, z1) = f["X"], f["Z"]
    ceil.setdefault("holes", []).append({"X": [x0, x1], "Z": [z0, z1]})
    s = dict(name=f.get("name", "Waffle"), axis=1, at=ceil["at"], X=[x0, x1], Z=[z0, z1], waffle=True)
    m.surfaces.append(s); m.by_name[s["name"]] = s


def waffle_draw(cv, f, base):
    """Ray-traced coffers. Changes the base image (the coffers are part of the architecture)."""
    m = cv.m; s = m.surface(f.get("name", "Waffle")); W = cv.sid(s["name"])
    ids, P = cv.ids, cv.P; mask = ids == W
    (x0, x1), (z0, z1) = f["X"], f["Z"]
    mod, rib, depth = f["module"], f["rib"], f["depth"]
    d = m.rays(ids.shape)
    y0 = s["at"]; h = rib/2
    Q = P[mask]; D = d[mask]
    u = (Q[:, 0]-x0)/mod; v = (z1-Q[:, 2])/mod; iu, iv = np.floor(u), np.floor(v)
    fu, fv = (u-iu)*mod, (v-iv)*mod
    on_rib = (fu < h) | (fu > mod-h) | (fv < h) | (fv > mod-h)
    cx0 = x0+iu*mod+h; cx1 = x0+(iu+1)*mod-h; cz1 = z1-iv*mod-h; cz0 = z1-(iv+1)*mod+h
    with np.errstate(divide="ignore", invalid="ignore"):
        tt = depth/D[:, 1]
        tx = np.where(D[:, 0] > 0, (cx1-Q[:, 0])/D[:, 0], np.where(D[:, 0] < 0, (cx0-Q[:, 0])/D[:, 0], np.inf))
        tz = np.where(D[:, 2] > 0, (cz1-Q[:, 2])/D[:, 2], np.where(D[:, 2] < 0, (cz0-Q[:, 2])/D[:, 2], np.inf))
    tmin = np.minimum(tt, np.minimum(tx, tz))
    face = np.where(on_rib, 0, np.where(tmin == tt, 1, np.where(tmin == tx, 2, 3)))
    hit = Q + np.where(on_rib, 0, tmin)[:, None]*D
    gu = np.clip(1-np.abs(hit[:, 0]-(cx0+cx1)/2)/((cx1-cx0)/2), 0, 1)
    gv = np.clip(1-np.abs(hit[:, 2]-(cz0+cz1)/2)/((cz1-cz0)/2), 0, 1)
    over = base.copy(); sub = over[mask]
    cols = {1: GLOW, 2: (45, 165, 235), 3: (30, 130, 215)}
    lit = f.get("lit", True)
    g = {1: 0.55+0.45*np.sqrt(gu*gv), 2: np.full(len(Q), 0.85), 3: np.full(len(Q), 0.9)}
    for k_, col in cols.items():
        k = face == k_
        if not lit: col = (225, 225, 225)
        for ch in range(3):
            sub[k, ch] = (sub[k, ch]*(1-g[k_][k]) + col[ch]*g[k_][k]).astype(np.uint8)
    over[mask] = sub
    lab = np.full(ids.shape, -1, np.int64)
    lab[mask] = (face+1) + 7*((iu.astype(np.int64)*97 + iv.astype(np.int64)) % 100000)
    e = np.zeros(ids.shape, bool)
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]; e[1:, :] |= lab[1:, :] != lab[:-1, :]
    e &= mask | np.roll(mask, 1, 0) | np.roll(mask, 1, 1)
    res = cv2.addWeighted(over, 0.6, base, 0.4, 0); res = np.minimum(res, base)
    res[e] = (res[e]*0.35).astype(np.uint8)
    edge = cv2.Canny(mask.astype(np.uint8)*255, 50, 150) > 0
    res[cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0] = 0
    cv.report.append(dict(layer=f.get("layer", ""), type="waffle", surface=s["name"], x=round(x0, 2), y=round(y0, 2), z=round(z0, 2),
                          note=f"X {x0:.2f}..{x1:.2f}, Z {z0:.2f}..{z1:.2f}, {round((x1-x0)/mod)} coffers across, "
                               f"module {mod*12:.0f} in, rib {rib*12:.0f} in, depth {depth*12:.0f} in"))
    return res


# ---------------------------------------------------------------- lights
def downlight(cv, f):
    m = cv.m; s = m.surface(f["plane"])
    for x, z in itertools.product(as_list(f["x"]), as_list(f["z"])):
        c = m.to3d(s, x, z); rad = f.get("d", 8/12)/2
        th = np.linspace(0, 2*np.pi, 64, endpoint=False)
        top = [[c[0]+rad*np.cos(t), c[1], c[2]+rad*np.sin(t)] for t in th]
        ty = f.get("beam_to", 0.0); pr = f.get("pool_r", 1.5)
        pool = [[c[0]+pr*np.cos(t), ty, c[2]+pr*np.sin(t)] for t in th]
        pt, pp = m.project(top), m.project(pool)
        if not cv.visible([c], m.project([c]))[0]:
            cv.add(f, "downlight", f["plane"], c, visible=False); continue
        img = cv.img
        if f.get("cone", True):
            hull = cv2.convexHull(np.float32(np.vstack([pt, pp]))).astype(np.int32)
            cone = img.copy(); cv2.fillPoly(cone, [hull], BEAM, cv2.LINE_AA)
            img[:] = cv2.addWeighted(cone, 0.35, img, 0.65, 0)
        if cv.visible(pool, pp).mean() > 0.6:
            a = f.get("pool_a", 0.5)
            pim = img.copy(); cv2.fillPoly(pim, [np.int32(pp)], GLOW, cv2.LINE_AA)
            img[:] = cv2.addWeighted(pim, a, img, 1-a, 0)
        cv2.fillPoly(cv.over, [np.int32(pt)], (40, 200, 255), cv2.LINE_AA)
        cv2.polylines(img, [np.int32(pt)], True, (0, 0, 0), 1, cv2.LINE_AA)
        cv.add(f, "downlight", f["plane"], c, visible=True)


def sconce(cv, f):
    m = cv.m; s = m.surface(f["plane"]); i = cv.sid(f["plane"])
    hk = 2 if s["axis"] == 0 else 0
    for u, y in itertools.product(as_list(f["along"]), as_list(f["y"])):
        mask = cv.ids == i
        U, Yp = cv.P[..., hk], cv.P[..., 1]
        g = np.exp(-((U-u)/f.get("spread", 0.9))**2 - ((Yp-y)/f.get("reach", 2.6))**2)
        cv.glow(mask, g)
        bw, bh = f.get("w", 0.4)/2, f.get("h", 1.0)/2
        body = [m.to3d(s, u-bw, y-bh), m.to3d(s, u+bw, y-bh), m.to3d(s, u+bw, y+bh), m.to3d(s, u-bw, y+bh)]
        c = m.to3d(s, u, y)
        if cv.visible(body, m.project(body)).mean() > 0.5:
            bp = np.int32(m.project(body))
            cv2.fillPoly(cv.img, [bp], (255, 255, 255)); cv2.polylines(cv.img, [bp], True, (0, 0, 0), 1, cv2.LINE_AA)
        cv.add(f, "sconce", f["plane"], c)


def uplight(cv, f):
    m = cv.m
    for face in as_list(f["faces"]):
        s = m.surface(face); i = cv.sid(face); a = s["axis"]
        hk = 0 if a == 2 else 2; key = "X" if a == 2 else "Z"
        uc = f.get("at", (s[key][0]+s[key][1])/2)
        mask = cv.ids == i
        U, Yp = cv.P[..., hk], cv.P[..., 1]
        width = 0.35 + 0.16*np.clip(Yp, 0, None)
        g = np.exp(-((U-uc)/width)**2) * np.exp(-np.clip(Yp, 0, None)/f.get("fade", 12.0)) * (Yp > 0)
        cv.glow(mask, g)
        side = s.get("side", "front")
        out = {"front": -1, "back": 1, "left": -1, "right": 1}[side]
        c = [0.0, 0.0, 0.0]; c[a] = s["at"] + out*f.get("offset", 0.5); c[hk] = uc
        ring = [[c[0]+0.3*np.cos(t), 0.0, c[2]+0.3*np.sin(t)] for t in np.linspace(0, 2*np.pi, 32, endpoint=False)]
        rp = m.project(ring); vis = cv.visible(ring, rp).mean() > 0.5
        if vis:
            cv2.fillPoly(cv.img, [np.int32(rp)], (255, 255, 255), cv2.LINE_AA)
            cv2.polylines(cv.img, [np.int32(rp)], True, (0, 0, 0), 1, cv2.LINE_AA)
        cv.add(f, "uplight", face, c, visible=bool(vis))


def wash(cv, f):
    m = cv.m; s = m.surface(f["plane"]); i = cv.sid(f["plane"]); a = s["axis"]
    hk = 0 if a == 2 else 2
    u0, u1 = f["range"]; yt = f.get("y_top", s["Y"][1])
    mask = cv.ids == i
    U, Yp = cv.P[..., hk], cv.P[..., 1]
    edge = np.clip(np.minimum(U-u0, u1-U)/1.5, 0, 1)
    g = f.get("strength", 0.8)*np.exp(-np.clip(yt-Yp, 0, None)/f.get("fade", 10.0))*edge*(Yp <= yt)
    cv.glow(mask, g)
    if f.get("slot"):
        sp = m.surface(f["slot"]["plane"]); sx = f["slot"]["offset"]
        yv = sp["at"]; wall = s["at"]
        if a == 0: cv.seg([wall+sx, yv, u0], [wall+sx, yv, u1], 2)
        else: cv.seg([u0, yv, wall+sx], [u1, yv, wall+sx], 2)
    cv.add(f, "wash", f["plane"], m.to3d(s, u0, yt), note=f"range {u0:.2f}..{u1:.2f}")


LIGHTS = dict(downlight=downlight, sconce=sconce, uplight=uplight, wash=wash)
