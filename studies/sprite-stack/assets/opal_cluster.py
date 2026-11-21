"""Opal cluster: faceted crystal spires growing from a deepstone base (the Opal Deep).

build(seed=5, emit=0.55)

Each spire is a six-sided prism that swells slightly toward its shoulder and ends in a
pointed pyramid. Facets get deliberate shade steps by which way they face, the root of
each spire is a second opal hue (the play of colour), and the tips are white-hot.
`emit` is the glow of the spire bodies (the palette default burns the facets out).
"""
import math

import numpy as np

from stack.voxel import Vox

DIMS = (26, 26, 30)
LIGHT = np.array([-0.55, 0.45, 0.72]) / np.linalg.norm([-0.55, 0.45, 0.72])   # game key light
FACET = (-1, -2, -3)      # shade steps for facets facing toward / across / away from it

# base point, tip point, radius, tip length, body colour, root colour
SPIRES = [
    ((12.6, 12.0, 1.5), (13.8, 12.8, 29.4), 3.5, 7.5, 'opal_teal', 'opal_lilac'),    # the tall one
    ((8.2, 14.4, 1.5), (3.4, 17.4, 20.5), 2.7, 6.0, 'opal_pink', 'opal_lilac'),
    ((17.4, 13.0, 1.5), (22.4, 14.6, 22.5), 2.8, 6.0, 'opal_lilac', 'opal_teal'),
    ((12.0, 17.6, 1.5), (10.0, 23.0, 13.5), 2.3, 4.5, 'opal_teal', 'opal_pink'),
    ((16.2, 8.6, 1.5), (19.6, 3.6, 16.5), 2.4, 5.0, 'opal_pink', 'opal_teal'),
    ((8.0, 8.6, 1.5), (4.0, 4.6, 12.5), 2.1, 4.5, 'opal_lilac', 'opal_pink'),
    ((18.2, 18.0, 1.0), (22.0, 22.0, 9.5), 1.9, 3.5, 'opal_teal', 'opal_lilac'),
]

# small shards around the foot: base, tip, radius, colour
SHARDS = [
    ((5.0, 12.0, 1.0), (3.0, 11.4, 6.2), 1.3, 'opal_teal'),
    ((17.2, 22.2, 0.8), (18.0, 24.2, 5.4), 1.3, 'opal_pink'),
    ((21.0, 9.6, 0.8), (23.0, 8.8, 5.8), 1.3, 'opal_lilac'),
    ((11.0, 5.6, 1.0), (10.2, 3.4, 6.4), 1.3, 'opal_teal'),
]


def _prism(v, base, tip, R, tip_len, twist=math.pi / 6, swell=0.8):
    """Six-sided pointed prism from base to tip. twist = pi/6 turns an edge toward +y (the
    game camera), 0 turns a flat face toward it.
    Returns (mask, axial coordinate t, length, facet light term, edge mask)."""
    p0 = np.array(base, float); p1 = np.array(tip, float)
    a = p1 - p0
    L = float(np.linalg.norm(a)); a /= L
    u = np.array([0.0, 1.0, 0.0]) - a[1] * a                     # +y, flattened onto the cross-section
    u /= np.linalg.norm(u)
    w = np.cross(a, u)
    dx, dy, dz = v.x - p0[0], v.y - p0[1], v.z - p0[2]
    t = dx * a[0] + dy * a[1] + dz * a[2]
    ru = dx * u[0] + dy * u[1] + dz * u[2]
    rw = dx * w[0] + dy * w[1] + dz * w[2]
    h = np.full(v.idx.shape, -1e9, np.float32)
    h2 = np.full(v.idx.shape, -1e9, np.float32)
    lit = np.zeros(v.idx.shape, np.float32)
    for k in range(6):
        ang = twist + k * math.pi / 3
        d = ru * math.cos(ang) + rw * math.sin(ang)
        n = u * math.cos(ang) + w * math.sin(ang)
        m = d > h
        h2 = np.where(m, h, np.maximum(h2, d))
        h = np.where(m, d, h)
        lit = np.where(m, float(n @ LIGHT), lit)
    shoulder = L - tip_len
    shaft = R * (swell + (1 - swell) * np.clip(t / max(shoulder, 1e-3), 0, 1))
    prof = np.where(t < shoulder, shaft, R * (L - t) / tip_len)
    mask = (h <= prof) & (t >= -3.0) & (t <= L)
    edge = mask & (h - h2 < 0.75) & (h > prof - 1.2)
    return mask, t, L, lit, edge


