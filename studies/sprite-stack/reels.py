#!/usr/bin/env python3
"""Animated renders.  python3 reels.py showcase|diorama [procs]"""
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes                                                    # noqa: E402
from scenes import baked, have                                   # noqa: E402
from stack.font import draw_text                                 # noqa: E402
from stack.render import Camera, render                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 24
SIZE = (1280, 720)
SS = 2


def seg(t, a, b):
    return min(1.0, max(0.0, (t - a) / (b - a)))


def ease(p):
    return p * p * (3 - 2 * p)


def ease_out(p):
    return 1 - (1 - p) ** 3


def caption(img, text, sub=None):
    draw_text(img, 36, SIZE[1] - 58, text, scale=3, align='left')
    if sub:
        draw_text(img, 36, SIZE[1] - 30, sub, scale=2, align='left', rgb=(150, 162, 190))


# ---- showcase reel ---------------------------------------------------------------------
SHOW_LEN = 17.5
SWAPS = [dict(), dict(jacket='cloth_red', scarf='cloth_cream'), dict(jacket='cloth_green', scarf='cloth_ochre'),
         dict(jacket='cloth_purple', scarf='cloth_teal'), dict(jacket='cloth_ochre', scarf='cloth_blue'), dict()]


def showcase_frame(i):
    t = i / FPS
    sc = scenes.showcase()
    yaw = -25 + 360.0 * t / SHOW_LEN
    cam = Camera(yaw, size=SIZE, **scenes.SHOWCASE_CAM)
    cap = None
    # A. layers drop in, centre piece first
    if t < 3.4:
        order = sorted(range(len(sc.objs)), key=lambda j: float(np.hypot(sc.objs[j].pos[0], sc.objs[j].pos[1])))
        for rank, j in enumerate(order):
            o = sc.objs[j]
            Zd = o.b.dims[2]
            off = np.zeros((Zd, 3), np.float32)
            started = 0
            for n, k in enumerate(o.b.layers):
                start = 0.1 + rank * 0.07 + n * 0.028
                p = seg(t, start, start + 0.5)
                off[k, 2] = (1 - ease_out(p)) * 34
                if t > start:
                    started = k + 1
            o.layer_off = off
            o.kmax = started
        cap = ('STACKING', 'EVERY ASSET IS A PILE OF FLAT SPRITES')
    # B. turntable with name tags
    lab = seg(t, 3.5, 4.0) * (1 - seg(t, 7.0, 7.5))
    if 3.4 <= t < 7.5:
        cap = ('ANY ANGLE', 'SAME SPRITES, ROTATED AND RE-STACKED')
    # C. light sweep, then lamps only
    if 7.5 <= t < 11.7:
        az = 2 * math.pi * ease(seg(t, 7.6, 9.4))
        x0, y0, z0 = sc.key_dir
        sc.key_dir = (x0 * math.cos(az) - y0 * math.sin(az), x0 * math.sin(az) + y0 * math.cos(az), z0)
        d = ease(seg(t, 9.3, 10.1)) * (1 - ease(seg(t, 11.1, 11.7)))
        sc.key_power = 1.25 * (1 - d) + 0.05 * d
        sc.ambient = 0.55 * (1 - d) + 0.13 * d
        sc.emit_gain = 1 + 0.3 * d
        sc.floor['rim_glow'] = 0.22 + 0.25 * d
        for o in sc.objs:
            o.light_gain = 1 + 0.8 * d
        cap = ('LIGHTING', 'BAKED NORMALS: MOVING KEY LIGHT, SHADOWS, LAMPS')
    # D. pull one stack apart, show the slice sprites
    inset = None
    tgt = sc.by_label.get('PROSPECTOR')
    if 11.7 <= t < 15.0 and tgt is not None:
        g = ease(seg(t, 11.8, 12.6)) * (1 - ease(seg(t, 14.3, 14.95)))
        tgt.gap = 1.3 * g
        tgt.thick = 1 - 0.55 * g
        layers = tgt.b.layers
        n = int(seg(t, 12.2, 14.4) * (len(layers) - 1) + 0.5)
        if 12.0 <= t < 14.6:
            inset = (tgt.b, layers[n], n + 1, len(layers))
        cap = ('SLICES', 'PULLED APART: 30 SPRITES OF 28x22 PIXELS')
    # E. palette swap on identical geometry
    if t >= 15.0 and tgt is not None:
        n = min(len(SWAPS) - 1, int((t - 15.0) / 0.42))
        tgt.albedo = baked('explorer', outfit='prospector', **SWAPS[n]).albedo
        cap = ('PALETTE SWAP', 'MATERIAL COLOURS ARE DATA, NOT PAINTED IN')
    img = render(sc, cam, ss=SS)
    if lab > 0:
        scenes.label_pass(img, sc, cam, alpha=lab)
    if inset:
        b, k, n, tot = inset
        X, Y, _ = b.dims
        cell = 7
        tile = np.full((Y, X, 3), (20, 26, 40), np.uint8)
        tile[b.occ[k]] = b.rgb8[k][b.occ[k]]
        tile = np.repeat(np.repeat(tile, cell, 0), cell, 1)
        x0, y0 = 36, 60
        img[y0 - 3:y0 + Y * cell + 3, x0 - 3:x0 + X * cell + 3] = (96, 214, 204)
        img[y0:y0 + Y * cell, x0:x0 + X * cell] = tile
        draw_text(img, x0, y0 - 28, f'PROSPECTOR  LAYER {n}/{tot}', scale=2, align='left', rgb=(150, 232, 222))
    if cap:
        caption(img, *cap)
    return img


