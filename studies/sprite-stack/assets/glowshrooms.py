"""Glowshrooms: glowing cave mushrooms on a mossy rock mound.

build(seed=7, cap_emit=0.5)

One tall mushroom with a broad domed cap leans over four smaller ones. Caps are hollow
domes tipped slightly toward the camera so their spotted tops show in the side view;
the undersides are dark gills, lit by a teal light that hangs under the big cap.
`cap_emit` is the glow of the cap skin (the spots keep the palette's stronger glow).
"""
import math

import numpy as np

from stack.voxel import Vox

DIMS = (26, 24, 28)

# stem base, stem top, stem radius (base, top), cap radius (x, y), cap height, tilt toward +y / +x (deg), spots
SHROOMS = [
    dict(base=(11.6, 10.4, 3.5), top=(12.6, 11.6, 19.0), stem=(2.7, 1.9), R=(9.6, 9.0), H=7.6,
         tilt=(13, 4), bend=(-1.6, 0.6), spots=9, spot_r=1.45),
    dict(base=(20.0, 15.4, 2.0), top=(20.8, 16.4, 10.0), stem=(1.7, 1.3), R=(4.2, 4.2), H=3.8,
         tilt=(14, 10), bend=(0.8, 0.0), spots=3, spot_r=0.95),
    dict(base=(5.8, 16.4, 1.5), top=(5.0, 17.2, 7.4), stem=(1.5, 1.2), R=(3.4, 3.3), H=3.0,
         tilt=(12, -12), bend=(-0.5, 0.0), spots=2, spot_r=0.9),
    dict(base=(17.0, 5.0, 2.0), top=(16.4, 4.2, 9.0), stem=(1.4, 1.1), R=(3.1, 3.0), H=2.8,
         tilt=(-10, -8), bend=(0.5, 0.0), spots=2, spot_r=0.9),
    dict(base=(12.6, 19.6, 1.5), top=(13.0, 20.4, 4.6), stem=(1.2, 1.1), R=(2.5, 2.4), H=2.2,
         tilt=(10, 0), bend=(0.0, 0.0), spots=1, spot_r=0.8),
]


def _dirs(n, rng, jitter=0.2):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = np.pi * (1 + 5 ** 0.5) * i + rng.uniform(0, 6.28)
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    d += rng.normal(scale=jitter, size=d.shape)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _lump(v, c, r, n, rng, lo=0.84, hi=1.0):
    """Convex plane-cut rock lump: (depth inside, facet normal per voxel)."""
    depth = np.full(v.idx.shape, 1e9, np.float32)
    nrm = np.zeros(v.idx.shape + (3,), np.float32)
    for d in _dirs(n, rng):
        if d[2] < -0.5:
            continue
        support = np.sqrt((r[0] * d[0]) ** 2 + (r[1] * d[1]) ** 2 + (r[2] * d[2]) ** 2) * rng.uniform(lo, hi)
        f = support - ((v.x - c[0]) * d[0] + (v.y - c[1]) * d[1] + (v.z - c[2]) * d[2])
        m = f < depth
        depth = np.where(m, f, depth)
        nrm[m] = d
    return depth, nrm


def _cap_frame(v, c, tilt):
    """Local coordinates of a cap centred at c, tipped tilt[0] deg toward +y and tilt[1] toward +x."""
    ay, ax = math.radians(tilt[0]), math.radians(tilt[1])
    x, y, z = v.x - c[0], v.y - c[1], v.z - c[2]
    y1 = y * math.cos(ay) + z * math.sin(ay)          # tip toward +y
    z1 = -y * math.sin(ay) + z * math.cos(ay)
    x2 = x * math.cos(ax) + z1 * math.sin(ax)         # tip toward +x
    z2 = -x * math.sin(ax) + z1 * math.cos(ax)
    return x2, y1, z2


