"""Specialist altar of the Opal Deep: a stepped deepstone plinth cut with glowing inlay
channels, two prongs cradling a large faceted opal shard that floats above the socket,
and crystal growths creeping in around the base.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (30, 30, 40)
CX, CY = 15.0, 15.0
STEPS = ((13.5, 0, 3), (11.0, 3, 6), (8.5, 6, 11), (6.5, 11, 14))     # half-width, z0, z1
INLAY = 'opal_inlay'          # opal_teal run thin in a carved channel: glows, hardly blooms
STONE = ('deepstone', 'slate')

GLYPH = ('..##..',      # the sigil on the front of the plinth
         '.#..#.',
         '#.##.#',
         '.#..#.',
         '..##..')


def _oct(v, R, k=1.42):
    ax, ay = np.abs(v.x - CX), np.abs(v.y - CY)
    return (np.maximum(ax, ay) <= R) & (ax + ay <= k * R)


def _plinth(v):
    for (R, z0, z1) in STEPS:
        step = _oct(v, R) & (v.z >= z0) & (v.z < z1)
        v.fill(step, 'deepstone')
        v.paint(step & (v.z >= z1 - 1), shade=1)                              # tread
        v.paint(step & (v.z >= z1 - 1) & ~_oct(v, R - 1), shade=2)            # worn, lit rim
        v.paint(step & (v.z < z0 + 1), shade=-1)                              # shadowed foot
    # wear: darker stains and a couple of broken corners
    n = v.noise(5.0, seed=2)
    v.paint(v.is_mat('deepstone') & (n > 0.62), add=-1)
    v.carve(v.m_ellipsoid((3.0, 8.5, 3.2), (2.6, 3.0, 2.2)))
    v.carve(v.m_ellipsoid((22.5, 25.0, 6.3), (1.8, 1.8, 1.6)))
    v.add(v.m_ellipsoid((1.8, 6.0, 0.6), (1.4, 1.3, 1.1)), 'deepstone', shade=-1)     # the fallen chip
    # socket in the top
    v.carve(v.m_cyl((CX, CY), 3.6, 13, 14))
    v.paint(v.m_cyl((CX, CY), 3.6, 12, 13), mat='opal_teal')
    v.paint(v.m_cyl((CX, CY), 1.6, 12, 13), mat='opal_white')


def _channels(v):
    surf = v.m_surface() & v.is_mat(*STONE)
    ax, ay = np.abs(v.x - CX), np.abs(v.y - CY)
    # four radial channels, two voxels wide, running from the socket down every step
    v.paint(surf & ((ax < 1) | (ay < 1)) & (v.z >= 1), mat=INLAY)
    # a dashed band around the tall step
    R = STEPS[2][0]
    band = surf & (v.z >= 8) & (v.z < 9) & ~_oct(v, R - 1)
    along = np.where(ax > ay, v.y, v.x)
    v.paint(band & (np.floor(along / 2.0) % 2 == 0) & (np.maximum(ax, ay) > R - 1), mat=INLAY)
    # the sigil replaces the channel on the front face of the tall step
    yf = int(CY + R)                                    # y index of the front face
    face = v.m_box((CX - 5, yf, 6), (CX + 5, yf + 1, 11))
    v.paint(face, mat='deepstone', shade=-1)
    for r, row in enumerate(GLYPH):
        for c, ch in enumerate(row):
            if ch == '#':
                v.paint(v.m_box((CX - 3 + c, yf, 10 - r), (CX - 2 + c, yf + 1, 11 - r)), mat=INLAY)
    v.paint(v.m_box((CX - 1, yf, 8), (CX + 1, yf + 1, 9)), mat='opal_pink')


def _prong(v, sx):
    """A stone horn curving in toward the shard; sx = -1 / +1 side."""
    pts = ((11.0, 2.0, 2.6), (12.2, 9.5, 2.3), (10.8, 16.5, 1.8), (7.8, 22.0, 0.9))   # |dx|, z, radius
    horn = np.zeros(v.idx.shape, bool)
    for (a, b) in zip(pts[:-1], pts[1:]):
        horn |= v.m_capsule((CX + sx * a[0], CY, a[1]), (CX + sx * b[0], CY, b[1]), a[2], r1=b[2])
    horn &= (v.z >= 3)
    v.fill(horn, 'slate')
    v.paint(horn & (v.z < 6), shade=-1)
    v.paint(horn & (v.z >= 15) & (v.z < 19), shade=1)
    v.paint(horn & (v.z >= 10) & (v.z < 11), mat=INLAY)                     # inlaid ring
    v.paint(horn & (v.z >= 19), mat='opal_pink')                            # glowing claw tip
    v.paint(horn & (v.z >= 21.5), mat='opal_white')


def _shard(v, c, R, lo, hi, flip=False, mono=None):
    """Faceted bipyramid: widest at c, tips `lo` below and `hi` above. The four broad
    facets alternate opal tones (crown: teal / pink, pavilion: lilac / teal) with a pale
    glint set in each crown facet and a pale tip. mono=(crown, pavilion) for splinters
    too small to carry facets."""
    cx, cy, cz = c
    dz = v.z - cz
    t = np.where(dz >= 0, 1 - dz / hi, 1 + dz / lo)
    rr = R * np.clip(t, 0, 1)
    ax, ay = np.abs(v.x - cx), np.abs(v.y - cy)
    m = (ax + ay <= rr) & (np.maximum(ax, ay) <= rr * 0.8) & (t > 0.02)
    odd = ((v.x > cx) ^ (v.y > cy)) ^ flip                                  # alternate quadrants
    upper = dz >= 0
    if mono:
        v.fill(m & upper, mono[0])
        v.fill(m & ~upper, mono[1])
    else:
        v.fill(m & upper & odd, 'opal_pink')
        v.fill(m & upper & ~odd, 'opal_teal')
        v.fill(m & ~upper & odd, 'opal_teal')
        v.fill(m & ~upper & ~odd, 'opal_lilac')
        # a glint in the middle of each crown facet, and a second colour low on the pavilion
        glint = m & v.m_surface() & (ax - ay > -0.5) & (ax - ay < 1.5) & (dz >= hi * 0.26) & (dz < hi * 0.45)
        v.paint(glint, mat='opal_white')
        v.paint(m & ~upper & odd & (t < 0.62), mat='opal_pink')
    v.paint(m & upper & (t < 0.2), mat='opal_white')                        # crown tip
    v.paint(m & ~upper & (t < 0.4), add=-1)                                 # deeper colour toward the lower tip
    return m


def _crystal(v, base, tip, r, mat, tipmat=None):
    m = v.m_capsule(base, tip, r, r1=0.45) & ~v.occ
    v.fill(m, mat)
    L = tip[2] - base[2]
    v.paint(m & (v.z < base[2] + L * 0.3), shade=-1)
    v.paint(m & (v.z > base[2] + L * 0.6), shade=1)
    v.paint(m & (v.z > tip[2] - 1.2), mat=tipmat or 'opal_white')


def build(lit=True):
    v = Vox(*DIMS, name='altar')
    v.pivot = (CX, CY)
    # the opal materials are the shared ones, run a little cooler so the facet colours
    # survive the glow instead of blowing out to white
    for name, e in (('opal_teal', 1.05), ('opal_pink', 1.05), ('opal_lilac', 1.05), ('opal_white', 0.85)):
        v.mat(name, emit=e)
    v.mat(INLAY, rgb=(86, 214, 200), emit=0.8, spec=0.6, gloss=30)
    _plinth(v)
    _channels(v)
    _prong(v, -1)
    _prong(v, +1)

    # the shard, and two splinters drifting around it
    _shard(v, (CX, CY, 28.5), 6.6, 12.5, 11.0)
    _shard(v, (6.5, 20.5, 31.5), 2.4, 3.8, 3.2, mono=('opal_lilac', 'opal_teal'))
    _shard(v, (23.5, 9.5, 26.0), 2.0, 3.2, 2.8, mono=('opal_pink', 'opal_lilac'))

    # crystal growths at the corners (front-left is the big one)
    _crystal(v, (4.4, 25.6, 0), (3.2, 27.2, 10.0), 1.9, 'opal_teal')
    _crystal(v, (7.4, 27.4, 0), (9.2, 28.8, 6.5), 1.5, 'opal_lilac')
    _crystal(v, (2.4, 22.6, 0), (1.2, 21.4, 5.5), 1.3, 'opal_pink')
    _crystal(v, (25.6, 26.4, 0), (26.8, 27.8, 7.0), 1.6, 'opal_pink')
    _crystal(v, (27.8, 23.6, 0), (28.8, 22.4, 4.5), 1.2, 'opal_teal')
    _crystal(v, (26.2, 4.0, 0), (27.4, 2.6, 8.5), 1.7, 'opal_lilac')
    _crystal(v, (23.2, 2.4, 0), (22.0, 1.2, 5.0), 1.3, 'opal_teal')
    _crystal(v, (20.8, 23.2, 6), (21.6, 24.4, 10.5), 1.1, 'opal_teal')       # one has taken root on a step

    if lit:
        v.light((CX, CY, 16.5), (0.45, 0.95, 0.90), radius=24, power=0.55)   # teal, under the shard
        v.light((CX, 22.0, 31.0), (1.0, 0.62, 0.86), radius=28, power=0.5)   # pink, in front of it
    return v