# ---- diorama reel ----------------------------------------------------------------------
DIO_LEN = 10.0


def diorama_frame(i):
    t = i / FPS
    sc = scenes.diorama()
    yaw = -17 * math.cos(2 * math.pi * t / DIO_LEN)
    d = ease(seg(t, 3.6, 4.8)) * (1 - ease(seg(t, 8.6, 9.8)))
    scenes.set_dusk(sc, d)
    cam = Camera(yaw, size=SIZE, **scenes.DIORAMA_CAM)
    img = render(sc, cam, ss=SS)
    caption(img, 'SIDE-VIEW WORLD AS ONE STACK' if d < 0.5 else 'LAMPS ONLY',
            'TERRAIN CELLS, PROPS AND CHARACTERS ARE ALL SLICE SPRITES')
    return img


REELS = dict(showcase=(showcase_frame, SHOW_LEN), diorama=(diorama_frame, DIO_LEN))
_fn = None
_dir = None


def _work(i):
    Image.fromarray(_fn(i)).save(os.path.join(_dir, f'{i:04d}.png'), compress_level=1)
    return i


def run(name, procs=4, only=None):
    global _fn, _dir
    _fn, length = REELS[name]
    n = int(round(length * FPS))
    _dir = os.path.join(HERE, 'out', 'frames', name)
    os.makedirs(_dir, exist_ok=True)
    if only is not None:
        for i in only:
            _work(i)
        return
    # bake everything once so forked workers share it
    (scenes.showcase() if name == 'showcase' else scenes.diorama())
    for sw in SWAPS:
        baked('explorer', outfit='prospector', **sw)
    t0 = time.time()
    with mp.get_context('fork').Pool(procs) as pool:
        for j, _ in enumerate(pool.imap_unordered(_work, range(n), chunksize=2)):
            if j % 24 == 0:
                print(f'  {name}: {j}/{n} frames, {time.time() - t0:.0f}s', flush=True)
    out = os.path.join(HERE, 'out', 'web', f'{name}.mp4')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(_dir, '%04d.png'),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', out], check=True)
    print(f'  -> {out}  ({time.time() - t0:.0f}s)')


if __name__ == '__main__':
    name = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == 'frames':
        run(name, only=[int(a) for a in sys.argv[3:]])
    else:
        run(name, procs=int(sys.argv[2]) if len(sys.argv) > 2 else 4)
