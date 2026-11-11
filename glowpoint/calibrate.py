"""Find the camera of a perspective image from its vanishing points.

  python3 -m glowpoint.calibrate image.png [--known X1,Y1,X2,Y2,HEIGHT] [--eye-height FT] [--f PX] [--out camera.json]

Works for one-, two- and three-point perspectives. Best on renders from 3D software (exact lines);
also works on clean hand drawings, with less accuracy.

  1. Finds straight lines (OpenCV line segment detector).
  2. Groups them by vanishing point (up to three), with RANSAC.
  3. Calculates the lens f, the principal point, and the camera turn/tilt/roll.
     - three finite vanishing points: principal point = their orthocentre, f from any pair
     - two finite (verticals parallel): principal point = image centre, f from the two
     - one finite (one-point): f cannot be found from lines; give --f, or measure it later
  4. Sets the scale from known verticals: --known x1,y1,x2,y2,H means the floor point (x1,y1) and the
     point (x2,y2) straight above it are H feet apart. Give --known several times to check the scale:
     the tool prints the eye height from each one and how much they disagree, and uses the median.
     Or give --eye-height.

The world frame: origin on the floor below the camera, Y up, Z along the vanishing direction that is
most in front of the camera, X to the right of it. Write model.json surfaces in this frame.

Writes camera.json (paste into model.json "camera"), and calibration.png that shows the line groups.
"""
import argparse, json
import numpy as np
import cv2
from . import pngmark
from .model import rotation, angles


def _lsd(gray):
    try:
        return cv2.createLineSegmentDetector(0)
    except Exception:          # some OpenCV versions do not have the LSD detector
        return None


def segments(gray, min_len=None):
    H, W = gray.shape
    min_len = min_len or 0.03*max(H, W)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    lsd = _lsd(gray)
    if lsd is not None:
        L = lsd.detect(blur)[0]
    else:                      # fallback: edges + probabilistic Hough transform
        edges = cv2.Canny(blur, 50, 150)
        L = cv2.HoughLinesP(edges, 0.5, np.pi/1800, threshold=30, minLineLength=int(min_len), maxLineGap=2)
    if L is None: return np.zeros((0, 4))
    L = L.reshape(-1, 4).astype(float)
    ln = np.hypot(L[:, 2]-L[:, 0], L[:, 3]-L[:, 1])
    return L[ln > min_len]


def _lines(S, scale, c):
    """Homogeneous lines in normalized coordinates (centred, divided by scale)."""
    p = np.c_[(S[:, :2]-c)/scale, np.ones(len(S))]; q = np.c_[(S[:, 2:]-c)/scale, np.ones(len(S))]
    l = np.cross(p, q); return l/np.linalg.norm(l[:, :2], axis=1, keepdims=True)


def _err(S, v, scale, c):
    """Angle (degrees) between each segment and the direction from its middle to the vanishing point v."""
    mid = ((S[:, :2]+S[:, 2:])/2 - c)/scale
    d_seg = S[:, 2:]-S[:, :2]
    if abs(v[2]) > 1e-9: d_vp = v[:2]/v[2] - mid
    else: d_vp = np.tile(v[:2], (len(S), 1))
    a = np.arctan2(d_seg[:, 1], d_seg[:, 0]) - np.arctan2(d_vp[:, 1], d_vp[:, 0])
    a = np.abs((a + np.pi/2) % np.pi - np.pi/2)
    return np.degrees(a)


def find_vps(S, shape, n=3, tol=1.0, iters=3000, seed=0):
    H, W = shape; c = np.array([W/2, H/2]); scale = max(H, W)
    w = np.hypot(S[:, 2]-S[:, 0], S[:, 3]-S[:, 1])
    Ls = _lines(S, scale, c)
    rng = np.random.default_rng(seed)
    left = np.ones(len(S), bool); vps = []
    for _ in range(n):
        idx = np.nonzero(left)[0]
        if len(idx) < 6: break
        best = None
        for _ in range(iters):
            i, j = rng.choice(idx, 2, replace=False)
            v = np.cross(Ls[i], Ls[j]); nv = np.linalg.norm(v)
            if nv < 1e-12: continue
            v = v/nv
            inl = left & (_err(S, v, scale, c) < tol)
            sc = w[inl].sum()
            if best is None or sc > best[0]: best = (sc, v, inl)
        sc, v, inl = best
        for _ in range(3):                                   # refine: least squares on the inliers
            A = Ls[inl]*w[inl, None]
            v = np.linalg.svd(A)[2][-1]
            inl = left & (_err(S, v, scale, c) < tol)
        if inl.sum() < 6: break
        res = _err(S[inl], v, scale, c)
        d = S[inl, 2:]-S[inl, :2]
        vert = float(np.mean(np.abs(np.abs(np.degrees(np.arctan2(d[:, 1], d[:, 0]))) - 90) < 20))
        vps.append(dict(v=v, inliers=inl, n=int(inl.sum()), weight=float(w[inl].sum()),
                        rms_deg=float(np.sqrt(np.mean(res**2))), vertical_share=vert))
        left &= ~inl
    return vps, c, scale


