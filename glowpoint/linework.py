"""Draw the model as a clean line drawing, for views that have no architect's drawing
(a new camera position) and for test images."""
import numpy as np
import cv2


def draw(m, shape=(700, 1050), floor_grid=4.0):
    ids, P, dep = m.raycast(shape)
    H, W = shape
    img = np.full((H, W, 3), 255, np.uint8)
    for i, s in enumerate(m.surfaces):
        k = ids == i
        if not k.any(): continue
        tone = {1: 246, 0: 252, 2: 240}[s["axis"]]
        if s["name"] == "Floor": tone = 250
        img[k] = tone
    if floor_grid:
        fl = [i for i, s in enumerate(m.surfaces) if s["name"] == "Floor"]
        if fl:
            for k in (0, 2):
                u = P[..., k]; gy, gx = np.gradient(u); g = np.hypot(gx, gy)
                dd = np.abs(u - np.round(u/floor_grid)*floor_grid)
                img[(ids == fl[0]) & (dd < 0.6*g) & (g < 1.5)] = 200
    e = np.zeros((H, W), bool)
    e[:, 1:] |= ids[:, 1:] != ids[:, :-1]; e[1:, :] |= ids[1:, :] != ids[:-1, :]
    img[e] = 20
    return img
