#!/usr/bin/env python3
"""Pixelating a 3D render vs a sprite stack: the same character four ways.

  A  a smooth 3D model (the explorer's shapes evaluated on a 4x finer grid, standing in
     for a Blender mesh), lit
  B  A pixelated: one sample of the finished picture per 8 px block
  C  A pixelated with anti-aliasing: every block is the average of what it covers
  D  the sprite stack: cells cut in object space, lit per cell, edges anti-aliased

B and C have the same lighting as D. What differs is where the grid lives.

python3 compare.py            still  -> out/renders/compare.png (+ panels)
python3 compare.py reel       4 s rotation -> out/web/compare.mp4
"""
import math
import multiprocessing as mp
import os
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets                                                    # noqa: E402
import stack.voxel as voxel                                      # noqa: E402
from stack.font import draw_text                                 # noqa: E402
from stack.render import Camera, Scene, render                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FINE = 4            # the smooth stand-in is built at 4x the voxel resolution
PX = 8              # screen pixels per stack voxel, and the pixelate block size
W, H = 400, 448
FPS = 24


def build_fine(name, **params):
    """Evaluate an asset's shapes on a FINE-times finer grid (same code, same proportions)."""
    orig = voxel.Vox.__init__

    def init(self, X, Y, Z, name='asset', grounded=True):
        orig(self, X * FINE, Y * FINE, Z * FINE, name, grounded)
        self.x, self.y, self.z = self.x / FINE, self.y / FINE, self.z / FINE   # shapes stay in design units
    voxel.Vox.__init__ = init
    try:
        v = assets.build(name, **params)
    finally:
        voxel.Vox.__init__ = orig
    v.pivot = (v.pivot[0] * FINE if v.pivot[0] < v.idx.shape[2] / FINE + 1 else v.pivot[0],
               v.pivot[1] * FINE if v.pivot[1] < v.idx.shape[1] / FINE + 1 else v.pivot[1])
    v.lights = [dict(L, pos=tuple(c * FINE for c in L['pos']), radius=L['radius'] * FINE) for L in v.lights]
    return v


_b = {}


def subjects():
    if not _b:
        _b['stack'] = assets.build('explorer', outfit='prospector').bake()
        _b['fine'] = build_fine('explorer', outfit='prospector').bake()
    return _b['stack'], _b['fine']


def studio(b, unit):
    sc = Scene()
    sc.floor = dict(kind='plane', rgb=(40, 46, 62), gloss=0.0, radius=60 * unit)
    sc.bg = dict(inner=(40, 46, 62), outer=(24, 28, 40), dots=False)
    sc.add(b, (0, 0, 0))
    return sc


def panels(yaw, elev=34.0):
    stack_b, fine_b = subjects()
    look = (0, 0, 15)
    cam_s = Camera(yaw, elev, PX, look, (W, H))
    cam_f = Camera(yaw, elev, PX / FINE, tuple(c * FINE for c in look), (W, H))
    a = render(studio(fine_b, FINE), cam_f, ss=3)
    # B: the filter proper - one sample of the finished smooth picture per block
    b = np.repeat(np.repeat(a[PX // 2::PX, PX // 2::PX], PX, 0), PX, 1)
    # C: the same blocks, each the average of what it covers
    c = a.astype(np.float32).reshape(H // PX, PX, W // PX, PX, 3).mean(axis=(1, 3))
    c = np.repeat(np.repeat((c + 0.5).astype(np.uint8), PX, 0), PX, 1)
    d = render(studio(stack_b, 1), cam_s, ss=3)
    return [a, b, c, d]


TITLES = [('SMOOTH 3D MODEL', 'LIT'), ('PIXELATE FILTER', 'SAME LIGHT, SCREEN GRID'),
          ('PIXELATE + ANTI-ALIASING', 'SAME LIGHT, BLOCKS AVERAGED'), ('SPRITE STACK', 'CELLS ON THE MODEL, LIT, AA')]


def sheet(tiles, captions=True):
    pad = 12
    img = np.full((H + (64 if captions else 0) + pad * 2, W * 4 + pad * 5, 3), (14, 18, 28), np.uint8)
    for i, t in enumerate(tiles):
        x0 = pad + i * (W + pad)
        img[pad:pad + H, x0:x0 + W] = t
        if captions:
            draw_text(img, x0 + W / 2, pad + H + 12, TITLES[i][0], scale=2, shadow=None)
            draw_text(img, x0 + W / 2, pad + H + 36, TITLES[i][1], scale=2, rgb=(150, 160, 184), shadow=None)
    return img


def still(yaw=38.0):
    tiles = panels(yaw)
    out = os.path.join(HERE, 'out', 'renders')
    os.makedirs(os.path.join(out, 'panels'), exist_ok=True)
    for i, t in enumerate(tiles):
        Image.fromarray(t).save(os.path.join(out, 'panels', f'compare_{i + 1}.png'))
    Image.fromarray(sheet(tiles)).save(os.path.join(out, 'compare.png'))
    print('->', os.path.join(out, 'compare.png'))


def _frame(i):
    n = 4 * FPS
    img = sheet(panels(20 + 360.0 * i / n))
    Image.fromarray(img).save(os.path.join(HERE, 'out', 'frames', 'compare', f'{i:04d}.png'), compress_level=1)
    return i


def reel(procs=4):
    os.makedirs(os.path.join(HERE, 'out', 'frames', 'compare'), exist_ok=True)
    subjects()
    with mp.get_context('fork').Pool(procs) as pool:
        for j, _ in enumerate(pool.imap_unordered(_frame, range(4 * FPS), chunksize=2)):
            if j % 24 == 0:
                print(f'  compare: {j}/{4 * FPS}', flush=True)
    out = os.path.join(HERE, 'out', 'web', 'compare.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i',
                    os.path.join(HERE, 'out', 'frames', 'compare', '%04d.png'), '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], check=True)
    print('->', out)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'reel':
        reel(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    else:
        still()
