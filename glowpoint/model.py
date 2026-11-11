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
        self.surfaces = []
        for s in d["surfaces"]:
            s = dict(s); s["axis"] = AX[s["axis"]]; self.surfaces.append(s)
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
