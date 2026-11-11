"""3D model of the space behind a perspective drawing.

model.json holds:
  camera    vp (vanishing point, px), f (lens, px), eye_height (ft)
  surfaces  flat rectangles: name, axis (the axis they are perpendicular to), at, and ranges on the other two axes
  boxes     columns and objects: name, kind, X/Y/Z ranges. Each box becomes faces named
            "<name> front|back|left|right|top|bottom" (front faces the viewer, -Z).
All lengths in feet. X right, Y up (floor = 0), Z away from the viewer.
"""
import json, os
import numpy as np

AX = {"X": 0, "Y": 1, "Z": 2}


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
        c = d["camera"]
        self.x0, self.y0 = c["vp"]; self.f = c["f"]; self.h = c["eye_height"]
        self.surfaces = []
        for s in d["surfaces"]:
            s = dict(s); s["axis"] = AX[s["axis"]]; self.surfaces.append(s)
        self.boxes = {b["name"]: Box(b) for b in d.get("boxes", [])}
        for b in self.boxes.values():
            self.surfaces += b.faces()
        self.by_name = {s["name"]: s for s in self.surfaces}

    # ---- geometry -------------------------------------------------------
    def surface(self, name):
        if name not in self.by_name:
            raise KeyError(f"No surface named '{name}'. Known: {sorted(self.by_name)}")
        return self.by_name[name]

    def project(self, P):
        P = np.atleast_2d(np.asarray(P, float))
        Z = P[:, 2]
        return np.stack([self.x0 + self.f*P[:, 0]/Z, self.y0 - self.f*(P[:, 1]-self.h)/Z], 1)

    def rays(self, shape):
        H, W = shape
        ys, xs = np.mgrid[0:H, 0:W].astype(float)
        return np.stack([(xs-self.x0)/self.f, -(ys-self.y0)/self.f, np.ones_like(xs)], -1)

    def raycast(self, shape):
        """Per pixel: index of the nearest surface, 3D hit point, depth (Z)."""
        d = self.rays(shape); C = np.array([0, self.h, 0.])
        best = np.full(shape, np.inf); ids = np.full(shape, -1); P = np.zeros(shape+(3,))
        for i, s in enumerate(self.surfaces):
            a = s["axis"]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (s["at"] - C[a]) / d[..., a]
                Q = C + t[..., None]*d
            ok = (t > 0) & np.isfinite(t)
            for k, key in enumerate("XYZ"):
                if k == a: continue
                lo, hi = s[key]; ok &= (Q[..., k] >= lo-1e-6) & (Q[..., k] <= hi+1e-6)
            for hole in s.get("holes", []):
                ins = np.ones_like(ok)
                for key, (lo, hi) in hole.items():
                    kk = AX[key]; ins &= (Q[..., kk] > lo) & (Q[..., kk] < hi)
                ok &= ~ins
            upd = ok & (t < best)
            best[upd] = t[upd]; ids[upd] = i; P[upd] = Q[upd]
        return ids, P, best

    def to3d(self, surf, u, v):
        """Plane coordinates -> 3D.  Horizontal planes: (X, Z).  Walls at constant X: (Z, Y).
        Walls at constant Z: (X, Y)."""
        a = surf["axis"]; P = [0.0, 0.0, 0.0]; P[a] = surf["at"]
        if a == 1: P[0], P[2] = u, v
        elif a == 0: P[2], P[1] = u, v
        else: P[0], P[1] = u, v
        return P
