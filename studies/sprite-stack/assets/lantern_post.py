"""Lantern post: a crooked timber with an iron bracket and a hanging lantern, lashed with
rope, a mossy stone at its foot. The bracket reaches along +x so the lantern hangs clear
of the post in the side view.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (12, 12, 32)     # x = bracket direction, y = depth, z = up
POST = ((4.7, 6.0, 0.0), (2.6, 6.7, 15.0), (4.0, 5.5, 30.6))   # foot, bend, top
LX, LY = 8, 5           # the lantern's centre column (voxel indices)


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
    v = Vox(*DIMS, name='lantern_post')
    v.pivot = (4.5, 6.0)
    v.mat('rope', rgb=(222, 200, 150))
    foot, bend, top = POST

    # ---- post ---------------------------------------------------------------------------
    post = v.m_capsule(foot, bend, 2.1, 1.7) | v.m_capsule(bend, top, 1.7, 1.5)
    post &= v.z < 31
    v.fill(post, 'wood')
    spine = np.where(v.z < bend[2], foot[0] + (bend[0] - foot[0]) * v.z / bend[2],
                     bend[0] + (top[0] - bend[0]) * (v.z - bend[2]) / (top[2] - bend[2]))
    v.paint(post & (v.x < spine - 0.4), shade=-1)                            # shaded back
    v.paint(post & (v.z < 3.5), shade=-2)                                    # damp foot
    v.paint(post & (v.z >= 30), mat='wood_light', shade=0)                   # sawn top
    v.paint(post & v.m_box((0, 0, 8), (99, 99, 9)) & (v.y > 6.5), shade=-2)    # axe notches
    v.paint(post & v.m_box((0, 0, 20), (99, 99, 21)) & (v.y > 6.0) & (v.x > spine), shade=-2)

    # ---- mossy stone and a pebble at the foot --------------------------------------------
    stone = _rock_mask(v, (7.0, 7.4, 2.0), (3.7, 3.5, 3.2), 3)
    v.fill(stone & ~post, 'stone')
    v.paint(stone & (v.z < 1.5), shade=-1)
    pebble = _rock_mask(v, (1.9, 3.6, 0.8), (1.9, 2.1, 1.7), 5, chips=2)
    v.fill(pebble & ~post, 'stone', shade=-1)
    nz = v.noise(3.0, seed=4)
    moss = v.is_mat('stone') & v.m_surface() & (v.z > 2.6 + 3.0 * (nz - 0.5))
    v.paint(moss, mat='moss')
    v.paint(v.is_mat('moss') & ~v.m_exposed_top(), shade=-1)
    v.paint(v.is_mat('moss') & v.m_exposed_top() & (nz > 0.55), mat='moss_light')
    v.paint(post & v.m_surface() & (v.z < 5.5 + 4.0 * (nz - 0.5)) & (v.y > 6.2), mat='moss', shade=-1)   # creeping up the foot

    # ---- iron bracket ---------------------------------------------------------------------
    v.box((3, 5, 27), (11, 7, 29), 'iron_dark')                              # arm
    v.box((10, 5, 26), (11, 7, 27), 'iron_dark', shade=-1)                   # turned-down tip
    v.capsule((3.6, 6.0, 23.4), (6.6, 6.0, 26.6), 0.8, 'iron_dark', shade=-1)   # gusset
    v.paint(v.is_mat('iron_dark') & (v.z >= 28), shade=1)

    # ---- rope lashings where the iron meets the wood ----------------------------------------
    wrap = v.m_capsule(foot, bend, 2.1 + 0.8, 1.7 + 0.8) | v.m_capsule(bend, top, 1.7 + 0.8, 1.5 + 0.8)
    for z0, z1 in ((13.0, 17.0), (24.0, 26.0)):                              # the splice at the bend, and under the arm
        ring = wrap & (v.z >= z0) & (v.z < z1)
        v.fill(ring & ~v.is_mat('iron_dark'), 'rope')
        v.paint(ring & v.is_mat('rope') & ((v.z - z0).astype(int) % 2 == 0), shade=-1)   # turns of the rope
    v.box((1, 7, 9), (2, 8, 13), 'rope', shade=-1)                           # loose end

    # ---- lantern --------------------------------------------------------------------------
    x0, y0 = LX - 2, LY - 2
    v.box((LX, LY, 25), (LX + 1, LY + 1, 27), 'iron_dark', shade=-2)         # chain
    v.box((LX - 1, LY - 1, 24), (LX + 2, LY + 2, 25), 'iron_dark', shade=0)  # cap
    v.box((x0, y0, 23), (x0 + 5, y0 + 5, 24), 'iron_dark', shade=-1)
    v.box((LX - 1, LY - 1, 19), (LX + 2, LY + 2, 23), 'lamp')                # flame core
    for cx in (x0, x0 + 4):
        for cy in (y0, y0 + 4):
            v.box((cx, cy, 19), (cx + 1, cy + 1, 23), 'iron_dark', shade=-2)   # cage bars
    v.box((x0, y0, 18), (x0 + 5, y0 + 5, 19), 'iron_dark', shade=-2)         # base
    v.box((LX - 1, LY - 1, 17), (LX + 2, LY + 2, 18), 'iron_dark', shade=-3)
    v.light((LX + 0.5, LY + 0.5, 21.0), (1.0, 0.72, 0.36), radius=34, power=1.3)
    return v
