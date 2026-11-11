"""Measure positions in feet from pixels, with the camera in model.json (or in a camera.json).

  python3 -m glowpoint.measure SOURCE floor X Y              floor point under pixel (X, Y)
  python3 -m glowpoint.measure SOURCE height X1 Y1 X2 Y2     height of pixel 2 above floor pixel 1
  python3 -m glowpoint.measure SOURCE plane X Y AXIS VALUE   point under the pixel on the plane AXIS = VALUE
  python3 -m glowpoint.measure SOURCE project X Y Z          the pixel where a 3D point (ft) appears

SOURCE is a project folder (uses model.json) or a camera.json file.

  height   measures along the true vertical. In a three-point image vertical edges lean; pixel 2 is
           simply a point on the same vertical edge as floor pixel 1.
  plane    works for any axis: "plane 620 180 Y 24" (a 24 ft ceiling), "plane 120 300 X -25.4" (a point on the
           wall X = -25.4), "plane 500 400 Z 68" (a point on the back wall Z = 68).
  project  checks the model numerically: project a box corner and compare the pixel with the image.

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
    ap.add_argument("source"); ap.add_argument("command", choices=["floor", "height", "plane", "project"])
    ap.add_argument("values", nargs="+")
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
    elif a.command == "project":
        q = (np.array([num(0), num(1), num(2)]) - cam.C) @ cam.R.T
        if q[2] <= 0: print("behind the camera"); return 1
        print(f"pixel {cam.cx + cam.f*q[0]/q[2]:.1f}, {cam.cy - cam.f*q[1]/q[2]:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
