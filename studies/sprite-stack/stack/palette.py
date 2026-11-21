"""Shared Wylden material palette for sprite-stack assets.

Each material is a base colour plus how it responds to light:
  emit  - emissive strength (0 = none; 1-2 glows; 3+ is a light source and blooms)
  spec  - specular highlight strength (0..1)
  gloss - specular tightness (higher = smaller, sharper highlight)
Per-voxel `shade` steps (-3..3) move along a hue-shifted ramp from each base colour.
"""

PALETTE = {
    # rock and earth
    'stone':        dict(rgb=(126, 128, 140)),
    'stone_dark':   dict(rgb=(84, 86, 102)),
    'stone_light':  dict(rgb=(168, 168, 174)),
    'basalt':       dict(rgb=(60, 58, 74)),
    'slate':        dict(rgb=(66, 78, 108)),
    'deepstone':    dict(rgb=(52, 56, 96)),
    'silt':         dict(rgb=(170, 176, 196)),
    'dirt':         dict(rgb=(124, 86, 62)),
    'dirt_dark':    dict(rgb=(86, 60, 50)),
    'clay':         dict(rgb=(170, 106, 78)),
    'sand':         dict(rgb=(214, 186, 130)),
    'coal':         dict(rgb=(38, 38, 48), spec=0.25, gloss=18),
    # growth
    'moss':         dict(rgb=(92, 146, 70)),
    'moss_light':   dict(rgb=(146, 188, 84)),
    'fern':         dict(rgb=(58, 118, 72)),
    'leaf':         dict(rgb=(72, 140, 86)),
    'grass':        dict(rgb=(110, 168, 78)),
    'petal':        dict(rgb=(240, 196, 92)),
    # wood
    'wood':         dict(rgb=(146, 100, 60)),
    'wood_dark':    dict(rgb=(100, 66, 46)),
    'wood_light':   dict(rgb=(186, 140, 88)),
    'bark':         dict(rgb=(94, 70, 58)),
    'bark_dark':    dict(rgb=(64, 48, 46)),
    'heartwood':    dict(rgb=(200, 156, 100)),
    # metal
    'iron':         dict(rgb=(128, 134, 150), spec=0.55, gloss=28),
    'iron_dark':    dict(rgb=(74, 78, 94), spec=0.45, gloss=24),
    'steel':        dict(rgb=(186, 194, 210), spec=0.8, gloss=40),
    'brass':        dict(rgb=(210, 164, 70), spec=0.7, gloss=30),
    'copper':       dict(rgb=(206, 122, 74), spec=0.6, gloss=26),
    'gold':         dict(rgb=(246, 198, 66), spec=0.9, gloss=36),
    'silver':       dict(rgb=(214, 220, 232), spec=0.9, gloss=44),
    # cloth, leather, body
    'leather':      dict(rgb=(152, 94, 58)),
    'leather_dark': dict(rgb=(102, 62, 46)),
    'cloth_red':    dict(rgb=(192, 62, 58)),
    'cloth_blue':   dict(rgb=(60, 98, 170)),
    'cloth_teal':   dict(rgb=(46, 146, 146)),
    'cloth_green':  dict(rgb=(78, 128, 70)),
    'cloth_cream':  dict(rgb=(228, 210, 172)),
    'cloth_purple': dict(rgb=(124, 82, 160)),
    'cloth_ochre':  dict(rgb=(204, 148, 62)),
    'cloth_dark':   dict(rgb=(58, 56, 76)),
    'skin':         dict(rgb=(238, 186, 142)),
    'skin_tan':     dict(rgb=(196, 136, 96)),
    'skin_dark':    dict(rgb=(140, 92, 68)),
    'hair_brown':   dict(rgb=(86, 56, 42)),
    'hair_black':   dict(rgb=(44, 40, 52)),
    'hair_red':     dict(rgb=(176, 82, 44)),
    'hair_blonde':  dict(rgb=(226, 186, 104)),
    'eye':          dict(rgb=(34, 30, 44)),
    'bone':         dict(rgb=(226, 218, 196)),
    'chitin':       dict(rgb=(52, 60, 92), spec=0.6, gloss=30),
    'chitin_warm':  dict(rgb=(110, 58, 62), spec=0.6, gloss=30),
    'flesh':        dict(rgb=(200, 110, 120)),
    # fire and light
    'ember':        dict(rgb=(255, 132, 44), emit=2.2),
    'ember_hot':    dict(rgb=(255, 214, 120), emit=3.6),
    'ember_dim':    dict(rgb=(196, 70, 40), emit=0.9),
    'lamp':         dict(rgb=(255, 226, 156), emit=3.6),
    'glass':        dict(rgb=(170, 214, 226), spec=0.9, gloss=50),
    'amber':        dict(rgb=(255, 178, 62), emit=1.3, spec=0.6, gloss=30),
    # ores
    'ore_copper':   dict(rgb=(222, 132, 76), spec=0.7, gloss=26),
    'ore_gold':     dict(rgb=(250, 206, 76), spec=0.9, gloss=36),
    'ore_iron':     dict(rgb=(170, 150, 156), spec=0.5, gloss=22),
    'ore_ember':    dict(rgb=(255, 120, 50), emit=1.6),
    # the Opal Deep
    'opal_teal':    dict(rgb=(96, 232, 214), emit=1.5, spec=0.9, gloss=40),
    'opal_pink':    dict(rgb=(250, 152, 212), emit=1.4, spec=0.9, gloss=40),
    'opal_lilac':   dict(rgb=(172, 152, 255), emit=1.4, spec=0.9, gloss=40),
    'opal_white':   dict(rgb=(232, 244, 250), emit=1.0, spec=1.0, gloss=48),
    'crystal':      dict(rgb=(150, 206, 232), spec=1.0, gloss=48),
    # fungi
    'shroom_cap':   dict(rgb=(84, 214, 196), emit=1.2),
    'shroom_spot':  dict(rgb=(214, 250, 236), emit=2.4),
    'shroom_stem':  dict(rgb=(214, 216, 196)),
    'shroom_red':   dict(rgb=(214, 84, 70)),
    'water':        dict(rgb=(70, 140, 190), spec=0.9, gloss=48),
}
