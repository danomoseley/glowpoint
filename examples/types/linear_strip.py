"""Example plugin: a linear LED strip along a surface (under a desk top, along a handrail, in a cove).
Copy this file into <project>/types/ or a GLOWPOINT_TYPES folder, then change it.

design.json:
  {"type": "linear_strip", "plane": "Desk right", "from": ["box('Desk').z0", 2.9], "to": ["box('Desk').z1", 2.9]}

  plane       the surface the strip is on
  from, to    the two ends, in that surface's position coordinates
              (horizontal surfaces: [x, z]; walls at constant X: [along (Z), y]; walls at constant Z: [along (X), y])
  glow        width of the glow, ft (default 1.0)
"""
import numpy as np

INFO = {"linear_strip": {"name": "LED strip",
                         "description": "a linear LED strip along a surface, between two points, with a soft glow",
                         "example": "an LED strip under the desk top, from end to end"}}


def linear_strip(cv, f):
    m = cv.m; s = m.surface(f["plane"]); i = cv.sid(f["plane"])
    A = np.array(m.to3d(s, *f["from"])); B = np.array(m.to3d(s, *f["to"]))
    # glow on the surface: distance of each pixel's 3D point from the strip
    P = cv.P; AB = B - A; L2 = AB @ AB
    t = np.clip(((P - A) @ AB) / L2, 0, 1)
    d = np.linalg.norm(P - (A + t[..., None]*AB), axis=-1)
    g = np.exp(-(d / f.get("glow", 1.0))**2)
    cv.glow(cv.ids == i, g)
    cv.seg(A.tolist(), B.tolist(), 2)                       # the strip itself, hidden where something is in front
    cv.add(f, "linear_strip", f["plane"], ((A + B)/2).tolist(), note=f"length {np.sqrt(L2):.2f} ft")


LIGHTS = {"linear_strip": linear_strip}


def helpers(model):
    """Extra expression names. Here: the centre between two boxes on X (floor area between them)."""
    def between(a, b):
        lo, hi = sorted([model.boxes[a], model.boxes[b]], key=lambda bx: bx.x0)
        return (lo.x1 + hi.x0) / 2
    return {"between": between}
