"""Ceiling elements (coffers, coves, slats, light wells) on a sloped ceiling.

They are built and drawn in the frame of the slope, where the slope is level and distances run along it
(a 2 ft coffer is 2 ft along the slope), with the same code as on a level ceiling. The new surfaces keep that
frame, so ray casting sees them tilted with the slope. Positions in design.json stay in plan (X, Z).
"""
import copy

import numpy as np

from glowpoint.model import Model, slope_frame, SLOPE, AX


def _cos(s):
    return 1.0 / np.sqrt(1.0 + s["grad"] ** 2)


def to_local_u(s, u):
    return s["u0"] + (u - s["u0"]) / _cos(s)


def to_plan_u(s, u):
    return s["u0"] + (u - s["u0"]) * _cos(s)


def local_feature(f, s):
    """The feature with its plan positions along the slope turned into distances along the slope."""
    fl = dict(f); key = "XYZ"[s["k"]]
    if key in fl: fl[key] = [to_local_u(s, v) for v in fl[key]]
    lk = key.lower()
    if lk in fl:
        fl[lk] = [to_local_u(s, v) for v in fl[lk]] if isinstance(fl[lk], (list, tuple)) else to_local_u(s, fl[lk])
    fl["plane"] = f.get("plane", "Ceiling")
    return fl


class FrameModel:
    """The model, seen in the frame of one slope. Surfaces of that slope (and the slope itself) are level there."""
    def __init__(self, m, slope):
        self.m, self.slope, self.fr = m, slope, slope_frame(slope)
        self.real_of = {}; self.surfaces = []
        for s_ in m.surfaces:
            ps = self._local(s_); self.surfaces.append(ps); self.real_of[id(ps)] = s_
        self.by_name = {ps["name"]: ps for ps in self.surfaces}
        self.C = self.fr.to_local(m.C); self.C_drawing = self.fr.to_local(m.C_drawing)
        self.f, self.R, self.cx, self.cy = m.f, m.R @ self.fr.R.T, m.cx, m.cy

    def _local(self, s_):
        if s_.get("frame") is not None and s_.get("frame_of") == self.slope["name"]:
            return {k: v for k, v in s_.items() if k not in ("frame", "frame_of")}
        if s_ is self.slope:
            key = "XYZ"[s_["k"]]; other = s_["other"]
            loc = dict(name=s_["name"], axis=1, at=s_["y0"], **{key: sorted(to_local_u(s_, v) for v in s_[key]), other: s_[other]})
            loc["holes"] = [{k: ([to_local_u(s_, v) for v in r] if k == key else r) for k, r in h.items()} for h in s_.get("holes", [])]
            if "outline" in s_:
                ku = AX[key]; loc["outline"] = [[to_local_u(s_, p[0]) if ku == 0 else p[0], to_local_u(s_, p[1]) if ku == 2 else p[1]]
                                                for p in s_["outline"]]
            loc["_n_holes"] = len(loc["holes"])
            return loc
        return s_

    def surface(self, name):
        return self.by_name[name] if name in self.by_name else self.m.surface(name)

    def rays(self, shape): return self.fr.vec_local(self.m.rays(shape))
    def depth(self, P): return self.m.depth(self.fr.to_world(np.atleast_2d(P)))
    def project(self, P): return self.m.project(self.fr.to_world(np.atleast_2d(P)))
    def cam(self, P): return self.m.cam(self.fr.to_world(np.atleast_2d(P)))
    def to3d(self, s, u, v): return Model.to3d(self, s, u, v)

    def raycast(self, shape):
        keep = self.m.surfaces
        self.m.surfaces = [self.real_of.get(id(ps), ps) for ps in self.surfaces]
        try:
            ids, P, dep = self.m.raycast(shape)
        finally:
            self.m.surfaces = keep
        return ids, self.fr.to_local(P), dep


def prepare(prep, m, f, slope):
    """Run a prepare function in the frame of the slope, and give the real model what it added."""
    pm = FrameModel(m, slope); fl = local_feature(f, slope)
    before = {id(s) for s in pm.surfaces}
    prep(pm, fl)
    for ps in pm.surfaces:
        if id(ps) in before: continue
        ps = dict(ps, frame=pm.fr, frame_of=slope["name"])
        m.surfaces.append(ps); m.by_name[ps["name"]] = ps
    loc = pm.by_name[slope["name"]]; key = "XYZ"[slope["k"]]
    for h in loc.get("holes", [])[loc["_n_holes"]:]:              # new holes, back to plan positions
        slope.setdefault("holes", []).append({k: ([to_plan_u(slope, v) for v in r] if k == key else r) for k, r in h.items()})


def draw(drw, cv, f, base, slope):
    """Run a draw function in the frame of the slope; write the 3D points and the report back in world terms."""
    pm = FrameModel(cv.m, slope); fl = local_feature(f, slope)
    pcv = copy.copy(cv); pcv.m = pm; pcv.P = pm.fr.to_local(cv.P); pcv.report = []
    pcv.P_world = cv.P; pcv.frame = pm.fr
    out = drw(pcv, fl, base)
    cv.P[...] = pm.fr.to_world(pcv.P)
    for r in pcv.report:
        if all(k in r for k in ("x", "y", "z")):
            w = pm.fr.to_world([float(r["x"]), float(r["y"]), float(r["z"])])
            r = dict(r, x=round(float(w[0]), 2), y=round(float(w[1]), 2), z=round(float(w[2]), 2))
        cv.report.append(r)
    return out
