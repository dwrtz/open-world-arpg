#!/usr/bin/env python3
"""Still renders for the sprite-stack study.  python3 stills.py [name ...]  (no args = all)"""
import math
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets                                                    # noqa: E402
import scenes                                                    # noqa: E402
from scenes import baked, have                                   # noqa: E402
from stack.font import draw_text                                 # noqa: E402
from stack.render import Camera, Scene, render                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'renders')
BG = (14, 18, 28)


def save(img, name):
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(img).save(path)
    print(f'  -> {path}  {img.shape[1]}x{img.shape[0]}')
    return path


def canvas(w, h):
    return np.full((h, w, 3), BG, np.uint8)


def studio(objs, key_dir=None):
    """Plain dark floor, the same soft key as the previews."""
    sc = Scene()
    sc.floor = dict(kind='plane', rgb=(40, 46, 62), gloss=0.0, radius=70)
    sc.bg = dict(inner=(40, 46, 62), outer=(24, 28, 40), dots=False)
    if key_dir:
        sc.key_dir = key_dir
    for (b, pos, yaw) in objs:
        sc.add(b, pos, yaw)
    return sc


# ---- 1. the technique, step by step ----------------------------------------------------
def technique():
    """Classic stack vs anti-aliased vs anti-aliased + lit, same stacks, same camera."""
    objs = [(baked('explorer', outfit='prospector'), (-17, 6, 0), 20)]
    if have('furnace'):
        objs.append((baked('furnace'), (16, -4, 0), -20))
    W, H, scale = 620, 560, 8
    cam = Camera(32, 36, scale, (2, 0, 15), (W, H))
    panels = [
        ('CLASSIC SPRITE STACK', 'ONE STEP PER LAYER, HARD TEXELS', dict(pixel=scale, mode='albedo', shadows=False)),
        ('+ ANTI-ALIASING', 'SAME SLICES, SMOOTH COVERAGE', dict(ss=4, mode='albedo', shadows=False)),
        ('+ LIGHTING', 'NORMALS, OCCLUSION, SHADOWS, GLOW', dict(ss=4, mode='lit')),
    ]
    pad = 18
    img = canvas(W * 3 + pad * 4, H + 96)
    for i, (title, sub, kw) in enumerate(panels):
        sc = studio(objs)
        if kw.get('pixel'):
            cam_i = Camera(cam.yaw, cam.elev, scale, cam.look, (W // scale * scale, H // scale * scale))
            r = render(sc, cam_i, **kw)
            tile = canvas(W, H); tile[:r.shape[0], :r.shape[1]] = r
        else:
            tile = render(sc, cam, **kw)
        x0 = pad + i * (W + pad)
        img[pad:pad + H, x0:x0 + W] = tile
        save(tile, f'panels/technique_{i + 1}.png')
        draw_text(img, x0 + W / 2, pad + H + 16, title, scale=3, shadow=None)
        draw_text(img, x0 + W / 2, pad + H + 48, sub, scale=2, rgb=(150, 160, 184), shadow=None)
    return save(img, 'technique.png')


def buffers():
    """What each slice stores and what the light pass adds."""
    name = 'furnace' if have('furnace') else 'explorer'
    b = baked(name)
    W, H, scale = 440, 440, 9
    cam = Camera(40, 36, scale, (0, 0, b.dims[2] * 0.45), (W, H))
    panels = [('ALBEDO SLICES', 'albedo'), ('BAKED NORMALS', 'normal'), ('BAKED OCCLUSION', 'ao'),
              ('LIGHT ONLY', 'light'), ('FINAL', 'lit')]
    pad = 14
    img = canvas(W * len(panels) + pad * (len(panels) + 1), H + 62)
    for i, (title, mode) in enumerate(panels):
        sc = studio([(b, (0, 0, 0), 0)])
        tile = render(sc, cam, ss=4, mode=mode)
        x0 = pad + i * (W + pad)
        img[pad:pad + H, x0:x0 + W] = tile
        save(tile, f'panels/buffer_{mode}.png')
        draw_text(img, x0 + W / 2, pad + H + 14, title, scale=3, shadow=None)
    return save(img, 'buffers.png')


# ---- 2. a stack is just sprites --------------------------------------------------------
def slices():
    """Assembled, pulled apart into its layers, and the sprite sheet those layers come from."""
    vox = assets.build('explorer', outfit='prospector')
    b = vox.bake()
    X, Y, Z = b.dims
    W, H, scale = 470, 640, 9
    pad = 16
    sc = studio([(b, (0, 0, 0), 0)])
    a = render(sc, Camera(35, 36, scale, (0, 0, 15), (W, H)), ss=4)
    sc2 = studio([(b, (0, 0, 0), 0)])
    o = sc2.objs[0]; o.gap = 1.25; o.thick = 0.45
    bb = render(sc2, Camera(35, 36, 6.2, (0, 0, 34), (W, H)), ss=4)
    # sheet, nearest-neighbour enlarged, with cell borders
    layers = b.layers
    cols = 5
    rows = int(math.ceil(len(layers) / cols))
    cell = 4
    cw, ch = X * cell + 6, Y * cell + 6
    sw, sh = cols * cw + 6, rows * ch + 6
    sheet = np.full((sh, sw, 3), (30, 36, 52), np.uint8)
    for i, k in enumerate(layers):
        r, c = divmod(i, cols)
        tile = np.full((Y, X, 3), (22, 26, 40), np.uint8)
        occ = b.occ[k]
        tile[occ] = b.rgb8[k][occ]
        tile = np.repeat(np.repeat(tile, cell, 0), cell, 1)
        y0, x0 = 6 + r * ch, 6 + c * cw
        sheet[y0:y0 + Y * cell, x0:x0 + X * cell] = tile
    save(a, 'panels/slices_stack.png'); save(bb, 'panels/slices_apart.png'); save(sheet, 'panels/slices_sheet.png')
    Ht = max(H, sh) + 70
    img = canvas(W * 2 + sw + pad * 4, Ht)
    img[pad:pad + H, pad:pad + W] = a
    img[pad:pad + H, pad * 2 + W:pad * 2 + W * 2] = bb
    x0 = pad * 3 + W * 2
    y0 = pad + (H - sh) // 2 if sh < H else pad
    img[y0:y0 + sh, x0:x0 + sw] = sheet
    draw_text(img, pad + W / 2, pad + H + 16, 'ONE STACK', scale=3, shadow=None)
    draw_text(img, pad * 2 + W * 1.5, pad + H + 16, f'{len(layers)} LAYERS', scale=3, shadow=None)
    draw_text(img, x0 + sw / 2, pad + H + 16, f'THE ASSET: {len(layers)} SPRITES, {X}x{Y} PX', scale=3, shadow=None)
    return save(img, 'slices.png')


# ---- 3. composable characters ----------------------------------------------------------
def composable():
    """Body, headwear, back gear and tool are separate stacks that interleave at runtime."""
    from assets import explorer
    W, H, scale = 1760, 470, 7.5
    sc = studio([])
    x = -98
    part_names = ['body', 'head', 'back', 'tool']
    ps = explorer.parts('prospector')
    marks = []
    for i, pn in enumerate(part_names):
        sc.add(ps[pn].bake(), (x, 0, 0), 25)
        marks.append(x)
        x += 25
    eq_x = x - 3
    x += 14
    for outfit in ('prospector', 'warden', 'delver'):
        for pn, pv in explorer.parts(outfit).items():      # drawn as four separate stacks
            sc.add(pv.bake(), (x, 0, 0), 25)
        marks.append(x)
        x += 34
    cam = Camera(0, 34, scale, (-2, 0, 14), (W, H))
    sc.floor['radius'] = 130
    sc.extent = 150
    img = render(sc, cam, ss=3)
    from stack.render import project
    labels = ['BODY', 'HEADWEAR', 'BACK GEAR', 'TOOL', 'PROSPECTOR', 'WARDEN', 'DELVER']
    for lx, lab in zip(marks, labels):
        px, py = project(cam, (lx, 14, 0))
        draw_text(img, px, py + 26, lab, scale=2)
    px, py = project(cam, (eq_x, 0, 14))
    draw_text(img, px + 22, py - 10, '=', scale=5)
    for m in marks[:3]:
        px, py = project(cam, (m + 12.5, 0, 14))
        draw_text(img, px, py - 10, '+', scale=4)
    return save(img, 'composable.png')


# ---- 4. hero stills --------------------------------------------------------------------
def lineup(size=(1920, 1080), ss=3, yaw=24.0):
    sc = scenes.showcase()
    k = size[0] / 1280.0
    c = dict(scenes.SHOWCASE_CAM); c['scale'] *= k
    cam = Camera(yaw, size=size, **c)
    img = render(sc, cam, ss=ss)
    scenes.label_pass(img, sc, cam, scale=3)
    return save(img, 'lineup.png')


def diorama(size=(1920, 1080), ss=3, yaw=-7.0, name='diorama.png', dusk=0.0):
    sc = scenes.diorama()
    scenes.set_dusk(sc, dusk)
    k = size[0] / 1280.0
    c = dict(scenes.DIORAMA_CAM); c['scale'] *= k
    cam = Camera(yaw, size=size, **c)
    return save(render(sc, cam, ss=ss), name)


def diorama_dark():
    return diorama(name='diorama_dark.png', dusk=1.0, yaw=7.0)


def diorama_side():
    """Flat-on: the game's side view. The cut face is plain pixel art; depth shows on every floor."""
    return diorama(name='diorama_side.png', yaw=0.0)


def worlds(seeds=(1, 2, 3, 4)):
    """Four seeds through the same generator: every slab below is generated, none is authored."""
    import worldgen as wg
    W, H = 960, 540
    img = canvas(W * 2, H * 2)
    for i, seed in enumerate(seeds):
        world = wg.generate(seed)
        sc = scenes.world_scene(world)
        c = dict(scenes.WORLD_CAM); c['scale'] *= W / 1280.0
        tile = render(sc, Camera(-6.0, size=(W, H), **c), ss=3)
        draw_text(tile, 24, H - 34, f'SEED {seed}', scale=3, align='left')
        save(tile, f'panels/world_{i + 1}.png')
        r, col = divmod(i, 2)
        img[r * H:(r + 1) * H, col * W:(col + 1) * W] = tile
    return save(img, 'worlds.png')


ALL = dict(worlds=worlds, technique=technique, buffers=buffers, slices=slices, composable=composable, lineup=lineup,
           diorama=diorama, diorama_dark=diorama_dark, diorama_side=diorama_side)

if __name__ == '__main__':
    for n in (sys.argv[1:] or list(ALL)):
        t0 = time.time()
        print(n)
        ALL[n]()
        print(f'  {time.time() - t0:.1f}s')
