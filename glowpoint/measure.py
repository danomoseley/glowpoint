"""Measure positions in feet from pixels, with the camera in model.json (or a camera.json).

  python3 -m glowpoint.measure <project or camera.json> floor X Y            floor point under pixel (X, Y)
  python3 -m glowpoint.measure <project or camera.json> height X1 Y1 X2 Y2   height of pixel 2 above floor pixel 1
  python3 -m glowpoint.measure <project or camera.json> plane X Y AXIS VALUE point under pixel on the plane AXIS=VALUE
                                                                            (for example: plane 620 180 Y 24 for a 24 ft ceiling)
Use these to find wall bases, column corners and ceiling heights when you write model.json.
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


def main(argv):
    if len(argv) < 4: print(__doc__); return 1
    cam = Cam(argv[1]); cmd = argv[2]; v = [float(x) for x in argv[3:] if x.replace('.', '', 1).replace('-', '', 1).isdigit()]
    if cmd == "floor":
        P = cam.on_plane(v[0], v[1], "Y", 0.0); print(f"X {P[0]:.2f}  Z {P[2]:.2f}  ft (floor)")
    elif cmd == "height":
        print(f"height {cam.height(*v[:4]):.2f} ft")
    elif cmd == "plane":
        P = cam.on_plane(v[0], v[1], argv[5], v[2]); print(f"X {P[0]:.2f}  Y {P[1]:.2f}  Z {P[2]:.2f}  ft")
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
