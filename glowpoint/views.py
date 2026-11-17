"""Several views of one model: more photos, drawings, or renders of the same space, each with its own camera.

  python3 -m glowpoint.views corners <project>                         named 3D corners of the model, to mark
  python3 -m glowpoint.views add <project> NAME IMAGE --point PX,PY,X,Y,Z --point ... [--f PX]
                                                                       place the camera of a new image
  python3 -m glowpoint.views list <project>                            the views and their errors

The main drawing and its camera stay as they are. Each extra view is stored in model.json under "views":

  "views": {"desk": {"drawing": "view_desk.jpg", "camera": {...}, "points": [...], "error_px": 1.8}}

To place a view: find 4 or more points of the model in the new image (6 or more, not all on one plane, give
the most reliable result; the lens is found too, unless you give --f). Good points are corners that the model
already has: room corners, column corners, the corners of a desk. "corners" lists them with their 3D
positions; read their pixels in the new image with glowpoint.zoom. Then:

  python3 -W ignore -m glowpoint.render <project> --view NAME --check    check image for that view
  python3 -W ignore -m glowpoint.render <project> --view NAME            the design on that view
  python3 -W ignore -m glowpoint.render <project> --all-views            the design on every view

Everything else (measure, zoom --model) takes --view NAME too. The design is the same in every view:
"visible" in design.json still means visible in the main drawing.
"""
import argparse, json, os, shutil, sys

import cv2
import numpy as np

from glowpoint.model import Model, angles

D = np.diag([1.0, -1.0, 1.0])        # glowpoint (Y up) <-> OpenCV (Y down)


def corners(project):
    """Named 3D points of the model: box corners and surface corners."""
    m = Model(project); out = []
    for b in m.boxes.values():
        for xn, x in (("left", b.x0), ("right", b.x1)):
            for zn, z in (("front", b.z0), ("back", b.z1)):
                for yn, y in (("bottom", b.y0), ("top", b.top)):
                    out.append((f"{b.name}: {zn}-{xn}-{yn}", x, y, z))
    for s in m.surfaces:
        if "box" in s or s.get("frame") is not None: continue
        a = s["axis"]
        if "outline" in s and a in (1, 3, 4):
            pts = [m.to3d(s, u, v) for u, v in s["outline"]]
        elif "outline" in s:
            pts = [m.to3d(s, u, v) for u, v in s["outline"]]
        elif a == 1 or a in (3, 4):
            pts = [m.to3d(s, x, z) for x in s["X"] for z in s["Z"]]
        elif a == 0:
            pts = [m.to3d(s, z, y) for z in s["Z"] for y in s["Y"]]
        else:
            pts = [m.to3d(s, x, y) for x in s["X"] for y in s["Y"]]
        for i, p in enumerate(pts):
            out.append((f"{s['name']}: corner {i + 1}", *[round(float(v), 3) for v in p]))
    return out


