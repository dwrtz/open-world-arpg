"""Moss golem: a hulking pile of basalt boulders from the Moss & Ember caves. Faces +x.

Every body part is a chipped boulder; the seams where boulders meet are darkened, and the
ones near the chest glow with the ember core's heat. Built on the y < centre side and
mirrored, then the moss is grown asymmetrically on top.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (28, 26, 40)   # x = facing, y = shoulders, z = up
CY = 13.0
OX = 0.5              # shifts the whole figure along x inside the volume
CORE = (19.6 + OX, CY, 22.5)


def _rock_mask(v, c, r, seed, chips=5, rough=0.10):
    """A boulder: an ellipsoid with a noise swell and a few flat chips knocked off."""
    rng = np.random.default_rng(seed)
    dx = (v.x - c[0]) / r[0]; dy = (v.y - c[1]) / r[1]; dz = (v.z - c[2]) / r[2]
    swell = 1.0 + rough * 2.0 * (v.noise(4.5, seed) - 0.5)
    m = (dx * dx + dy * dy + dz * dz) <= swell * swell
    for _ in range(chips):
        a = rng.normal(size=3)
        a /= np.linalg.norm(a)
        m &= (dx * a[0] + dy * a[1] + dz * a[2]) < rng.uniform(0.62, 0.86)
    return m


def build():
    v = Vox(*DIMS, name='moss_golem')
    v.pivot = (12.0 + OX, CY)
    lab = np.zeros(v.idx.shape, np.int16)      # which boulder owns each voxel
    ids = {}

    def rock(name, c, r, seed, shade=0, chips=5):
        c = (c[0] + OX, c[1], c[2])
        m = _rock_mask(v, c, r, seed, chips)
        ids[name] = len(ids) + 1
        v.fill(m, 'basalt', shade)
        lab[m] = ids[name]
        t = (v.z - c[2]) / r[2]
        v.paint(m & (t > 0.4), add=1)          # lit crown
        v.paint(m & (t < -0.45), add=-1)       # dark underside
        return m

    # ---- boulders (far side and centre line; mirrored below) ---------------------------
    rock('foot', (10.5, 8.6, 2.6), (5.0, 3.6, 3.4), 1, shade=-2)
    rock('shin', (10.5, 8.8, 8.0), (3.6, 3.4, 4.2), 2, shade=-1)
    rock('pelvis', (11.5, CY, 13.5), (5.5, 7.0, 4.4), 3, shade=-2)
    rock('hump', (7.2, CY, 26.5), (6.2, 9.0, 7.0), 4)
    chest = rock('chest', (14.0, CY, 23.0), (8.5, 10.0, 8.0), 5)
    rock('arm', (15.5, 3.6, 21.5), (3.4, 3.2, 5.0), 6)
    rock('forearm', (18.5, 3.8, 14.5), (3.6, 3.4, 4.6), 7)
    rock('fist', (21.5, 4.0, 7.5), (5.0, 4.0, 5.0), 8, shade=1)
    rock('shoulder', (12.5, 4.6, 28.0), (6.4, 5.0, 5.8), 9, shade=1)
    head = rock('head', (18.5, CY, 32.6), (5.2, 5.6, 4.8), 10)
    rock('jaw', (21.0, CY, 29.4), (3.8, 4.6, 2.6), 11, shade=-1, chips=2)
    rock('brow', (20.4, CY, 36.4), (3.6, 5.2, 1.9), 12, chips=2)

    # ---- chest cavity and ember core ---------------------------------------------------
    hole = v.m_ellipsoid((23.0 + OX, CY, 22.5), (5.2, 3.8, 4.2))
    v.carve(hole & chest)
    v.paint(v.m_ellipsoid((23.0 + OX, CY, 22.5), (6.3, 4.9, 5.3)) & chest, shade=-2)   # scorched walls
    v.ellipsoid(CORE, (2.2, 2.6, 2.9), 'ember')
    v.ellipsoid(CORE, (1.3, 1.6, 1.8), 'ember_hot')

    # ---- eyes on the front-side corners of the head ------------------------------------
    eye = v.m_box((20.3 + OX, 8.0, 32.8), (25.0 + OX, 10.0, 34.8)) & head & v.m_surface()
    v.paint(eye, mat='ember_hot')

    v.mirror_y()
    Y = DIMS[1]
    lab[:, Y - Y // 2:, :] = lab[:, :Y // 2, :][:, ::-1, :]

    # one extra slab stacked on the near shoulder, for an uneven outline
    rock('slab', (10.5, 21.6, 33.4), (3.8, 3.4, 2.6), 13, chips=3)

    # ---- moss over the shoulders, back and head ----------------------------------------
    nz = v.noise(5.0, seed=11)
    line = np.full(v.idx.shape, 99.0, np.float32)
    for name, z0 in (('shoulder', 31.6), ('slab', 33.6), ('hump', 30.0), ('chest', 29.5)):
        line[lab == ids[name]] = z0
    line[((lab == ids['head']) | (lab == ids['brow'])) & (v.x < 20.0 + OX)] = 36.0   # the brow stays bare
    moss = v.m_surface() & v.is_mat('basalt') & (v.z > line + 4.0 * (nz - 0.5))
    v.paint(moss, mat='moss', shade=0)
    for thr in (0.48, 0.6):                                           # fluffy clumps, up to two voxels deep
        m = v.is_mat('moss')
        up = np.zeros_like(m); up[1:] = m[:-1]
        v.add(up & (nz > thr), 'moss')
    v.paint(v.is_mat('moss') & ~v.m_exposed_top(), shade=-1)          # shaded sides and under-layer
    v.paint(v.is_mat('moss') & v.m_exposed_top() & (nz > 0.56), mat='moss_light')
    strand = v.noise(2.5, seed=5)[:1]                                 # one value per column
    for i in range(5):                                                # tendrils creeping down the rock
        m = v.is_mat('moss', 'moss_light')
        above = np.zeros_like(m); above[:-1] = m[1:]
        v.paint(above & v.is_mat('basalt') & v.m_surface() & (strand > 0.56 + 0.05 * i), mat='moss', shade=-1)

    # ---- seams between boulders: dark crevices, glowing near the core ------------------
    seam = np.zeros(v.idx.shape, bool)
    for ax in range(3):
        for sh in (1, -1):
            other = np.roll(lab, sh, axis=ax)
            seam |= (other != lab) & (other > 0)
    seam &= (lab > 0) & v.is_mat('basalt') & v.m_surface()
    v.paint(seam, shade=-3)
    d = np.sqrt((v.x - CORE[0]) ** 2 + (v.y - CORE[1]) ** 2 + (v.z - CORE[2]) ** 2)
    v.paint(seam & (d < 10.5), mat='ember_dim', shade=0)
    v.paint(seam & (d < 6.0), mat='ember', shade=0)

    v.light((24.0 + OX, CY, 22.5), (1.0, 0.52, 0.2), radius=30, power=1.4)
    return v
