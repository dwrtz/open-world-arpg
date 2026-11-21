"""Opal Scarab: a low, domed beetle of the Opal Deep with a crystal cluster growing out of
its back. Faces +x. Built on the y < centre side and mirrored; the crystals are added
afterwards so the cluster stays lopsided.
"""
from stack.voxel import Vox

DIMS = (30, 24, 18)   # x = facing, y = leg span, z = up
CY = 12.0

# (hip, knee, foot) for the far-side legs; mirrored onto the near side
LEGS = (
    ((20.5, 7.0, 3.6), (23.8, 3.1, 6.0), (26.6, 1.7, 1.0)),   # front, reaching forward
    ((14.0, 5.6, 3.6), (14.6, 2.3, 6.4), (14.2, 1.4, 1.0)),   # middle, straight out
    ((8.0, 6.6, 3.6), (4.9, 2.9, 6.2), (2.3, 1.8, 1.0)),      # rear, trailing
)

# (base, tip, base radius, tip radius, material)
CRYSTALS = (
    ((11.0, 12.6, 10.5), (9.8, 12.0, 17.6), 2.1, 0.9, 'opal_teal'),
    ((14.0, 9.8, 10.5), (16.2, 8.2, 15.4), 1.6, 0.7, 'opal_pink'),
    ((8.4, 15.0, 10.0), (6.2, 17.0, 14.6), 1.6, 0.7, 'opal_teal'),
    ((12.6, 15.4, 10.5), (14.0, 17.0, 13.8), 1.3, 0.6, 'opal_pink'),
    ((7.6, 10.2, 10.0), (5.6, 8.8, 13.2), 1.2, 0.6, 'opal_teal'),
)


def build():
    v = Vox(*DIMS, name='scarab')
    v.pivot = (14.0, CY)
    v.mat('shell', rgb=(84, 70, 156), spec=0.35, gloss=22)      # violet wing cases
    v.mat('chitin', spec=0.3, gloss=20)                         # legs, head and shield: less glare
    v.mat('seamglow', rgb=(60, 176, 170), emit=0.7)             # opal light leaking between the wing cases

    # ---- legs (under the body, so the shell overlaps the hips) ------------------------
    for hip, knee, foot in LEGS:
        v.capsule(hip, knee, 1.9, 'chitin', shade=0)
        v.capsule(knee, foot, 1.7, 'chitin', r1=1.1, shade=-1)
        v.ellipsoid(knee, (1.9, 1.9, 1.6), 'shell', shade=1)    # armoured knuckle joint
    v.paint(v.is_mat('chitin') & (v.z < 1.0), shade=-3)         # claw tips

    # ---- body -------------------------------------------------------------------------
    v.fill(v.m_ellipsoid((13.5, CY, 3.6), (9.4, 6.2, 2.4)), 'chitin', shade=-2)    # belly
    elytra = v.m_ellipsoid((12.0, CY, 3.4), (10.0, 7.5, 9.2)) & (v.z > 2.6)
    v.fill(elytra, 'shell')
    shield = v.m_ellipsoid((20.8, CY, 3.6), (4.8, 6.4, 7.0)) & (v.z > 2.2) & (v.x > 18.6)
    v.fill(shield, 'chitin', shade=-1)
    head = v.m_ellipsoid((25.2, CY, 4.0), (3.3, 3.9, 3.2)) & (v.z > 1.6)
    v.fill(head & ~shield, 'chitin', shade=-2)

    # shading clusters: lit crown, darker skirt, pale rim, seams
    v.paint(v.is_mat('shell') & (v.z > 10.4), shade=1)
    v.paint(v.is_mat('shell') & (v.z < 6.0), shade=-1)
    v.paint(v.is_mat('shell') & (v.z < 3.6), shade=2)                               # rim of the wing cases
    v.paint(shield & (v.z > 8.0), shade=0)
    v.paint(shield & (v.x < 19.6), shade=-3)                                        # gap behind the shield
    v.carve(v.is_mat('shell') & (v.x < 8.0) & (abs(v.y - CY) < (8.0 - v.x) * 0.7))   # wing tips part at the rear
    seam = v.is_mat('shell') & (abs(v.y - CY) < 1.0)
    v.carve(seam & v.m_exposed_top())                                               # split-wing seam, a real groove
    v.paint(seam, mat='seamglow', shade=0)
    v.paint(v.is_mat('shell') & (abs(abs(v.y - CY) - 4.4) < 0.6) & (v.x < 17) & (v.z > 6), add=-1)   # wing-case groove

    # mandibles
    v.capsule((26.6, 9.4, 2.8), (29.0, 8.4, 2.6), 1.0, 'bone')
    v.capsule((29.0, 8.4, 2.6), (29.5, 10.6, 2.6), 0.8, 'bone', shade=1)

    # eyes on the front-side corners of the head
    v.paint(v.m_box((26.0, 8.0, 5.0), (28.4, 10.0, 6.0)) & head & v.m_surface(), mat='shroom_spot')

    v.mirror_y()

    # ---- opal cluster -----------------------------------------------------------------
    for base, tip, r0, r1, mat in CRYSTALS:
        m = v.m_capsule(base, tip, r0, r1)
        v.paint(v.m_capsule(base, base, r0 + 1.2) & v.is_mat('shell'), shade=-2)    # cracked socket
        v.fill(m, mat)
        v.paint(m & (v.z > tip[2] - 0.9), mat='opal_white')
        v.paint(m & (v.z < base[2] + 2.0) & v.is_mat(mat), shade=-2)
    v.light((10.5, CY, 16.0), (0.38, 0.95, 0.88), radius=22, power=0.8)
    return v