def to_pixels(v, c, scale):
    """Finite vanishing point in pixels, or None if it is (practically) at infinity."""
    if abs(v[2]) < 1e-9: return None
    p = v[:2]/v[2]
    if np.linalg.norm(p) > 30: return None                  # more than 30 image widths away
    return p*scale + c


def orthocentre(a, b, c_):
    A = np.array([c_-b, c_-a]); rhs = np.array([np.dot(c_-b, a), np.dot(c_-a, b)])
    return np.linalg.solve(A, rhs)


def solve_camera(vps, c, scale, f_given=None):
    vert = max(vps, key=lambda d: d["vertical_share"]) if vps else None
    if vert is not None and vert["vertical_share"] < 0.5: vert = None
    horiz = sorted([d for d in vps if d is not vert], key=lambda d: -d["weight"])[:2]
    fin = {id(d): to_pixels(d["v"], c, scale) for d in vps}
    finite_h = [d for d in horiz if fin[id(d)] is not None]
    vfin = fin[id(vert)] if vert is not None else None
    notes = []
    pp = c.copy()
    if len(finite_h) == 2 and vfin is not None:
        pp = orthocentre(fin[id(finite_h[0])], fin[id(finite_h[1])], vfin); kind = "three-point"
        if np.linalg.norm(pp-c) > 0.25*scale:
            notes.append("principal point far from the image centre: the image may be cropped or shifted; using the centre")
            pp = c.copy()
    elif len(finite_h) == 2: kind = "two-point"
    elif len(finite_h) == 1 and vfin is not None: kind = "two-point (tilted)"
    else: kind = "one-point"
    f = f_given
    if f is None:
        pairs = []
        if len(finite_h) == 2: pairs.append((fin[id(finite_h[0])], fin[id(finite_h[1])]))
        for d in finite_h:
            if vfin is not None: pairs.append((fin[id(d)], vfin))
        for a, b in pairs:
            f2 = -np.dot(a-pp, b-pp)
            if f2 > 0: f = float(np.sqrt(f2)); break
    if f is None:
        notes.append("the lens cannot be found from the lines in a one-point view: give --f (or measure a square)")
        return dict(kind=kind, f=None, principal=pp.tolist(), notes=notes), None

    def cam_dir(d):
        p = fin[id(d)]
        if p is not None: v = np.array([p[0]-pp[0], -(p[1]-pp[1]), f])
        else: v = np.array([d["v"][0], -d["v"][1], 0.0])
        return v/np.linalg.norm(v)
    up = cam_dir(vert) if vert is not None else np.array([0, 1.0, 0])
    if up[1] < 0: up = -up
    hd = [cam_dir(d) for d in horiz]
    if not hd: return dict(kind=kind, f=f, principal=pp.tolist(), notes=notes+["no horizontal directions found"]), None
    raw_angles = [float(np.degrees(np.arccos(abs(np.dot(a, b))))) for a, b in
                  ([(hd[0], hd[1])] if len(hd) == 2 else []) + [(h, up) for h in hd]]
    Z = max(hd, key=lambda v: abs(v[2]))                     # the direction most in front of the camera
    if Z[2] < 0: Z = -Z
    Z = Z - np.dot(Z, up)*up; Z /= np.linalg.norm(Z)
    X = np.cross(up, Z)
    M = np.stack([X, up, Z], 1)                              # columns: world axes in camera coordinates
    U, _, Vt = np.linalg.svd(M); R = U @ Vt                  # nearest true rotation
    yaw, pitch, roll = angles(R)
    return dict(kind=kind, f=f, principal=pp.tolist(), yaw=yaw, pitch=pitch, roll=roll,
                axis_angles_deg=raw_angles, notes=notes), R


