"""Procedural side-view world -> sprite stack.

The world is a 2D grid of material cells (x across, z up), the same model Wylden's design
uses. generate() writes that grid from a seed; to_vox() gives the grid depth and returns it
as a stack: one row of cells becomes CELL slices. Digging is dig(): it clears cells, and the
stack is rebuilt from the grid. Nothing about the terrain is authored by hand.
"""
import numpy as np

from stack.voxel import Vox

CELL = 2          # voxels per world cell
DEPTH = 34        # how deep the cross-section is drawn (cosmetic; play stays in the plane)
W, H = 128, 60    # cells

MATS = ['air', 'grass', 'dirt', 'dirt_dark', 'stone', 'stone_dark', 'basalt', 'deepstone', 'slate',
        'coal', 'ore_copper', 'ore_gold', 'vein_ember', 'vein_opal', 'vein_pink']
M = {n: i for i, n in enumerate(MATS)}
LOCAL = {'vein_opal': dict(rgb=(104, 214, 204), emit=0.4, spec=0.8, gloss=36),
         'vein_pink': dict(rgb=(232, 150, 204), emit=0.35, spec=0.8, gloss=36),
         'vein_ember': dict(rgb=(240, 122, 56), emit=0.7)}


def noise2(w, h, scale, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((int(h / scale) + 3, int(w / scale) + 3))
    xs, zs = np.arange(w) / scale, np.arange(h) / scale
    ix, iz = xs.astype(int), zs.astype(int)
    tx, tz = xs - ix, zs - iz
    tx, tz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
    a = g[iz][:, ix] * (1 - tx) + g[iz][:, ix + 1] * tx
    b = g[iz + 1][:, ix] * (1 - tx) + g[iz + 1][:, ix + 1] * tx
    return a * (1 - tz)[:, None] + b * tz[:, None]


def generate(seed=1, w=W, h=H):
    """World plan -> caverns and routes -> materials. Returns a dict with the cell grid."""
    rng = np.random.default_rng(seed)
    x = np.arange(w)[None, :].astype(float)
    z = np.arange(h)[:, None].astype(float)
    # 1. world plan: surface line, strata, a biome field (0 = Moss & Ember, 1 = Opal Deep)
    surf = h - 8 + (noise2(w, 1, 24, seed * 7 + 1)[0] - 0.5) * 6
    wav = noise2(w, h, 20, seed * 7 + 2)
    d_dirt = surf[None, :] - 6 + (wav - 0.5) * 5
    d_deep = h * 0.36 + (wav - 0.5) * 8
    biome = np.clip((x / w - 0.35) * 2.2 + (noise2(w, h, 30, seed * 7 + 3) - 0.5) * 0.8, 0, 1)
    rock = np.full((h, w), M['stone'], np.uint8)
    rock[z >= d_dirt] = M['dirt']
    rock[z < d_deep] = M['deepstone']
    n1, n2, n3 = noise2(w, h, 6, seed * 7 + 4), noise2(w, h, 9, seed * 7 + 5), noise2(w, h, 3.2, seed * 7 + 6)
    rock[(rock == M['dirt']) & (n1 > 0.62)] = M['dirt_dark']
    rock[(rock == M['stone']) & (n2 > 0.6)] = M['stone_dark']
    rock[np.isin(rock, (M['stone'], M['stone_dark'])) & (n1 > 0.66) & (biome < 0.5)] = M['basalt']
    rock[(rock == M['deepstone']) & (n2 > 0.62)] = M['slate']
    # 2. deposits follow the plan: coal under the soil, copper and gold in stone, ember in the
    #    mossy west, opal in the deep east
    r1, r2 = noise2(w, h, 7, seed * 7 + 8), noise2(w, h, 5, seed * 7 + 9)
    stone = np.isin(rock, (M['stone'], M['stone_dark'], M['basalt']))
    deep = np.isin(rock, (M['deepstone'], M['slate']))
    rock[stone & (np.abs(r1 - 0.5) < 0.014) & (biome > 0.3)] = M['ore_copper']
    rock[stone & (n3 > 0.86) & (biome > 0.45)] = M['ore_gold']
    rock[stone & (np.abs(r2 - 0.48) < 0.011) & (biome < 0.4)] = M['vein_ember']
    rock[np.isin(rock, (M['dirt'], M['dirt_dark'], M['stone'])) & (np.abs(z - d_dirt) < 1.2) & (n2 > 0.55)] = M['coal']
    rock[deep & (np.abs(r2 - 0.5) < 0.011) & (biome > 0.35)] = M['vein_opal']
    rock[deep & (np.abs(r1 - 0.55) < 0.008) & (biome > 0.55)] = M['vein_pink']
    rock[z >= surf[None, :]] = M['air']
    rock[(z >= surf[None, :] - 1) & (z < surf[None, :])] = M['grass']
    # 3. landmarks and routes: a descending chain of caverns, a shaft to the surface,
    #    narrow passages hinting at the way on, and scattered pockets
    air = z >= surf[None, :]
    warp = (noise2(w, h, 8, seed * 7 + 10) - 0.5) * 0.45
    caverns = []
    cz = h * 0.62 + rng.uniform(-2, 2)
    for i in range(3):
        cx = w * (0.16 + 0.34 * i) + rng.uniform(-3, 3)
        rx, rz = rng.uniform(9.5, 12), rng.uniform(9, 10.5)
        floor = int(round(cz - rz * 0.62))
        air |= (((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 < 1 + warp) & (z >= floor)
        caverns.append(dict(cx=float(cx), cz=float(cz), rx=float(rx), rz=float(rz), floor=floor))
        cz -= rng.uniform(0.55, 0.8) * rz

    def worm(p0, p1, r, seed_):
        n = int(max(abs(p1[0] - p0[0]), abs(p1[1] - p0[1])) * 1.5) + 2
        wob = np.random.default_rng(seed_)
        for t in np.linspace(0, 1, n):
            px = p0[0] + (p1[0] - p0[0]) * t
            pz = p0[1] + (p1[1] - p0[1]) * t + np.sin(t * 9 + seed_) * 1.6 * np.sin(t * np.pi)
            rr = r * (0.8 + 0.4 * wob.random())
            air[((x - px) ** 2 + (z - pz) ** 2) < rr * rr] = True
    c0 = caverns[0]
    worm((c0['cx'] - c0['rx'] * 0.5, c0['cz'] + c0['rz'] * 0.5), (c0['cx'] - c0['rx'] * 0.3 + rng.uniform(-4, 4), h), 3.2, seed + 1)
    for a, b in zip(caverns[:-1], caverns[1:]):
        worm((a['cx'] + a['rx'] * 0.7, a['cz'] + a['rz'] * 0.45), (b['cx'] - b['rx'] * 0.7, b['cz'] + b['rz'] * 0.55), 1.7, seed + 5)
    air |= (noise2(w, h, 5, seed * 7 + 11) > 0.86) & (z < d_dirt - 3) & (z > 3)
    # 4. validate: every cavern must be reachable from the open sky through air cells
    reach = np.zeros_like(air)
    reach[-1] = air[-1]
    for _ in range(4 * (w + h)):
        grow = reach.copy()
        grow[1:] |= reach[:-1]; grow[:-1] |= reach[1:]; grow[:, 1:] |= reach[:, :-1]; grow[:, :-1] |= reach[:, 1:]
        grow &= air
        if (grow == reach).all():
            break
        reach = grow
    ok = all(reach[int(c['cz']), int(c['cx'])] for c in caverns)
    cells = rock.copy()
    cells[air] = M['air']
    return dict(seed=seed, cells=cells, rock=rock, caverns=caverns, surf=surf, biome=biome, connected=bool(ok))


def dig(world, cx, cz, r, floor=None):
    """Clear the cells within r of (cx, cz), optionally keeping everything below a floor.
    Returns the (x, z, material) of every solid cell removed."""
    cells = world['cells']
    h, w = cells.shape
    x = np.arange(w)[None, :]; z = np.arange(h)[:, None]
    m = ((x - cx) ** 2 + (z - cz) ** 2 <= r * r) & (cells != M['air'])
    if floor is not None:
        m &= z >= floor
    zs, xs = np.nonzero(m)
    out = [(int(a), int(b), MATS[cells[b, a]]) for a, b in zip(xs, zs)]
    cells[m] = M['air']
    return out


def to_vox(world, depth=DEPTH, cell=CELL):
    """Give the cell grid depth and return it as a stack (each cell row = `cell` slices)."""
    cells, rock = world['cells'], world['rock']
    h, w = cells.shape
    seed = world['seed']
    v = Vox(w * cell, depth, h * cell, name=f"world_{seed}")
    up = lambda g: np.repeat(np.repeat(g, cell, 0), cell, 1)[:, None, :]      # [Z, 1, X]
    rk, cl = up(rock), up(cells)
    for name, pal in LOCAL.items():
        v.mat(name, **pal)
    for name in MATS[1:]:
        v.fill(np.broadcast_to(rk == M[name], v.idx.shape), name)
    # texture: calm clustered shade, the same for every seed's materials
    v.speckle(['stone', 'stone_dark', 'basalt', 'deepstone', 'slate', 'dirt', 'dirt_dark'], 0.14, step=-1, scale=5, seed=seed + 30)
    # air cells are open toward the viewer; the rock behind them stays as a dark back wall
    yb = 8 + (v.noise(9, seed + 5)[:, :1, :] - 0.5) * 5
    open_ = np.broadcast_to(cl == M['air'], v.idx.shape)
    sky = np.broadcast_to(rk == M['air'], v.idx.shape)
    back = open_ & ~sky & (v.y < yb + 3)
    for name in ('ore_copper', 'ore_gold', 'coal'):
        v.paint(back & v.is_mat(name), mat='stone_dark')
    v.paint(back & v.is_mat('vein_opal', 'vein_pink'), mat='deepstone')
    v.paint(back & v.is_mat('vein_ember'), mat='basalt')
    v.paint(back, shade=-2)
    v.carve(open_ & (v.y >= yb))
    v.carve(sky)
    # dressing from context: moss on cave floors in the west, grass tufts on the surface
    bio = up(world['biome'])
    tops = v.m_exposed_top(2)
    v.paint(tops & (v.y > 12) & (bio < 0.55) & (v.noise(6, seed + 60) > 0.5)
            & v.is_mat('stone', 'stone_dark', 'basalt', 'dirt', 'dirt_dark'), mat='moss')
    v.paint(v.is_mat('moss') & (v.noise(3, seed + 61) > 0.68), mat='moss_light')
    rng = np.random.default_rng(seed + 70)
    for _ in range(90):
        gx, gy = int(rng.integers(1, w * cell - 1)), int(rng.integers(1, depth - 1))
        k = h * cell - 2
        while k > h * cell * 0.7 and not v.idx[k, gy, gx]:
            k -= 1
        if v.idx[k, gy, gx] and v.mats[v.idx[k, gy, gx]]['name'] == 'grass' and k + 2 < h * cell:
            if rng.random() < 0.8:
                v.box((gx, gy, k + 1), (gx + 1, gy + 1, k + 2 + int(rng.integers(0, 2))), 'grass', shade=1)
            else:
                v.box((gx, gy, k + 1), (gx + 1, gy + 1, k + 2), 'fern')
                v.box((gx, gy, k + 2), (gx + 1, gy + 1, k + 3), 'petal')
    return v


# prefab stacks the generator places in context: (asset, params, which cavern, offset in cells, yaw)
PROPS = [
    ('glowshrooms', {}, 0, -2.0, 20), ('lantern_post', {}, 0, -8.5, 0),
    ('ore_rock', {'kind': 'copper'}, 1, 4.5, 30), ('chest', {}, 1, -3.0, 0),
    ('opal_cluster', {}, 2, 4.0, 0), ('scarab', {}, 2, -4.5, 180),
]


def floor_voxel(v, xv, yv, z_hint):
    k = int(z_hint)
    while k > 0 and not v.idx[k, int(yv), int(xv)]:
        k -= 1
    return k + 1


def placements(world, v, cell=CELL):
    """Where each prefab stands, in voxel coordinates of the slab."""
    out = []
    for (name, params, ci, dx, yaw) in PROPS:
        c = world['caverns'][ci]
        xv = (c['cx'] + dx) * cell
        yv = 21
        zs = [floor_voxel(v, xv + ox, yv + oy, (c['floor'] + 6) * cell) for ox in (-5, 0, 5) for oy in (-3, 3)]
        out.append((name, params, xv, yv, int(np.median(zs)), yaw))
    return out
