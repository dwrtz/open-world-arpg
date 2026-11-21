"""Explorer: the player character as a composable stack.

Parts (body, headwear, back gear, tool) are separate voxel volumes that share one frame,
so they can be merged into a single stack or kept as separate stacks and layered at
runtime (the renderer's per-layer height test interleaves them correctly).
"""
from stack.voxel import Vox

DIMS = (28, 22, 36)   # x = facing, y = shoulders, z = up
CY = 11.0

OUTFITS = {
    'prospector': dict(jacket='cloth_blue', trousers='leather_dark', scarf='cloth_red', skin='skin',
                       hair='hair_brown', head='helmet', back='pack', tool='pickaxe'),
    'warden':     dict(jacket='cloth_green', trousers='leather_dark', scarf='cloth_cream', skin='skin_tan',
                       hair='hair_red', head='hat', back='quiver', tool='sword'),
    'delver':     dict(jacket='cloth_dark', trousers='cloth_dark', scarf='cloth_teal', skin='skin_dark',
                       hair='hair_black', head='hood', back='tank', tool='lantern', goggles=True),
}


def _new(name):
    v = Vox(*DIMS, name=name)
    v.pivot = (12.5, CY)
    return v


def body(o):
    v = _new('explorer_body')
    # boots and legs (one side, then mirrored)
    v.box((9, 6, 0), (15, 10, 3), 'leather_dark')
    v.box((15, 6, 0), (16, 10, 2), 'leather_dark')            # toe
    v.paint(v.m_box((0, 0, 0), (40, 40, 1)), shade=-2)        # sole
    v.box((10, 6, 3), (14, 10, 8), o['trousers'])
    # torso
    v.rbox((8, 5, 7), (16, 17, 17.5), o['jacket'], r=2.2)
    v.paint(v.m_box((0, 0, 7), (40, 40, 11)) & v.is_mat(o['jacket']), shade=-1)
    v.paint(v.m_box((0, 0, 8), (40, 40, 10)) & v.is_mat(o['jacket']), mat='leather_dark', shade=0)   # belt
    v.paint(v.m_box((15, 10, 8), (17, 12, 10)), mat='brass', shade=1)                                # buckle
    v.paint(v.m_box((15, 10, 10), (17, 12, 17)) & v.is_mat(o['jacket']), shade=-1)                   # jacket seam
    # head
    v.ellipsoid((12.5, CY, 22.6), (5.6, 5.9, 5.6), o['skin'])
    v.paint(v.m_box((0, 0, 17), (40, 40, 19)) & v.is_mat(o['skin']), shade=-1)                       # under-chin
    hair = (v.x < 10.4) | (v.z > 26.2) | ((v.x < 13.5) & (v.z > 22.5) & (abs(v.y - CY) > 4.0))
    v.paint(hair & v.is_mat(o['skin']), mat=o['hair'])
    v.paint(v.is_mat(o['hair']) & (v.z > 26.5), shade=1)
    v.paint(v.m_box((15.2, 6.0, 20.6), (19, 8.0, 23.6)) & v.is_mat(o['skin']) & v.m_surface(), mat='eye')   # wraps the corner: reads from front and side
    # far-side arm, hanging
    v.capsule((12.5, 4.0, 15.6), (13.2, 3.4, 10.4), 1.75, o['jacket'])
    v.ellipsoid((13.3, 3.4, 9.2), (1.7, 1.7, 1.7), o['skin'])
    v.mirror_y()
    v.carve(v.m_box((0, 12, 8), (40, 40, 17.5)) & v.m_capsule((12.5, 18.0, 15.6), (13.2, 18.6, 10.4), 1.9)
            | (v.m_ellipsoid((13.3, 18.6, 9.2), (1.8, 1.8, 1.8))))
    # near-side arm, raised to hold a tool
    v.capsule((12.5, 17.8, 15.6), (16.4, 18.6, 12.2), 1.75, o['jacket'])
    v.ellipsoid((17.3, 18.8, 11.8), (1.7, 1.7, 1.7), o['skin'])
    # scarf
    v.fill(v.m_cyl((12.3, CY), 5.3, 16.2, 18.6) & ~v.m_cyl((12.3, CY), 3.2, 16.2, 18.6), o['scarf'])
    v.box((6, 12, 12), (8, 14, 17), o['scarf'], shade=-1)
    if o.get('goggles'):
        v.paint(v.is_mat('eye'), mat='opal_teal')
        v.paint(v.m_box((14, 0, 23.6), (19, 40, 24.6)) & v.is_mat(o['skin']) & v.m_surface(), mat='leather_dark')
    v.socket('hand', (17.3, 18.8, 11.8))
    v.socket('head', (12.5, CY, 25.0))
    v.socket('back', (7.5, CY, 13.0))
    return v


