"""Workbench: a sturdy plank bench with a lower shelf, an iron vise at the +x end, a
mallet, tongs and an unrolled blueprint on top, a saw hung on the front, ore on the shelf
and a small lantern at the back corner.
"""
import numpy as np

from stack.voxel import Vox

DIMS = (36, 18, 24)
TOP0, TOP1 = 12, 15          # bench top slab (z)
X0, X1 = 1, 33               # bench top extent (x)
Y0, Y1 = 1, 16               # bench top extent (y); +y is the front


def _frame(v):
    # legs
    for lx in (3, 28):
        for ly in (2, 12):
            v.box((lx, ly, 0), (lx + 3, ly + 3, TOP0), 'wood_dark')
    v.paint(v.m_box((0, 0, 0), (99, 99, 1)), shade=-1)
    # aprons under the top, front and back, and end rails
    v.box((6, 13.5, TOP0 - 2), (28, 15, TOP0), 'wood', shade=-1)
    v.box((6, 2, TOP0 - 2), (28, 3.5, TOP0), 'wood', shade=-1)
    for lx in (3.5, 28.5):
        v.box((lx, 5, TOP0 - 2), (lx + 2, 12, TOP0), 'wood', shade=-1)
    # lower shelf: three boards on end rails
    v.box((4, 2.5, 3), (30, 14.5, 5), 'wood', shade=-1)
    v.paint(v.m_box((0, 6.5, 4), (99, 7.5, 5)) | v.m_box((0, 10.5, 4), (99, 11.5, 5)), mat='wood_dark', shade=-1)
    # top: four planks along x, each its own tone, ends not quite flush
    planks = ((1, 5, 0, 0, 0), (5, 9, 1, -1, 1), (9, 13, 0, 0, -1), (13, 16, 1, 1, 0))   # y0, y1, shade, dx0, dx1
    for (y0, y1, sh, d0, d1) in planks:
        v.box((X0 + d0, y0, TOP0), (X1 + d1, y1, TOP1), 'wood', shade=sh)
    top = v.m_box((0, 0, TOP0), (99, 99, TOP1))
    v.paint(top & ((v.x < X0 + 1.5) | (v.x > X1 - 1.5)) & (v.z < TOP1 - 1), add=-1)       # end grain
    v.paint(top & (v.z < TOP0 + 1), add=-1)                                              # underside
    v.carve(v.m_box((X0, Y1 - 2, TOP1 - 1), (X0 + 2, Y1, TOP1)))                         # a chipped corner
    # worn, darker patches on the work surface
    n = v.noise(5.0, seed=6)
    v.paint(top & (v.z >= TOP1 - 1) & (n > 0.66), add=-1)
    # nail heads on the front edge over the legs
    for nx in (4, 29):
        v.paint(v.m_box((nx, 15, TOP0 + 1), (nx + 1, 17, TOP0 + 2)), mat='iron_dark')


def _vise(v):
    z = TOP1
    I = 'iron_dark'
    v.box((26, 8, z), (33, 13, z + 1), I, shade=-1)                    # base plate
    v.box((27, 8, z + 1), (29, 13, z + 5), I)                          # fixed jaw
    v.box((31, 8, z + 1), (33, 13, z + 5), I)                          # moving jaw
    v.box((29, 9.5, z + 1), (31, 11.5, z + 3), I, shade=-1)            # slide
    v.paint(v.m_box((27, 8, z + 4), (33, 13, z + 5)) & v.is_mat(I), mat='iron')      # jaw tops
    v.box((29, 10, z + 3), (31, 11, z + 6), 'copper')                  # a bar clamped in the jaws
    v.box((33, 10, z + 2), (35, 11, z + 3), 'steel')                   # screw
    v.box((34.5, 10, z - 1), (35.5, 11, z + 5), 'steel')               # tommy bar
    v.box((34.5, 10, z + 5), (35.5, 11, z + 6), I)


def _mallet(v):
    """Standing on its head at the back of the bench, handle up."""
    z = TOP1
    head = v.m_rbox((16.5, 2.0, z), (24.5, 7, z + 4), 1.0)
    v.fill(head, 'wood_dark')
    v.paint(head & ((v.x < 17.5) | (v.x >= 23.5)), mat='heartwood', shade=-1)         # struck end grain
    v.paint(head & v.m_exposed_top() & (v.x >= 17.5) & (v.x < 23.5), shade=1)
    v.fill(v.m_cyl((20.5, 4.5), 1.05, z + 4, z + 9), 'wood_light')
    v.paint(v.m_cyl((20.5, 4.5), 1.05, z + 8, z + 9), mat='wood_light', shade=-1)


TONGS = ('.###.',      # jaws, hung on a nail
         '.#.#.',
         '.#.#.',
         '..o..',      # pivot rivet
         '.#.#.',
         '.#.#.',
         '#...#',      # handles
         '#...#',
         '#...#')


