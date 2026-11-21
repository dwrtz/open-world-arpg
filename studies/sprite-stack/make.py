#!/usr/bin/env python3
"""Sprite-stack study CLI.

  python make.py preview NAME [k=v ...]   four-angle lit preview -> out/preview/NAME.png
  python make.py sheet NAME               slice sheets -> out/slices/
  python make.py list
"""
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets                                     # noqa: E402
from stack.render import Camera, Scene, render    # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def _params(args):
    p = {}
    for a in args:
        k, v = a.split('=', 1)
        try:
            v = float(v) if '.' in v else int(v)
        except ValueError:
            pass
        p[k] = v
    return p


def preview(name, params=None, yaws=(35, 125, 215, 305), elev=36, scale=7, cell=(360, 360), ss=3, side=True):
    """Lit turnaround contact sheet (plus a low side view, the in-game framing)."""
    params = params or {}
    t0 = time.time()
    vox = assets.build(name, **params)
    b = vox.bake()
    X, Y, Z = b.dims
    tiles = []
    views = [(y, elev) for y in yaws] + ([(0, 24)] if side else [])
    for yaw, el in views:
        sc = Scene()
        sc.floor = dict(kind='plane', rgb=(40, 46, 62), gloss=0.0, radius=40)
        sc.bg = dict(inner=(40, 46, 62), outer=(22, 26, 38), dots=False)
        sc.add(b, (0, 0, 0))
        cam = Camera(yaw, el, scale, (0, 0, Z * 0.45), cell)
        tiles.append(render(sc, cam, ss=ss))
    img = np.concatenate(tiles, 1)
    os.makedirs(os.path.join(OUT, 'preview'), exist_ok=True)
    suffix = ''.join(f'_{v}' for v in params.values())
    path = os.path.join(OUT, 'preview', f'{name}{suffix}.png')
    Image.fromarray(img).save(path)
    print(f'{name}: {X}x{Y}x{Z}, {vox.count()} voxels, {len(b.layers)} layers -> {path}  ({time.time() - t0:.1f}s)')
    return path


def sheet(name, params=None):
    vox = assets.build(name, **(params or {}))
    base = os.path.join(OUT, 'slices', vox.name)
    meta = vox.save_sheet(base)
    print(f"{vox.name}: {meta['layers']} layers of {meta['size'][0]}x{meta['size'][1]} -> {base}.png")


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'list':
        print('\n'.join(assets.names()))
    elif cmd == 'preview':
        preview(sys.argv[2], _params(sys.argv[3:]))
    elif cmd == 'sheet':
        sheet(sys.argv[2], _params(sys.argv[3:]))
    else:
        print(__doc__)
