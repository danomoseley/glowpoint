"""3D model of the space behind a perspective drawing.

model.json holds:
  camera    one-point:  vp (vanishing point, px), f (lens, px), eye_height (ft)
            general:    f, principal [px, px], position [x, y, z] ft, yaw, pitch, roll (degrees)
                        yaw turns right, pitch looks up, roll turns the image clockwise
  surfaces  flat rectangles: name, axis (the axis they are perpendicular to), at, and ranges on the other two axes
  boxes     columns and objects: name, kind, X/Y/Z ranges. Each box becomes faces named
            "<name> front|back|left|right|top|bottom" (front faces the viewer, -Z).
All lengths in feet. X right, Y up (floor = 0), Z away from the viewer.
"""
import json, os
import numpy as np


def rotation(yaw=0.0, pitch=0.0, roll=0.0):
    """Rows of the result: the camera's right, up and forward directions in world coordinates."""
    y, p, r = np.radians([yaw, pitch, roll])
    fwd = np.array([np.sin(y)*np.cos(p), np.sin(p), np.cos(y)*np.cos(p)])
    right0 = np.array([np.cos(y), 0.0, -np.sin(y)])
    up0 = np.cross(fwd, right0)
    right = np.cos(r)*right0 - np.sin(r)*up0
    up = np.sin(r)*right0 + np.cos(r)*up0
    return np.stack([right, up, fwd])


def angles(R):
    """Inverse of rotation(): (yaw, pitch, roll) in degrees."""
    fwd = R[2]
    yaw = np.degrees(np.arctan2(fwd[0], fwd[2])); pitch = np.degrees(np.arcsin(np.clip(fwd[1], -1, 1)))
    R0 = rotation(yaw, pitch, 0)
    roll = np.degrees(np.arctan2(-np.dot(R[0], R0[1]), np.dot(R[0], R0[0])))
    return float(yaw), float(pitch), float(roll)

AX = {"X": 0, "Y": 1, "Z": 2}
SLOPE = 3            # internal axis number of a sloped surface
VAULT = 4            # internal axis number of a barrel vault


class Frame:
    """A turned coordinate system in which a sloped surface is level: local = R (world - o) + o."""
    def __init__(self, R, o):
        self.R = np.asarray(R, float); self.o = np.asarray(o, float)

    def to_local(self, P):
        P = np.asarray(P, float); return (P - self.o) @ self.R.T + self.o

    def to_world(self, P):
        P = np.asarray(P, float); return (P - self.o) @ self.R + self.o

    def vec_local(self, d):
        return np.asarray(d, float) @ self.R.T


def slope_frame(s):
    """The frame in which the slope s is the level plane y = y0, with distances along the slope."""
    th = np.arctan(s["grad"]); c, sn = np.cos(th), np.sin(th)
    o = np.zeros(3); o[s["k"]] = s["u0"]; o[1] = s["y0"]
    if s["k"] == 0: R = [[c, sn, 0], [-sn, c, 0], [0, 0, 1]]
    else: R = [[1, 0, 0], [0, c, sn], [0, -sn, c]]
    return Frame(R, o)


def make_slope(s):
    """A sloped surface: it rises along X or Z, from "from": [u0, y0] to "to": [u1, y1], over the range of the
    other horizontal axis.  Adds the fields that the rest of glowpoint uses."""
    k = AX[s["along"]]; other = "Z" if k == 0 else "X"
    (u0, y0), (u1, y1) = s["from"], s["to"]
    if abs(u1 - u0) < 1e-9: raise ValueError(f"slope {s['name']}: 'from' and 'to' are at the same {s['along']}")
    s["axis"] = SLOPE; s["k"] = k; s["u0"], s["y0"], s["u1"], s["y1"] = u0, y0, u1, y1
    s["grad"] = (y1 - y0) / (u1 - u0)
    if s["along"] not in s or "outline" not in s: s[s["along"]] = sorted([u0, u1])
    s["Y"] = sorted([y0, y1]); s["other"] = other
    s["at"] = (y0 + y1) / 2                       # mean height (use height_at for the height at a point)
    return s


def make_vault(s):
    """A barrel vault: a circular arc across X (along Z) or across Z (along X), from the springing height
    "spring" up by "rise" at the crown, over the range across."""
    along = s.get("along", "Z"); k = AX["X" if along == "Z" else "Z"]           # the axis across the vault
    lo, hi = s["XYZ"[k]]; w = hi - lo; h = s["rise"]
    if not 0 < h <= w / 2 + 1e-9: raise ValueError(f"vault {s['name']}: rise must be between 0 and half the width")
    R = (w * w / 4 + h * h) / (2 * h)
    s.update(axis=VAULT, k=k, uc=(lo + hi) / 2, radius=R, yc=s["spring"] + h - R)
    s["Y"] = [s["spring"], s["spring"] + h]; s["at"] = s["spring"] + h
    return s


