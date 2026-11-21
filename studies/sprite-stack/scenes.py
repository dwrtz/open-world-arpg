"""Scene builders shared by the stills and the reel."""
import math
import os

import numpy as np

import assets
from stack.font import draw_text
from stack.render import Camera, Scene, project, render

_cache = {}


def baked(name, **params):
    key = (name, tuple(sorted(params.items())))
    if key not in _cache:
        _cache[key] = assets.build(name, **params).bake()
    return _cache[key]


def have(name):
    return name in assets.names()


DAIS = dict(kind='dais', radius=100, thickness=5, rgb=(28, 34, 52), ring_rgb=(64, 74, 102),
            rim_rgb=(214, 150, 78), gloss=0.27, rim_glow=0.22)

# the showcase line-up: one centre piece, an inner ring of big pieces, an outer ring
CENTER = ('altar', {}, 'OPAL ALTAR')
INNER = [
    ('furnace', {}, 'FURNACE'), ('moss_golem', {}, 'MOSS GOLEM'),
    ('giant_root', {}, 'GIANT ROOT'), ('workbench', {}, 'WORKBENCH'),
]
OUTER = [
    ('explorer', {'outfit': 'prospector'}, 'PROSPECTOR'), ('ore_rock', {'kind': 'copper'}, 'COPPER ORE'),
    ('anvil', {}, 'ANVIL'), ('glowshrooms', {}, 'GLOWSHROOMS'),
    ('explorer', {'outfit': 'delver'}, 'DELVER'), ('opal_cluster', {}, 'OPAL CLUSTER'),
    ('scarab', {}, 'OPAL SCARAB'), ('lantern_post', {}, 'LANTERN'),
    ('explorer', {'outfit': 'warden'}, 'WARDEN'), ('ore_rock', {'kind': 'gold'}, 'GOLD ORE'),
    ('minecart', {}, 'MINECART'), ('chest', {}, 'CHEST'),
]
FACES_X = {'explorer', 'scarab', 'moss_golem', 'minecart'}     # these face +x; props present +y


def _ring(items, radius, phase):
    out = []
    items = [it for it in items if have(it[0])]
    for i, (name, params, label) in enumerate(items):
        ang = phase + 360.0 * i / max(1, len(items))
        x, y = radius * math.cos(math.radians(ang)), radius * math.sin(math.radians(ang))
        yaw = ang - 30 if name in FACES_X else ang - 90
        out.append((name, params, label, x, y, yaw))
    return out


def lineup():
    out = []
    if have(CENTER[0]):
        out.append((*CENTER, 0, 0, 0))
    return out + _ring(INNER, 44, 45) + _ring(OUTER, 77, 208)


def showcase(items=None, floor=None):
    sc = Scene()
    sc.floor = dict(floor or DAIS)
    sc.by_label = {}
    for (name, params, label, x, y, yaw) in (items or lineup()):
        if not have(name):
            continue
        o = sc.add(baked(name, **params), (x, y, 0), yaw, label)
        sc.by_label[label] = o
    return sc


SHOWCASE_CAM = dict(elev=38.0, scale=4.8, look=(0, 0, 11))


def label_pass(img, scene, cam, scale=2, alpha=1.0, only=None, front_only=True):
    """Pixel-font name tags above each labelled stack (fading out toward the back)."""
    th = math.radians(cam.yaw)
    for o in scene.objs:
        if not o.label or (only and o.label not in only):
            continue
        a = alpha
        if front_only:
            yr = float(o.pos[0]) * math.sin(th) + float(o.pos[1]) * math.cos(th)
            a *= min(1.0, max(0.0, (yr + 4) / 22.0))
        if a <= 0.02:
            continue
        top = float(o.pos[2]) + (max(o.b.layers) + 1) * (1 + o.gap) + 4
        x, y = project(cam, (float(o.pos[0]), float(o.pos[1]), top))
        draw_text(img, x, y - 7 * scale, o.label, scale=scale, alpha=a)
    return img


def frame(scene, cam, ss=2, labels=False, **kw):
    img = render(scene, cam, ss=ss, **kw)
    if labels:
        label_pass(img, scene, cam, alpha=float(labels))
    return img


# ---- side-view cave diorama -------------------------------------------------------------
# (asset, params, x, y, z_hint, yaw); x and z_hint in cave_slab layout units (scaled by its K)
CAST = [
    ('furnace',      {},                       23, 23, 50,   0),
    ('anvil',        {},                       47, 26, 50,   0),
    ('glowshrooms',  {},                       78, 19, 36,  20),
    ('lantern_post', {},                       90, 15, 36,   0),
    ('minecart',     {},                       95, 28, 36,   0),
    ('explorer',     {'outfit': 'prospector'}, 112, 25, 36,   0),
    ('scarab',       {},                      127, 25, 18, 180),
    ('opal_cluster', {},                      144, 20, 18,   0),
    ('chest',        {},                      141, 23, 60,   0),
    ('explorer',     {'outfit': 'warden'},     58, 22, 82,   0),
    ('lantern_post', {},                       36, 14, 82,   0),
    ('ore_rock',     {'kind': 'gold'},        120, 20, 82,  30),
]


def diorama(cast=None, light_gain=1.0):
    from assets import cave_slab
    key = ('cave_slab_vox',)
    if key not in _cache:
        _cache[key] = assets.build('cave_slab')
    slab = _cache[key]
    sc = Scene()
    sc.extent = 190
    sc.bloom = 0.6
    sc.key_frame = 'world'
    sc.key_dir = (-0.35, 0.5, 0.8)
    sc.key_rgb = (1.0, 0.95, 0.86)
    sc.key_power = 1.0
    sc.sky_rgb = (0.34, 0.44, 0.70)
    sc.ground_rgb = (0.16, 0.14, 0.16)
    sc.ambient = 0.40
    sc.bg = dict(inner=(22, 40, 58), outer=(4, 7, 14), center=(0.5, 0.5), dots=True)
    px, py = slab.pivot
    sc.slab = sc.add(baked('cave_slab'), (0, 0, 0))
    sc.cast = []
    for (name, params, x, y, zh, yaw) in (cast or CAST):
        if not have(name):
            continue
        b = baked(name, **params)
        xv = x * cave_slab.K
        zs = [cave_slab.floor_at(slab, xv + dx, y + dy, zh * cave_slab.K) for dx in (-5, 0, 5) for dy in (-3, 3)]
        z = int(np.median(zs))
        o = sc.add(b, (xv - px, y - py, z), yaw)
        o.light_gain = light_gain
        sc.cast.append(o)
    return sc


DIORAMA_CAM = dict(elev=24.0, scale=4.8, look=(0, 0, 60))


def set_dusk(sc, t):
    """0 = daylight from the front, 1 = lamps only."""
    t = min(1.0, max(0.0, t))
    sc.key_power = 1.0 * (1 - t) + 0.05 * t
    sc.ambient = 0.40 * (1 - t) + 0.13 * t
    sc.sky_rgb = tuple(a * (1 - t) + b * t for a, b in zip((0.34, 0.44, 0.70), (0.20, 0.26, 0.52)))
    for o in sc.objs:
        o.light_gain = 1.0 + 0.7 * t
    sc.emit_gain = 1.0 + 0.25 * t
    return sc