def _dirs(n, rng, jitter=0.2):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = np.pi * (1 + 5 ** 0.5) * i + rng.uniform(0, 6.28)
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    d += rng.normal(scale=jitter, size=d.shape)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _lump(v, c, r, n, rng, lo=0.82, hi=1.0):
    """Convex plane-cut rock lump. Returns (depth inside, facet normal per voxel)."""
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


def _facet(lit):
    """Shade step per facet. Opal is emissive, so the ramp sits low to keep its colour:
    facets toward the key light are near the base hue, the rest step down."""
    return np.where(lit > 0.45, FACET[0], np.where(lit > 0.0, FACET[1], FACET[2])).astype(np.int8)


def _spire(v, base, tip, R, tip_len, body, root, twist, edge_noise, swell=0.8, white=0.4):
    m, t, L, lit, edge = _prism(v, base, tip, R, tip_len, twist=twist, swell=swell)
    v.fill(m, body)
    v.shade[m] = _facet(lit)[m]
    if root:
        rooty = m & (t < L * 0.34 + (edge_noise - 0.5) * 5.0)
        v.paint(rooty, mat=root)
    v.paint(m & (t > L - tip_len), add=1)                      # the point catches more light
    if R >= 3.0:
        v.paint(edge & (lit > 0.0), add=1)                     # bright ridge between lit facets
    v.paint(m & (t > L - tip_len * white), mat='opal_white', shade=0)
    return m


def build(seed=5, emit=0.55):
    rng = np.random.default_rng(seed)
    v = Vox(*DIMS, name='opal_cluster')
    v.pivot = (12.8, 12.8)
    # A whole spire of full-strength opal burns out to white and loses its facets, so the
    # bodies glow a little less than the palette default; the tips keep the full glow.
    for name in ('opal_teal', 'opal_pink', 'opal_lilac'):
        v.mat(name, emit=emit)

    # --- deepstone base: a low faceted mound with a ledge toward the camera ---------------
    depth, nrm = _lump(v, (12.6, 12.6, 0.5), (9.6, 9.0, 6.4), 12, rng)
    for c, r, n in (((6.2, 10.6, 0.3), (5.2, 5.2, 4.4), 9), ((19.2, 14.6, 0.3), (5.2, 5.6, 4.2), 9),
                    ((15.2, 6.6, 0.3), (5.2, 4.6, 3.6), 9), ((9.2, 19.4, 0.3), (6.2, 5.0, 4.0), 9),
                    ((17.0, 19.8, 0.3), (5.4, 4.4, 3.2), 9)):
        d2, n2 = _lump(v, c, r, n, rng)
        m = d2 > depth
        depth = np.where(m, d2, depth); nrm[m] = n2[m]
    depth = depth + (v.noise(7, seed) - 0.5) * 1.0
    rock = depth > 0
    v.fill(rock, 'deepstone')
    s = np.full(v.idx.shape, -1, np.int8)
    s[nrm[..., 2] > 0.6] = 0
    s[(nrm[..., 2] <= 0.6) & (nrm @ LIGHT.astype(np.float32) < 0.1)] = -2
    v.shade[rock] = s[rock]
    v.paint(rock & (v.z < 1), add=-1)

    # --- spires ------------------------------------------------------------------------
    edge = v.noise(4, seed + 1)
    opal = np.zeros(v.idx.shape, bool)
    for i, (base, tip, R, tip_len, body, root) in enumerate(SPIRES):
        twist = math.pi / 6 + (0.0, 0.35, -0.3, 0.5, 0.2, -0.45, 0.3)[i % 7]
        opal |= _spire(v, base, tip, R, tip_len, body, root, twist, edge)
    for i, (base, tip, R, col) in enumerate(SHARDS):
        opal |= _spire(v, base, tip, R, 2.6, col, None, 0.7 * i, edge, swell=1.0, white=0.5)

    # crust: the rock right around each spire is stained darker, with a few opal chips
    grown = np.zeros_like(opal)
    for ax in (0, 1, 2):
        for sh in (-1, 1):
            grown |= np.roll(opal, sh, axis=ax)
    ring = grown & v.is_mat('deepstone')
    v.paint(ring, shade=-2)
    chips = v.m_exposed_top() & v.is_mat('deepstone') & (v.noise(2.5, seed + 2) > 0.8)
    v.paint(chips, mat='opal_lilac', shade=-1)

    # the light sits inside the tall spire, so it washes the floor and the neighbours'
    # inner faces rather than flattening the facets that face the camera
    v.light((13.0, 12.3, 10.0), (0.52, 0.82, 1.0), radius=32, power=1.0)
    return v