def height_at(s, x, z):
    """Height of a level, sloped or vaulted surface above the point (x, z)."""
    if s["axis"] == SLOPE:
        u = x if s["k"] == 0 else z
        return s["y0"] + s["grad"] * (u - s["u0"])
    if s["axis"] == VAULT:
        u = x if s["k"] == 0 else z
        return s["yc"] + np.sqrt(max(s["radius"] ** 2 - (u - s["uc"]) ** 2, 0.0))
    return s["at"]


def _in_polygon(u, v, poly):
    """Vectorised even-odd test: are the points (u, v) inside the polygon [[u, v], ...]?"""
    inside = np.zeros(np.shape(u), bool); n = len(poly)
    for i in range(n):
        (u1, v1), (u2, v2) = poly[i], poly[(i + 1) % n]
        with np.errstate(divide="ignore", invalid="ignore"):
            cross = ((v1 > v) != (v2 > v)) & (u < (u2 - u1) * (v - v1) / (v2 - v1 + 1e-300) + u1)
        inside ^= cross
    return inside


def hit_surface(s, C, d):
    """Distance t along the rays d from C to the surface s (inf where they miss), and the hit points."""
    C = np.asarray(C, float); d = np.asarray(d, float)
    fr = s.get("frame")
    Cl, dl = (fr.to_local(C), fr.vec_local(d)) if fr is not None else (C, d)
    a = s["axis"]
    with np.errstate(divide="ignore", invalid="ignore"):
        if a == SLOPE:                     # y = y0 + grad (u - u0)
            k = s["k"]
            t = (s["y0"] + s["grad"] * (Cl[k] - s["u0"]) - Cl[1]) / (dl[..., 1] - s["grad"] * dl[..., k])
        elif a == VAULT:                   # (u - uc)^2 + (y - yc)^2 = R^2, the upper arc, seen from below
            k = s["k"]; du, dy = dl[..., k], dl[..., 1]; cu, cy = Cl[k] - s["uc"], Cl[1] - s["yc"]
            A = du * du + dy * dy; B = 2 * (cu * du + cy * dy); Cc = cu * cu + cy * cy - s["radius"] ** 2
            disc = B * B - 4 * A * Cc
            sq = np.sqrt(np.maximum(disc, 0))
            t1, t2 = (-B - sq) / (2 * A), (-B + sq) / (2 * A)
            Q1y, Q2y = Cl[1] + t1 * dy, Cl[1] + t2 * dy
            # the nearer hit on the arc above the springing line
            ok1 = (t1 > 0) & (Q1y >= s["spring"] - 1e-6); ok2 = (t2 > 0) & (Q2y >= s["spring"] - 1e-6)
            t = np.where(ok1, t1, np.where(ok2, t2, np.inf)); t = np.where(disc >= 0, t, np.inf)
        else:
            t = (s["at"] - Cl[a]) / dl[..., a]
        Q = Cl + t[..., None] * dl
    ok = (t > 0) & np.isfinite(t)
    for k_, key in enumerate("XYZ"):
        if k_ == a or (a in (SLOPE, VAULT) and key == "Y") or key not in s: continue
        lo, hi = s[key]; ok &= (Q[..., k_] >= lo - 1e-6) & (Q[..., k_] <= hi + 1e-6)
    if "outline" in s:
        ku, kv = (AX[x] for x in uv_keys(s))
        ok &= _in_polygon(Q[..., ku], Q[..., kv], s["outline"])
    for hole in s.get("holes", []):
        ins = np.ones_like(ok)
        for key, (lo, hi) in hole.items():
            kk = AX[key]; ins &= (Q[..., kk] > lo) & (Q[..., kk] < hi)
        ok &= ~ins
    t = np.where(ok, t, np.inf)
    return t, C + t[..., None] * d


def expand_surface(s):
    """One surface from model.json -> one or more internal surfaces (hip and gable ceilings make several)."""
    ax = s.get("axis")
    if ax == "hip": return hip_faces(s)
    if ax == "gable": return gable_faces(s)
    if ax == "slope": out = make_slope(s)
    elif ax == "vault": out = make_vault(s)
    else: s["axis"] = AX[ax]; out = s
    if "outline" in out:                          # a polygon: its ranges come from the outline if not given
        ku, kv = uv_keys(out)
        for key, vals in ((ku, [p[0] for p in out["outline"]]), (kv, [p[1] for p in out["outline"]])):
            if key not in out or out["axis"] in (SLOPE, VAULT): out[key] = [min(vals), max(vals)]
    return [out]