def head_helmet(o):
    v = _new('helmet')
    dome = v.m_ellipsoid((12.3, CY, 25.4), (6.3, 6.6, 5.0)) & (v.z > 25.5)
    v.fill(dome, 'brass')
    v.paint(dome & (v.z > 28.6), shade=1)
    v.fill(v.m_cyl((12.6, CY), 7.1, 25.0, 26.0), 'brass', shade=-1)       # brim
    v.paint(v.m_box((0, 10, 26), (40, 12, 40)) & v.is_mat('brass'), shade=-1)   # crest
    v.box((17.6, 9.5, 26.0), (19.6, 12.5, 29.0), 'iron_dark')
    v.box((18.6, 10, 26.5), (20.6, 12, 28.5), 'lamp')
    v.light((23, CY, 27.5), (1.0, 0.86, 0.55), radius=30, power=1.1)
    return v


def head_hat(o):
    v = _new('hat')
    v.fill(v.m_cyl((12.5, CY), 9.0, 25.0, 26.2), 'leather')               # wide brim
    v.paint(v.m_cyl((12.5, CY), 9.0, 25.0, 26.2) & ~v.m_cyl((12.5, CY), 7.6, 25.0, 26.2), shade=-1)
    v.fill(v.m_cyl((12.5, CY), 5.4, 26.0, 30.6, r1=4.4), 'leather')       # crown
    v.paint(v.m_box((0, 0, 26), (40, 40, 27.2)) & v.m_cyl((12.5, CY), 5.6, 26.0, 27.2), mat='cloth_cream')
    v.paint(v.is_mat('leather') & (v.z > 29.6), shade=1)
    v.box((9, 15, 27), (10, 16, 33), 'petal')                             # feather
    v.box((8, 15, 31), (9, 16, 34), 'petal', shade=1)
    return v


def head_hood(o):
    v = _new('hood')
    shell = v.m_ellipsoid((11.6, CY, 23.2), (6.8, 6.9, 6.6)) & ~v.m_ellipsoid((13.4, CY, 22.4), (5.9, 5.4, 5.3))
    v.fill(shell & (v.z > 17.5) & (v.x < 16.2), 'cloth_purple')
    v.paint(v.is_mat('cloth_purple') & (v.z > 27.5), shade=1)
    v.paint(v.is_mat('cloth_purple') & (v.x > 14.8), shade=-1)            # rim
    v.capsule((6.4, CY, 26.5), (4.4, CY, 23.0), 1.3, 'cloth_purple', r1=0.6, shade=-1)   # tail
    return v


def back_pack(o):
    v = _new('pack')
    v.rbox((3, 6, 8), (8.4, 16, 17), 'leather', r=1.4)
    v.paint(v.m_box((0, 0, 14.5), (40, 40, 17)) & v.is_mat('leather'), mat='leather_dark')   # flap
    v.paint(v.m_box((0, 10, 12), (4, 12, 15)), mat='brass', shade=1)                          # clasp
    v.fill(v.m_capsule((5.6, 5.0, 18.6), (5.6, 17.0, 18.6), 2.0), 'cloth_cream')              # bedroll
    v.paint(v.is_mat('cloth_cream') & ((abs(v.y - 7.5) < 0.6) | (abs(v.y - 14.5) < 0.6)), mat='leather_dark')
    v.paint(v.is_mat('cloth_cream') & (v.z < 18), shade=-1)
    return v


def back_quiver(o):
    v = _new('quiver')
    v.capsule((6.4, 13.6, 9.5), (5.6, 8.2, 20.5), 1.9, 'leather_dark')
    v.paint(v.is_mat('leather_dark') & (v.z > 19), mat='brass')
    for i, (dy, dz) in enumerate(((0.0, 0), (-1.2, 1), (1.0, 2))):
        v.capsule((5.6, 8.0 + dy, 21.0), (5.4, 7.0 + dy, 24.0 + dz), 0.5, 'wood_light')
        v.box((4.6, 6.2 + dy, 24 + dz), (6.6, 7.8 + dy, 26 + dz), 'cloth_red' if i != 1 else 'cloth_cream')
    return v


