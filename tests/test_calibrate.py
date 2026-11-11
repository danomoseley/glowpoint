"""Calibration test with known answers.

Renders the lobby model as linework from known cameras (one-, two- and three-point), runs the camera
setup on each image, and compares the result with the true camera.

  python3 tests/test_calibrate.py            (needs projects/lobby/model.json; the drawing is not needed)
"""
import os, sys, tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from glowpoint.model import Model
from glowpoint import linework, calibrate as CAL
from glowpoint.measure import Cam

PROJECT = os.path.join(os.path.dirname(__file__), "..", "projects", "lobby")
CAMERAS = {
    "two-point, turned 30 deg":         dict(f=700, principal=[525, 350], position=[-12, 5.5, 18], yaw=30, pitch=0, roll=0),
    "two-point, turned -40 deg":        dict(f=600, principal=[525, 350], position=[30, 5.5, 22], yaw=-40, pitch=0, roll=0),
    "three-point, turned and tilted":   dict(f=650, principal=[525, 350], position=[-8, 5.5, 15], yaw=25, pitch=12, roll=0),
    "three-point, looking down, roll":  dict(f=750, principal=[525, 350], position=[5, 16, 10], yaw=-20, pitch=-15, roll=2),
}


def yaw_diff(a, b):
    """The world frame can come out turned by a multiple of 90 deg; compare modulo 90."""
    d = (a - b) % 90
    return min(d, 90 - d)


def run(verbose=True):
    ok = True
    out_dir = tempfile.mkdtemp(prefix="glowpoint_test_")
    for name, cam in CAMERAS.items():
        m = Model(PROJECT); m.set_camera(cam)
        img = linework.draw(m, (700, 1050))
        cv2.imwrite(os.path.join(out_dir, name.replace(" ", "_").replace(",", "") + ".png"), img)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        S = CAL.segments(gray)
        vps, c, scale = CAL.find_vps(S, gray.shape)
        res, R = CAL.solve_camera(vps, c, scale)
        if R is None:
            print(f"FAIL  {name}: no camera ({res['notes']})"); ok = False; continue
        # scale: a 10 ft vertical at the near-left corner of Column R1
        b = m.boxes["Column R1"]; base = [b.x0, 0, b.z0]; top = [b.x0, 10, b.z0]
        (x1, y1), (x2, y2) = m.project([base, top])
        h = CAL.scale_from_known(res, (x1, y1, x2, y2, 10.0))
        # measure: floor distance from below the camera to the far-right base corner of Column R1
        c2 = Cam.__new__(Cam); c2.C = np.array([0, h, 0.]); c2.R = R; c2.f = res["f"]; c2.cx, c2.cy = res["principal"]
        corner = [b.x1, 0, b.z0]; (cx_, cy_), = m.project([corner])
        got = c2.on_plane(cx_, cy_, "Y", 0.0); true_d = np.hypot(corner[0]-cam["position"][0], corner[2]-cam["position"][2])
        dist_err = abs(np.hypot(got[0], got[2]) - true_d)
        err = dict(f=abs(res["f"]-cam["f"])/cam["f"]*100, yaw=yaw_diff(res["yaw"], cam["yaw"]),
                   pitch=abs(res["pitch"]-cam["pitch"]), roll=abs(res["roll"]-cam["roll"]),
                   eye=abs(h-cam["position"][1])/cam["position"][1]*100, dist=dist_err/true_d*100)
        good = err["f"] < 2 and err["yaw"] < 1 and err["pitch"] < 1 and err["roll"] < 1 and err["eye"] < 3 and err["dist"] < 3
        ok &= good
        if verbose:
            print(f"{'PASS' if good else 'FAIL'}  {name}: {res['kind']}, "
                  f"f {res['f']:.1f} (true {cam['f']}, {err['f']:.2f}%), yaw err {err['yaw']:.2f}, "
                  f"pitch {res['pitch']:.2f} (true {cam['pitch']}), roll {res['roll']:.2f} (true {cam['roll']}), "
                  f"eye {h:.2f} ft (true {cam['position'][1]}, {err['eye']:.2f}%), "
                  f"floor distance {np.hypot(got[0], got[2]):.2f} ft (true {true_d:.2f})")
    # one-point: the original lobby camera. The lens cannot come from lines; the tool must say so.
    m = Model(PROJECT); img = linework.draw(m, (700, 1050))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); S = CAL.segments(gray)
    vps, c, scale = CAL.find_vps(S, gray.shape); res, R = CAL.solve_camera(vps, c, scale)
    good = res["kind"] == "one-point" and R is None
    ok &= good
    print(f"{'PASS' if good else 'FAIL'}  one-point lobby camera: detected '{res['kind']}', asks for the lens: {R is None}")
    print(f"test images in {out_dir}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
