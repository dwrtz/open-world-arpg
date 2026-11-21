"""Mine cart: a flared wooden tub with iron fittings on a short piece of track, heaped with
ore. It travels along x; the near (+y) side carries the showiest ore.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (28, 18, 20)    # x = along the track, y = across, z = up
CX, CY = 14.0, 9.0
RAIL_TOP = 3.0
AXLE_Z = RAIL_TOP + 3.0
TUB_Z0, TUB_Z1 = 8.0, 16.0

# ore chunks: centre, radii, shade, ore material (None = bare stone)
CHUNKS = (
    ((5.8, 9.0, 15.8), (2.4, 2.6, 2.2), -2, None),
    ((8.0, 6.6, 16.0), (3.2, 2.8, 2.6), -2, None),
    ((13.0, 6.2, 16.4), (3.0, 2.6, 2.8), -1, 'ore_copper'),
    ((18.6, 6.8, 16.0), (3.4, 2.8, 2.6), -2, None),
    ((22.0, 9.4, 15.8), (2.4, 2.8, 2.2), -2, None),
    ((7.6, 11.6, 16.0), (3.0, 2.8, 2.5), -1, 'ore_copper'),
    ((18.2, 11.8, 16.4), (3.3, 3.0, 2.8), -1, 'ore_copper'),
    ((10.0, 9.0, 17.3), (2.7, 2.5, 2.5), -2, None),
    ((15.6, 8.8, 17.5), (2.9, 2.7, 2.5), -1, 'ore_gold'),
    ((12.6, 11.8, 17.0), (3.5, 3.2, 3.0), -1, 'ore_gold'),
)


def _rock_mask(v, c, r, seed, chips=4, rough=0.10):
    """A chipped lump: an ellipsoid with a noise swell and a few flat facets."""
    rng = np.random.default_rng(seed)
    dx = (v.x - c[0]) / r[0]; dy = (v.y - c[1]) / r[1]; dz = (v.z - c[2]) / r[2]
    swell = 1.0 + rough * 2.0 * (v.noise(3.5, seed) - 0.5)
    m = (dx * dx + dy * dy + dz * dz) <= swell * swell
    for _ in range(chips):
        a = rng.normal(size=3)
        a /= np.linalg.norm(a)
        m &= (dx * a[0] + dy * a[1] + dz * a[2]) < rng.uniform(0.62, 0.86)
    return m


def build():
    v = Vox(*DIMS, name='minecart')
    v.pivot = (CX, CY)

    # ---- track: three sleepers, two rails -------------------------------------------------
    for x0, y0, y1, sh in ((2, 1, 17, 0), (12, 0, 17, -1), (23, 1, 18, 0)):
        v.rbox((x0, y0, 0), (x0 + 3.5, y1, 2), 'wood_dark', r=0.7, shade=sh)
    v.paint(v.is_mat('wood_dark') & (v.z > 1), add=1)
    for y0 in (2, 14):
        v.box((0, y0, 1), (28, y0 + 2, RAIL_TOP), 'iron', shade=-2)             # notched into the sleepers
        v.paint(v.m_box((0, y0, 2), (28, y0 + 2, RAIL_TOP)), shade=0)          # polished running surface

    # ---- running gear -------------------------------------------------------------------
    for x in (8.0, 20.0):
        v.cyl((x, AXLE_Z), 1.0, 2, 16, 'iron_dark', axis='y', shade=-2)        # axle
        for y0, face in ((2, 2), (14, 15)):
            v.cyl((x, AXLE_Z), 3.0, y0, y0 + 2, 'iron_dark', axis='y', shade=-1)
            outer = v.m_box((0, face, 0), (99, face + 1, 99))
            v.paint(outer & v.m_cyl((x, AXLE_Z), 2.0, y0, y0 + 2, axis='y'), shade=-3)          # dished centre
            v.paint(outer & v.m_cyl((x, AXLE_Z), 1.0, y0, y0 + 2, axis='y'), mat='iron', shade=1)   # hub
    v.box((5, 5, 6), (23, 13, TUB_Z0 + 1), 'wood_dark', shade=-1)              # chassis beam

    # ---- tub: flares outward toward the rim ---------------------------------------------
    t = np.clip((v.z - TUB_Z0) / (TUB_Z1 - TUB_Z0), 0, 1)
    hx = 7.6 + 3.4 * t; hy = 4.0 + 3.0 * t
    ax = abs(v.x - CX); ay = abs(v.y - CY)
    band = (v.z >= TUB_Z0) & (v.z < TUB_Z1)
    tub = (ax < hx) & (ay < hy) & band
    inner = (ax < hx - 1.6) & (ay < hy - 1.6) & (v.z >= TUB_Z0 + 2)
    v.fill(tub, 'wood')
    v.carve(inner & band)
    plank = np.floor((v.z - TUB_Z0) / 2.0).astype(int)
    v.paint(tub & (plank % 2 == 1), shade=1)                                   # alternating planks
    v.paint(tub & (v.z >= TUB_Z1 - 1), mat='iron_dark', shade=1)               # rim band
    corner = (ax > hx - 1.2) & (ay > hy - 1.2)
    v.paint(tub & corner & v.is_mat('wood'), mat='iron_dark', shade=0)         # corner straps
    for x0, x1, x2 in ((5, 3, 1), (23, 25, 27)):                               # drawbars and buffers
        v.box((min(x0, x1), 8, 7), (max(x0, x1), 10, 9), 'iron_dark', shade=-1)
        v.box((min(x1, x2), 7, 6), (max(x1, x2), 11, 9), 'iron_dark')

    # ---- ore heap -------------------------------------------------------------------------
    lab = np.zeros(v.idx.shape, np.int16)
    load = (ax < hx - 1.6) & (ay < hy - 1.6) & (v.z >= TUB_Z0 + 2) & (v.z < TUB_Z1 - 1)
    v.fill(load, 'stone', shade=-2)
    lab[load] = 99
    reach = ((ax < 9.6) & (ay < 5.6)) | (v.z >= TUB_Z1)                         # may heap over the rim, not through the walls
    reach &= (ax < 11.2) & (ay < 7.2)
    for i, (c, r, sh, ore) in enumerate(CHUNKS):
        m = _rock_mask(v, c, r, 40 + i) & reach & (v.z >= TUB_Z1 - 3) & ~v.is_mat('wood', 'iron', 'iron_dark')
        v.fill(m, 'stone', sh)
        lab[m] = i + 1
        v.paint(m & (v.z > c[2] + 0.4 * r[2]), add=1)
        if ore:                                                                # one broad seam of ore through the lump
            a = np.random.default_rng(70 + i).normal(size=3) * 0.6 + np.array([0.0, 0.7, 1.0])
            a /= np.linalg.norm(a)
            side = ((v.x - c[0]) * a[0] + (v.y - c[1]) * a[1] + (v.z - c[2]) * a[2]) / max(r)
            v.paint(m & (side > 0.05) & (side < 0.62), mat=ore, shade=0)
            v.paint(m & (side > 0.05) & (side < 0.3) & v.is_mat(ore), shade=-1)
    seam = np.zeros(v.idx.shape, bool)
    for axis in range(3):
        for s in (1, -1):
            other = np.roll(lab, s, axis=axis)
            seam |= (other != lab) & (other > 0)
    v.paint(seam & (lab > 0) & v.is_mat('stone'), shade=-3)
    # a few opal bits caught in the load, each standing on whatever tops its column
    for x, y in ((10, 13), (21, 11), (16, 6)):
        z = int(np.nonzero(v.occ[:, y, x])[0].max())
        v.box((x, y, z), (x + 1, y + 1, z + 2), 'opal_teal')
    return v