def _shroom(v, S, rng, wob):
    base = np.array(S['base']); top = np.array(S['top'])
    r0, r1 = S['stem']
    # stem: two segments through a bent midpoint, flared foot
    mid = (base + top) / 2 + np.array([S['bend'][0], S['bend'][1], 0.0])
    rm = (r0 + r1) / 2
    stem = v.m_capsule(base, mid, r0, rm) | v.m_capsule(mid, top, rm, r1)
    stem |= v.m_ellipsoid(base + (0, 0, -0.3), (r0 * 1.35, r0 * 1.35, r0 * 0.9))
    v.fill(stem, 'shroom_stem')
    v.paint(stem & (v.z < base[2] + (top[2] - base[2]) * 0.3), shade=-1)
    if r0 > 2.0:                                                       # a skirt ring on the big one
        ring_c = base + (top - base) * 0.66
        ring = v.m_cyl((ring_c[0], ring_c[1]), r1 + 1.5, ring_c[2] - 0.8, ring_c[2] + 0.8)
        v.fill(ring, 'shroom_stem', shade=-1)
        v.paint(ring & (v.z > ring_c[2]), shade=1)

    # cap: hollow dome with an uneven rim
    Rx, Ry = S['R']; H = S['H']
    lx, ly, lz = _cap_frame(v, top + (0, 0, -0.6), S['tilt'])
    rim = 1.0 + (wob - 0.5) * 0.22
    dome = ((lx / (Rx * rim)) ** 2 + (ly / (Ry * rim)) ** 2 + (lz / H) ** 2 <= 1.0) & (lz > -0.9)
    t = max(1.5, min(Rx, Ry) * 0.24)                                   # shell thickness at the rim
    hollow = ((lx / (Rx - t)) ** 2 + (ly / (Ry - t)) ** 2 + ((lz + 0.9) / (H * 0.5)) ** 2 <= 1.0)
    cap = dome & ~hollow
    v.fill(cap, 'shroom_cap')
    # underside gills and the down-turned rim
    below = np.zeros_like(cap); below[1:] = ~cap[:-1]
    under = cap & below
    v.paint(cap, shade=-1)
    v.paint(cap & (lz > H * 0.62), shade=0)                            # lit crown
    v.paint(cap & (lz < H * 0.22), shade=-2)                           # rim band
    v.paint(under, shade=-3)                                           # gills
    v.paint(under & (np.sqrt((lx / Rx) ** 2 + (ly / Ry) ** 2) > 0.86), shade=-2)
    v.paint(stem & hollow & (lz > -2.5), shade=-1)                     # stem neck in the cap's shade

    # spots: round dots on the upper dome
    top_skin = cap & ~under & v.m_surface()
    placed = []
    tries = 0
    while len(placed) < S['spots'] and tries < 400:
        tries += 1
        az = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.uniform(0.0, 0.62))
        px, py = Rx * rr * math.cos(az), Ry * rr * math.sin(az)
        pz = H * math.sqrt(max(0.0, 1 - rr * rr))
        if all((px - q[0]) ** 2 + (py - q[1]) ** 2 + (pz - q[2]) ** 2 > (S['spot_r'] * 3.1) ** 2 for q in placed):
            placed.append((px, py, pz))
    for i, (px, py, pz) in enumerate(placed):
        sr = S['spot_r'] * (1.0 if i % 3 else 1.25)
        dot = ((lx - px) ** 2 + (ly - py) ** 2 + (lz - pz) ** 2) <= sr * sr
        v.paint(dot & top_skin, mat='shroom_spot', shade=0)
    return cap, stem


def _fern(v, base, fronds, rng, length=5.0, start=0.0):
    """A tuft of arching fronds: dark at the root, lighter at the drooping tips."""
    for k in range(fronds):
        az = start + 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / fronds
        L = length * rng.uniform(0.85, 1.15)
        d = np.array([math.cos(az), math.sin(az), 0.0])
        b = np.array(base, float)
        mid = b + d * L * 0.45 + (0, 0, L * 0.8)
        tip = b + d * L + (0, 0, L * 0.45)
        v.add(v.m_capsule(b, mid, 0.8, 0.75), 'fern', shade=-1)
        m2 = v.m_capsule(mid, tip, 0.75, 0.5) & ~v.occ
        v.fill(m2, 'fern', shade=0)
        v.paint(m2 & v.m_ellipsoid(tip, (1.3, 1.3, 1.3)), shade=2)


