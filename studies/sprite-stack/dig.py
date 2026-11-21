#!/usr/bin/env python3
"""Digging through a generated world, drawn as sprite stacks.

An explorer tunnels from the first cavern of a generated world toward the second. Every
pickaxe bite clears cells in the world's cell grid (worldgen.dig); the terrain stack is then
rebuilt from the grid and re-baked, so slices, normals, occlusion and shadows all follow the
edit. The pickaxe swing is a four-pose flipbook of small stacks; debris is tiny stacks.

python3 dig.py [procs]   ->  out/web/dig.mp4      python3 dig.py frames 60 120 ...
"""
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
import worldgen as wg                                            # noqa: E402
from assets import explorer                                      # noqa: E402
from reels import caption, ease, seg                             # noqa: E402
from scenes import baked, have                                   # noqa: E402
from stack.render import Camera, Scene, render                   # noqa: E402
from stack.voxel import Vox                                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, SIZE, SS = 24, (1280, 720), 2
SEED = 1
C = wg.CELL
BITE_R = 5.2          # cells
STEP = 4              # cells advanced per three bites
T0, DT = 2.5, 0.28    # first bite, seconds between bites
POSES = {'rest': 20, 'raised': -32, 'mid': 34, 'struck': 78}

S = {}                # everything precomputed before forking


def pick_pose(phi_deg):
    """The pickaxe at a swing angle, as its own small stack (same frame as the explorer, shifted)."""
    v = Vox(46, 22, 46, name='pick', grounded=False)
    sx, sz = 9, 6
    v.pivot = (12.5 + sx, 11.0)
    phi = math.radians(phi_deg)
    d = np.array([math.sin(phi), 0, math.cos(phi)]); p = np.array([math.cos(phi), 0, -math.sin(phi)])
    Hh = np.array([17.3 + sx, 18.8, 11.8 + sz])
    v.capsule(tuple(Hh - 5.5 * d), tuple(Hh + 10.5 * d), 0.9, 'wood')
    T = Hh + 10.8 * d
    v.capsule(tuple(T), tuple(T - 5.6 * p - 1.2 * d), 1.3, 'steel', r1=0.6)
    v.capsule(tuple(T), tuple(T + 6.0 * p - 1.6 * d), 1.3, 'steel', r1=0.6)
    v.ellipsoid(tuple(T), (1.5, 1.4, 1.5), 'iron_dark')
    return v, sz


def prepare():
    world = wg.generate(SEED)
    A, B = world['caverns'][0], world['caverns'][1]
    fl = A['floor']
    cells0 = world['cells']
    x = int(A['cx'])
    while cells0[fl + 6, x] == 0:
        x += 1
    x_wall = x                                   # first solid cell at mid height
    xb = int(B['cx'] - B['rx'] * 0.85)           # where the next cavern begins
    steps = int(math.ceil((xb - x_wall) / STEP)) + 1
    bites = []
    for s in range(steps):
        for dz in (13.4, 8.0, 3.0):
            bites.append((x_wall + 1.5 + STEP * s, fl + dz))
    states, debris = [], []
    for n in range(len(bites) + 1):
        if n:
            removed = wg.dig(world, bites[n - 1][0], bites[n - 1][1], BITE_R, floor=fl)
            debris.append(removed)
        vox = wg.to_vox(world)
        states.append((vox.bake(), vox.pivot, wg.placements(world, vox) if n == 0 else None))
        print(f'  state {n}/{len(bites)}: {vox.count()} voxels', flush=True)
    ps = explorer.parts('prospector')
    body = ps['body']
    body.blit(ps['back']); body.blit(ps['head'])
    picks = {}
    for name, ang in POSES.items():
        v, sz = pick_pose(ang)
        picks[name] = (v.bake(), sz)
    chunk = {}
    for m in wg.MATS[1:]:
        v = Vox(3, 3, 3, name='chunk', grounded=False)
        for nme, pal in wg.LOCAL.items():
            v.mat(nme, **pal)
        v.rbox((0, 0, 0), (3, 3, 3), m, r=1.2)
        v.box((1, 1, 1), (2, 2, 2), m)
        chunk[m] = v.bake()
    for name, params, *_ in states[0][2]:
        baked(name, **params)
    S.update(world=world, floor=fl, x_wall=x_wall, bites=bites, steps=steps, states=states, debris=debris,
             body=body.bake(), picks=picks, chunk=chunk, length=T0 + DT * len(bites) + 3.4)
    return S


