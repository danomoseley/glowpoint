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
        self.fixtures = {}

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
    mod, depth = f["module"], f["depth"]
    shape = f.get("shape", "square")
    d = m.rays(ids.shape)
    y0 = s["at"]
    Q = P[mask]; D = d[mask]
    nx, nz = int((x1-x0)/mod + 0.01), int((z1-z0)/mod + 0.01)          # full coffers across and deep
    align = f.get("align", "start")
    ox = ((x1-x0) - nx*mod)/2 if align == "centre" else 0.0           # start of the grid
    oz = ((z1-z0) - nz*mod)/2 if align == "centre" else 0.0
    u = (Q[:, 0]-x0-ox)/mod; v = (z1-oz-Q[:, 2])/mod; iu, iv = np.floor(u), np.floor(v)
    partial = (iu < 0) | (iu >= nx) | (iv < 0) | (iv >= nz)          # cells that are not full coffers
    if shape == "round":
        r = f["d"]/2
        if not 0 < 2*r < mod: raise ValueError(f"round coffers: d ({2*r:.3f} ft) must be smaller than the module ({mod:.3f} ft)")
        ccx = x0 + ox + (iu+0.5)*mod; ccz = z1 - oz - (iv+0.5)*mod    # centre of each cell
        dx_, dz_ = Q[:, 0]-ccx, Q[:, 2]-ccz
        on_rib = (np.hypot(dx_, dz_) > r) | partial                    # a cut round coffer is left solid
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = depth/D[:, 1]                                      # to the coffer top
            a = D[:, 0]**2 + D[:, 2]**2; b = 2*(dx_*D[:, 0] + dz_*D[:, 2]); c = dx_**2 + dz_**2 - r*r
            tw = (-b + np.sqrt(np.maximum(b*b - 4*a*c, 0)))/(2*a)    # to the round wall (we start inside)
        tw = np.where(np.isfinite(tw) & (tw > 0), tw, np.inf)
        tmin = np.minimum(tt, tw)
        face = np.where(on_rib, 0, np.where(tmin == tt, 1, 2))
        hit = Q + np.where(on_rib, 0, tmin)[:, None]*D
        rr = np.hypot(hit[:, 0]-ccx, hit[:, 2]-ccz)
        top_glow = 0.55 + 0.45*np.clip(1 - rr/r, 0, 1)
        # walls: a little darker where the wall turns away from the camera
        wnx, wnz = -(hit[:, 0]-ccx)/r, -(hit[:, 2]-ccz)/r
        facing = np.clip(-(wnx*D[:, 0] + wnz*D[:, 2])/np.sqrt(np.maximum(a, 1e-12)), 0, 1)
        wall_g = 0.7 + 0.25*facing
        g = {1: top_glow, 2: wall_g, 3: wall_g}
        cell_lab = (iu.astype(np.int64)*97 + iv.astype(np.int64)) % 100000
    else:
        rib = f["rib"]; h = rib/2
        fu, fv = (u-iu)*mod, (v-iv)*mod
        on_rib = (fu < h) | (fu > mod-h) | (fv < h) | (fv > mod-h)
        if align == "centre": on_rib |= partial                        # centred grid: solid border
        cx0 = x0+ox+iu*mod+h; cx1 = x0+ox+(iu+1)*mod-h; cz1 = z1-oz-iv*mod-h; cz0 = z1-oz-(iv+1)*mod+h
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = depth/D[:, 1]
            tx = np.where(D[:, 0] > 0, (cx1-Q[:, 0])/D[:, 0], np.where(D[:, 0] < 0, (cx0-Q[:, 0])/D[:, 0], np.inf))
            tz = np.where(D[:, 2] > 0, (cz1-Q[:, 2])/D[:, 2], np.where(D[:, 2] < 0, (cz0-Q[:, 2])/D[:, 2], np.inf))
        tmin = np.minimum(tt, np.minimum(tx, tz))
        face = np.where(on_rib, 0, np.where(tmin == tt, 1, np.where(tmin == tx, 2, 3)))
        hit = Q + np.where(on_rib, 0, tmin)[:, None]*D
        gu = np.clip(1-np.abs(hit[:, 0]-(cx0+cx1)/2)/((cx1-cx0)/2), 0, 1)
        gv = np.clip(1-np.abs(hit[:, 2]-(cz0+cz1)/2)/((cz1-cz0)/2), 0, 1)
        g = {1: 0.55+0.45*np.sqrt(gu*gv), 2: np.full(len(Q), 0.85), 3: np.full(len(Q), 0.9)}
        cell_lab = (iu.astype(np.int64)*97 + iv.astype(np.int64)) % 100000
    cv.P[mask] = hit                                   # true 3D point: ceiling, coffer top or coffer wall
    cv.dep[mask] = m.depth(hit)
    over = base.copy(); sub = over[mask]
    cols = {1: GLOW, 2: (45, 165, 235), 3: (30, 130, 215)}
    lit = f.get("lit", True)
    for k_, col in cols.items():
        k = face == k_
        if not lit: col = (228, 228, 228) if k_ == 1 else (200, 200, 200)
        for ch in range(3):
            sub[k, ch] = (sub[k, ch]*(1-g[k_][k]) + col[ch]*g[k_][k]).astype(np.uint8)
    over[mask] = sub
    lab = np.full(ids.shape, -1, np.int64)
    lab[mask] = np.where(face == 0, 1, (face+1) + 7*cell_lab)      # the flat ceiling has no cell lines
    e = np.zeros(ids.shape, bool)
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]; e[1:, :] |= lab[1:, :] != lab[:-1, :]
    e &= mask | np.roll(mask, 1, 0) | np.roll(mask, 1, 1)
    res = cv2.addWeighted(over, 0.6, base, 0.4, 0); res = np.minimum(res, base)
    res[e] = (res[e]*0.35).astype(np.uint8)
    edge = cv2.Canny(mask.astype(np.uint8)*255, 50, 150) > 0
    res[cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0] = 0
    cv.report.append(dict(layer=f.get("layer", ""), type="waffle", surface=s["name"], x=round(x0, 2), y=round(y0, 2), z=round(z0, 2),
                          note=f"X {x0:.2f}..{x1:.2f}, Z {z0:.2f}..{z1:.2f}, {nx} x {nz} coffers, {shape}, align {align}, "
                               f"module {mod*12:.1f} in, " + (f"diameter {f['d']*12:.1f} in" if shape == "round" else f"rib {f['rib']*12:.1f} in")
                               + f", depth {depth*12:.1f} in"))
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
        sp = m.surface(f["slot"]["plane"]); wall = s["at"]
        side = 1.0 if m.C_drawing[a] > wall else -1.0               # the slot is always on the room side
        sx = side*abs(f["slot"]["offset"])
        yv = sp["at"]
        if a == 0: cv.seg([wall+sx, yv, u0], [wall+sx, yv, u1], 2)
        else: cv.seg([u0, yv, wall+sx], [u1, yv, wall+sx], 2)
    cv.add(f, "wash", f["plane"], m.to3d(s, u0, yt), note=f"range {u0:.2f}..{u1:.2f}")