def _grass(v, base, rng, n=5, spread=1.6):
    for _ in range(n):
        x = base[0] + rng.uniform(-spread, spread)
        y = base[1] + rng.uniform(-spread, spread)
        h = rng.uniform(2.0, 4.2)
        col = v.m_box((math.floor(x), math.floor(y), 0), (math.floor(x) + 1, math.floor(y) + 1, 12))
        zs = v.z[col & v.occ]
        z0 = (zs.max() + 0.5) if zs.size else 0.0
        if z0 > 7:
            continue
        blade = col & (v.z >= z0) & (v.z < z0 + h)
        v.add(blade, 'fern', shade=1)
        v.paint(blade & (v.z > z0 + h - 1.2), shade=2)


def build(seed=7, cap_emit=0.5):
    rng = np.random.default_rng(seed)
    v = Vox(*DIMS, name='glowshrooms')
    v.pivot = (13.0, 12.0)
    # a whole cap at full glow burns out to white; the spots keep the strong glow
    v.mat('shroom_cap', emit=cap_emit)

    # --- mossy rock mound: a few chunky rocks, bare sides, a moss blanket on top -----------
    depth, nrm = _lump(v, (12.2, 11.0, 0.4), (8.8, 7.6, 5.6), 11, rng)
    for c, r, n in (((19.6, 14.0, 0.3), (5.2, 5.6, 3.8), 9), ((6.2, 15.0, 0.3), (5.0, 5.2, 3.4), 9),
                    ((17.8, 6.4, 0.3), (5.0, 4.4, 3.6), 9), ((12.8, 18.0, 0.3), (5.0, 4.0, 2.6), 8)):
        d2, n2 = _lump(v, c, r, n, rng)
        m = d2 > depth
        depth = np.where(m, d2, depth); nrm[m] = n2[m]
    depth = depth + (v.noise(8, seed) - 0.5) * 0.9
    rock = depth > 0
    v.fill(rock, 'stone_dark')
    s = np.zeros(v.idx.shape, np.int8)
    face = np.modf(np.abs(np.sin(nrm @ np.array([12.9, 78.2, 37.7], np.float32)) * 43758.5))[0]
    s[(nrm[..., 2] < 0.5) & (face > 0.5)] = -1
    v.shade[rock] = s[rock]
    v.paint(rock & (v.z < 1), add=-1)
    mn = v.noise(6, seed + 1)
    moss = v.m_exposed_top() & rock & (nrm[..., 2] > 0.5) & ((mn > 0.3) | (v.z > 3.0))
    lip = np.zeros_like(moss); lip[:-1] = moss[1:]                     # one voxel of overhang down the side
    lip &= v.m_surface() & rock & (mn > 0.5)
    v.paint(moss, mat='moss', shade=0)
    v.paint(lip, mat='moss', shade=-1)
    v.paint(moss & (v.noise(4.5, seed + 2) > 0.62), shade=1)           # sunlit-looking tufts

    # --- mushrooms ------------------------------------------------------------------------
    wob = v.noise(6, seed + 3)
    for S in SHROOMS:
        _shroom(v, S, rng, wob)

    # --- ferns and grass: at the ends of the mound, clear of the rock faces ----------------
    _fern(v, (3.0, 9.4, 0.5), 4, rng, length=5.4, start=1.9)
    _fern(v, (22.8, 20.0, 0.5), 4, rng, length=5.0, start=0.4)
    _grass(v, (8.6, 20.6), rng, n=4, spread=1.3)
    _grass(v, (23.6, 9.4), rng, n=4, spread=1.3)

    v.light((12.6, 13.6, 15.0), (0.3, 0.95, 0.85), radius=28, power=1.0)
    return v