def _tongs(v, x0=22, ztop=13, y=16):
    """Blacksmith's tongs hung on a nail on the front edge, drawn as a little bitmap."""
    for r, row in enumerate(TONGS):
        for c, ch in enumerate(row):
            if ch == '.':
                continue
            m = v.m_box((x0 + c, y, ztop - 1 - r), (x0 + c + 1, y + (2 if ch == 'o' else 1), ztop - r))
            v.fill(m, 'steel' if ch == 'o' else 'iron')
    v.fill(v.m_box((x0 + 2, y, ztop), (x0 + 3, y + 1, ztop + 1)), 'iron_dark')        # nail


def _blueprint(v):
    z = TOP1
    sheet = v.m_box((8, 8.5, z), (18, 15.5, z + 1))
    v.fill(sheet, 'cloth_blue')
    # drawn lines
    ink = (v.m_box((10, 10, z), (16, 11, z + 1)) | v.m_box((10, 10, z), (11, 14, z + 1))
           | v.m_box((13, 13, z), (16, 14, z + 1)) | v.m_box((15, 10, z), (16, 14, z + 1)))
    v.paint(sheet & ink, mat='cloth_cream')
    # the rolled end
    roll = v.m_cyl((7.2, z + 1.5), 1.6, 8.0, 16.0, axis='y')
    v.fill(roll, 'cloth_blue', shade=-1)
    v.paint(roll & ((v.y < 9) | (v.y >= 15)), mat='cloth_cream')
    v.paint(roll & v.m_exposed_top(), shade=0)


def _saw(v):
    """Hung on two nails in the front edge of the top."""
    y0, y1 = 16, 17
    blade = v.m_box((4, y0, 7), (17, y1, 13)) & (v.z >= 7.5 + (17 - v.x) * 0.26)
    v.fill(blade, 'steel')
    below = np.zeros_like(blade); below[1:] = blade[:-1]
    v.paint(blade & ~below, mat='iron', shade=-1)                                     # toothed edge
    handle = v.m_rbox((16, y0, 6.5), (21, y1 + 1, 13), 0.8)
    v.fill(handle, 'heartwood')
    v.carve(v.m_box((18, 14, 9), (20, 19, 11)))                                       # grip hole
    v.paint(v.m_box((16, y0, 11), (17, y1 + 1, 12)) | v.m_box((16, y0, 9), (17, y1 + 1, 10)), mat='brass')
    for px in (6, 13):                                                                # nails it hangs on
        v.fill(v.m_box((px, y0, 13), (px + 1, y1, 14)), 'iron_dark')


def _ore(v, c, r, ore, seed):
    lump = v.m_ellipsoid(c, r) & ~v.occ
    n = v.noise(2.2, seed=seed)
    v.fill(lump, 'stone_dark')
    v.paint(lump & (n > 0.56), mat=ore)
    v.paint(lump & (n > 0.70), shade=1)
    v.paint(lump & (v.z < c[2] - r[2] * 0.3) & v.is_mat('stone_dark'), shade=-1)


def _lantern(v, x, y):
    z = TOP1
    I = 'iron_dark'
    v.box((x, y, z), (x + 4, y + 4, z + 1), I)
    v.box((x + 1, y + 1, z + 1), (x + 3, y + 3, z + 5), 'lamp')
    for (px, py) in ((x, y), (x + 3, y), (x, y + 3), (x + 3, y + 3)):
        v.box((px, py, z + 1), (px + 1, py + 1, z + 5), I)
    v.box((x, y, z + 5), (x + 4, y + 4, z + 6), I)
    v.box((x + 1, y + 1, z + 6), (x + 3, y + 3, z + 7), I, shade=1)
    v.box((x + 1.5, y + 1, z + 7), (x + 2.5, y + 3, z + 9), 'brass')                  # carry ring
    v.carve(v.m_box((x + 1.5, y + 1.6, z + 7), (x + 2.5, y + 2.4, z + 8)))
    v.light((x + 2, y + 2.5, z + 3.5), (1.0, 0.78, 0.42), radius=24, power=1.0)


def build():
    v = Vox(*DIMS, name='workbench')
    v.pivot = (17.0, 8.5)
    _frame(v)
    _vise(v)
    _mallet(v)
    _tongs(v)
    _blueprint(v)
    _saw(v)
    _lantern(v, 2.0, 2.0)
    # ore: a heap on the shelf, one lump up on the bench
    _ore(v, (20.0, 12.0, 6.8), (2.8, 2.3, 2.2), 'ore_copper', 3)
    _ore(v, (15.4, 11.6, 6.2), (2.0, 2.1, 1.6), 'ore_copper', 5)
    _ore(v, (24.4, 10.6, 6.4), (2.3, 2.2, 1.8), 'ore_copper', 8)
    _ore(v, (12.0, 4.5, TOP1 + 1.4), (2.4, 2.1, 1.9), 'ore_gold', 12)
    # and a couple dropped on the floor at the vise end
    _ore(v, (33.6, 10.5, 1.7), (2.3, 2.6, 2.2), 'ore_copper', 15)
    _ore(v, (33.2, 6.0, 1.2), (1.9, 1.8, 1.6), 'ore_copper', 17)
    # a crate tucked on the shelf at the back-left
    v.box((6, 4, 5), (13, 10, 10), 'wood', shade=1)
    v.paint(v.m_box((6, 4, 5), (13, 10, 10)) & ((v.z < 6) | (v.z >= 9)), mat='wood_dark')
    return v
