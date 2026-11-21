"""Ore rock: a faceted boulder with ore surfacing as veins and chunky nuggets.

build(kind='copper' | 'gold' | 'iron' | 'ember', seed=None)

The boulder is a union of convex, plane-cut lumps (so it has flat facets rather than a
smooth ellipsoid skin), nudged by low-frequency noise. Ore runs through it as two tilted
sheets (the veins) that swell into nuggets where they break the surface. Each kind has
its own host rock, ore colour and a small accent so it reads at a glance:
  copper - grey stone, orange ore, a touch of green verdigris
  gold   - dark stone, bright yellow ore
  iron   - dark stone, pale metallic ore in a rusty crust
  ember  - basalt, glowing ore with hot cores and a warm point light
Each kind has its own default seed, so the four are different boulders; any seed works.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (24, 22, 18)

KINDS = {
    'copper': dict(host='stone', ore='ore_copper', seed=3,
                   accent=('verdigris', dict(rgb=(86, 178, 150))), stain=0.5),
    'gold':   dict(host='stone_dark', ore='ore_gold', seed=5),
    'iron':   dict(host='stone_dark', ore='ore_iron', seed=31,
                   accent=('rust', dict(rgb=(164, 84, 52))), stain=0.45, run=3, crust=True),
    'ember':  dict(host='basalt', ore='ore_ember', seed=17, vein='ember_dim', hot='ember_hot'),
}


def _dirs(n, rng, jitter=0.2):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = np.pi * (1 + 5 ** 0.5) * i + rng.uniform(0, 6.28)
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    d += rng.normal(scale=jitter, size=d.shape)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _lump(v, c, r, n, rng, lo=0.82, hi=1.0, closed=False):
    """Convex plane-cut lump. Returns (depth inside in voxels, facet normal per voxel)."""
    depth = np.full(v.idx.shape, 1e9, np.float32)
    nrm = np.zeros(v.idx.shape + (3,), np.float32)
    for d in _dirs(n, rng):
        if d[2] < -0.5 and not closed:
            continue
        support = np.sqrt((r[0] * d[0]) ** 2 + (r[1] * d[1]) ** 2 + (r[2] * d[2]) ** 2)
        support *= rng.uniform(lo, hi)
        f = support - ((v.x - c[0]) * d[0] + (v.y - c[1]) * d[1] + (v.z - c[2]) * d[2])
        m = f < depth
        depth = np.where(m, f, depth)
        nrm[m] = d
    # few planes leave long corners; round those off just outside the guide ellipsoid
    ex, ey, ez = (v.x - c[0]) / r[0], (v.y - c[1]) / r[1], (v.z - c[2]) / r[2]
    en = np.sqrt(ex * ex + ey * ey + ez * ez)
    e = (1.2 - en) * min(r)
    m = e < depth
    depth = np.where(m, e, depth)
    rn = np.stack([ex / r[0], ey / r[1], ez / r[2]], -1)
    rn /= np.maximum(np.linalg.norm(rn, axis=-1, keepdims=True), 1e-6)
    nrm[m] = rn[m]
    return depth, nrm


def _union(a, b):
    m = b[0] > a[0]
    return np.where(m, b[0], a[0]), np.where(m[..., None], b[1], a[1])


def _pick(v, mask, rng, k, min_dist):
    """Pick up to k well-spaced voxel centres from mask (seeded, greedy)."""
    zs, ys, xs = np.nonzero(mask)
    out = []
    for i in rng.permutation(len(zs)):
        p = np.array([xs[i] + 0.5, ys[i] + 0.5, zs[i] + 0.5])
        if all(np.linalg.norm(p - q) >= min_dist for q in out):
            out.append(p)
            if len(out) == k:
                break
    return out


def build(kind='copper', seed=None):
    K = KINDS[kind]
    seed = K['seed'] if seed is None else seed
    rng = np.random.default_rng(seed)
    v = Vox(*DIMS, name=f'ore_rock_{kind}')
    host, ore = K['host'], K['ore']
    cx, cy = 12.0, 9.8
    v.pivot = (cx, cy + 1.5)

    # --- boulder: a tall main lump, a shoulder and a toe --------------------------------
    f = _lump(v, (10.6, 9.8, 5.6), (7.9, 7.2, 11.6), 13, rng)
    f = _union(f, _lump(v, (16.2, 10.2, 3.6), (5.5, 6.4, 8.4), 10, rng))
    f = _union(f, _lump(v, (7.2, 12.0, 2.4), (5.0, 5.4, 6.2), 9, rng))
    depth, nrm = f
    # a slanted cut across the summit so the top is a facet, not a point
    cap_n = np.array([0.22, 0.18, 0.96]); cap_n /= np.linalg.norm(cap_n)
    cap = 9.4 - ((v.x - 10.6) * cap_n[0] + (v.y - 9.8) * cap_n[1] + (v.z - 5.6) * cap_n[2])
    m = cap < depth
    depth = np.where(m, cap, depth); nrm[m] = cap_n
    depth = depth + (v.noise(8, seed) - 0.5) * 1.2
    rock = depth > 0
    v.fill(rock, host)

    # facet shading: lit tops, darker undersides, some side faces a step down
    s = np.zeros(v.idx.shape, np.int8)
    face = np.modf(np.abs(np.sin(nrm @ np.array([12.9, 78.2, 37.7], np.float32)) * 43758.5))[0]
    s[nrm[..., 2] > 0.6] = 1
    s[(nrm[..., 2] <= 0.6) & (face > 0.5)] = -1                       # every other side facet
    s[nrm[..., 2] < -0.15] = -2
    v.shade[rock] = s[rock]
    v.paint(rock & (v.z < 2), add=-1)                                   # grounded base

    # --- veins: two tilted, slightly warped sheets of ore -------------------------------
    warp = (v.noise(6, seed + 3) - 0.5) * 3.0
    sheet_a = np.abs((v.x - 11.5) * 0.52 + (v.z - 7.0) * 0.72 - (v.y - cy) * 0.46 + warp) < 0.85
    sheet_b = np.abs((v.x - 15.0) * -0.62 + (v.z - 5.0) * 0.55 - (v.y - cy) * 0.56 + warp * 0.8) < 0.75
    sheet_b &= v.x > 11.5 + warp                                        # a branch, not a full crossing
    veins = (sheet_a | sheet_b) & rock & (depth < 3) & (v.z > 1)
    veins &= v.noise(7, seed + 4) > 0.3                                 # gaps, so it is not a hoop
    v.paint(veins, mat=K.get('vein', ore), shade=0)

    # --- nuggets: the veins swell where they break the surface --------------------------
    surf = v.m_surface() & veins & (v.z > 2.5)
    front = surf & ((v.y > cy + 0.5) | (v.z > 9))
    back = surf & (v.y < cy - 1.5)
    spots = _pick(v, front, rng, 4, 5.0) + _pick(v, back, rng, 2, 6.0)
    # one stray nugget low on the plain side, so the ore is not all in one corner
    lone = v.m_surface() & rock & (v.x < 8) & (v.y > cy + 2) & (v.z > 3) & (v.z < 7)
    spots += _pick(v, lone, rng, 1, 0.0)
    centre = np.array([cx, cy, 5.0])
    flush = np.zeros(v.idx.shape, bool)
    proud = np.zeros(v.idx.shape, bool)
    cores = []
    edge = v.noise(3.0, seed + 5)
    for i, p in enumerate(spots):
        out = p - centre
        out = out / np.linalg.norm(out)
        r = (2.8, 2.2, 2.5, 2.0, 2.4, 2.1, 2.3)[i % 7]
        flush |= v.m_ellipsoid(p, (r + (edge - 0.5) * 1.4,) * 3) & rock & (depth < 2.2)
        q = p + out * 0.7
        q[:2] = np.clip(q[:2], 3.2, (DIMS[0] - 3.2, DIMS[1] - 3.2))    # keep the nugget whole inside the volume
        h = r * 0.8
        d, _n = _lump(v, q, (h, h, h), 8, np.random.default_rng(seed + 40 + i), lo=0.75, hi=1.0, closed=True)
        proud |= (d > 0) & v.m_ellipsoid(q, (h * 1.35,) * 3)
        cores.append((q, h))
    v.paint(flush, mat=ore, shade=0)
    v.fill(proud, ore, shade=0)
    under = np.zeros_like(proud); under[1:] = ~v.occ[:-1]
    v.paint(proud & under, shade=-1)

    # --- accents ----------------------------------------------------------------------
    if K.get('accent'):
        name, spec = K['accent']
        v.mat(name, **spec)
        if K.get('crust'):                                              # weathered crust around the nuggets
            v.paint(flush & ~proud & ~veins, mat=name, shade=0)
        streak = np.zeros_like(proud)
        for dz in range(1, K.get('run', 3) + 1):                        # stains run down from the nuggets
            streak[:-dz] |= proud[dz:]
        halo = streak & v.is_mat(host) & v.m_surface() & (v.noise(3.0, seed + 6) > K.get('stain', 0.5))
        v.paint(halo, mat=name, shade=0)
    if K.get('hot'):
        for q, h in cores[:4]:
            v.paint(v.m_ellipsoid(q, (h * 0.5,) * 3) & proud, mat=K['hot'], shade=0)

    # --- loose pebbles ----------------------------------------------------------------
    for (px, py, rr, s2) in ((3.4, 18.6, (2.4, 2.0, 2.0), 21), (19.8, 18.4, (1.9, 1.7, 1.6), 22),
                             (21.8, 3.6, (1.7, 1.6, 1.4), 23)):
        d, n = _lump(v, (px, py, rr[2] * 0.4), rr, 9, np.random.default_rng(seed + s2))
        m = (d > 0) & ~v.occ
        v.fill(m, host)
        v.paint(m & (n[..., 2] > 0.6), shade=1)
    v.paint(v.m_ellipsoid((4.0, 19.2, 1.6), (1.3, 1.3, 1.1)) & v.is_mat(host), mat=ore, shade=0)

    # --- moss: one cap on the shoulder and a thin skirt at the feet ---------------------
    moss_n = v.noise(5, seed + 7)
    if kind != 'ember':
        cap = v.m_exposed_top() & v.is_mat(host) & (v.x > 13) & (v.z > 5) & (moss_n > 0.42)
        v.paint(cap, mat='moss', shade=0)
        v.paint(cap & (v.noise(3, seed + 8) > 0.58), mat='moss_light')
        skirt = v.m_surface() & v.is_mat(host) & (v.z < 2.2) & (moss_n > 0.58)
        v.paint(skirt, mat='moss', shade=-1)
    else:
        skirt = v.m_surface() & v.is_mat(host) & (v.z < 2.2) & (moss_n > 0.62)
        v.paint(skirt, mat='moss', shade=-2)
        v.light((cx, cy + 9.5, 8.0), (1.0, 0.5, 0.2), radius=28, power=1.0)
    return v
