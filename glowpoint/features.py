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
        sp = m.surface(f["slot"]["plane"]); sx = f["slot"]["offset"]
        yv = sp["at"]; wall = s["at"]
        if a == 0: cv.seg([wall+sx, yv, u0], [wall+sx, yv, u1], 2)
        else: cv.seg([u0, yv, wall+sx], [u1, yv, wall+sx], 2)
    cv.add(f, "wash", f["plane"], m.to3d(s, u0, yt), note=f"range {u0:.2f}..{u1:.2f}")


def pendant(cv, f):
    """A pendant hanging from a horizontal surface. Height: "y" (bottom of the shade above the floor)
    or "drop" (from the ceiling to the bottom of the shade)."""
    m = cv.m; s = m.surface(f["plane"])
    for x, z in itertools.product(as_list(f["x"]), as_list(f["z"])):
        top = m.to3d(s, x, z)
        y = f["y"] if "y" in f else top[1] - f.get("drop", 10.0)
        r = f.get("d", 1.5)/2; hgt = f.get("h", 0.6)
        th = np.linspace(0, 2*np.pi, 48, endpoint=False)
        bottom = [[x+r*np.cos(t), y, z+r*np.sin(t)] for t in th]
        upper = [[x+r*0.55*np.cos(t), y+hgt, z+r*0.55*np.sin(t)] for t in th]
        c = [x, y + hgt/2, z]
        shade = bottom + upper
        sp = m.project(shade); vis = cv.visible(shade, sp)
        if vis.mean() < 0.5:
            cv.add(f, "pendant", f["plane"], [x, y, z], visible=False); continue
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
        cv.add(f, "pendant", f["plane"], [x, y, z], visible=True)


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
        s = dict(name=f.get("surface_name", "ceiling"), axis=1, at=None)
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


LIGHTS = dict(downlight=downlight, sconce=sconce, uplight=uplight, wash=wash, pendant=pendant, fixture=fixture)
