"""Measure positions in feet from pixels, with the camera in model.json (or in a camera.json).

  python3 -m glowpoint.measure SOURCE floor X Y              floor point under pixel (X, Y)
  python3 -m glowpoint.measure SOURCE height X1 Y1 X2 Y2     height of pixel 2 above floor pixel 1
  python3 -m glowpoint.measure SOURCE plane X Y AXIS VALUE   point under the pixel on the plane AXIS = VALUE
  python3 -m glowpoint.measure SOURCE project X Y Z          the pixel where a 3D point (ft) appears
  python3 -m glowpoint.measure SOURCE box X1 Y1 X2 Y2 [X3 Y3 ...] --top X Y [--name NAME]
                                                             a box from its visible base corners on the floor
                                                             and one top pixel straight above the FIRST corner;
                                                             prints a line for model.json "boxes"

SOURCE is a project folder (uses model.json) or a camera.json file.

  height   measures along the true vertical. In a three-point image vertical edges lean; pixel 2 is
           simply a point on the same vertical edge as floor pixel 1.
  plane    works for any axis: "plane 620 180 Y 24" (a 24 ft ceiling), "plane 120 300 X -25.4" (a point on the
           wall X = -25.4), "plane 500 400 Z 68" (a point on the back wall Z = 68).
  project  checks the model numerically: project a box corner and compare the pixel with the image.
  box      give 2 to 4 base corners that you can see. With 2 corners (one side), add --depth FT, the size
           of the hidden side, and --toward wall|camera for the direction of the hidden side. Snap the box
           to a wall with --snap "Left wall" (moves its nearest side onto that wall; needs a project folder).

Pixels: a whole number is the centre of a pixel; fractions are allowed.
"""
import json, os, sys
import numpy as np
from .model import Model, rotation


class Cam:
    def __init__(self, src):
        if os.path.isdir(src):
            m = Model(src); self.C, self.R, self.f, self.cx, self.cy = m.C, m.R, m.f, m.cx, m.cy
        else:
            c = json.load(open(src))
            if "vp" in c: self.C, self.R, (self.cx, self.cy) = np.array([0, c["eye_height"], 0.]), np.eye(3), c["vp"]
            else: self.C, self.R, (self.cx, self.cy) = np.array(c["position"], float), rotation(c["yaw"], c["pitch"], c["roll"]), c["principal"]
            self.f = c["f"]

    def ray(self, x, y):
        return np.array([(x-self.cx)/self.f, -(y-self.cy)/self.f, 1.0]) @ self.R

    def on_plane(self, x, y, axis, value):
        a = "XYZ".index(axis); d = self.ray(x, y)
        t = (value - self.C[a]) / d[a]
        if t <= 0: raise ValueError("that pixel does not see this plane (it is behind the camera)")
        return self.C + t*d

    def height(self, x1, y1, x2, y2):
        B = self.on_plane(x1, y1, "Y", 0.0); d = self.ray(x2, y2); u = np.array([0, 1.0, 0]); w0 = self.C - B
        a, b, c, dd, e = d@d, d@u, u@u, d@w0, u@w0
        return (a*e - b*dd)/(a*c - b*b)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source"); ap.add_argument("command", choices=["floor", "height", "plane", "project", "box"])
    ap.add_argument("values", nargs="+")
    ap.add_argument("--top", nargs=2, type=float, metavar=("X", "Y"), help="box: a top pixel above the first corner")
    ap.add_argument("--name", default="Object"); ap.add_argument("--kind", default="object")
    ap.add_argument("--depth", type=float, help="box with 2 corners: size of the hidden side, ft")
    ap.add_argument("--toward", choices=["wall", "camera"], default="wall")
    ap.add_argument("--snap", help="box: move the nearest side onto this wall (project folder only)")
    a = ap.parse_args(argv)
    cam = Cam(a.source); v = a.values
    num = lambda i: float(v[i])
    if a.command == "floor":
        P = cam.on_plane(num(0), num(1), "Y", 0.0); print(f"X {P[0]:.2f}  Z {P[2]:.2f}  ft (floor)")
    elif a.command == "height":
        print(f"height {cam.height(num(0), num(1), num(2), num(3)):.2f} ft")
    elif a.command == "plane":
        if len(v) != 4 or v[2].upper() not in "XYZ": ap.error("plane needs: X Y AXIS VALUE, for example 620 180 Y 24")
        P = cam.on_plane(num(0), num(1), v[2].upper(), num(3)); print(f"X {P[0]:.2f}  Y {P[1]:.2f}  Z {P[2]:.2f}  ft")
    elif a.command == "box":
        import json
        if len(v) < 4 or len(v) % 2: ap.error("box needs 2 to 4 corners: X1 Y1 X2 Y2 [X3 Y3 [X4 Y4]]")
        if not a.top: ap.error("box needs --top X Y (a top pixel straight above the first corner)")
        pts = [cam.on_plane(float(v[i]), float(v[i+1]), "Y", 0.0) for i in range(0, len(v), 2)]
        h = cam.height(float(v[0]), float(v[1]), a.top[0], a.top[1])
        xs = [p[0] for p in pts]; zs = [p[2] for p in pts]
        if len(pts) == 2:
            if not a.depth: ap.error("with 2 corners, give --depth FT for the hidden side")
            d = np.array([pts[1][0]-pts[0][0], pts[1][2]-pts[0][2]]); n = np.array([-d[1], d[0]]); n /= np.linalg.norm(n)
            mid = (np.array([pts[0][0], pts[0][2]]) + np.array([pts[1][0], pts[1][2]]))/2
            to_cam = np.array([cam.C[0], cam.C[2]]) - mid
            if (np.dot(n, to_cam) > 0) == (a.toward == "wall"): n = -n
            for p in pts: xs.append(p[0] + n[0]*a.depth); zs.append(p[2] + n[1]*a.depth)
        X = [min(xs), max(xs)]; Z = [min(zs), max(zs)]
        if a.snap:
            from .model import Model
            s = Model(a.source).surface(a.snap); k = {"X": 0, "Z": 1}["XYZ"[s["axis"]]]
            rng = [X, Z][k]; w = s["at"]
            if abs(rng[0]-w) < abs(rng[1]-w): rng[0] = w
            else: rng[1] = w
        box = {"name": a.name, "kind": a.kind, "X": [round(X[0], 2), round(X[1], 2)], "Y": [0, round(h, 2)],
               "Z": [round(Z[0], 2), round(Z[1], 2)]}
        print(json.dumps(box))
        print(f"size {X[1]-X[0]:.2f} x {h:.2f} x {Z[1]-Z[0]:.2f} ft (X x height x Z)", file=sys.stderr)
    elif a.command == "project":
        q = (np.array([num(0), num(1), num(2)]) - cam.C) @ cam.R.T
        if q[2] <= 0: print("behind the camera"); return 1
        print(f"pixel {cam.cx + cam.f*q[0]/q[2]:.1f}, {cam.cy - cam.f*q[1]/q[2]:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