def frame(i):
    t = i / FPS
    bites, fl = S['bites'], S['floor']
    n = sum(1 for j in range(len(bites)) if t >= T0 + DT * j)
    slab, (px, py), _ = S['states'][n]
    sc = Scene()
    sc.extent = 190; sc.bloom = 0.6
    sc.key_frame = 'world'; sc.key_dir = (-0.35, 0.5, 0.8); sc.key_rgb = (1.0, 0.95, 0.86)
    sc.sky_rgb = (0.34, 0.44, 0.70); sc.ground_rgb = (0.16, 0.14, 0.16); sc.ambient = 0.40
    sc.bg = dict(inner=(22, 40, 58), outer=(4, 7, 14), center=(0.5, 0.5), dots=True)
    sc.add(slab, (0, 0, 0))
    for (name, params, xv, yv, zv, yaw) in S['states'][0][2]:
        if have(name):
            sc.add(baked(name, **params), (xv - px, yv - py, zv), yaw)
    # the explorer walks forward as each column of cells is cleared
    def pivot_x(steps_done):
        return 2 * S['x_wall'] - 12.4 + 2 * STEP * steps_done
    done = 0.0
    for s in range(S['steps']):
        t_end = T0 + DT * (3 * s + 2)
        done += ease(seg(t, t_end + 0.05, t_end + 0.3))
    ex = pivot_x(done) - px
    ey, ez = 22 - py, fl * C
    # swing: raised before each bite, struck on it
    pose, lunge = 'rest', 0.0
    for j in range(len(bites)):
        dt = t - (T0 + DT * j)
        if -0.2 <= dt < -0.06:
            pose = 'raised'
        elif -0.06 <= dt < -0.02:
            pose = 'mid'
        elif -0.02 <= dt < 0.09:
            pose, lunge = 'struck', 1.5
    sc.add(S['body'], (ex + lunge, ey, ez), 0)
    pk, sz = S['picks'][pose]
    sc.add(pk, (ex + lunge, ey, ez - sz), 0)
    # debris: small stacks thrown back from each bite
    for j in range(n):
        age = t - (T0 + DT * j)
        if age > 0.75 or not S['debris'][j]:
            continue
        rng = np.random.default_rng(1000 + j)
        rem = S['debris'][j]
        for q in range(min(22, len(rem))):
            cx, cz, m = rem[int(rng.integers(0, len(rem)))]
            v0 = np.array([-rng.uniform(8, 30), rng.uniform(6, 30), rng.uniform(8, 28)])
            p0 = np.array([cx * C + 1 - px, rng.uniform(20, 32) - py, cz * C + 1])
            pos = p0 + v0 * age + np.array([0, 0, -70.0]) * age * age * 0.5
            if pos[2] < fl * C - 1:
                continue
            sc.add(S['chunk'][m], tuple(pos), float(rng.uniform(0, 360) + age * 400), shadow=False)
    # camera: wide, push in to the dig, pull back out at the end
    L = S['length']
    zoom = ease(seg(t, 0.7, 2.2)) * (1 - ease(seg(t, L - 2.2, L - 0.6)))
    wide = scenes.WORLD_CAM
    look_d = (ex + 20, 0, ez + 19)
    scale = wide['scale'] * (1 - zoom) + 7.4 * zoom
    look = tuple(a * (1 - zoom) + b * zoom for a, b in zip(wide['look'], look_d))
    cam = Camera(-6.0 - 4.0 * zoom, wide['elev'], scale, look, SIZE)
    img = render(sc, cam, ss=SS)
    if t < 2.3:
        caption(img, f'GENERATED WORLD, SEED {SEED}', 'A GRID OF MATERIAL CELLS. EACH ROW OF CELLS IS TWO SLICES')
    elif t < L - 2.2:
        caption(img, 'DIGGING', f'BITE {n}/{len(bites)}: CELLS CLEARED, STACK REBUILT FROM THE GRID')
    else:
        caption(img, 'THE EDIT IS THE WORLD', 'NO MESH TO REBUILD: THE TUNNEL IS JUST CHANGED CELLS')
    return img


def _work(i):
    Image.fromarray(frame(i)).save(os.path.join(HERE, 'out', 'frames', 'dig', f'{i:04d}.png'), compress_level=1)
    return i


if __name__ == '__main__':
    os.makedirs(os.path.join(HERE, 'out', 'frames', 'dig'), exist_ok=True)
    t0 = time.time()
    prepare()
    n = int(round(S['length'] * FPS))
    print(f"steps {S['steps']}, bites {len(S['bites'])}, {S['length']:.1f}s, {n} frames, prep {time.time() - t0:.0f}s", flush=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'frames':
        for i in sys.argv[2:]:
            _work(int(i))
        sys.exit(0)
    with mp.get_context('fork').Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        for j, _ in enumerate(pool.imap_unordered(_work, range(n), chunksize=2)):
            if j % 24 == 0:
                print(f'  dig: {j}/{n} frames, {time.time() - t0:.0f}s', flush=True)
    out = os.path.join(HERE, 'out', 'web', 'dig.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(HERE, 'out', 'frames', 'dig', '%04d.png'),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], check=True)
    print('->', out, f'({time.time() - t0:.0f}s)')
