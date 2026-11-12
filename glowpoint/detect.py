"""Detect architecture in the original drawing.

  python3 -m glowpoint.detect coffers <project> [--plane Ceiling] [--area X0 X1 Z0 Z1] [--depth FT] [--add]

coffers: finds a grid of square or round coffers drawn on a horizontal surface (usually the ceiling) and
prints a "waffle" feature for design.json with the module, the rib width (square) or diameter (round), and
the area. It writes out/detect_coffers.png: the detected coffer edges in red over the drawing. Check it.

  --plane   the surface the coffers are on (default Ceiling; it must be horizontal)
  --area    limit the search to this rectangle on the surface (ft). Default: the whole visible surface
  --depth   coffer depth, ft. A line drawing seldom shows it clearly, so the default is 6 in: set the real one
  --add     add the feature to design.json as a new first layer "Coffers (detected)" (run again: it replaces that layer)

The feature has "replace": true, so the render erases the drawn coffers in that area and draws its own
(with the depth, shape and fixtures that you set). It has "lit": false.

How it works: with the camera, the surface is resampled into a plan view (seen from straight below), where a
coffer grid is evenly spaced. The spacing comes from the autocorrelation of the line profiles, the rib width
from the pairs of lines in one module, round coffers from circles (Hough transform) in the plan view.
Works best on renders from 3D software and clean drawings; check the overlay on hand sketches.
"""
import argparse, json, os, sys
import numpy as np
import cv2
from .model import Model
from . import pngmark

RES = 0.04          # plan view resolution, ft per pixel (about half an inch)


def plan_view(m, img, surf_name, area=None, res=RES, min_px_per_ft=6.0):
    """Resample a horizontal surface of the drawing into a plan view. Returns darkness (0..1, NaN where the
    surface is not visible or too small in the drawing) and the plan axes (xs, zs)."""
    s = m.surface(surf_name)
    if s["axis"] != 1: raise ValueError(f"{surf_name} is not horizontal")
    (x0, x1), (z0, z1) = (area[:2], area[2:]) if area else (s["X"], s["Z"])
    xs = np.arange(x0, x1, res); zs = np.arange(z0, z1, res)
    X, Z = np.meshgrid(xs, zs)
    P = np.stack([X.ravel(), np.full(X.size, s["at"]), Z.ravel()], 1)
    pix = m.project(P); dep = m.depth(P)
    H, W = img.shape[:2]
    ids = m.raycast((H, W))[0]
    si = [i for i, q in enumerate(m.surfaces) if q["name"] == surf_name][0]
    px = pix[:, 0].reshape(X.shape).astype(np.float32); py = pix[:, 1].reshape(X.shape).astype(np.float32)
    ok = (dep.reshape(X.shape) > 0) & (px >= 0) & (px < W-1) & (py >= 0) & (py < H-1)
    ok &= (m.f/np.maximum(dep.reshape(X.shape), 1e-6)) >= min_px_per_ft          # enough detail
    xi = np.clip(np.round(px).astype(int), 0, W-1); yi = np.clip(np.round(py).astype(int), 0, H-1)
    ok &= ids[yi, xi] == si                                                       # the surface is visible there
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)/255.0
    D = 1.0 - cv2.remap(gray, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1.0)
    D[~ok] = np.nan
    plan_view.detail = (m.f/np.maximum(dep.reshape(X.shape), 1e-6))     # drawing pixels per foot, for each plan pixel
    return D, xs, zs


