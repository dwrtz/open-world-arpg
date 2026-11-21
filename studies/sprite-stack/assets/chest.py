"""Treasure chest: banded wood, lock on the +y face, lid propped open on a heap of coins.

The lid is modelled closed in its own frame (hinge line along x at the back rim) and
sampled through a rotation, so `open_deg` can be changed freely.
"""
import math

import numpy as np

from stack.voxel import Vox

DIMS = (22, 16, 18)        # x = width, y = depth (front is +y), z = up
TOP = 9.0                  # rim height of the body
HINGE = (3.0, TOP)         # y, z of the hinge line
BANDS = ((4.0, 6.0), (16.0, 18.0))


def build(open_deg=25.0):
    v = Vox(*DIMS, name='chest')
    v.mat('glint', rgb=(255, 240, 176), emit=2.6)
    v.mat('coin', rgb=(240, 178, 50), spec=0.6, gloss=30)
    band = np.zeros(v.idx.shape, bool)
    for x0, x1 in BANDS:
        band |= (v.x >= x0) & (v.x < x1)

    # ---- body ---------------------------------------------------------------------------
    v.rbox((0.5, 2.5, 0), (21.5, 15.5, 2.0), 'wood_dark', r=0.8)                # plinth
    body = v.m_box((1, 3, 1), (21, 15, TOP))
    v.fill(body, 'wood')
    inside = v.m_box((2.5, 4.5, 4), (19.5, 13.5, TOP))
    v.carve(inside)
    v.paint(body & (v.z < 3), shade=-1)                                            # bottom plank sits in shadow
    v.paint(body & ((abs(v.z - 3.5) < 0.6) | (abs(v.z - 6.5) < 0.6)), shade=-2)   # plank gaps
    v.paint(body & (v.z > TOP - 1), shade=1)                                       # lit rim
    v.paint(body & band & v.is_mat('wood'), mat='brass', shade=0)                  # straps
    v.paint(v.is_mat('brass') & (v.z < 2.5), shade=-1)
    for x in (1, 20):                                                              # corner irons
        v.paint(v.m_box((x, 14, 1), (x + 1, 15, TOP)) | v.m_box((x, 3, 1), (x + 1, 4, TOP)), mat='iron_dark', shade=0)
    # side handles
    for x0 in (0.0, 21.0):
        v.box((x0, 7, 4), (x0 + 1, 11, 6), 'iron_dark')

    # ---- coins --------------------------------------------------------------------------
    heap = v.m_ellipsoid((11.0, 9.8, 7.0), (8.8, 4.8, 4.3)) & (v.x > 2.5) & (v.x < 19.5) & (v.y > 4.5) & (v.y < 13.5) & (v.z > 4)
    heap |= inside & (v.z < TOP - 1.5)
    v.fill(heap, 'coin')
    v.speckle('coin', 0.30, step=-1, scale=1.7, seed=3)
    v.speckle('coin', 0.22, step=1, scale=1.7, seed=8)
    v.paint(v.is_mat('coin') & ~v.m_exposed_top(2), shade=-2)

    # ---- lid, sampled in its closed frame -----------------------------------------------
    th = math.radians(open_deg)
    dy = v.y - HINGE[0]; dz = v.z - HINGE[1]
    ly = dy * math.cos(th) + dz * math.sin(th)
    lz = -dy * math.sin(th) + dz * math.cos(th)
    arch = ((ly - 6.25) / 6.25) ** 2 + (np.maximum(lz - 1.0, 0) / 5.3) ** 2 <= 1.0
    lid = arch & (lz >= 0) & (v.x >= 0.5) & (v.x < 21.5)
    hollow = (((ly - 6.25) / 4.2) ** 2 + (lz / 4.0) ** 2 <= 1.0) & (abs(v.x - 11.0) < 9.2)
    lining = (((ly - 6.25) / 5.2) ** 2 + (lz / 5.0) ** 2 <= 1.0) & (abs(v.x - 11.0) < 10.0)
    shell = lid & ~hollow
    v.fill(shell, 'wood')
    plank = np.floor((np.degrees(np.arctan2(lz - 0.5, ly - 6.25)) + 18.0) / 36.0).astype(int)
    v.paint(shell & (plank % 2 == 0), shade=1)                                     # alternating planks
    v.paint(shell & (lz < 1.0), shade=-1)                                          # lip
    v.paint(shell & band, mat='brass', shade=0)
    v.paint(shell & ((v.x < 1.0) | (v.x > 21.0)), mat='wood', shade=-1)            # end boards
    v.paint(shell & lining, mat='wood_dark', shade=1)                              # underside, catches the glow
    # hasp hanging from the lid's front lip
    v.fill((ly >= 12.0) & (ly < 13.4) & (lz > -0.9) & (lz < 1.6) & (abs(v.x - 11.0) < 1.5), 'brass', shade=1)

    # ---- lock plate on the front --------------------------------------------------------
    v.box((9, 15, 3), (13, 16, 8), 'brass')
    v.box((10, 15, 4), (12, 16, 6), 'eye')                                        # keyhole
    v.paint(v.m_box((9, 15, 7), (13, 16, 8)), shade=1)
    for x0, _ in BANDS:                                                           # strap studs
        v.paint(v.m_box((x0, 14, 2), (x0 + 1, 15, 3)) | v.m_box((x0 + 1, 14, 7), (x0 + 2, 15, 8)), mat='iron_dark', shade=0)

    # ---- glints on the coins ------------------------------------------------------------
    top = v.m_exposed_top() & v.is_mat('coin')
    for x, y in ((7, 11), (13, 12), (16, 9)):
        v.paint(top & v.m_box((x, y, 0), (x + 1, y + 1, 99)), mat='glint')
    v.light((11.0, 11.0, TOP + 2.5), (1.0, 0.76, 0.34), radius=20, power=0.9)
    return v