def pendant(cv, f):
    """A pendant hanging from a horizontal surface ("plane") or from a height ("from_y", for example the top
    of the coffers). Height: "y" (bottom of the shade above the floor) or "drop" (from the cord start to the
    bottom of the shade)."""
    m = cv.m
    s = m.surface(f["plane"]) if "plane" in f else None
    if s is None and "from_y" not in f: raise ValueError("pendant needs 'plane' or 'from_y'")
    for x, z in itertools.product(as_list(f["x"]), as_list(f["z"])):
        top = [x, f["from_y"], z] if "from_y" in f else m.to3d(s, x, z)     # where the cord starts
        y = f["y"] if "y" in f else top[1] - f.get("drop", 10.0)
        r = f.get("d", 1.5)/2; hgt = f.get("h", 0.6)
        th = np.linspace(0, 2*np.pi, 48, endpoint=False)
        bottom = [[x+r*np.cos(t), y, z+r*np.sin(t)] for t in th]
        upper = [[x+r*0.55*np.cos(t), y+hgt, z+r*0.55*np.sin(t)] for t in th]
        c = [x, y + hgt/2, z]
        shade = bottom + upper
        sp = m.project(shade); vis = cv.visible(shade, sp)
        if vis.mean() < 0.5:
            cv.add(f, "pendant", f.get("plane", "y=%g" % top[1]), [x, y, z], visible=False); continue
        pc = m.project([c])[0]; halo = max(5, int(m.f*r*2.2/max(m.depth([c])[0], 0.1)))
        cv2.circle(cv.over, tuple(np.int32(pc)), halo, (120, 230, 255), -1, cv2.LINE_AA)
        pr = f.get("pool_r", 0.0)
        if pr > 0:
            ty = f.get("beam_to", 0.0)
            pool = [[x+pr*np.cos(t), ty, z+pr*np.sin(t)] for t in th]; pp = m.project(pool)
            if cv.visible(pool, pp).mean() > 0.6:
                pim = cv.img.copy(); cv2.fillPoly(pim, [np.int32(pp)], GLOW, cv2.LINE_AA)
                cv.img[:] = cv2.addWeighted(pim, 0.35, cv.img, 0.65, 0)
        cv.seg(top, [x, y + hgt, z], 1)
        hull = cv2.convexHull(np.float32(sp)).astype(np.int32)
        cv2.fillPoly(cv.img, [hull], (255, 255, 255), cv2.LINE_AA)
        cv2.polylines(cv.img, [hull], True, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.polylines(cv.img, [np.int32(m.project(bottom))], True, (0, 0, 0), 1, cv2.LINE_AA)
        cv.add(f, "pendant", f.get("plane", "y=%g" % top[1]), [x, y, z], visible=True)


# ---------------------------------------------------------------- drawn fixtures
COLORS = {"lit": (175, 238, 255), "trim": (238, 238, 238), "metal": (190, 190, 190), "dark": (60, 60, 60),
          "black": (20, 20, 20), "white": (255, 255, 255)}


def _color(c):
    return tuple(int(v) for v in (COLORS[c] if isinstance(c, str) else c[::-1]))   # names, or [R, G, B]


def _shape_dist(shape, u, v, part):
    """Signed distance (ft) from the outline of a part: < 0 inside. u, v are local plane coordinates."""
    if shape == "round":
        return np.hypot(u, v) - part["d"]/2
    w = part.get("w", part.get("d")); l = part.get("l", w)
    return np.maximum(np.abs(u) - w/2, np.abs(v) - l/2)


def fixture(cv, f):
    """A fixture drawn from its parts, flush on a surface. The parts come from the fixture list
    (design.json "fixtures", or <project>/fixtures.json)."""
    m = cv.m
    spec = cv.fixtures.get(f["fixture"]) if isinstance(f["fixture"], str) else f["fixture"]
    if spec is None:
        raise KeyError(f"No fixture named '{f['fixture']}'. Known: {sorted(cv.fixtures)}")
    if "y" in f and "plane" not in f:
        s = dict(name="level", axis=1, at=None)
    else:
        s = m.surface(f["plane"])
    a = s["axis"]
    size = max(max(p.get("d", 0), p.get("w", 0), p.get("l", 0)) for p in spec["parts"])
    rot = np.radians(f.get("rotate", 0)); cr, sr = np.cos(rot), np.sin(rot)
    glow = spec.get("glow")
    H, W = cv.ids.shape
    if a == 1: keys = [("x", "z")]
    else: keys = [("along", "y")]
    for p1, p2 in itertools.product(as_list(f[keys[0][0]]), as_list(f[keys[0][1]])):
        if a == 1:
            at = f["y"] if "y" in f else s["at"]; c = [p1, at, p2]; ui, vi = 0, 2
        elif a == 0:
            at = s["at"]; c = [at, p2, p1]; ui, vi = 2, 1
        else:
            at = s["at"]; c = [p1, p2, at]; ui, vi = 0, 1
        # pixels near this fixture: bounding box of its projected footprint
        r = size/2 + (glow.get("r", 0) if glow else 0)
        corners = []
        for du, dv in ((-r, -r), (r, -r), (r, r), (-r, r)):
            q = list(c); q[ui] += du; q[vi] += dv; corners.append(q)
        pc = m.project(corners)
        if not np.all(np.isfinite(pc)) or np.any(m.depth(corners) <= 0):
            cv.add(f, "fixture", f.get("plane", "y=%g" % at), c, visible=False); continue
        x0, y0 = np.floor(pc.min(0)).astype(int) - 2; x1, y1 = np.ceil(pc.max(0)).astype(int) + 3
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W), min(y1, H)
        if x0 >= x1 or y0 >= y1:
            cv.add(f, "fixture", f.get("plane", "y=%g" % at), c, visible=False); continue
        P = cv.P[y0:y1, x0:x1]
        on = (np.abs(P[..., a] - at) < 0.02) & (cv.ids[y0:y1, x0:x1] >= 0)
        du = P[..., ui] - c[ui]; dv = P[..., vi] - c[vi]
        u = cr*du + sr*dv; v = -sr*du + cr*dv
        gy, gx = np.gradient(u); px = np.hypot(gx, gy) + 1e-9          # ft per pixel here
        drawn = np.zeros(on.shape, bool)
        img = cv.img[y0:y1, x0:x1]
        for part in spec["parts"]:
            kind = part.get("kind", "fill"); shape = part.get("shape", "round")
            dist = _shape_dist(shape, u, v, part)
            if kind == "fill":
                k = on & (dist <= 0)
            elif kind == "line":
                k = on & (np.abs(dist) <= np.maximum(part.get("width", 0.04)/2, 0.6*px))
            elif kind == "slots":
                n = part.get("n", 3); ang = np.radians(part.get("angle", 0))
                t = np.cos(ang)*u + np.sin(ang)*v
                span = part.get("w", part.get("d")); pitch = span/(n+1)
                k = on & (dist <= 0) & (np.abs(((t + span/2)/pitch) - np.round((t + span/2)/pitch))*pitch
                                        <= np.maximum(part.get("width", 0.03)/2, 0.6*px)) & (np.abs(t) < span/2)
            else:
                raise ValueError(f"unknown fixture part kind '{kind}' (fill, line, slots)")
            if k.any():
                img[k] = _color(part.get("color", "black" if kind != "fill" else "lit"))
                drawn |= k
        if glow:
            d3 = np.linalg.norm(P - np.array(c), axis=-1)
            g = glow.get("strength", 0.6)*np.exp(-(d3/glow.get("r", 1.0))**2)
            sub = cv.over[y0:y1, x0:x1]; kk = (g > 0.03) & ~drawn & (cv.ids[y0:y1, x0:x1] >= 0)
            for ch, val in enumerate(GLOW):
                sub[..., ch][kk] = (sub[..., ch][kk]*(1-g[kk]) + val*g[kk]).astype(np.uint8)
        cv.add(f, "fixture", f.get("plane", "y=%g" % at), c, visible=bool(drawn.any()), note=f["fixture"] if isinstance(f["fixture"], str) else "")


