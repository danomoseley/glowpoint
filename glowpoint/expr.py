"""Relationships for design.json.

Any position in design.json can be a number or a text expression. Expressions refer to the model by name,
so lights follow when the model changes. Available in expressions:

  box('Desk').x0 .x1 .xc .z0 .z1 .zc .y0 .top     a column or object
  surf('Left soffit').at  .X .Y .Z                  a surface: its position and its ranges
  gap('Column L1', 'Column R1')                     (lo, hi) between the inner faces of two boxes, on X
  gap('Column L1', 'Column L2', 'Z')                the same, on Z
  centre_line('Column L1', 'Column R1', 'Z')        average of the two box centres on an axis
  inset((lo, hi), d)                                (lo+d, hi-d)
  mid((lo, hi))                                     the centre of a range
  spaced(lo, hi, n)                                 n positions, equal spaces, half a space at each end
  spaced_ends(lo, hi, n)                            n positions, the first and last at lo and hi
  every(start, stop, step)                          start, start+step, ... up to stop
  inch(n)                                           inches to feet
  visible_faces('column')                           (for uplights) every box face of that kind that is visible
"""
import numpy as np


class Surf:
    def __init__(self, s):
        self.at = s["at"]; self.X = s.get("X"); self.Y = s.get("Y"); self.Z = s.get("Z"); self.name = s["name"]


def namespace(model, visible=None):
    def box(n):
        if n not in model.boxes: raise KeyError(f"No box named '{n}'. Known: {sorted(model.boxes)}")
        return model.boxes[n]

    def gap(a, b, axis="X"):
        A, B = box(a), box(b)
        lo = {"X": (A.x0, A.x1), "Z": (A.z0, A.z1)}[axis]; hi = {"X": (B.x0, B.x1), "Z": (B.z0, B.z1)}[axis]
        if lo[0] > hi[0]: lo, hi = hi, lo
        return (lo[1], hi[0])

    def centre_line(a, b, axis="Z"):
        A, B = box(a), box(b)
        return {"X": (A.xc + B.xc)/2, "Z": (A.zc + B.zc)/2}[axis]

    def spaced(lo, hi, n):
        L = hi - lo; return [lo + L*(i+0.5)/n for i in range(n)]

    def spaced_ends(lo, hi, n):
        return list(np.linspace(lo, hi, n)) if n > 1 else [(lo+hi)/2]

    def every(start, stop, step):
        out, v = [], start
        while v <= stop + 1e-9: out.append(v); v += step
        return out

    def visible_faces(kind="column", min_px=150):
        if visible is None: raise RuntimeError("visible_faces() is only available for lights")
        out = []
        for s, px in visible:
            b = s.get("box")
            if b and model.boxes[b].kind == kind and px >= min_px and s["side"] != "top":
                out.append(s["name"])
        return out

    return dict(box=box, surf=lambda n: Surf(model.surface(n)), gap=gap, centre_line=centre_line,
                inset=lambda r, d: (r[0]+d, r[1]-d), mid=lambda r: (r[0]+r[1])/2,
                spaced=spaced, spaced_ends=spaced_ends, every=every, inch=lambda n: n/12,
                visible_faces=visible_faces, min=min, max=max, abs=abs, round=round)


def ev(value, ns):
    """Numbers and lists pass through; text is evaluated against the model."""
    if isinstance(value, str):
        return eval(value, {"__builtins__": {}}, ns)
    if isinstance(value, list):
        return [ev(v, ns) for v in value]
    return value


def as_list(v):
    if isinstance(v, (list, tuple)) and not (len(v) == 2 and isinstance(v, tuple)):
        return list(v)
    return [v]