def hip_faces(s):
    """A hip ceiling (or a pyramid): four sloped faces from the eave height up to a ridge.
    "X", "Z": the area; "eave", "ridge": heights; "ridge_along": X or Z (default: the longer side);
    "ridge_length": length of the ridge (default: so that all four faces have the same slope; 0 = pyramid)."""
    (x0, x1), (z0, z1) = s["X"], s["Z"]; e, r = s["eave"], s["ridge"]; name = s["name"]
    along = s.get("ridge_along", "Z" if (z1 - z0) >= (x1 - x0) else "X")
    if along == "Z":
        w = (x1 - x0) / 2; L = s.get("ridge_length", max((z1 - z0) - 2 * w, 0)); a = ((z1 - z0) - L) / 2
        xc = (x0 + x1) / 2; ra, rb = z0 + a, z1 - a
        faces = [dict(name=f"{name} left", along="X", **{"from": [x0, e], "to": [xc, r]}, outline=[[x0, z0], [x0, z1], [xc, rb], [xc, ra]]),
                 dict(name=f"{name} right", along="X", **{"from": [x1, e], "to": [xc, r]}, outline=[[x1, z0], [xc, ra], [xc, rb], [x1, z1]]),
                 dict(name=f"{name} front", along="Z", **{"from": [z0, e], "to": [z0 + a, r]}, outline=[[x0, z0], [xc, ra], [x1, z0]]),
                 dict(name=f"{name} back", along="Z", **{"from": [z1, e], "to": [z1 - a, r]}, outline=[[x0, z1], [x1, z1], [xc, rb]])]
        if L > 1e-6:
            faces[2]["outline"] = [[x0, z0], [xc, ra], [x1, z0]]
    else:
        w = (z1 - z0) / 2; L = s.get("ridge_length", max((x1 - x0) - 2 * w, 0)); a = ((x1 - x0) - L) / 2
        zc = (z0 + z1) / 2; ra, rb = x0 + a, x1 - a
        faces = [dict(name=f"{name} front", along="Z", **{"from": [z0, e], "to": [zc, r]}, outline=[[x0, z0], [ra, zc], [rb, zc], [x1, z0]]),
                 dict(name=f"{name} back", along="Z", **{"from": [z1, e], "to": [zc, r]}, outline=[[x0, z1], [x1, z1], [rb, zc], [ra, zc]]),
                 dict(name=f"{name} left", along="X", **{"from": [x0, e], "to": [x0 + a, r]}, outline=[[x0, z0], [x0, z1], [ra, zc]]),
                 dict(name=f"{name} right", along="X", **{"from": [x1, e], "to": [x1 - a, r]}, outline=[[x1, z0], [rb, zc], [x1, z1]])]
    out = []
    for fc in faces:
        if abs(fc["from"][0] - fc["to"][0]) < 1e-9: continue          # a face with no depth (square pyramid edge case)
        fc.update(axis="slope", X=[x0, x1], Z=[z0, z1], hip=name)
        out += expand_surface(fc)
    return out


def gable_faces(s):
    """A gable ceiling: two sloped faces from the eave height up to a ridge in the middle.
    "X", "Z": the area; "eave", "ridge": heights; "ridge_along": X or Z (default Z)."""
    (x0, x1), (z0, z1) = s["X"], s["Z"]; e, r = s["eave"], s["ridge"]; name = s["name"]
    if s.get("ridge_along", "Z") == "Z":
        xc = (x0 + x1) / 2
        faces = [dict(name=f"{name} left", along="X", **{"from": [x0, e], "to": [xc, r]}, Z=[z0, z1]),
                 dict(name=f"{name} right", along="X", **{"from": [x1, e], "to": [xc, r]}, Z=[z0, z1])]
    else:
        zc = (z0 + z1) / 2
        faces = [dict(name=f"{name} front", along="Z", **{"from": [z0, e], "to": [zc, r]}, X=[x0, x1]),
                 dict(name=f"{name} back", along="Z", **{"from": [z1, e], "to": [zc, r]}, X=[x0, x1])]
    out = []
    for fc in faces:
        fc.update(axis="slope", gable=name); out += expand_surface(fc)
    return out


def uv_keys(s):
    """The two coordinates used for positions on a surface: (X, Z) on level and sloped surfaces,
    (Z, Y) on walls at constant X, (X, Y) on walls at constant Z."""
    return {0: ("Z", "Y"), 1: ("X", "Z"), 2: ("X", "Y"), SLOPE: ("X", "Z"), VAULT: ("X", "Z")}[s["axis"]]