def luminous(cv, f):
    """A glowing area on a surface: a luminous ceiling, a backlit stretch ceiling, a light wall.
    Area: X and Z on horizontal surfaces, Z and Y on walls at constant X, X and Y on walls at constant Z."""
    m = cv.m; s = m.surface(f["plane"]); i = cv.sid(f["plane"]); a = s["axis"]
    keys = [k for k in "XYZ" if k != "XYZ"[a]]
    P = cv.P; k = cv.ids == i
    soft = f.get("soft", 0.5)
    edge = np.ones(k.shape)
    for key in keys:
        lo, hi = f[key]; c = P[..., "XYZ".index(key)]
        k &= (c >= lo) & (c <= hi)
        edge = np.minimum(edge, np.clip(np.minimum(c-lo, hi-c)/max(soft, 1e-6), 0, 1))
    g = f.get("strength", 0.9)*(0.6 + 0.4*edge)
    for ch, val in enumerate((150, 235, 255)):
        cv.img[..., ch][k] = (cv.img[..., ch][k]*(1-g[k]) + val*g[k]).astype(np.uint8)
    cv.glow(k, g*0.8)
    mod = f.get("grid")
    if mod:                                                      # panel joints
        for key in keys:
            lo = f[key][0]; u = P[..., "XYZ".index(key)] - lo
            gy, gx = np.gradient(u); px = np.hypot(gx, gy)
            line = k & (np.abs(u - np.round(u/mod)*mod) < np.maximum(f.get("joint", 0.03)/2, 0.5*px)) & (px < mod/3)
            cv.img[line] = (cv.img[line]*0.75).astype(np.uint8)
    c = [0.0, 0.0, 0.0]; c[a] = s["at"]
    for key in keys: c["XYZ".index(key)] = sum(f[key])/2
    area = np.prod([f[key][1]-f[key][0] for key in keys])
    cv.add(f, "luminous", f["plane"], c, visible=bool(k.any()), note=f"{area:.1f} sq ft" + (f", panels {mod*12:.0f} in" if mod else ""))