def back_tank(o):
    v = _new('tank')
    v.fill(v.m_capsule((5.4, 8.4, 9.5), (5.4, 8.4, 17.5), 2.3), 'copper')
    v.fill(v.m_capsule((5.4, 13.6, 9.5), (5.4, 13.6, 17.5), 2.3), 'copper')
    v.paint(v.is_mat('copper') & ((abs(v.z - 11.5) < 0.6) | (abs(v.z - 16.5) < 0.6)), mat='iron_dark')
    v.paint(v.is_mat('copper') & (v.z > 18.4), shade=1)
    v.box((4.6, 10, 18), (6.4, 12, 21), 'iron_dark')
    v.box((4.6, 10, 21), (6.4, 12, 22), 'opal_teal')
    return v


def tool_pickaxe(o):
    v = _new('pickaxe')
    v.capsule((15.6, 18.8, 6.5), (20.6, 18.8, 21.5), 0.9, 'wood')
    v.capsule((20.9, 18.8, 22.2), (15.6, 18.8, 24.4), 1.3, 'steel', r1=0.6)
    v.capsule((20.9, 18.8, 22.2), (26.6, 18.8, 19.6), 1.3, 'steel', r1=0.6)
    v.ellipsoid((20.9, 18.8, 22.2), (1.5, 1.4, 1.5), 'iron_dark')
    return v


def tool_sword(o):
    v = _new('sword')
    v.capsule((16.2, 18.8, 10.0), (18.2, 18.8, 13.4), 0.9, 'leather_dark')     # grip
    v.capsule((17.0, 17.0, 14.3), (19.6, 20.6, 13.5), 0.9, 'brass')            # guard
    v.capsule((18.6, 18.8, 14.6), (24.8, 18.8, 28.0), 1.35, 'steel', r1=0.7)   # blade
    v.paint(v.is_mat('steel') & (v.y > 19.0), shade=1)
    v.paint(v.is_mat('steel') & (v.y < 18.0), shade=-1)
    v.ellipsoid((15.9, 18.8, 9.4), (1.1, 1.1, 1.1), 'brass')
    return v


def tool_lantern(o):
    v = _new('lantern')
    v.capsule((17.3, 18.8, 12.2), (19.6, 18.8, 13.8), 0.7, 'iron_dark')        # hook arm
    v.box((19, 18, 12), (21, 20, 13.4), 'iron_dark')                            # hanger
    v.box((18, 17, 11), (22, 21, 12), 'iron_dark')                              # cap
    v.box((18, 17, 5), (22, 21, 6), 'iron_dark')                                # base
    v.box((19, 18, 6), (21, 20, 11), 'lamp')                                    # flame core
    for (x, y) in ((18, 17), (21, 17), (18, 20), (21, 20)):
        v.box((x, y, 6), (x + 1, y + 1, 11), 'iron_dark')                       # corner posts
    v.light((20, 19, 8.5), (1.0, 0.72, 0.36), radius=36, power=1.6)
    return v


HEAD = {'helmet': head_helmet, 'hat': head_hat, 'hood': head_hood}
BACK = {'pack': back_pack, 'quiver': back_quiver, 'tank': back_tank}
TOOL = {'pickaxe': tool_pickaxe, 'sword': tool_sword, 'lantern': tool_lantern}


def parts(outfit='prospector', **over):
    """Separate stacks for body / headwear / back gear / tool, all in the same frame."""
    o = dict(OUTFITS[outfit], **over)
    out = {'body': body(o)}
    if o.get('head'): out['head'] = HEAD[o['head']](o)
    if o.get('back'): out['back'] = BACK[o['back']](o)
    if o.get('tool'): out['tool'] = TOOL[o['tool']](o)
    return out


def build(outfit='prospector', **over):
    ps = parts(outfit, **over)
    v = ps['body']
    v.name = f'explorer_{outfit}'
    for k in ('back', 'head', 'tool'):
        if k in ps:
            v.blit(ps[k], (0, 0, 0))
    return v