class Box:
    def __init__(self, d):
        self.name, self.kind = d["name"], d.get("kind", "object")
        self.x0, self.x1 = d["X"]; self.y0, self.y1 = d["Y"]; self.z0, self.z1 = d["Z"]

    @property
    def xc(self): return (self.x0 + self.x1) / 2
    @property
    def zc(self): return (self.z0 + self.z1) / 2
    @property
    def top(self): return self.y1

    def faces(self):
        n = self.name
        return [
            dict(name=n+" front", axis=2, at=self.z0, X=[self.x0, self.x1], Y=[self.y0, self.y1], box=n, side="front"),
            dict(name=n+" back",  axis=2, at=self.z1, X=[self.x0, self.x1], Y=[self.y0, self.y1], box=n, side="back"),
            dict(name=n+" left",  axis=0, at=self.x0, Y=[self.y0, self.y1], Z=[self.z0, self.z1], box=n, side="left"),
            dict(name=n+" right", axis=0, at=self.x1, Y=[self.y0, self.y1], Z=[self.z0, self.z1], box=n, side="right"),
            dict(name=n+" top",   axis=1, at=self.y1, X=[self.x0, self.x1], Z=[self.z0, self.z1], box=n, side="top"),
        ]


class Model:
    def __init__(self, project_dir):
        self.dir = project_dir
        d = json.load(open(os.path.join(project_dir, "model.json")))
        self.raw = d
        self.drawing = os.path.join(project_dir, d["drawing"])
        self.set_camera(d["camera"])
        self.C_drawing = self.C.copy()        # the drawing's eye: the room is on this side of every wall
        self.surfaces = []
        for s in d["surfaces"]:
            s = dict(s)
            for s2 in expand_surface(s):
                self.surfaces.append(s2)
        self.boxes = {b["name"]: Box(b) for b in d.get("boxes", [])}
        for b in self.boxes.values():
            self.surfaces += b.faces()
        self.by_name = {s["name"]: s for s in self.surfaces}

    def set_camera(self, c):
        self.f = c["f"]
        if "vp" in c:                                  # one-point perspective, camera looks along +Z
            self.cx, self.cy = c["vp"]; self.C = np.array([0.0, c["eye_height"], 0.0]); self.R = np.eye(3)
        else:
            self.cx, self.cy = c["principal"]; self.C = np.array(c["position"], float)
            self.R = rotation(c.get("yaw", 0), c.get("pitch", 0), c.get("roll", 0))
        self.h = float(self.C[1])
        self.x0, self.y0 = self.cx, self.cy           # kept for older code

    # ---- geometry -------------------------------------------------------
    def surface(self, name):
        if name not in self.by_name:
            raise KeyError(f"No surface named '{name}'. Known: {sorted(self.by_name)}")
        return self.by_name[name]

    def cam(self, P):
        """World points -> camera coordinates (right, up, forward)."""
        return (np.atleast_2d(np.asarray(P, float)) - self.C) @ self.R.T

    def depth(self, P):
        """Distance in front of the camera, along its forward direction."""
        return self.cam(P)[:, 2]

    def project(self, P):
        q = self.cam(P)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.stack([self.cx + self.f*q[:, 0]/q[:, 2], self.cy - self.f*q[:, 1]/q[:, 2]], 1)

    def rays(self, shape):
        """World ray direction for each pixel, scaled so that its forward component is 1
        (so the ray parameter t is the camera depth)."""
        H, W = shape
        ys, xs = np.mgrid[0:H, 0:W].astype(float)
        dc = np.stack([(xs-self.cx)/self.f, -(ys-self.cy)/self.f, np.ones_like(xs)], -1)
        return dc @ self.R

    def raycast(self, shape):
        """Per pixel: index of the nearest surface, 3D hit point, depth along the camera's forward axis."""
        d = self.rays(shape); C = self.C
        best = np.full(shape, np.inf); ids = np.full(shape, -1); P = np.zeros(shape+(3,))
        for i, s in enumerate(self.surfaces):
            t, Q = hit_surface(s, C, d)
            upd = t < best
            best[upd] = t[upd]; ids[upd] = i; P[upd] = Q[upd]
        return ids, P, best

    def to3d(self, surf, u, v):
        """Plane coordinates -> 3D.  Horizontal and sloped planes: (X, Z).  Walls at constant X: (Z, Y).
        Walls at constant Z: (X, Y)."""
        a = surf["axis"]
        if a in (SLOPE, VAULT): return [u, float(height_at(surf, u, v)), v]
        P = [0.0, 0.0, 0.0]; P[a] = surf["at"]
        if a == 1: P[0], P[2] = u, v
        elif a == 0: P[2], P[1] = u, v
        else: P[0], P[1] = u, v
        return P
