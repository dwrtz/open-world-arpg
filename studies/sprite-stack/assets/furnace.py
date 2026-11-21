"""Smelting furnace: a squat, round-shouldered stack of basalt blocks with an arched,
iron-framed firebox on the +y face, a short capped chimney and moss over one shoulder.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (30, 26, 36)
CX, CY = 15.0, 11.0          # body centre (the mouth is centred on CX)
MOUTH_Z = 9.0                # centre of the arch's round top
MOUTH_R = 5.5
CHIM = (9.5, 8.5)            # chimney centre: back-left of the dome
HOT = ('ember', 'ember_hot', 'ember_dim', 'coal')
IRON = 'iron_black'           # sooty wrought iron, darker than every stone
METAL = ('iron', 'iron_dark', IRON)


def _cells(v, course_h, block_w, seed):
    """Running-bond block layout: per-voxel random value of its block, and a seam mask."""
    course = np.floor(v.z / course_h).astype(int)
    off = np.where(course % 2 == 0, 0.0, block_w / 2.0) + 1.0
    fx, fy = (v.x + off) / block_w, (v.y + off) / block_w
    bx, by = np.floor(fx).astype(int), np.floor(fy).astype(int)
    rng = np.random.default_rng(seed)
    table = rng.random((course.max() + 2, by.max() + 2, bx.max() + 2))
    val = table[course, by, bx]
    seam = ((v.z % course_h) < 1) | ((fx - bx) * block_w < 1) | ((fy - by) * block_w < 1)
    return val, seam


def _arch(v, r, z0=3.0):
    """Arch profile in the x-z plane, extruded along all of y."""
    return v.m_cyl((CX, MOUTH_Z), r, -1, 99, axis='y') | v.m_box((CX - r, -1, z0), (CX + r, 99, MOUTH_Z))


def build(lit=True):
    v = Vox(*DIMS, name='furnace')
    v.pivot = (CX, CY + 1.5)
    v.mat(IRON, rgb=(48, 50, 62), spec=0.32, gloss=20)

    # ---- body: plinth + round-shouldered beehive, built block by block ------------------
    val, seam = _cells(v, 5, 7, seed=11)

    def body(g):   # g = grow, in voxels
        ax, ay, az = 13.0 + g, 10.0 + g, 14.5 + g
        zz = np.maximum(v.z - 8.0, 0.0)          # straight drum below z = 8, dome above
        hive = (np.abs((v.x - CX) / ax) ** 3.0 + np.abs((v.y - CY) / ay) ** 3.0 + (zz / az) ** 2.4) <= 1.0
        plinth = (np.abs((v.x - CX) / (14.0 + g)) ** 4.0 + np.abs((v.y - CY) / (11.0 + g)) ** 4.0 <= 1.0) & (v.z < 3)
        porch = _arch(v, MOUTH_R + 3.6 + g, 0) & v.m_box((0, CY, 0), (99, 22.0 + g, 99))
        return hive | plinth | porch

    proud = (val > 0.70) & (v.z > 3)
    v.fill(body(0), 'stone_dark')
    v.add(body(1) & proud & (v.y < 21.0), 'stone_dark')           # some blocks sit proud
    stone = v.is_mat('stone_dark')
    v.paint(stone & (val < 0.34), mat='basalt', shade=1)          # violet basalt blocks
    v.paint(stone & (val > 0.90), shade=1)                        # a few pale ones
    v.paint(v.occ & seam, mat='basalt', shade=-1)                 # joints
    v.paint(v.occ & (v.z < 3), add=-1)                            # plinth sits darker

    # ---- chimney ------------------------------------------------------------------------
    cval, cseam = _cells(v, 4, 5, seed=5)
    chim = v.m_cyl(CHIM, 4.8, 14, 29, r1=4.2)
    v.add(chim, 'stone_dark')
    cm = chim & (v.z > 20) & ~body(1)
    v.paint(cm & (cval < 0.4), mat='basalt', shade=1)
    v.paint(cm & cseam, mat='basalt', shade=-1)
    v.fill(v.m_cyl(CHIM, 5.4, 27, 29), 'iron_dark')                               # collar
    v.fill(v.m_cyl(CHIM, 2.8, 29, 32), IRON, shade=-1)                            # sooty throat
    v.fill(v.m_cyl(CHIM, 6.3, 32, 34), 'iron_dark')                               # rain cap: two plates
    v.paint(v.m_cyl(CHIM, 6.3, 32, 33), mat=IRON)
    v.fill(v.m_cyl(CHIM, 4.0, 34, 35), 'iron_dark')
    v.fill(v.m_cyl(CHIM, 1.6, 35, 36), 'iron')                                    # finial

    # ---- firebox ------------------------------------------------------------------------
    arch = _arch(v, MOUTH_R)
    frame = _arch(v, MOUTH_R + 2.6) & ~arch & v.m_box((0, 20.0, 3), (99, 24.0, 99))
    v.fill(frame, IRON)
    v.paint(frame & (v.y >= 22), mat='iron_dark')                                  # face plate
    cavity = arch & v.m_box((0, 9.0, 3), (99, 99, 99))
    v.carve(cavity)
    # hearth slab pushing out of the mouth
    v.fill(v.m_rbox((CX - 9.5, 16, -4), (CX + 9.5, 25.6, 3), 2.0) & (v.z < 3), 'stone_dark', shade=-1)
    v.paint(v.m_box((0, 23, 2), (99, 26, 3)) & v.is_mat('stone_dark'), mat='basalt', shade=0)
    # inner walls: soot near the lip, glowing deeper in
    p = np.pad(cavity, 1)
    near = (p[:-2, 1:-1, 1:-1] | p[2:, 1:-1, 1:-1] | p[1:-1, :-2, 1:-1] | p[1:-1, 2:, 1:-1]
            | p[1:-1, 1:-1, :-2] | p[1:-1, 1:-1, 2:]) & ~cavity
    wall = near & v.occ & ~v.is_mat(*METAL)
    v.paint(wall, mat='basalt', shade=-2)
    v.paint(wall & (v.y < 18), mat='ember_dim', shade=-1)
    v.paint(wall & (v.y < 11), mat='ember_dim', shade=0)
    # ember bed
    bed = v.m_ellipsoid((CX, 16.0, 2.6), (5.4, 6.6, 4.2)) & cavity
    v.fill(bed, 'ember')
    n = v.noise(3.0, seed=4)
    v.paint(bed & v.m_ellipsoid((CX + 0.4, 15.0, 3.4), (3.6, 4.4, 3.6)), mat='ember_hot')
    v.paint(bed & (n > 0.6) & (v.y > 18), mat='ember_dim')
    # dim coals spilling over the lip
    lip = (v.m_ellipsoid((CX - 1.8, 23.2, 3.0), (4.0, 1.9, 1.7)) | v.m_ellipsoid((CX + 3.4, 22.4, 3.2), (2.2, 1.6, 1.9)))
    v.add(lip & (v.z >= 3), 'coal')
    v.paint(lip & (n > 0.5) & v.is_mat('coal'), mat='ember_dim')
    # grate bars across the lower mouth
    for bx in (CX - 3.5, CX - 0.5, CX + 2.5):
        v.fill(v.m_box((bx, 22, 3), (bx + 1, 23, 9)), IRON, shade=-1)
    v.fill(v.m_box((CX - MOUTH_R, 22, 8), (CX + MOUTH_R, 23, 9)), IRON, shade=-1)
    # rivets on the frame
    for (rx, rz) in ((CX - 7.0, 5), (CX + 7.0, 5), (CX - 5.8, 13.2), (CX + 5.8, 13.2), (CX, 16.0)):
        v.paint(v.m_box((rx - 0.5, 23, rz - 0.5), (rx + 0.5, 24, rz + 0.5)), mat='steel', shade=1)

    # ---- moss: the top, the -x shoulder, a little spill down the front --------------------
    blocked = v.is_mat(*METAL, *HOT, 'steel')
    n1 = v.noise(6.0, seed=21, octaves=2)
    bias = np.clip((17.0 - v.x) / 14.0, -0.5, 1.0) * 0.34 + np.clip((v.z - 10.0) / 12.0, 0, 1) * 0.20
    top = v.m_exposed_top() & ~blocked & (v.z > 3.5) & (v.z < 28)
    v.paint(top & (n1 + bias > 0.70), mat='moss')
    # hang down the sides one to three voxels under mossy tops
    m = v.is_mat('moss')
    drip = np.zeros_like(m)
    drip[:-1] |= m[1:]
    drip[:-2] |= m[2:] & (n1[2:] > 0.50)
    drip[:-3] |= m[3:] & (n1[3:] > 0.58)
    v.paint(drip & v.m_surface() & ~blocked, mat='moss', shade=-1)
    v.paint(v.is_mat('moss') & v.m_exposed_top() & (v.noise(4.0, seed=8) > 0.56), mat='moss_light')
    # a few plump tufts
    for (tx, ty, tz, r) in ((4.6, 8.5, 16.0, 2.4), (3.6, 14.5, 12.5, 2.1), (16.5, 5.5, 21.5, 2.3), (8.5, 18.0, 19.0, 2.0)):
        v.add(v.m_ellipsoid((tx, ty, tz), (r, r, r * 0.8)), 'moss')

    # ---- loose coal at the base -----------------------------------------------------------
    for (x, y, z, rx, ry, rz) in ((26.8, 23.8, 1.5, 2.6, 2.2, 2.2), (28.7, 21.2, 1.0, 1.5, 1.7, 1.5),
                                  (24.6, 25.2, 0.9, 1.5, 1.2, 1.4), (27.4, 22.2, 3.3, 1.6, 1.5, 1.4),
                                  (2.6, 23.4, 1.2, 2.1, 1.9, 1.7), (5.0, 25.0, 0.8, 1.4, 1.2, 1.2),
                                  (22.4, 23.6, 4.0, 2.0, 1.7, 1.6), (20.2, 24.8, 3.7, 1.4, 1.2, 1.2)):   # two staged on the hearth
        v.add(v.m_ellipsoid((x, y, z), (rx, ry, rz)), 'coal')
    loose = v.is_mat('coal') & ((v.x > 19.5) | (v.x < 7)) & (v.y > 19) & (v.z < 6)
    v.paint(loose & (v.z < 1), shade=-1)
    v.paint(loose & v.m_exposed_top() & (v.noise(2.0, seed=9) > 0.6), shade=1)     # a glint or two

    if lit:
        v.light((CX, 27.0, 7.0), (1.0, 0.55, 0.22), radius=34, power=1.4)
    return v