def solve(points, size, f=None):
    """Camera from pixel <-> 3D pairs. points: [(px, py, X, Y, Z), ...]; size: (W, H).
    Returns (camera dict in glowpoint's general form, rms error in pixels)."""
    pts = np.asarray(points, float)
    if len(pts) < 4: raise ValueError("a view needs 4 or more points (6 or more to find the lens)")
    img = pts[:, :2].copy(); obj = pts[:, 2:] @ D            # OpenCV wants a right-handed world (Y down)
    W, H = size; c = (W / 2.0, H / 2.0)

    def attempt(fv):
        K = np.array([[fv, 0, c[0]], [0, fv, c[1]], [0, 0, 1]], float)
        best = None
        for flag in (cv2.SOLVEPNP_SQPNP, cv2.SOLVEPNP_EPNP, cv2.SOLVEPNP_ITERATIVE):
            try:
                ok, rv, tv = cv2.solvePnP(obj, img, K, None, flags=flag)
            except cv2.error:
                continue
            if not ok: continue
            try:
                rv, tv = cv2.solvePnPRefineLM(obj, img, K, None, rv, tv)
            except cv2.error:
                pass
            proj, _ = cv2.projectPoints(obj, rv, tv, K, None)
            Rc = cv2.Rodrigues(rv)[0]
            if ((obj @ Rc.T + tv.ravel())[:, 2] <= 0).any(): continue    # points behind the camera
            e = float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - img) ** 2, 1))))
            if best is None or e < best[0]: best = (e, rv, tv)
        return best

    if f is None:
        if len(pts) < 6: raise ValueError("give 6 or more points to find the lens, or give --f")
        fs = np.geomspace(0.3 * max(W, H), 4.0 * max(W, H), 40)
        tries = [(attempt(fv), fv) for fv in fs]
        tries = [(r, fv) for r, fv in tries if r is not None]
        if not tries: raise ValueError("no camera fits these points: check that each pixel matches its 3D point")
        (r, fv) = min(tries, key=lambda t: t[0][0])
        lo, hi = fv / 1.12, fv * 1.12                              # refine the lens (golden section)
        g = (np.sqrt(5) - 1) / 2
        for _ in range(40):
            a, b = hi - g * (hi - lo), lo + g * (hi - lo)
            ra, rb = attempt(a), attempt(b)
            ea = ra[0] if ra else np.inf; eb = rb[0] if rb else np.inf
            if ea < eb: hi = b
            else: lo = a
        f = (lo + hi) / 2
    res = attempt(f)
    if res is None: raise ValueError("no camera fits these points with this lens")
    e, rv, tv = res
    Rc = cv2.Rodrigues(rv)[0]
    Rg = D @ Rc @ D                                              # glowpoint rows: right, up, forward
    Cg = D @ (-Rc.T @ tv.ravel())
    yaw, pitch, roll = angles(Rg)
    cam = {"f": round(float(f), 2), "principal": [round(c[0], 1), round(c[1], 1)],
           "position": [round(float(v), 3) for v in Cg], "yaw": round(yaw, 3), "pitch": round(pitch, 3), "roll": round(roll, 3)}
    return cam, e


def add(project, name, image, points, f=None):
    """Copy the image into the project, place its camera, and store the view in model.json."""
    if name in ("main", "concept"): raise ValueError("choose another view name")
    from glowpoint import pngmark
    if pngmark.is_marked(image):
        raise ValueError(f"{image} is an image that glowpoint made: use the original photo, drawing, or render")
    im = cv2.imread(image)
    if im is None: raise FileNotFoundError(image)
    ext = os.path.splitext(image)[1].lower() or ".png"
    fn = f"view_{name}{ext}"
    dst = os.path.join(project, fn)
    if os.path.abspath(image) != os.path.abspath(dst): shutil.copy(image, dst)
    cam, e = solve(points, (im.shape[1], im.shape[0]), f)
    mp = os.path.join(project, "model.json"); d = json.load(open(mp))
    d.setdefault("views", {})[name] = {"drawing": fn, "camera": cam, "points": [list(map(float, p)) for p in points],
                                       "error_px": round(e, 2)}
    json.dump(d, open(mp, "w"), indent=1)
    # each point: where the new camera puts it
    m = Model(project, view=name); pj = m.project([p[2:] for p in points])
    worst = max(float(np.hypot(*(np.asarray(p[:2]) - q))) for p, q in zip(points, pj))
    print(f"view {name}: camera {cam}")
    print(f"  error {e:.2f} px on average, worst point {worst:.1f} px"
          + ("  (good)" if e < 3 else "  (check the points: a pixel may not match its 3D point)"))
    return cam, e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("corners"); c.add_argument("project")
    a_ = sub.add_parser("add"); a_.add_argument("project"); a_.add_argument("name"); a_.add_argument("image")
    a_.add_argument("--point", action="append", required=True, help="PX,PY,X,Y,Z: a pixel and its 3D point (ft)")
    a_.add_argument("--f", type=float, help="lens in pixels, if known")
    l = sub.add_parser("list"); l.add_argument("project")
    a = ap.parse_args(argv)
    if a.cmd == "corners":
        for n, x, y, z in corners(a.project): print(f"{n:45s} X {x:8.2f}  Y {y:7.2f}  Z {z:8.2f}")
    elif a.cmd == "add":
        pts = [tuple(float(v) for v in p.split(",")) for p in a.point]
        if any(len(p) != 5 for p in pts): ap.error("each --point is PX,PY,X,Y,Z")
        add(a.project, a.name, a.image, pts, a.f)
    else:
        d = json.load(open(os.path.join(a.project, "model.json")))
        print(f"main: {d['drawing']}")
        for n, v in d.get("views", {}).items(): print(f"{n}: {v['drawing']}, {len(v.get('points', []))} points, error {v.get('error_px')} px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
