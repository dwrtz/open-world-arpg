"""Anvil: a horned iron anvil (horn toward +x) on a tree-stump block, a smith's hammer
leaning against the bark and a glowing ingot waiting on the face.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (24, 18, 20)
SX, SY = 10.5, 8.0           # stump centre
AY = 8.0                     # anvil centreline (y)
TOP = 7                      # stump height = underside of the anvil feet


def _stump(v):
    dx, dy = v.x - SX, v.y - SY
    th = np.arctan2(dy, dx)
    rad = np.sqrt((dx / 8.3) ** 2 + (dy / 7.5) ** 2)                 # 1.0 at the nominal rim
    wob = 1.0 + 0.045 * np.sin(3 * th + 0.8) + 0.03 * np.sin(7 * th + 2.0)
    # root lobes: the foot of the trunk swells out at a few angles
    lobes = np.maximum(0, np.cos(th - 2.5)) ** 6 + np.maximum(0, np.cos(th + 0.5)) ** 6 + 0.8 * np.maximum(0, np.cos(th - 0.9)) ** 8
    flare = 1.0 + (0.05 + 0.20 * lobes) * np.clip((3.2 - v.z) / 3.2, 0, 1)
    trunk = (rad <= wob * flare) & (v.z < TOP)
    v.fill(trunk, 'bark')
    # bark: vertical ridges and furrows around the trunk
    cell = np.floor((th + np.pi) / (2 * np.pi) * 20).astype(int)
    rng = np.random.default_rng(7).random(21)
    side = trunk & (rad > wob * flare - 0.2)
    v.paint(side & (rng[cell] < 0.36), mat='bark_dark')
    v.paint(side & (rng[cell] > 0.78), shade=1)
    v.paint(trunk & (v.z < 1), add=-1)
    # sawn top: bark rim, pale sapwood, growth rings, darker heart
    top = trunk & (v.z >= TOP - 1)
    rr = rad / wob
    inner = top & (rr < 0.87)
    v.paint(inner, mat='heartwood')
    v.paint(inner & (rr > 0.52) & (rr < 0.68), mat='wood_light', shade=-1)   # one bold growth ring
    v.paint(inner & (rr < 0.30), mat='wood_light', shade=-1)
    # a split in the end grain, running out to the bark at the front
    v.paint(top & v.m_capsule((SX - 3.5, SY + 4.2, TOP - 0.5), (SX - 5.6, SY + 6.6, TOP - 0.5), 0.6), mat='wood_dark')
    return trunk


def _anvil(v):
    I = 'iron_dark'
    z = TOP
    # feet, stepping in to the waist and back out to the body
    feet = v.m_rbox((4.5, AY - 4.5, z - 3), (16.5, AY + 4.5, z + 2), 1.5) & (v.z >= z)
    v.fill(feet, I)
    v.box((6.0, AY - 3.5, z + 2), (15.0, AY + 3.5, z + 3), I)
    v.box((7.0, AY - 2.5, z + 3), (14.0, AY + 2.5, z + 5), I, shade=-1)
    v.box((6.0, AY - 3.0, z + 5), (15.0, AY + 3.0, z + 6), I)
    # body with heel (-x) and face
    v.box((3.5, AY - 3.0, z + 6), (16.0, AY + 3.0, z + 11), I)
    v.carve(v.m_box((0, 0, z + 6), (6.0, 40, z + 8)))                                # thin heel
    # horn: a tapering cone with a flat top, one step below the face
    horn = v.m_capsule((14.5, AY, z + 8.0), (23.2, AY, z + 9.3), 3.3, r1=0.8) & (v.z < z + 10) & (v.x >= 16) & (abs(v.y - AY) < 3.0)
    v.fill(horn, I)
    # worn working surfaces: the face, and the top of the horn
    top = v.is_mat(I) & v.m_exposed_top()
    v.paint(top & (v.z >= z + 10), mat='iron')
    v.paint(top & (v.z >= z + 9) & (v.x >= 16), mat='iron', shade=-1)
    v.paint(v.m_box((4.5, AY - 1.0, z + 10), (6.0, AY + 1.0, z + 11)), mat='coal', shade=-1)    # hardy hole


def build(ingot=True):
    v = Vox(*DIMS, name='anvil')
    v.pivot = (SX + 0.5, SY)
    _stump(v)
    _anvil(v)

    # moss in the bark on the back and a tuft at the root
    n = v.noise(3.0, seed=3)
    bark = v.is_mat('bark', 'bark_dark')
    back = bark & v.m_surface() & (v.y < 6) & (v.x < 11)
    v.paint(back & (n + (v.z - 4.0) * 0.07 > 0.56), mat='moss')                      # thick at the rim, thinning down
    v.paint(v.is_mat('moss') & (v.z < 4), shade=-1)
    v.add(v.m_ellipsoid((3.4, 3.2, 0.8), (2.0, 1.8, 1.5)), 'moss')
    v.paint(v.is_mat('moss') & v.m_exposed_top() & (n > 0.5), mat='moss_light')

    # hammer leaning on the stump, head down on the ground at the front
    v.capsule((19.4, 16.0, 2.6), (12.6, 15.6, 12.6), 1.0, 'wood_light')
    v.paint(v.is_mat('wood_light') & (v.z > 10.2), mat='leather_dark')               # grip wrap
    head = v.m_rbox((16.4, 14.2, 0), (22.8, 17.8, 4.4), 0.8)
    v.fill(head, 'iron_dark')
    v.paint(head & ((v.x < 17.6) | (v.x > 21.6)), mat='iron')                        # struck faces
    v.paint(head & v.m_exposed_top() & (v.x > 17.6) & (v.x < 21.6), shade=1)

    if ingot:
        v.box((8.0, AY - 1.0, TOP + 11), (13.0, AY + 1.0, TOP + 12), 'ember')
        v.box((10.0, AY - 1.0, TOP + 11), (12.0, AY + 1.0, TOP + 12), 'ember_hot')
        v.box((8.0, AY - 1.0, TOP + 11), (9.0, AY + 1.0, TOP + 12), 'ember_dim')
        v.light((10.5, AY + 1.5, TOP + 14.0), (1.0, 0.58, 0.24), radius=20, power=0.8)
    return v
