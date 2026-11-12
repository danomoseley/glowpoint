"""Build docs/menu.png: one labelled tile for each light and ceiling type, on the lobby test model.

  python3 docs/make_menu.py

The designs are in docs/menu_tiles.json. Add a tile there when you add a type. AGENTS.md tells agents to
show this image with the welcome and the menu.
"""
import json, os, shutil, subprocess, sys, tempfile
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def render(proj, name, layers):
    d = os.path.join(proj, f"d_{name}.json")
    json.dump({"title": "", "legend_at": "below", "layers": layers}, open(d, "w"))
    subprocess.run([sys.executable, "-W", "ignore", "-m", "glowpoint.render", proj, "--linework", "--design", d,
                    "--out", f"{name}.png"], cwd=ROOT, check=True, capture_output=True)
    return cv2.imread(os.path.join(proj, "out", f"{name}.png"))


def main():
    spec = json.load(open(os.path.join(HERE, "menu_tiles.json")))["tiles"]
    with tempfile.TemporaryDirectory() as proj:
        shutil.copy(os.path.join(ROOT, "tests/fixtures/lobby/model.json"), proj)
        shutil.copy(os.path.join(ROOT, "examples/fixtures.json"), proj)
        base = render(proj, "base", [])
        Hi = 700                      # linework without a drawing is 1050 x 700; the legend is drawn below it
        base = base[:Hi].astype(int); Wi = base.shape[1]
        W, Hh, cap_h, cols, title_h = 600, 400, 48, 3, 90
        rows = (len(spec) + cols - 1) // cols
        sheet = np.full((title_h + rows * (Hh + cap_h) + 10, cols * W + (cols + 1) * 10, 3), 255, np.uint8)
        cv2.putText(sheet, "glowpoint: lights and ceilings", (14, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (40, 40, 40), 2, cv2.LINE_AA)
        cv2.putText(sheet, "Each type takes colour temperature, counts and spacing tied to the architecture, and other views. "
                    "Each tile is cropped to the light.", (16, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1, cv2.LINE_AA)
        for i, t in enumerate(spec):
            im = render(proj, t["type"], t["layers"])[:Hi]
            ys, xs = np.nonzero(np.abs(im.astype(int) - base).sum(2) > 30)
            x0, x1, y0, y1 = np.percentile(xs, 1), np.percentile(xs, 99), np.percentile(ys, 1), np.percentile(ys, 99)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            w = min(max((x1 - x0) * 1.35, (y1 - y0) * 1.35 * 1.5, Wi * 0.5), Wi); h = w / 1.5
            X0 = int(np.clip(cx - w / 2, 0, Wi - w)); Y0 = int(np.clip(cy - h / 2, 0, Hi - h))
            crop = cv2.resize(im[Y0:Y0 + int(h), X0:X0 + int(w)], (W, Hh), interpolation=cv2.INTER_AREA)
            r, k = divmod(i, cols); x = 10 + k * (W + 10); y = title_h + r * (Hh + cap_h)
            sheet[y:y + Hh, x:x + W] = crop
            cv2.rectangle(sheet, (x, y), (x + W - 1, y + Hh - 1), (200, 200, 200), 1)
            cv2.putText(sheet, t["caption"], (x + 4, y + Hh + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (30, 30, 30), 2, cv2.LINE_AA)
    from glowpoint import pngmark
    pngmark.write(os.path.join(HERE, "menu.png"), sheet)
    print(f"wrote docs/menu.png ({len(spec)} tiles)")


if __name__ == "__main__":
    sys.path.insert(0, ROOT); main()
