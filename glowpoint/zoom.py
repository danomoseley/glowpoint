"""Make a zoomed image with pixel coordinates, to read exact positions off a drawing.

  python3 -m glowpoint.zoom drawing.png                          whole image, grid every 50 px
  python3 -m glowpoint.zoom drawing.png X0 Y0 X1 Y1              zoom on that box, fine grid
  python3 -m glowpoint.zoom drawing.png X0 Y0 X1 Y1 --mark 302,444 --mark 203,492
  python3 -m glowpoint.zoom drawing.png X0 Y0 X1 Y1 --model <project>     model edges in red over the image
  options: --out FILE (default: out/zoom.png next to the image), --step PX (grid spacing in source pixels)

The grid labels are pixels of the ORIGINAL image, so you can pass them straight to glowpoint.measure.
Pixel convention: a whole number is the CENTRE of that pixel; each grid line is drawn through pixel centres.
Fractions (302.5) are allowed everywhere.
--model compares the model with the image: each red line is a model edge. Where a red line is off an image
line, that surface or box needs a correction.
Typical use: look at the whole image, find the corner you need, zoom on a box about 100-200 px wide
around it, read the coordinates, and check them with --mark before you measure.
"""
import argparse
import numpy as np
import cv2
from . import pngmark


def nice_step(span_px):
    for s in (2, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        if span_px / s <= 14: return s
    return 1000


def model_edges(img, project):
    """The image with the model's surface edges drawn in red, using the camera in model.json."""
    from .model import Model
    m = Model(project); ids = m.raycast(img.shape[:2])[0]
    e = np.zeros(ids.shape, bool)
    e[:, 1:] |= ids[:, 1:] != ids[:, :-1]; e[1:, :] |= ids[1:, :] != ids[:-1, :]
    out = img.copy(); out[e] = (0, 0, 255)
    return out


def zoom(img, box=None, step=None, marks=(), target_w=1000):
    H, W = img.shape[:2]
    x0, y0, x1, y1 = box if box else (0, 0, W, H)
    x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(W, int(x1)), min(H, int(y1))
    crop = img[y0:y1, x0:x1]
    k = max(1.0, target_w / max(1, (x1-x0)))
    big = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST if k >= 3 else cv2.INTER_CUBIC)
    step = step or nice_step(max(x1-x0, y1-y0))
    pad_l, pad_t = 46, 22
    out = np.full((big.shape[0]+pad_t, big.shape[1]+pad_l, 3), 255, np.uint8)
    out[pad_t:, pad_l:] = big
    for gx in range((x0 // step + 1) * step if x0 % step else x0, x1, step):
        X = int((gx - x0 + 0.5) * k) + pad_l
        cv2.line(out, (X, pad_t), (X, out.shape[0]), (255, 170, 120), 1)
        cv2.putText(out, str(gx), (X-12, 15), 0, 0.4, (200, 60, 0), 1, cv2.LINE_AA)
    for gy in range((y0 // step + 1) * step if y0 % step else y0, y1, step):
        Y = int((gy - y0 + 0.5) * k) + pad_t
        cv2.line(out, (pad_l, Y), (out.shape[1], Y), (255, 170, 120), 1)
        cv2.putText(out, str(gy), (2, Y+4), 0, 0.4, (200, 60, 0), 1, cv2.LINE_AA)
    for (mx, my) in marks:
        X = int((mx - x0 + 0.5) * k) + pad_l; Y = int((my - y0 + 0.5) * k) + pad_t
        cv2.drawMarker(out, (X, Y), (0, 0, 230), cv2.MARKER_CROSS, 18, 2)
        cv2.putText(out, f"{mx:g},{my:g}", (X+8, Y-8), 0, 0.45, (0, 0, 230), 1, cv2.LINE_AA)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image"); ap.add_argument("box", nargs="*", type=float)
    ap.add_argument("--mark", action="append", default=[]); ap.add_argument("--step", type=int)
    ap.add_argument("--out"); ap.add_argument("--model", help="project folder: draw its model edges in red")
    a = ap.parse_args()
    img = cv2.imread(a.image)
    if img is None: raise SystemExit(f"cannot read {a.image}")
    if a.box and len(a.box) != 4: raise SystemExit("give the box as X0 Y0 X1 Y1")
    marks = [tuple(float(v) for v in m.split(",")) for m in a.mark]
    if a.model: img = model_edges(img, a.model)
    import os
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.image)), "out", "zoom.png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pngmark.write(out, zoom(img, a.box or None, a.step, marks))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