def scale_from_known(cam, known):
    """known = (x1, y1, x2, y2, H): floor point and the point above it, H ft apart. Returns eye height."""
    x1, y1, x2, y2, Hft = known
    R = rotation(cam["yaw"], cam["pitch"], cam["roll"]); f = cam["f"]; cx, cy = cam["principal"]
    ray = lambda x, y: np.array([(x-cx)/f, -(y-cy)/f, 1.0]) @ R
    C = np.array([0, 1.0, 0])                                # eye height 1 for now
    d1 = ray(x1, y1)
    if d1[1] >= 0: raise ValueError("the first point must be on the floor, below the horizon")
    B = C + d1*(-1.0/d1[1])                                  # floor point
    d2 = ray(x2, y2)
    # point on the vertical line through B nearest to ray 2
    u = np.array([0, 1.0, 0]); w0 = C - B
    a, b, c_ = np.dot(d2, d2), np.dot(d2, u), np.dot(u, u); d_, e = np.dot(d2, w0), np.dot(u, w0)
    s = (a*e - b*d_)/(a*c_ - b*b)
    return Hft/s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image"); ap.add_argument("--known", action="append", default=[],
                    help="x1,y1,x2,y2,H; give it several times to check the scale")
    ap.add_argument("--eye-height", type=float)
    ap.add_argument("--f", type=float, help="lens in pixels, if known (needed for one-point views)")
    ap.add_argument("--tol", type=float, default=1.0, help="line-to-vanishing-point tolerance, degrees (hand drawings: 2)")
    ap.add_argument("--out", default="camera.json"); ap.add_argument("--overlay", default="calibration.png")
    a = ap.parse_args()
    if pngmark.is_marked(a.image):
        raise SystemExit(f"{a.image} is an image that glowpoint made. Use the architect's original drawing.")
    img = cv2.imread(a.image); gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    S = segments(gray)
    vps, c, scale = find_vps(S, gray.shape, tol=a.tol)
    cam, R = solve_camera(vps, c, scale, a.f)
    print(f"{len(S)} line segments, {len(vps)} vanishing points, {cam['kind']} perspective")
    cols = [(0, 0, 255), (0, 160, 0), (255, 0, 0)]
    ov = (img*0.4 + 153).astype(np.uint8)
    for k, d in enumerate(vps):
        p = to_pixels(d["v"], c, scale)
        where = f"at ({p[0]:.0f}, {p[1]:.0f}) px" if p is not None else "at infinity"
        print(f"  VP{k+1}: {d['n']} lines, fit {d['rms_deg']:.2f} deg rms, {where}, {'vertical' if d['vertical_share'] > .5 else 'horizontal'}")
        for s in S[d["inliers"]]:
            cv2.line(ov, tuple(np.int32(s[:2])), tuple(np.int32(s[2:])), cols[k % 3], 2, cv2.LINE_AA)
    pngmark.write(a.overlay, ov)
    if R is None:
        for n in cam["notes"]: print("  note:", n)
        return
    print(f"  lens f = {cam['f']:.1f} px  (horizontal field of view {2*np.degrees(np.arctan(gray.shape[1]/2/cam['f'])):.1f} deg)")
    print(f"  principal point ({cam['principal'][0]:.1f}, {cam['principal'][1]:.1f})")
    print(f"  turn (yaw) {cam['yaw']:.2f} deg, tilt (pitch) {cam['pitch']:.2f} deg, roll {cam['roll']:.2f} deg")
    if cam.get("axis_angles_deg"):
        print("  angles between the found directions (90 = perfect): " + ", ".join(f"{x:.2f}" for x in cam["axis_angles_deg"]))
    for n in cam["notes"]: print("  note:", n)
    h = a.eye_height
    if a.known:
        hs = []
        for k in a.known:
            vals = [float(x) for x in k.split(",")]
            hk = scale_from_known(cam, vals); hs.append(hk)
            print(f"  eye height from the known {vals[4]:g} ft at ({vals[0]:g},{vals[1]:g}): {hk:.2f} ft")
        h = float(np.median(hs))
        if len(hs) > 1:
            spread = (max(hs) - min(hs))/h*100
            print(f"  known dimensions disagree by {spread:.0f}%; using the median, {h:.2f} ft"
                  + ("  <-- check them: more than 10% means a wrong pixel, a wrong dimension, or an inexact drawing" if spread > 10 else ""))
    if h is None:
        h = 5.5; print("  eye height not given: using 5.5 ft. Give --known or --eye-height for the real scale.")
    out = dict(f=round(cam["f"], 2), principal=[round(v, 2) for v in cam["principal"]], position=[0, round(h, 3), 0],
               yaw=round(cam["yaw"], 3), pitch=round(cam["pitch"], 3), roll=round(cam["roll"], 3))
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"wrote {a.out} and {a.overlay}")


if __name__ == "__main__":
    main()