def _period(profile, res, lo=0.5, hi=8.0):
    """Main period (ft) of a 1D profile from its autocorrelation: the shortest strong peak."""
    p = np.nan_to_num(profile - np.nanmean(profile))
    n = len(p)
    if n < 10: return None, 0.0
    ac = np.correlate(p, p, "full")[n-1:]; ac /= ac[0] + 1e-12
    L0, L1 = int(lo/res), min(int(hi/res), n//2)
    if L1 <= L0 + 2: return None, 0.0
    seg = ac[L0:L1]
    peaks = [i for i in range(1, len(seg)-1) if seg[i] >= seg[i-1] and seg[i] >= seg[i+1] and seg[i] > 0.1]
    if not peaks: return None, 0.0
    best = max(seg[i] for i in peaks)
    first = min(i for i in peaks if seg[i] >= 0.8*best)
    # sub-pixel peak position
    i = first; a, b, c = seg[i-1], seg[i], seg[i+1]
    off = 0.5*(a - c)/(a - 2*b + c) if (a - 2*b + c) != 0 else 0.0
    return (L0 + i + off)*res, float(best)


def _folded_peaks(profile, period, res, max_peaks=2):
    """Fold a profile over one period. Returns the folded profile and up to two line positions (ft, 0..period)."""
    n = max(int(round(period/res)), 4)
    pos = (np.arange(len(profile))*res) % period
    bins = np.minimum((pos/period*n).astype(int), n-1)
    fold = np.array([np.nanmean(profile[bins == b]) if np.any((bins == b) & ~np.isnan(profile)) else 0 for b in range(n)])
    fold = np.nan_to_num(fold) - np.nanmin(fold)
    fs = np.convolve(np.r_[fold[-2:], fold, fold[:2]], np.ones(3)/3, "same")[2:-2]
    _folded_peaks.max_peaks = max_peaks
    loc = [i for i in range(n) if fs[i] >= fs[(i-1) % n] and fs[i] > fs[(i+1) % n]]
    loc.sort(key=lambda i: -fs[i])
    min_sep = max(int(round(0.1/period*n)), 2)                   # lines at least 1.2 in apart
    peaks = []
    for j in loc:
        if all(min((j-q) % n, (q-j) % n) >= min_sep for q in peaks) and (not peaks or fs[j] > 0.35*fs[peaks[0]]):
            peaks.append(j)
        if len(peaks) == _folded_peaks.max_peaks: break
    def centroid(i):                                             # sub-bin position of a peak
        idx = np.array([(i+k) % n for k in (-1, 0, 1)]); w = fs[idx] - min(fs[idx]) + 1e-9
        return (i + np.dot(w, [-1, 0, 1])/w.sum() + 0.5)*period/n % period
    return fs, [centroid(q) for q in peaks]


def _cell_template(sub, x_off, z_off, module, phx, phz):
    """Average the plan view over all grid cells, centred on (phx, phz) + k*module. Returns an n x n image."""
    n = max(int(round(module/RES)), 8)
    H, W = sub.shape
    gx = (x_off + np.arange(W)*RES - phx + module/2) % module
    gz = (z_off + np.arange(H)*RES - phz + module/2) % module
    bx = np.minimum((gx/module*n).astype(int), n-1); bz = np.minimum((gz/module*n).astype(int), n-1)
    BX, BZ = np.meshgrid(bx, bz); v = ~np.isnan(sub)
    acc = np.zeros((n, n)); cnt = np.zeros((n, n))
    np.add.at(acc, (BZ[v], BX[v]), sub[v]); np.add.at(cnt, (BZ[v], BX[v]), 1)
    return acc/np.maximum(cnt, 1)


def _roundness(T):
    """How much the cell looks the same when turned 45 degrees (1 = circle, low = square)."""
    n = T.shape[0]; c = (n-1)/2
    R = cv2.warpAffine(T.astype(np.float32), cv2.getRotationMatrix2D((c, c), 45, 1.0), (n, n), flags=cv2.INTER_LINEAR)
    yy, xx = np.mgrid[:n, :n]; inside = (xx-c)**2 + (yy-c)**2 < (0.45*n)**2
    a, b = T[inside] - T[inside].mean(), R[inside] - R[inside].mean()
    return float((a*b).sum()/(np.sqrt((a*a).sum()*(b*b).sum()) + 1e-9))


def _rib_band(profile, period, res):
    """The rib face is the cleanest band in one module (no lines on it). Returns (width, centre) in ft."""
    fs, _ = _folded_peaks(profile, period, res); n = len(fs)
    lo, hi = fs.min(), fs.max()
    thr = lo + 0.2*(hi - lo)
    i0 = int(np.argmin(fs)); a = i0; b = i0
    while fs[(a-1) % n] <= thr and (i0 - a) < n: a -= 1
    while fs[(b+1) % n] <= thr and (b - i0) < n: b += 1
    width = (b - a + 1)*period/n
    centre = ((a + b)/2 + 0.5)*period/n % period
    return width, centre


def _extent(profile, start, period, centre, res):
    """First and last rib centre (ft) that enclose cells with lines in them."""
    n0 = int(np.floor((0 - centre)/period)) - 1
    cells = []
    k = n0
    while True:
        a = centre + k*period; b = a + period
        if a > len(profile)*res: break
        ia, ib = int(max(a, 0)/res), int(min(b, len(profile)*res)/res)
        if ib - ia > 0.6*period/res:
            cells.append((a, np.nanmean(profile[ia:ib])))
        k += 1
    if not cells: return None
    ev = np.array([c[1] for c in cells]); keep = ev > 0.45*np.nanmedian(ev[ev > np.nanpercentile(ev, 40)])
    idx = np.nonzero(keep)[0]
    return start + cells[idx[0]][0], start + cells[idx[-1]][0] + period


def detect_coffers(m, img, surf_name="Ceiling", area=None, depth=0.5):
    D, xs, zs = plan_view(m, img, surf_name, area)
    valid = ~np.isnan(D)
    if valid.sum() < 1000: raise ValueError("too little of the surface is visible in enough detail")
    # 1. where are the lines dense? (the coffer field)
    lines = np.nan_to_num(D) > 0.25
    k = max(int(1.5/RES) | 1, 3)
    dens = cv2.blur(lines.astype(np.float32), (k, k))
    vden = cv2.blur(valid.astype(np.float32), (k, k)) + 1e-6
    dens = dens/vden
    thr = max(0.04, 0.5*np.percentile(dens[valid], 95))
    field = (dens > thr) & valid
    n, lab, stats, _ = cv2.connectedComponentsWithStats(field.astype(np.uint8), 8)
    if n < 2: raise ValueError("no coffer field found")
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    zz, xx = np.nonzero(lab == big)
    bx0, bx1, bz0, bz1 = xs[xx.min()], xs[xx.max()], zs[zz.min()], zs[zz.max()]
    sub = D[zz.min():zz.max()+1, xx.min():xx.max()+1]
    det = plan_view.detail[zz.min():zz.max()+1, xx.min():xx.max()+1]
    # 2. spacing along X and Z. For the rib and the grid position, use only the parts shown in most detail:
    # far away the coffers are small and their deep edges shift, which blurs the profiles
    px_ = np.nanmean(sub, axis=0); pz_ = np.nanmean(sub, axis=1)
    fine = sub.copy(); vd = det[~np.isnan(sub)]
    if vd.size: fine[det < np.percentile(vd, 50)] = np.nan
    with np.errstate(all="ignore"):
        fx_ = np.nanmean(fine, axis=0); fz_ = np.nanmean(fine, axis=1)
    mx, sx = _period(px_, RES); mz, sz = _period(pz_, RES)
    if mx is None and mz is None: raise ValueError("no regular grid found")
    mods = [v for v in (mx, mz) if v is not None]
    module = float(np.mean(mods)) if (len(mods) == 2 and abs(mods[0]-mods[1]) < 0.06*max(mods)) else \
        (mx if (sx >= sz and mx is not None) else mz)
    # 3. round or square? circles in the plan view
    plan8 = np.uint8(255 - np.clip(np.nan_to_num(sub, nan=0.0), 0, 1)*255)
    plan8 = cv2.GaussianBlur(plan8, (5, 5), 1.2)
    rmin, rmax = int(0.15*module/RES), int(0.49*module/RES)
    circles = cv2.HoughCircles(plan8, cv2.HOUGH_GRADIENT, dp=1.2, minDist=int(0.7*module/RES), param1=80, param2=22,
                               minRadius=max(rmin, 4), maxRadius=max(rmax, 6))
    cells = (sub.shape[1]*RES/module)*(sub.shape[0]*RES/module)
    vis_cells = cells*np.mean(~np.isnan(sub))
    round_ = False; roundness = 0.0; shape_fill = 1.0
    if circles is not None and len(circles[0]) > 0.4*vis_cells:
        c0 = circles[0]
        hx = np.angle(np.mean(np.exp(2j*np.pi*(xs[xx.min()] + c0[:, 0]*RES)/module)))/(2*np.pi)*module
        hz = np.angle(np.mean(np.exp(2j*np.pi*(zs[zz.min()] + c0[:, 1]*RES)/module)))/(2*np.pi)*module
        roundness = _roundness(_cell_template(sub, xs[xx.min()], zs[zz.min()], module, hx, hz))
        # topology: a square grid is one connected network of lines; round coffers are separate closed outlines
        ln = (np.nan_to_num(sub, nan=0.0) > 0.45).astype(np.uint8)
        gap = max(int(round(0.06/RES)), 1)*2 + 1                  # close gaps of about 1 in in the outlines
        ln = cv2.morphologyEx(ln, cv2.MORPH_CLOSE, np.ones((gap, gap), np.uint8))
        nc, _, st, _ = cv2.connectedComponentsWithStats(ln, connectivity=8)
        sizes = st[1:, cv2.CC_STAT_AREA]
        min_px = int((0.5*module/RES)**2*0.05)
        separate = int(np.sum(sizes > min_px))
        biggest = sizes.max()/max(ln.sum(), 1) if len(sizes) else 1.0
        fill = 1.0
        if separate > 0.35*vis_cells:
            # separate outlines: round or square? A square fills its bounding box (about 0.95), a circle about 0.79
            ncl, lab2, st2, _ = cv2.connectedComponentsWithStats(ln, connectivity=8)
            lo_a, hi_a = (0.45*module/RES)**2, (1.05*module/RES)**2
            fills = []
            for j in range(1, ncl):
                x, y, w, h, area_ = st2[j]
                if not (lo_a <= w*h <= hi_a and 0.6 < w/max(h, 1) < 1.6 and area_ > min_px): continue
                ys_, xs_ = np.nonzero(lab2[y:y+h, x:x+w] == j)
                hull = cv2.convexHull(np.c_[xs_, ys_].astype(np.int32))
                fills.append(cv2.contourArea(hull)/max((w-1)*(h-1), 1))
            if len(fills) > 0.2*vis_cells:
                fill = float(np.median(fills))
        round_ = fill < 0.86; shape_fill = fill
        if os.environ.get("GLOWPOINT_DEBUG"):
            print(f"debug: separate {separate}, cells {vis_cells:.0f}, biggest {biggest:.2f}, fill {fill:.2f}", file=sys.stderr)
    out = {"type": "waffle", "name": "Waffle", "plane": surf_name, "lit": False, "replace": True}
    if round_:
        c = circles[0]
        cxs = xs[xx.min()] + c[:, 0]*RES; czs = zs[zz.min()] + c[:, 1]*RES
        r = float(np.median(c[:, 2]))*RES
        # grid phase from the circle centres
        phx = np.angle(np.mean(np.exp(2j*np.pi*cxs/module)))/(2*np.pi)*module
        phz = np.angle(np.mean(np.exp(2j*np.pi*czs/module)))/(2*np.pi)*module
        first_x = phx + np.ceil((cxs.min() - phx)/module - 0.5)*module
        last_x = phx + np.floor((cxs.max() - phx)/module + 0.5)*module
        first_z = phz + np.ceil((czs.min() - phz)/module - 0.5)*module
        last_z = phz + np.floor((czs.max() - phz)/module + 0.5)*module
        X = [first_x - module/2, last_x + module/2]; Z = [first_z - module/2, last_z + module/2]
        # the diameter: the radius from Hough is close; refine from the darkness ring in the folded cell
        out.update(shape="round", module=round(module, 4), d=round(2*r, 4))
        note = f"round coffers, {len(c)} circles found"
    else:
        _, lx = _folded_peaks(np.where(np.isnan(fx_), np.nanmean(fx_), fx_), module, RES, 4)
        _, lz = _folded_peaks(np.where(np.isnan(fz_), np.nanmean(fz_), fz_), module, RES, 4)
        def pairs(lines_ft):
            """(rib, centre, rank) for each pair of lines; the rib is the smaller gap between them."""
            out = []
            for i in range(len(lines_ft)):
                for j in range(i+1, len(lines_ft)):
                    a, b = sorted((lines_ft[i], lines_ft[j])); g1 = b - a; g2 = module - g1
                    rib_, c = (g1, (a + b)/2) if g1 <= g2 else (g2, ((b + module + a)/2) % module)
                    if 0.03*module < rib_ < 0.6*module: out.append((rib_, c, i + j))
            return out
        px2, pz2 = pairs(lx), pairs(lz)
        if px2 and pz2:
            # the ribs are the same in both directions: take the pair on each axis that agree best,
            # preferring strong lines (low rank)
            best = min(((a, b) for a in px2 for b in pz2),
                       key=lambda ab: abs(ab[0][0] - ab[1][0])/module + 0.04*(ab[0][2] + ab[1][2]))
            (rx, cx_, _), (rz, cz_, _) = best
            rib = (rx + rz)/2
        else:
            pp = px2 or pz2
            rx = rz = rib = pp[0][0] if pp else 0.15*module
            cx_ = (px2[0][1] if px2 else (lx[0] if lx else 0.0)); cz_ = (pz2[0][1] if pz2 else (lz[0] if lz else 0.0))
        ribs = [rib] if (px2 or pz2) else []
        if os.environ.get("GLOWPOINT_DEBUG"):
            print(f"debug: lines x {lx} z {lz} -> rib x {rx} z {rz}; field X {bx0:.2f}..{bx1:.2f} Z {bz0:.2f}..{bz1:.2f}", file=sys.stderr)
        ox = xs[xx.min()]; oz = zs[zz.min()]
        def edge_extent(profile, o, centre):
            """Outermost rib centres that have a rib-edge line next to them."""
            ref = np.nanpercentile(profile, 97)
            def has_line(pos):
                i = int(round((pos - o)/RES)); w = max(int(0.06/RES), 1)
                if i < 0 or i >= len(profile): return False
                return np.nanmax(profile[max(i-w, 0):i+w+1]) > 0.45*ref
            first = o + centre - np.floor(centre/module)*module - module
            ks = []; c = first
            while c < o + len(profile)*RES + module:
                if has_line(c - rib/2) or has_line(c + rib/2): ks.append(c)
                c += module
            if len(ks) < 2: return None
            # keep the longest run of consecutive grid positions
            runs, cur = [], [ks[0]]
            for q in ks[1:]:
                if abs(q - cur[-1] - module) < 0.1*module: cur.append(q)
                else: runs.append(cur); cur = [q]
            runs.append(cur); best = max(runs, key=len)
            return [best[0], best[-1]]
        ex = edge_extent(px_, ox, cx_); ez = edge_extent(pz_, oz, cz_)
        phx = ox + cx_; phz = oz + cz_
        X = ex if ex else [phx + np.ceil((bx0 - phx)/module)*module, phx + np.floor((bx1 - phx)/module)*module]
        Z = ez if ez else [phz + np.ceil((bz0 - phz)/module)*module, phz + np.floor((bz1 - phz)/module)*module]
        out.update(shape="square", module=round(module, 4), rib=round(rib, 4))
        note = "square coffers" + ("" if ribs else ", single-line grid: rib width not visible, 15% of the module assumed")
    # where the coffer field reaches the limit of what is visible (not an empty part of the ceiling), the coffers
    # probably continue out of view: extend to the surface edge, in whole modules
    s = m.surface(surf_name); ext = []
    lim = {"X": s["X"] if not area else list(area[:2]), "Z": s["Z"] if not area else list(area[2:])}
    def open_edge(axis, side):
        k = int(0.6/RES)
        if axis == "X":
            col = xx.min() - k if side == 0 else xx.max() + k
            if col < 0 or col >= D.shape[1]: return True
            band = D[zz.min():zz.max()+1, col]
        else:
            row = zz.min() - k if side == 0 else zz.max() + k
            if row < 0 or row >= D.shape[0]: return True
            band = D[row, xx.min():xx.max()+1]
        return np.mean(np.isnan(band)) > 0.6                     # mostly not visible there
    for axis, R_ in (("X", X), ("Z", Z)):
        for side in (0, 1):
            if open_edge(axis, side):
                edge = lim[axis][side]
                steps = np.floor(abs(edge - R_[side])/module)
                R_[side] = R_[side] - steps*module if side == 0 else R_[side] + steps*module
                if steps > 0: ext.append(f"{axis} {'start' if side == 0 else 'end'}")
    out.update(X=[round(X[0], 3), round(X[1], 3)], Z=[round(Z[0], 3), round(Z[1], 3)], depth=depth)
    nx = int(round((X[1]-X[0])/module)); nz = int(round((Z[1]-Z[0])/module))
    out["note"] = (f"detected: {note}; module {module*12:.1f} in, "
                   + (f"diameter {out['d']*12:.1f} in" if round_ else f"rib {out['rib']*12:.1f} in")
                   + f", {nx} x {nz} coffers; depth {depth*12:.1f} in is assumed, set the real one"
                   + (f"; extended out of view at {', '.join(ext)}" if ext else "")
                   + f"; outline fill {shape_fill:.2f}")
    return out


def overlay(m, img, feat):
    """The drawing with the detected coffer edges in red."""
    out = img.copy()
    s = m.surface(feat["plane"]); y = s["at"]
    (x0, x1), (z0, z1) = feat["X"], feat["Z"]; mod = feat["module"]
    ids = m.raycast(img.shape[:2])[0]; si = [i for i, q in enumerate(m.surfaces) if q is s][0]

    def poly(pts):
        pix = m.project(pts)
        for a, b in zip(pix[:-1], pix[1:]):
            if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))): continue
            cv2.line(out, tuple(np.int32(a)), tuple(np.int32(b)), (0, 0, 255), 1, cv2.LINE_AA)
    nx = int(round((x1-x0)/mod)); nz = int(round((z1-z0)/mod))
    if feat["shape"] == "round":
        r = feat["d"]/2; th = np.linspace(0, 2*np.pi, 40)
        for i in range(nx):
            for j in range(nz):
                cx = x0 + (i+0.5)*mod; cz = z1 - (j+0.5)*mod
                poly([[cx + r*np.cos(t), y, cz + r*np.sin(t)] for t in th])
    else:
        h = feat["rib"]/2
        for i in range(nx+1):
            for e in (-h, h):
                x = x0 + i*mod + e
                if x0 <= x <= x1: poly([[x, y, z] for z in np.linspace(z0, z1, 60)])
        for j in range(nz+1):
            for e in (-h, h):
                z = z1 - j*mod + e
                if z0 <= z <= z1: poly([[x, y, z] for x in np.linspace(x0, x1, 60)])
    keep = (ids == si)
    keep = cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    out[~keep] = img[~keep]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["coffers"]); ap.add_argument("project")
    ap.add_argument("--plane", default="Ceiling"); ap.add_argument("--area", nargs=4, type=float)
    ap.add_argument("--depth", type=float, default=0.5); ap.add_argument("--add", action="store_true")
    a = ap.parse_args(argv)
    m = Model(a.project); img = cv2.imread(m.drawing)
    if img is None: raise SystemExit(f"cannot read {m.drawing}")
    try:
        feat = detect_coffers(m, img, a.plane, a.area, a.depth)
    except ValueError as e:
        print(f"no coffers detected: {e}.\nNext: check that the {a.plane} surface in model.json matches the drawing "
              f"(render --check); try --area on a clear part of the ceiling; or measure the module with zoom and "
              f"measure and write the waffle feature yourself (AGENTS.md, Task: coffered ceilings).", file=sys.stderr)
        return 1
    os.makedirs(os.path.join(a.project, "out"), exist_ok=True)
    ov = os.path.join(a.project, "out", "detect_coffers.png")
    pngmark.write(ov, overlay(m, img, feat))
    print(json.dumps(feat))
    print(feat["note"], file=sys.stderr)
    print(f"check {ov}: the red lines must lie on the drawn coffers", file=sys.stderr)
    if a.add:
        dp = os.path.join(a.project, "design.json")
        d = json.load(open(dp)) if os.path.exists(dp) else {"layers": []}
        layer = {"name": "Coffers (detected)", "description": "coffers from the drawing", "features": [feat]}
        old = [i for i, l in enumerate(d.get("layers", [])) if l.get("name") == "Coffers (detected)"]
        if old: d["layers"][old[0]] = layer
        else: d.setdefault("layers", []).insert(0, layer)
        json.dump(d, open(dp, "w"), indent=1)
        print(f"{'replaced the earlier detected layer in' if old else 'added to'} {dp}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
