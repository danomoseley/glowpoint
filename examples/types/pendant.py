"""Example plugin: a pendant light. Copy this file into <project>/types/ or a GLOWPOINT_TYPES folder.

design.json:
  {"type": "pendant", "plane": "Ceiling", "x": 6, "z": "every(60, 100, 10)",
   "drop": 12, "d": 2, "pool_r": 4}

  plane   ceiling it hangs from        x, z   position(s) on that ceiling
  drop    cord length, ft              d      shade diameter, ft
  pool_r  radius of the pool on the floor, ft (0 = no pool)
"""
import itertools
import numpy as np
import cv2
from glowpoint.features import as_list, GLOW


def pendant(cv, f):
    m = cv.m; s = m.surface(f["plane"])
    for x, z in itertools.product(as_list(f["x"]), as_list(f["z"])):
        top = m.to3d(s, x, z)
        y = top[1] - f.get("drop", 10.0); r = f.get("d", 2.0)/2
        c = [x, y, z]
        th = np.linspace(0, 2*np.pi, 48, endpoint=False)
        rim = [[x+r*np.cos(t), y, z+r*np.sin(t)] for t in th]
        if not cv.visible([c], m.project([c]))[0]:
            cv.add(f, "pendant", f["plane"], c, visible=False); continue
        # glow around the shade (in the light layer)
        pc = m.project([c])[0]; halo = max(6, int(m.f*r*2.2/z))
        cv2.circle(cv.over, tuple(np.int32(pc)), halo, (120, 230, 255), -1, cv2.LINE_AA)
        # pool on the floor
        pr = f.get("pool_r", 3.0)
        if pr > 0:
            pool = [[x+pr*np.cos(t), 0.0, z+pr*np.sin(t)] for t in th]
            pp = m.project(pool)
            if cv.visible(pool, pp).mean() > 0.6:
                pim = cv.img.copy(); cv2.fillPoly(pim, [np.int32(pp)], GLOW, cv2.LINE_AA)
                cv.img[:] = cv2.addWeighted(pim, 0.35, cv.img, 0.65, 0)
        # cord and shade (in the linework)
        cv.seg(top, [x, y, z], 1)
        rp = np.int32(m.project(rim))
        cv2.fillPoly(cv.img, [rp], (255, 255, 255), cv2.LINE_AA)
        cv2.polylines(cv.img, [rp], True, (0, 0, 0), 1, cv2.LINE_AA)
        cv.add(f, "pendant", f["plane"], c, visible=True)


LIGHTS = {"pendant": pendant}


def helpers(model):
    """Extra expression names. Here: the centre of the floor area between two boxes, on X."""
    def between(a, b):
        A, B = model.boxes[a], model.boxes[b]
        lo, hi = sorted([A, B], key=lambda bx: bx.x0)
        return (lo.x1 + hi.x0) / 2
    return {"between": between}