def slots(cv, f):
    """Narrow recessed lines in a surface: lit slots (lens) or track channels (track), as parallel lines or a grid."""
    m = cv.m; s = m.surface(f["plane"]); i = cv.sid(f["plane"]); a = s["axis"]
    keys = [k for k in "XYZ" if k != "XYZ"[a]]                     # the two axes of the surface
    P = cv.P; k_area = cv.ids == i
    for key in keys:
        lo, hi = f[key]; c = P[..., "XYZ".index(key)]; k_area &= (c >= lo) & (c <= hi)
    w = f.get("w", 0.25); pitch = f.get("pitch", 4.0); style = f.get("style", "lens")
    direction = f.get("direction", "grid")
    # a line "along Z" has a constant X: its distance is measured across X
    across = {"z": [keys[0]], "x": [keys[1]], "grid": keys}.get(direction)
    if across is None: raise ValueError("slots direction must be 'x', 'z' or 'grid'")
    band = np.zeros(k_area.shape, bool); centre = np.zeros(k_area.shape, bool); n_lines = 0
    for key in across:
        lo, hi = f[key]; u = P[..., "XYZ".index(key)] - lo - f.get("offset", pitch/2)
        gy, gx = np.gradient(u); px = np.hypot(gx, gy)
        dist = np.abs(u - np.round(u/pitch)*pitch)
        band |= k_area & (dist <= np.maximum(w/2, 0.6*px)) & (px < pitch/3)
        centre |= k_area & (dist <= np.maximum(w/6, 0.4*px)) & (px < pitch/3)
        n_lines += int((hi - lo - f.get("offset", pitch/2))/pitch + 1e-6) + 1
    if style == "lens":
        for ch, val in enumerate((165, 238, 255)):
            cv.img[..., ch][band] = val
        # soft spill next to the slots
        if band.any():
            dist_px = cv2.distanceTransform((~band).astype(np.uint8), cv2.DIST_L2, 3)
            g = f.get("strength", 0.7)*np.exp(-(dist_px/6.0)**2)
            cv.glow(k_area & ~band, g)
    elif style == "track":
        cv.img[band] = (60, 60, 60)
        sp = f.get("spot_spacing")
        if sp:                                                     # spot heads along the tracks
            heads = np.zeros(band.shape, bool)
            for key in across:
                other = [kk for kk in keys if kk != key][0]
                lo_k = f[key][0]; u = P[..., "XYZ".index(key)] - lo_k - f.get("offset", pitch/2)
                du = np.abs(u - np.round(u/pitch)*pitch)
                lo_o = f[other][0]; v = P[..., "XYZ".index(other)] - lo_o - sp/2
                gy, gx = np.gradient(v); px = np.hypot(gx, gy)
                dv = np.abs(v - np.round(v/sp)*sp)
                hs = f.get("spot_size", 0.35)/2
                heads |= k_area & (du <= hs) & (dv <= hs) & (px < sp/6)      # only where the heads are separate
            if heads.any():
                for ch, val in enumerate((165, 238, 255)):
                    cv.img[..., ch][heads] = val
                dist_px = cv2.distanceTransform((~heads).astype(np.uint8), cv2.DIST_L2, 3)
                cv.glow(k_area & ~heads, 0.7*np.exp(-(dist_px/5.0)**2))
                edge = heads & ~cv2.erode(heads.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
                cv.img[edge] = (40, 40, 40)
    else:
        raise ValueError("slots style must be 'lens' or 'track'")
    c = [0.0, 0.0, 0.0]; c[a] = s["at"]
    for key in keys: c["XYZ".index(key)] = sum(f[key])/2
    cv.add(f, "slots", f["plane"], c, visible=bool(band.any()),
           note=f"{style} {direction}, {n_lines} lines, {w*12:.1f} in wide, {pitch:.2f} ft apart")


def linear_pendant(cv, f):
    """Suspended linear fixture: direct light down and indirect light up onto the ceiling."""
    m = cv.m
    s = m.surface(f["plane"]) if "plane" in f else None
    direction = f.get("direction", "z")
    L = f.get("length", 4.0); wd = f.get("w", 0.3); hh = f.get("h", 0.25)
    ai = 2 if direction == "z" else 0; bi = 0 if direction == "z" else 2     # along, across
    for x, z in itertools.product(as_list(f["x"]), as_list(f["z"])):
        top_y = f["from_y"] if "from_y" in f else (s["at"] if s else None)
        if top_y is None: raise ValueError("linear_pendant needs 'plane' or 'from_y'")
        yb = f["y"] if "y" in f else top_y - f.get("drop", 4.0)            # bottom of the fixture
        c = np.array([x, yb + hh/2, z])
        # body corners
        def pt(da, db, dy):
            q = c.copy(); q[ai] += da; q[bi] += db; q[1] += dy; return q.tolist()
        bottom = [pt(-L/2, -wd/2, -hh/2), pt(L/2, -wd/2, -hh/2), pt(L/2, wd/2, -hh/2), pt(-L/2, wd/2, -hh/2)]
        topq = [pt(-L/2, -wd/2, hh/2), pt(L/2, -wd/2, hh/2), pt(L/2, wd/2, hh/2), pt(-L/2, wd/2, hh/2)]
        allp = bottom + topq
        pix = m.project(allp); vis = cv.visible(allp, pix)
        if vis.mean() < 0.4 or not np.all(np.isfinite(pix)):
            cv.add(f, "linear_pendant", f.get("plane", "y=%g" % top_y), c.tolist(), visible=False); continue
        # indirect light on the surfaces above (ceiling) and direct light below, measured in 3D
        P = cv.P
        dperp = np.abs(P[..., bi] - c[bi])
        dalong = np.maximum(np.abs(P[..., ai] - c[ai]) - L/2, 0)
        above = (P[..., 1] > c[1] + hh) & (cv.ids >= 0)
        below = (P[..., 1] < c[1] - hh) & (cv.ids >= 0)
        up, down = f.get("up", 0.6), f.get("down", 0.5)
        if up > 0:
            sp = f.get("spread_up", 3.0)
            cv.glow(above, up*np.exp(-(dperp/sp)**2 - (dalong/sp)**2))
        if down > 0:
            sp = f.get("spread_down", 2.5)
            cv.glow(below & (P[..., 1] < 0.2), down*np.exp(-(dperp/sp)**2 - (dalong/sp)**2))
        # body: sides, then the lit bottom lens
        hull = cv2.convexHull(np.float32(pix)).astype(np.int32)
        cv2.fillPoly(cv.img, [hull], (225, 225, 225), cv2.LINE_AA)
        cv2.polylines(cv.img, [hull], True, (0, 0, 0), 1, cv2.LINE_AA)
        bp = np.int32(m.project(bottom))
        cv2.fillPoly(cv.img, [bp], (165, 238, 255), cv2.LINE_AA)
        cv2.polylines(cv.img, [bp], True, (60, 60, 60), 1, cv2.LINE_AA)
        # suspension cables at both ends
        for da in (-L/2*0.85, L/2*0.85):
            cv.seg(pt(da, 0, hh/2), [pt(da, 0, hh/2)[0], top_y, pt(da, 0, hh/2)[2]], 1)
        cv.add(f, "linear_pendant", f.get("plane", "y=%g" % top_y), [x, yb, z], visible=True,
               note=f"{L:.1f} ft along {direction.upper()}")


# ---------------------------------------------------------------- track lighting
MM = 1/304.8                                               # millimetres to feet
APERTURES = {                                              # track head diameters, from manufacturers' specs
    "XS": 32*MM, "S": 60*MM, "M": 92*MM, "L": 129*MM,      # ERCO Parscan sizes
    "2.5in": 2.5/12, "3in": 3/12, "3.75in": 3.75/12,       # Solais Xd20, Xd24, Xd30
    "2in": 2/12, "4in": 4/12,
}
HOUSING = {"white": (238, 238, 238), "black": (45, 45, 45), "silver": (195, 195, 195)}


def _ray_hit(m, o, d):
    """Nearest surface hit of one ray (origin o, direction d), honouring holes. Returns the point or None."""
    best, hit = np.inf, None
    for s in m.surfaces:
        a = s["axis"]
        if abs(d[a]) < 1e-9: continue
        t = (s["at"] - o[a]) / d[a]
        if t <= 1e-6 or t >= best: continue
        q = o + t*d; ok = True
        for k, key in enumerate("XYZ"):
            if k == a: continue
            lo, hi = s[key]
            if not (lo - 1e-6 <= q[k] <= hi + 1e-6): ok = False; break
        if ok:
            for hole in s.get("holes", []):
                if all(lo < q["XYZ".index(key)] < hi for key, (lo, hi) in hole.items()): ok = False; break
        if ok: best, hit = t, q
    return hit


def track(cv, f):
    """A track with heads. Mounting: surface (profile below the ceiling), recessed (flush channel with a trim
    flange), trimless (flush channel, no trim), suspended (profile hanging on cables)."""
    m = cv.m
    s = m.surface(f["plane"]) if "plane" in f else None
    yt = f["from_y"] if "from_y" in f else s["at"]
    mounting = f.get("mounting", "surface")
    direction = f.get("direction", "z"); ai = 2 if direction == "z" else 0; bi = 0 if direction == "z" else 2
    u0, u1 = f["range"]; pw = f.get("profile_w", 36*MM); ph = f.get("profile_h", 30*MM)
    col = HOUSING.get(f.get("color", "white"), HOUSING["white"]) if isinstance(f.get("color", "white"), str) else tuple(f["color"][::-1])
    ap = f.get("aperture", "S"); dia = APERTURES[ap] if isinstance(ap, str) else float(ap)
    head = f.get("head", "cylinder"); hl = f.get("head_l", 1.6*dia)
    tilt, pan = np.radians(f.get("tilt", 0)), np.radians(f.get("pan", 0))
    beam = np.radians(f.get("beam", 25)); pool = f.get("pool", 0.5)
    n_heads_total = 0
    for at in as_list(f["at"]):
        def P3(u, du=0.0, y=None):
            q = [0.0, 0.0, 0.0]; q[ai] = u; q[bi] = at + du; q[1] = yt if y is None else y; return q
        # ---- the track itself
        if mounting in ("surface", "suspended"):
            ytop = yt if mounting == "surface" else yt - f.get("drop", 3.0)
            ybot = ytop - ph
            # draw the profile in short pieces, so that a run that passes behind the camera or behind a
            # column still shows where it is visible
            edges = np.arange(u0, u1, f.get("piece", 1.0)).tolist() + [u1]
            for ua, ub in zip(edges[:-1], edges[1:]):
                corners = [P3(u, du, y) for u in (ua, ub) for du in (-pw/2, pw/2) for y in (ytop, ybot)]
                if np.any(m.depth(corners) <= 0.05): continue
                pix = m.project(corners); vis = cv.visible(corners, pix)
                if vis.mean() < 0.5: continue
                hull = cv2.convexHull(np.float32(pix)).astype(np.int32)
                cv2.fillPoly(cv.img, [hull], col, cv2.LINE_AA)
            # outline along the bottom edges of the profile
            for du in (-pw/2, pw/2):
                cv.seg(P3(u0, du, ybot), P3(u1, du, ybot), 1, n=400)
            if mounting == "suspended":
                n = max(2, int((u1 - u0)/f.get("cable_spacing", 8.0)) + 1)
                for u in np.linspace(u0 + 0.5, u1 - 0.5, n):
                    cv.seg(P3(u, 0, ytop), P3(u, 0, yt), 1)
            mount_y = ybot
        else:                                              # recessed / trimless: flush with the surface
            if s is None: raise ValueError("recessed or trimless track needs 'plane'")
            i = cv.sid(f["plane"]); P = cv.P
            on = (cv.ids == i) & (P[..., ai] >= u0) & (P[..., ai] <= u1)
            dperp = np.abs(P[..., bi] - at)
            gy, gx = np.gradient(P[..., bi]); px = np.hypot(gx, gy)
            chan = on & (dperp <= np.maximum(pw/2, 0.6*px))
            cv.img[chan] = (35, 35, 35)
            if mounting == "recessed":                     # visible trim flange around the channel
                fl = f.get("flange", 12*MM)
                trim = on & ~chan & (dperp <= pw/2 + fl)
                cv.img[trim] = col if col != HOUSING["black"] else (90, 90, 90)
                for du in (-(pw/2 + fl), pw/2 + fl):
                    cv.seg(P3(u0, du), P3(u1, du), 1)
            mount_y = yt
        # ---- heads
        if "count" in f:
            n = int(f["count"]); us = [u0 + (u1-u0)*(k+0.5)/n for k in range(n)]
        else:
            sp = f.get("spacing", 4.0); us = list(np.arange(u0 + sp/2, u1 - sp/2 + 1e-6, sp))
        for u in us:
            pivot = np.array(P3(u, 0, mount_y - (0 if head == "flush" else f.get("stem", 0.12))))
            # aim: straight down, tilted by 'tilt' towards the 'pan' direction (pan 0 = across the track, +)
            dirv = np.zeros(3); dirv[1] = -np.cos(tilt)
            dirv[bi] = np.sin(tilt)*np.cos(pan); dirv[ai] = np.sin(tilt)*np.sin(pan)
            if head == "flush":
                front = pivot + dirv*0.01
            else:
                front = pivot + dirv*hl
                cv.seg(P3(u, 0, mount_y), pivot.tolist(), 1)
            # rings at the back and front of the head, perpendicular to the aim
            tmp = np.array([1.0, 0, 0]) if abs(dirv[0]) < 0.9 else np.array([0, 0, 1.0])
            e1 = np.cross(dirv, tmp); e1 /= np.linalg.norm(e1); e2 = np.cross(dirv, e1)
            th = np.linspace(0, 2*np.pi, 40, endpoint=False)
            ring = lambda c, r: [(c + r*(np.cos(t)*e1 + np.sin(t)*e2)).tolist() for t in th]
            back, frontr, apr = ring(pivot, dia/2), ring(front, dia/2), ring(front, dia/2*0.78)
            allp = back + frontr
            pix = m.project(allp)
            if not np.all(np.isfinite(pix)) or cv.visible(allp, pix).mean() < 0.4:
                cv.add(f, "track head", f.get("plane", "y=%g" % yt), front.tolist(), visible=False,
                       note=f"{ap if isinstance(ap, str) else round(dia*12, 2)} ({dia*12:.2f} in) {head}, {mounting} track"); n_heads_total += 1; continue
            # beam pool where the aim ray lands
            if pool > 0:
                hit = _ray_hit(m, front, dirv)
                if hit is not None:
                    dist = np.linalg.norm(hit - front); r = dist*np.tan(beam/2) + dia/2
                    d3 = np.linalg.norm(cv.P - hit, axis=-1)
                    g = pool*np.exp(-(d3/r)**4)
                    cv.glow((cv.ids >= 0) & (d3 < 1.6*r), g)
            if head != "flush":
                hull = cv2.convexHull(np.float32(pix)).astype(np.int32)
                cv2.fillPoly(cv.img, [hull], col, cv2.LINE_AA)
                cv2.polylines(cv.img, [hull], True, (30, 30, 30), 1, cv2.LINE_AA)
            # the aperture, if it faces the camera
            to_cam = m.C - front
            if np.dot(to_cam, dirv) > 0:
                fp = np.int32(m.project(frontr)); apix = np.int32(m.project(apr))
                cv2.fillPoly(cv.img, [fp], (30, 30, 30) if head != "flush" else col, cv2.LINE_AA)
                cv2.fillPoly(cv.img, [apix], (165, 238, 255), cv2.LINE_AA)
            cv.add(f, "track head", f.get("plane", "y=%g" % yt), front.tolist(), visible=True,
                   note=f"{ap if isinstance(ap, str) else round(dia*12, 2)} ({dia*12:.2f} in) {head}, {mounting} track")
            n_heads_total += 1
    cv.add(f, "track", f.get("plane", "y=%g" % yt), [0.0, yt, 0.0], visible=True,
           note=f"{mounting}, {len(as_list(f['at']))} run(s) along {direction.upper()}, {u1-u0:.1f} ft, {n_heads_total} heads")


def glow(cv, f):
    """A soft glow around a point: a table lamp, floor lamp, or candle that is already in the drawing,
    or any small light source. The glow lights nearby surfaces and shows a halo around the source."""
    m = cv.m
    xs, ys, zs = as_list(f["x"]), as_list(f["y"]), as_list(f["z"])
    r = f.get("r", 2.0); st = f.get("strength", 0.7); halo = f.get("halo", 0.6)
    for x, y, z in itertools.product(xs, ys, zs):
        c = np.array([x, y, z], float)
        if m.depth([c])[0] <= 0:
            cv.add(f, "glow", "point", c.tolist(), visible=False); continue
        pc = m.project([c])[0]; vis = bool(cv.visible([c.tolist()], [pc])[0])
        d3 = np.linalg.norm(cv.P - c, axis=-1)
        cv.glow((cv.ids >= 0) & (d3 < 3*r), st*np.exp(-(d3/r)**2))           # light on the surfaces nearby
        if vis and halo > 0:                                                  # halo around the source itself
            rpx = max(4, int(m.f*halo/max(m.depth([c])[0], 0.1)))
            H, W = cv.ids.shape; yy, xx = np.ogrid[:H, :W]
            g = np.minimum(1.0, 1.3*np.exp(-(((xx-pc[0])**2 + (yy-pc[1])**2)/(rpx**2))))
            cv.glow(g > 0.05, g)
        cv.add(f, "glow", "point", c.tolist(), visible=vis)


LIGHTS = dict(glow=glow, downlight=downlight, sconce=sconce, uplight=uplight, wash=wash, pendant=pendant, fixture=fixture,
              luminous=luminous, slots=slots, linear_pendant=linear_pendant, track=track)
