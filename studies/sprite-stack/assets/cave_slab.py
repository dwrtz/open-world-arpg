"""Cave slab: a cut-away block of Wylden's side-view world as one big stack.

The world is fine material cells in the x-z plane. Here that cross-section is given real
depth (y) and sliced horizontally like any other stack, so the playable cave reads as a
diorama: the cut face shows the material strata and veins, the cave floors show depth,
and the whole thing can yaw for parallax. Props and characters are separate stacks.
"""
import numpy as np

from stack.voxel import Vox

K = 1.4                      # layout below is written on a 160 x 84 grid and scaled by K
X, Y, Z = int(160 * K), 38, int(84 * K)


def _cap2(x, z, p0, p1, r):
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    t = np.clip(((x - p0[0]) * dx + (z - p0[1]) * dz) / (dx * dx + dz * dz), 0, 1)
    return (x - (p0[0] + dx * t)) ** 2 + (z - (p0[1] + dz * t)) ** 2 <= r * r


def cave_mask(v, seed=3):
    """The carved cave as a 2D (x, z) shape, broadcast through depth."""
    x, z = v.x / K, v.z / K
    warp = (v.noise(18, seed)[:, :1, :] - 0.5) * 0.5 + (v.noise(6, seed + 9)[:, :1, :] - 0.5) * 0.2
    bump = np.rint((v.noise(9, seed + 11)[:1, :1, :] - 0.5) * 3.0) / K

    def ell(cx, cz, rx, rz):
        return ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 < 1 + warp

    alcove = ell(33, 52, 31, 12) & (z >= 42 + bump)
    main = ell(92, 41, 35, 15) & (z >= 28 + bump)
    ramp = (x > 52) & (x < 74) & (z >= np.maximum(28, 42 - (x - 56) * 0.9) + bump) & (z < 50)
    lower = ell(134, 21, 23, 13) & (z >= 10 + bump)
    drop = _cap2(x, z, (117, 33), (128, 21), 6.5)
    upper = (_cap2(x, z, (120, 62), (151, 61), 6.5) & (z >= 56 + bump)) | _cap2(x, z, (110, 52), (120, 60), 4.2)
    shaft = _cap2(x, z, (13, 56), (22, 90), 6.5 + warp * 3)
    return alcove | main | ramp | lower | drop | upper | shaft


def build(seed=3):
    v = Vox(X, Y, Z, name='cave_slab')
    x, y, z = v.x, v.y, v.z
    n_c = v.noise(24, seed + 2)[:, :1, :]
    surf = 77 * K + (v.noise(30, seed + 3)[:1, :1, :] - 0.5) * 10 + (v.noise(9, seed + 4)[:1, :, :] - 0.5) * 2
    solid = z < surf
    d1 = surf - 15 + (n_c - 0.5) * 11          # dirt above, stone below
    d2 = 30 * K + (n_c - 0.5) * 14             # stone above, deepstone below
    v.fill(solid, 'stone')
    v.fill(solid & (z >= d1), 'dirt')
    v.fill(solid & (z < d2), 'deepstone')
    # strata texture: a few large calm patches, not dither
    n8, n5, n11, n4 = v.noise(9, seed + 20), v.noise(6, seed + 21), v.noise(12, seed + 22), v.noise(4, seed + 23)
    v.paint(v.is_mat('dirt') & (n5 > 0.62), mat='dirt_dark')
    v.paint(v.is_mat('dirt', 'dirt_dark') & (n4 > 0.86), mat='stone_light')
    v.paint(v.is_mat('stone') & (n8 > 0.6), mat='stone_dark')
    v.paint(v.is_mat('stone', 'stone_dark') & (n11 > 0.68) & (x < 110 * K), mat='basalt')
    v.paint(v.is_mat('deepstone') & (n8 > 0.62), mat='slate')
    v.speckle(['stone', 'stone_dark', 'basalt', 'deepstone', 'slate', 'dirt', 'dirt_dark'], 0.14, step=-1, scale=5, seed=seed + 30)
    # veins and deposits: sparse accents that only faintly glow
    v.mat('vein_opal', rgb=(104, 214, 204), emit=0.4, spec=0.8, gloss=36)
    v.mat('vein_pink', rgb=(232, 150, 204), emit=0.35, spec=0.8, gloss=36)
    v.mat('vein_ember', rgb=(240, 122, 56), emit=0.7)
    rock = v.is_mat('stone', 'stone_dark', 'basalt')
    r1, r2, r3 = v.noise(11, seed + 40), v.noise(4.5, seed + 41), v.noise(10, seed + 42)
    v.paint(rock & (np.abs(r1 - 0.5) < 0.016) & (x > 84 * K), mat='ore_copper')
    v.paint(rock & (r2 > 0.84) & (x > 100 * K) & (z > 48 * K), mat='ore_gold')
    v.paint(rock & (np.abs(r3 - 0.47) < 0.012) & (x < 60 * K) & (z < 48 * K), mat='vein_ember')
    v.paint(v.is_mat('dirt', 'dirt_dark', 'stone') & (np.abs(z - d1) < 1.4) & (v.noise(12, seed + 43) > 0.6), mat='coal')
    deep = v.is_mat('deepstone', 'slate')
    v.paint(deep & (np.abs(r3 - 0.5) < 0.009) & (x > 84 * K), mat='vein_opal')
    v.paint(deep & (np.abs(r1 - 0.54) < 0.006) & (x > 104 * K), mat='vein_pink')
    v.fill(solid & (z >= surf - 2), 'grass')
    v.paint(v.is_mat('grass') & (z < surf - 1) & (n4 > 0.5), mat='dirt')

    # a sealed geode in the deep rock: something to dig toward
    gq = ((x / K - 38) / 8.5) ** 2 + ((z / K - 15.5) / 5.6) ** 2 + (v.noise(5, seed + 80)[:, :1, :] - 0.5) * 0.5
    v.mat('geode', rgb=(150, 126, 232), emit=0.45, spec=0.9, gloss=40)
    ring = (gq >= 1.0) & (gq < 1.42) & (y > 14)
    v.paint(ring, mat='geode')
    v.paint(ring & (v.noise(3, seed + 81) > 0.7), mat='opal_lilac')
    v.carve((gq < 1.0) & (y > 17))
    v.paint((gq < 1.0) & (y <= 17), mat='deepstone', shade=-3)       # dark back of the cavity
    for gx_, gz_, gl_ in ((33, 12.5, 4), (38, 11.5, 5), (43, 13, 4), (36, 19.5, -4), (41, 19, -3)):
        v.fill(v.m_capsule((gx_ * K, 24, gz_ * K), (gx_ * K + 0.6, 26, gz_ * K + gl_), 1.3, r1=0.4), 'geode', shade=1)
    v.light((38 * K, 28, 15.5 * K), (0.62, 0.52, 1.0), radius=17, power=0.55)

    # carve the cave, open toward the viewer
    cave2d = cave_mask(v, seed)
    yb = 9 + (v.noise(9, seed + 5)[:, :1, :] - 0.5) * 6
    v.carve(cave2d & (y >= yb))
    back = cave2d & (y < yb + 3)                     # the wall behind the cave recedes: dark and plain
    v.paint(back & v.is_mat('ore_copper', 'ore_gold', 'coal', 'stone_light'), mat='stone_dark')
    v.paint(back & v.is_mat('vein_opal', 'vein_pink'), mat='deepstone')
    v.paint(back & v.is_mat('vein_ember'), mat='basalt')
    v.paint(back, shade=-2)
    v.paint(back & (v.noise(6, seed + 6) > 0.6), shade=-3)

    def column(xi, yi, z0, up=True):
        """First solid voxel above (or below) z0 in a column."""
        k = int(z0)
        while 0 < k < Z - 1 and not v.idx[k, int(yi), int(xi)]:
            k += 1 if up else -1
        return k

    # stalactites and stalagmites (layout units, scaled)
    for (sx, sy, z0, L, r) in ((70, 24, 44, 8, 2.4), (84, 16, 44, 6, 2.0), (101, 28, 44, 9, 2.6), (112, 18, 42, 5, 1.8),
                               (30, 20, 54, 6, 2.2), (46, 30, 52, 5, 1.9), (128, 24, 22, 7, 2.2), (142, 16, 22, 5, 1.8)):
        sx = int(sx * K)
        zc = column(sx, sy, z0 * K, up=True)
        m = v.mats[v.idx[zc, sy, sx]]['name'] if v.idx[zc, sy, sx] else 'stone'
        v.fill(v.m_capsule((sx, sy, zc + 1), (sx + 0.4, sy, zc - L * K), r * 1.25, r1=0.6), m, shade=-1)
    for (sx, sy, z0, L, r) in ((78, 14, 36, 4, 2.0), (106, 30, 36, 5, 2.2), (146, 28, 18, 5, 2.0)):
        sx = int(sx * K)
        zf = column(sx, sy, z0 * K, up=False)
        m = v.mats[v.idx[zf, sy, sx]]['name'] if v.idx[zf, sy, sx] else 'stone'
        v.fill(v.m_capsule((sx, sy, zf - 1), (sx, sy, zf + L * K), r * 1.25, r1=0.6), m)

    # roots of something much larger, coming down through the soil
    for pts, r0, r1_, mat in (
        (((92, 24, 75), (89, 22, 64), (93, 20, 55), (90, 21, 47)), 3.2, 1.0, 'bark'),
        (((64, 28, 74), (67, 27, 66), (63, 26, 58)), 2.8, 0.9, 'bark'),
        (((40, 9, 73), (58, 10, 62), (84, 11, 52), (112, 10, 47), (136, 11, 38)), 4.0, 2.0, 'bark_dark'),
        (((120, 30, 74), (124, 28, 68)), 2.4, 1.2, 'bark'),
    ):
        pts = [(px_ * K, py_, pz_ * K) for (px_, py_, pz_) in pts]
        n = len(pts) - 1
        for i in range(n):
            ra = r0 + (r1_ - r0) * i / n; rb = r0 + (r1_ - r0) * (i + 1) / n
            v.fill(v.m_capsule(pts[i], pts[i + 1], ra, r1=rb), mat)
    v.speckle(['bark', 'bark_dark'], 0.25, step=1, scale=2.5, seed=seed + 50)

    # mine timbering at the ramp
    tx = int(66 * K)
    for py in (13, 33):
        zf = column(tx, py, 40 * K, up=False); zc = column(tx, py, 40 * K, up=True)
        v.box((tx - 1, py - 1, zf + 1), (tx + 2, py + 2, zc + 1), 'wood_dark')
    zc = min(column(tx, 13, 40 * K), column(tx, 33, 40 * K))
    v.box((tx - 2, 10, zc - 3), (tx + 3, 37, zc), 'wood')
    v.paint(v.is_mat('wood') & ((np.abs(y - 13.5) < 1.6) | (np.abs(y - 33.5) < 1.6)), mat='iron_dark')

    # a ladder up the shaft to the surface
    lx_ = int(19 * K)
    for ly_ in (15, 21):
        v.add(v.m_box((lx_, ly_, 56 * K), (lx_ + 1, ly_ + 1, 80 * K)), 'wood')
    for zz in range(int(57 * K), int(80 * K), 3):
        v.add(v.m_box((lx_, 15, zz), (lx_ + 1, 22, zz + 1)), 'wood_light')

    # growth: moss in the upper caves, grass and flowers on the surface
    tops = v.m_exposed_top(2)
    n6 = v.noise(6, seed + 60)
    v.paint(tops & (z > 26 * K) & (z < 66 * K) & (x < 116 * K) & (y > 13) & (n6 > 0.5) & ~v.is_mat('wood', 'wood_dark', 'iron_dark', 'bark', 'bark_dark'), mat='moss')
    v.paint(v.is_mat('moss') & (v.noise(3, seed + 61) > 0.68), mat='moss_light')
    rng = np.random.default_rng(seed + 70)
    for _ in range(110):
        gx, gy = int(rng.integers(1, X - 1)), int(rng.integers(1, Y - 1))
        k = Z - 2
        while k > 60 * K and not v.idx[k, gy, gx]:
            k -= 1
        if v.idx[k, gy, gx] and v.mats[v.idx[k, gy, gx]]['name'] in ('grass', 'dirt') and k + 2 < Z:
            kind = rng.random()
            if kind < 0.72:
                v.box((gx, gy, k + 1), (gx + 1, gy + 1, k + 2 + int(rng.integers(0, 2))), 'grass', shade=1)
            elif kind < 0.88:
                v.box((gx, gy, k + 1), (gx + 1, gy + 1, k + 2), 'fern')
                v.box((gx, gy, k + 2), (gx + 1, gy + 1, k + 3), 'petal')
            elif kind < 0.93:
                v.box((gx, gy, k + 1), (gx + 2, gy + 2, k + 2), 'stone_light')
    return v


def floor_at(v, xi, yi, z_hint):
    """Height a prop should stand at: one above the first solid voxel below z_hint."""
    k = int(z_hint)
    while k > 0 and not v.idx[k, int(yi), int(xi)]:
        k -= 1
    return k + 1
