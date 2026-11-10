"""Biome scenes: terrain plan, dressing, stations, lighting and cast.

Each builder returns a Scene describing where explorers stand so the render
script can place them on generated floors.
"""

import math
from dataclasses import dataclass, field

import numpy as np
from mathutils import Vector

from . import core, props, shaders, terrain

V = Vector
PITCH = 10.0


@dataclass
class Scene:
    name: str
    field: terrain.Field
    camera_target: tuple
    width: float
    details: list = field(default_factory=list)  # (suffix, target, width)
    cast: list = field(default_factory=list)  # (kind, pose, x, y, z_from, yaw)
    post: dict = field(default_factory=dict)


def screen_z(z_on_screen, y):
    """z that makes a point at depth y line up with z_on_screen at y=0 under the tilted ortho camera."""
    return z_on_screen - y * math.tan(math.radians(PITCH))


def hill_layer(name, rng, x_range, y, base, amp, scale, color, coll, bumps=None, z_bottom=-30.0):
    xs = np.linspace(x_range[0], x_range[1], 220)
    n = np.zeros_like(xs)
    for f, a in ((scale, 1.0), (scale / 2.3, 0.45), (scale / 6, 0.15)):
        ph = rng.random() * 10
        n += a * np.sin(xs / f + ph) + a * 0.5 * np.sin(xs / (f * 0.61) + ph * 1.7)
    top = base + amp * n
    if bumps is not None:
        for bx, bw, bh in bumps:
            top += bh * np.exp(-(((xs - bx) / bw) ** 2))
    verts, faces = [], []
    for i, (x, z) in enumerate(zip(xs, top)):
        verts += [(x, y, z), (x, y, z_bottom)]
        if i:
            a = 2 * i
            faces.append((a - 2, a, a + 1, a - 1))
    ob = core.mesh_object(name, verts, faces, coll=coll, smooth=False, recalc=False)
    core.set_material(ob, shaders.flat_shade(name, color))
    return ob


def tree(name, rng, base, height, canopy, trunk_mat, leaf_mat, coll, lean=0.0, leaf_tints=None):
    pts = [base + V((lean * (i / 4) ** 2, 0, height * i / 4)) for i in range(5)]
    rad = [0.32, 0.22, 0.18, 0.15, 0.12]
    rad = [r * height / 4.5 for r in rad]
    t = core.loft(f"{name}.trunk", [(p, r, r) for p, r in zip(pts, rad)], seg=12, cap=(None, 0.5), coll=coll)
    core.subsurf(t, 1)
    core.set_material(t, trunk_mat)
    top = pts[-1]
    centers, scales = [], []
    for _ in range(canopy):
        centers.append(np.array(top) + rng.normal(0, 1, 3) * np.array([0.8, 0.6, 0.45]) * height / 4.5)
        scales.append((0.75 + 0.55 * rng.random()) * height / 4.5)
    tints = leaf_tints if leaf_tints is not None else None
    ob = props.instance(
        f"{name}.canopy",
        props.rock(rng, 2, 0.35, 0.85),
        np.array(centers),
        scales=np.array(scales),
        rng=rng,
        tints=tints,
        material=leaf_mat,
        coll=coll,
    )
    core.subsurf(ob, 1)
    return t, ob


def scatter_layer(F, rng, name, templates, count, mat, coll, tints_hex, size=(0.6, 1.2), align=1.0, sink=0.0, **where):
    pts, nrm = F.scatter(rng, count, **where)
    if len(pts) == 0:
        return None
    sc = size[0] + (size[1] - size[0]) * rng.random(len(pts))
    pts = pts - nrm * sink
    tints = props.tint_palette(rng, tints_hex, len(pts))
    return props.instance(name, templates, pts, nrm, sc, align=align, rng=rng, tints=tints, material=mat, coll=coll)


def furnace(coll, base, rng):
    """Stone smelting furnace: a crafting station with a glowing mouth."""
    stone = core.principled("furnace.stone", "#6E625A", rough=0.9, bump=0.6, bump_scale=8)
    trim = core.principled("furnace.iron", "#3A3A40", rough=0.45, metal=1.0)
    b = V(base)
    body = core.loft(
        "furnace.body",
        [
            (b + V((0, 0, -0.2)), 0.62, 0.55, 3.0),
            (b + V((0, 0, 0.6)), 0.6, 0.53, 3.0),
            (b + V((0, 0, 1.15)), 0.5, 0.45, 2.6),
            (b + V((0, 0, 1.45)), 0.3, 0.28, 2.2),
        ],
        seg=24,
        cap=(0.2, 0.4),
        coll=coll,
    )
    core.subsurf(body, 2)
    core.set_material(body, stone)
    stones = props.instance(
        "furnace.stones",
        props.rock(rng, 1, 0.3, 0.55),
        np.array(
            [
                [b.x + 0.6 * math.cos(a), b.y - 0.5 * abs(math.sin(a)) - 0.05, b.z + 0.1 + 1.1 * (k % 5) / 5]
                for k, a in enumerate(np.linspace(-1.2, 1.2, 25))
            ]
        ),
        np.tile([0, -1, 0.2], (25, 1)),
        scales=0.11 + 0.05 * rng.random(25),
        rng=rng,
        tints=props.tint_palette(rng, ["#7A6C62", "#5E544E", "#8A7A6A"], 25),
        coll=coll,
        material=props.tinted_material("furnace.stones", rough=0.9),
    )
    core.subsurf(stones, 1)
    chim = core.loft(
        "furnace.chimney",
        [
            (b + V((-0.12, 0.05, 1.3)), 0.2, 0.2),
            (b + V((-0.16, 0.06, 2.4)), 0.16, 0.16),
            (b + V((-0.17, 0.06, 2.55)), 0.2, 0.2),
        ],
        seg=14,
        cap=(None, 0.0),
        coll=coll,
    )
    core.subsurf(chim, 1)
    core.set_material(chim, stone)
    mouth = core.ellipsoid("furnace.mouth", b + V((0.05, -0.5, 0.42)), (0.34, 0.12, 0.3), coll=coll)
    core.set_material(mouth, core.emission("furnace.fire", "#FF6A1A", 5.0))
    lip = core.loft(
        "furnace.lip",
        [(b + V((0.05, -0.56, 0.78)), 0.04, 0.42, 3.0), (b + V((0.05, -0.56, 0.86)), 0.04, 0.42, 3.0)],
        x_hint=(0, 0, 1),
        coll=coll,
        cap=(0.3, 0.3),
    )
    core.set_material(lip, trim)
    l1 = core.light("furnace.light", "POINT", b + V((0.05, -1.0, 0.5)), 140, color="#FF8C3A", size=0.3, coll=coll)
    l2 = core.light("furnace.glow", "POINT", b + V((0.0, -0.2, 2.8)), 40, color="#FF7A2A", size=0.4, coll=coll)
    return [body, chim, mouth, l1, l2]


def anvil(coll, base):
    iron = core.principled("anvil.iron", "#4A4D55", rough=0.35, metal=1.0, bump=0.05)
    wood = core.principled("anvil.stump", "#6A4A30", rough=0.8, bump=0.4, bump_scale=20)
    b = V(base)
    stump = core.loft(
        "anvil.stump",
        [(b + V((0, 0, -0.1)), 0.26, 0.26), (b + V((0, 0, 0.45)), 0.22, 0.22)],
        seg=14,
        cap=(0.0, 0.1),
        coll=coll,
    )
    core.subsurf(stump, 1)
    core.set_material(stump, wood)
    top = b.z + 0.55
    body = core.loft(
        "anvil.body",
        [
            (V((b.x - 0.42, b.y, top + 0.1)), 0.015, 0.015),
            (V((b.x - 0.22, b.y, top + 0.08)), 0.06, 0.07),
            (V((b.x - 0.05, b.y, top + 0.06)), 0.09, 0.11, 4.0),
            (V((b.x + 0.25, b.y, top + 0.06)), 0.09, 0.11, 4.0),
            (V((b.x + 0.27, b.y, top + 0.06)), 0.07, 0.1, 4.0),
        ],
        x_hint=(0, 0, 1),
        cap=(0.5, 0.3),
        coll=coll,
    )
    core.subsurf(body, 1)
    core.set_material(body, iron)
    foot = core.loft(
        "anvil.foot",
        [(V((b.x + 0.05, b.y, top - 0.02)), 0.07, 0.07, 3.0), (V((b.x + 0.05, b.y, b.z + 0.42)), 0.14, 0.15, 3.0)],
        coll=coll,
        cap=(0.2, 0.2),
    )
    core.subsurf(foot, 1)
    core.set_material(foot, iron)
    return [stump, body, foot]


def floating_embers(coll, rng, center, spread, count, color="#FFA040", strength=30.0):
    pts = np.array(center) + rng.normal(0, 1, (count, 3)) * np.array(spread)
    ob = props.instance(
        "embers",
        props.icosphere(0),
        pts,
        scales=0.012 + 0.02 * rng.random(count),
        rng=rng,
        coll=coll,
        material=core.emission("embers", color, strength),
    )
    return ob


# ---------------------------------------------------------------------------
# Moss & Ember
# ---------------------------------------------------------------------------


def moss_and_ember(coll, seed=7, res=0.08):
    rng = np.random.default_rng(seed)
    F = terrain.Field((-13.5, 13.5), (-10.5, 3.5), (-0.6, 7.5), res=res, seed=seed)
    xs = F.xs
    surf = 1.0 + 0.3 * np.sin(xs * 0.22 + 1.0) + 0.2 * F.noise1(3.0) + 1.2 * np.exp(-(((xs + 11.5) / 2.6) ** 2))
    surf += 0.45 * np.exp(-(((xs - 11.0) / 2.5) ** 2))
    F.set_surface(surf)
    F.tunnel(
        [(-10.2, 2.2, 0.95), (-8.8, 0.5, 1.05), (-7.4, -1.2, 1.1), (-5.8, -2.6, 1.15), (-4.2, -3.4, 1.2)],
        wobble=0.15,
        k=0.6,
    )
    F.chamber(
        1.2,
        -2.75,
        6.4,
        1.95,
        floor=lambda x: -4.55 + 0.12 * np.sin(x * 0.7) + 0.07 * np.cos(x * 1.9),
        k=0.6,
        wobble=0.22,
    )
    F.tunnel([(7.4, -3.7, 1.0), (8.9, -5.2, 1.0), (10.2, -6.6, 1.05)], wobble=0.15, k=0.6)
    F.tunnel(
        [(-3.0, -7.4, 0.95), (1.5, -7.5, 1.1), (6.0, -7.3, 1.15), (10.5, -7.2, 1.2), (14.5, -7.0, 1.2)],
        floor=lambda x: -8.3 + 0.1 * np.sin(x),
        wobble=0.15,
        k=0.6,
    )
    F.chamber(9.7, -1.5, 1.5, 0.8, floor=-2.2, wobble=0.18, k=0.4)
    F.build(pocket=3.0, pocket_var=0.6, relief=0.3, edge=0.14)
    ground = F.mesh("terrain", coll)
    mat = shaders.terrain_material(
        "moss_ember.terrain",
        strata=[
            (0.0, "#3A2C2A"),
            (0.3, "#5A4038"),
            (0.55, "#6E4E40"),
            (0.78, "#7E5A44"),
            (0.9, "#5A3F2E"),
            (1.0, "#3E2C22"),
        ],
        z_range=(-10.0, 1.4),
        cover=("#4E7A2E", "#86A63A"),
        cover_amount=0.75,
        veins=dict(color="#FF7A1E", strength=9.0, scale=0.8, width=0.022, amount=0.3, region_scale=0.35),
        front_dark=0.62,
        bump=0.45,
    )
    core.set_material(ground, mat)

    # Surface cover and trees.
    grass_mat = props.tinted_material("me.grass", rough=0.7, sss=0.2, sheen=0.3)
    leaf_mat = props.tinted_material("me.leaf", rough=0.75, sss=0.25, sheen=0.3)
    bark = shaders.bark_material("me.bark", dark="#3A2A22", light="#6A4E3A", moss="#5E8A34")
    is_surface = lambda c, n: c[:, 2] > np.interp(c[:, 0], xs, surf) - 0.5
    scatter_layer(
        F,
        rng,
        "me.grass",
        [props.tuft(rng, 9, 0.38, 0.025) for _ in range(6)],
        2200,
        grass_mat,
        coll,
        ["#5E8A2E", "#7AA03A", "#4D7428", "#93A844"],
        size=(0.5, 1.0),
        align=0.6,
        normal_min=0.55,
        y_range=(0.0, 7.4),
        mask=is_surface,
    )
    in_cave = lambda c, n: c[:, 2] < np.interp(c[:, 0], xs, surf) - 0.6
    scatter_layer(
        F,
        rng,
        "me.cave_grass",
        [props.tuft(rng, 6, 0.2, 0.02) for _ in range(4)],
        700,
        grass_mat,
        coll,
        ["#5E8A2E", "#4D7428", "#6E9638"],
        size=(0.6, 1.1),
        align=0.8,
        normal_min=0.6,
        y_range=(0.2, 3.4),
        mask=in_cave,
    )
    moss_mat = props.tinted_material("me.moss", rough=0.95, sheen=0.6)
    scatter_layer(
        F,
        rng,
        "me.moss",
        [props.rock(rng, 1, 0.4, 0.35) for _ in range(4)],
        900,
        moss_mat,
        coll,
        ["#3E6626", "#4E7A2E", "#35561F"],
        size=(0.07, 0.16),
        normal_min=0.45,
        y_range=(0.1, 3.6),
        mask=in_cave,
        sink=0.03,
    )
    for i, (x, y, h) in enumerate(
        [(-11.2, 5.6, 2.6), (-5.4, 6.6, 2.2), (4.2, 6.2, 2.8), (9.4, 5.0, 2.3), (12.4, 6.8, 2.6), (-1.6, 7.0, 1.9)]
    ):
        z = F.floor_at(x, y, 4.0)
        if z is None:
            continue
        tints = props.tint_palette(rng, ["#4F7A2C", "#6B9236", "#3E6526", "#8AA43E"], 16)
        tree(
            f"me.tree{i}",
            rng,
            V((x, y, z - 0.2)),
            h,
            16,
            bark,
            leaf_mat,
            coll,
            lean=rng.normal(0, 0.25),
            leaf_tints=tints,
        )

    # Cave dressing.
    rock_mat = props.tinted_material("me.pebbles", rough=0.85)
    scatter_layer(
        F,
        rng,
        "me.pebbles",
        [props.rock(rng, 1, 0.45, 0.6) for _ in range(5)],
        260,
        rock_mat,
        coll,
        ["#6B5A4E", "#5A4A40", "#7C6A5A"],
        size=(0.05, 0.16),
        normal_min=0.6,
        y_range=(0.1, 3.0),
        mask=in_cave,
    )
    strand_mat = props.tinted_material("me.strands", rough=0.9, sss=0.3, sheen=0.4)
    scatter_layer(
        F,
        rng,
        "me.strands",
        [props.strand(rng, 0.9, 0.035) for _ in range(6)],
        220,
        strand_mat,
        coll,
        ["#5E8A34", "#7AA040", "#4A6E2A"],
        size=(0.5, 1.4),
        align=0.0,
        normal_max=-0.55,
        y_range=(0.15, 2.6),
        mask=in_cave,
    )
    stal = scatter_layer(
        F,
        rng,
        "me.stalactites",
        [props.cone(7, 0.12, -0.6), props.cone(6, 0.08, -0.4)],
        70,
        rock_mat,
        coll,
        ["#5A4A40", "#6B5A4E"],
        size=(0.6, 1.3),
        align=0.0,
        normal_max=-0.7,
        y_range=(0.3, 2.8),
        mask=in_cave,
        sink=-0.05,
    )
    if stal:
        core.subsurf(stal, 1)
    cap_mat = props.tinted_material("me.mushroom", rough=0.5, sss=0.3, emit=1.2, emit_from_tint=True)
    shroom_pts, shroom_n = F.scatter(rng, 30, normal_min=0.7, y_range=(0.3, 2.6), mask=in_cave)
    props.instance(
        "me.mushrooms",
        [props.mushroom(rng, 0.22, 0.1), props.mushroom(rng, 0.3, 0.13)],
        shroom_pts,
        shroom_n,
        0.6 + 0.8 * rng.random(len(shroom_pts)),
        align=0.5,
        rng=rng,
        tints=props.tint_palette(rng, ["#D2552A", "#E0782E", "#B8402A"], len(shroom_pts)),
        material=cap_mat,
        coll=coll,
    )

    # Ember crystals: the prospector's target and the hidden pocket.
    ember_mat = props.tinted_material(
        "me.ember_crystal", rough=0.25, emit=2.6, emit_from_tint=True, transmission=0.3, coat=0.6
    )
    sites = [
        (8.0, 1.2, -3.2, (-1, 0, 0.1), 1.0),
        (9.6, 1.4, -2.15, (0, 0, 1), 0.7),
        (10.6, 1.2, -1.4, (-1, 0, 0), 0.6),
        (-3.4, 2.3, -4.4, (0.3, 0, 1), 0.6),
        (11.6, 1.5, -8.2, (0, 0, 1), 0.8),
        (3.6, 2.4, -0.95, (0, 0, -1), 0.55),
        (-1.8, 1.8, -7.9, (0, 0, 1), 0.6),
    ]
    for i, (x, y, z, n, s) in enumerate(sites):
        cl = props.crystal_cluster(rng, 6, s, 6, 0.6)
        pts = np.array([[x, y, z]])
        props.instance(
            f"me.ember{i}",
            cl,
            pts,
            np.array([n]),
            1.0,
            rng=rng,
            tints=props.tint_palette(rng, ["#FF5A12", "#FF7A1A"], 1),
            material=ember_mat,
            coll=coll,
        )
        core.light(
            f"me.ember_light{i}",
            "POINT",
            (x - 0.2 * n[0], y - 0.6, z + 0.3 * n[2] + 0.2),
            180 * s,
            color="#FF8A30",
            size=0.3,
            coll=coll,
        )

    # Crafting station.
    fx = -1.6
    fz = F.floor_at(fx, 1.9, -2.5)
    furnace(coll, (fx, 1.9, fz), rng)
    ax = 0.3
    az = F.floor_at(ax, 1.5, -2.5)
    anvil(coll, (ax, 1.5, az))
    floating_embers(coll, rng, (fx + 0.2, 1.4, fz + 2.2), (0.6, 0.3, 0.9), 30, strength=12.0)

    # Lighting.
    shaders.sky_world(
        [(0.0, "#F7C98E"), (0.62, "#F2B07E"), (0.8, "#C9868E"), (1.0, "#4C5288")],
        ambient="#5A6A8A",
        ambient_strength=0.25,
    )
    core.light(
        "me.sun", "SUN", (0, 0, 20), 3.2, color="#FFD2A0", size=math.radians(3), rotation=(52, -38, 0), coll=coll
    )
    core.light("me.cave_fill", "AREA", (0.5, -6.0, -3.5), 260, color="#7FA0D8", size=14, rotation=(90, 0, 0), coll=coll)
    core.light(
        "me.mouth_fill", "AREA", (-6.5, -3.0, 0.5), 120, color="#FFC890", size=4, rotation=(70, 0, -20), coll=coll
    )

    # Parallax hills.
    hill_layer(
        "me.hills_far",
        rng,
        (-40, 40),
        40.0,
        screen_z(2.4, 40.0),
        0.9,
        7.0,
        "#B98AA0",
        coll,
        bumps=[(-6, 4, 1.2), (14, 5, 1.6)],
    )
    hill_layer(
        "me.hills_mid", rng, (-40, 40), 22.0, screen_z(1.7, 22.0), 0.7, 4.0, "#7A6E8E", coll, bumps=[(8, 2.5, 0.9)]
    )
    hill_layer("me.hills_near", rng, (-40, 40), 12.0, screen_z(1.2, 12.0), 0.55, 2.2, "#4E5E6A", coll)

    sc = Scene("moss_and_ember", F, camera_target=(0.0, 1.5, -2.35), width=22.0)
    sc.details = [("forge", (-0.4, 1.5, -3.3), 7.5)]
    sc.cast = [
        ("prospector", "mine_strike", 6.75, 1.3, -2.5, -18.0),
        ("warden", "hammer_raise", -0.65, 1.2, -2.5, -22.0),
        ("pathfinder", "idle_lantern", -7.0, 1.4, -0.5, -28.0),
    ]
    return sc


# ---------------------------------------------------------------------------
# The Opal Deep
# ---------------------------------------------------------------------------


def ruin_pillar(coll, base, height, mat, rng, broken=False, name="ruin"):
    b = V(base)
    rings = [
        (b + V((0, 0, -0.3)), 0.42, 0.42, 4.0),
        (b + V((0, 0, 0.25)), 0.4, 0.4, 4.0),
        (b + V((0, 0, 0.32)), 0.3, 0.3, 6.0),
        (b + V((0, 0, height - 0.3)), 0.28, 0.28, 6.0),
        (b + V((0, 0, height - 0.22)), 0.38, 0.38, 4.0),
        (b + V((0, 0, height)), 0.4, 0.4, 4.0),
    ]
    if broken:
        rings = rings[:4]
        rings[-1] = (b + V((rng.normal(0, 0.05), 0, height * 0.55)), 0.27, 0.27, 6.0)
    ob = core.loft(f"{name}.pillar", rings, seg=24, cap=(0.1, 0.25 if not broken else 0.6), coll=coll)
    core.subsurf(ob, 1)
    core.set_material(ob, mat)
    return ob


def opal_deep(coll, seed=11, res=0.08):
    rng = np.random.default_rng(seed)
    F = terrain.Field((-13.5, 13.5), (-7.5, 7.5), (-0.6, 6.5), res=res, seed=seed)

    def floor(x):
        basin = -1.25 * np.exp(-(((x - 0.8) / 3.4) ** 4))
        return -3.4 + basin + 0.15 * np.sin(x * 0.8) + 0.25 * np.tanh((x - 6.5) * 0.6)

    F.chamber(0.2, 0.0, 10.2, 3.9, floor=floor, k=0.7, wobble=0.35)
    F.tunnel([(-14.5, 3.2, 1.1), (-11.5, 2.9, 1.15), (-8.8, 2.6, 1.1)], floor=1.95, wobble=0.12, k=0.7)
    F.tunnel([(8.5, -2.6, 1.0), (11.0, -3.4, 1.1), (14.5, -3.6, 1.1)], floor=-4.0, wobble=0.12, k=0.6)
    F.chamber(-9.5, -5.2, 2.6, 1.1, floor=-6.0, wobble=0.2, k=0.5)
    F.solid_blob([(5.6, -4.5, 0.75), (5.35, -1.5, 0.42), (5.3, 1.5, 0.4), (5.6, 4.4, 0.9)])
    F.solid_blob([(-8.6, 1.9, 0.55), (-6.6, 1.8, 0.45), (-5.6, 1.7, 0.3)])
    F.build(pocket=3.4, pocket_var=0.8, relief=0.38, edge=0.16, back_relief=0.55)
    ground = F.mesh("terrain", coll)
    mat = shaders.terrain_material(
        "opal.terrain",
        strata=[(0.0, "#2A2E4A"), (0.3, "#3A3E62"), (0.55, "#4A4E74"), (0.8, "#3E4468"), (1.0, "#343858")],
        z_range=(-7.0, 7.0),
        cover=("#4A5A82", "#5E6E96"),
        cover_amount=0.35,
        front_dark=0.5,
        bump=0.55,
        lichen=("#4FE0D0", 0.3, 5.0),
        rock_scale=1.1,
    )
    core.set_material(ground, mat)

    in_view = dict(y_range=(0.15, 3.6))
    opal = ["#C9A8FF", "#7FE6E0", "#FF9ED2", "#9FB8FF"]
    crystal_mat = props.tinted_material(
        "opal.crystal",
        rough=0.12,
        emit=0.45,
        emit_from_tint=True,
        transmission=0.4,
        coat=1.0,
        iridescent=["#7FF2E8", "#B89CFF", "#FF9AD5", "#FFF2C0"],
    )
    big_sites = [
        (-3.5, 2.0, None, 1.6),
        (4.6, 2.6, None, 1.1),
        (8.6, 1.8, None, 1.0),
        (-11.8, 1.6, 2.0, 0.9),
        (0.6, 2.0, "ceil", 1.5),
        (-5.4, 2.4, "ceil", 1.1),
        (7.6, 2.2, "ceil", 0.9),
    ]
    for i, (x, y, zf, s) in enumerate(big_sites):
        if zf == "ceil":
            z = F.ceiling_at(x, y, 0.0)
            n = (0, 0, -1)
        else:
            z = F.floor_at(x, y, 0.0 if zf is None else zf)
            n = (0, 0, 1)
        if z is None:
            continue
        cl = props.crystal_cluster(rng, 7, s, 6, 0.7)
        props.instance(
            f"opal.big{i}",
            cl,
            np.array([[x, y, z - 0.05 * n[2]]]),
            np.array([n]),
            1.0,
            rng=rng,
            tints=props.tint_palette(rng, opal, 1, 0.02),
            material=crystal_mat,
            coll=coll,
        )
        col = ["#7FE8F0", "#C8A0FF", "#FF9ACF"][i % 3]
        core.light(f"opal.light{i}", "POINT", (x, y - 0.9, z + 0.7 * n[2] * s), 320 * s, color=col, size=0.6, coll=coll)
    small = [props.crystal_cluster(rng, 4, 0.35, 6, 0.8) for _ in range(5)]
    scatter_layer(
        F,
        rng,
        "opal.small",
        small,
        120,
        crystal_mat,
        coll,
        opal,
        size=(0.5, 1.2),
        align=0.85,
        normal_min=0.5,
        **in_view,
    )
    scatter_layer(
        F,
        rng,
        "opal.small_ceiling",
        small,
        60,
        crystal_mat,
        coll,
        opal,
        size=(0.5, 1.0),
        align=0.9,
        normal_max=-0.5,
        **in_view,
    )
    rock_mat = props.tinted_material("opal.stone", rough=0.8)
    stal = scatter_layer(
        F,
        rng,
        "opal.stalactites",
        [props.cone(8, 0.16, -1.0), props.cone(7, 0.1, -0.6)],
        90,
        rock_mat,
        coll,
        ["#2E3250", "#3A3E5E", "#262A44"],
        size=(0.6, 1.5),
        align=0.0,
        normal_max=-0.75,
        sink=-0.05,
        **in_view,
    )
    if stal:
        core.subsurf(stal, 1)
    mite = scatter_layer(
        F,
        rng,
        "opal.stalagmites",
        [props.cone(8, 0.2, 0.8), props.cone(7, 0.14, 0.5)],
        40,
        rock_mat,
        coll,
        ["#2E3250", "#3A3E5E"],
        size=(0.6, 1.4),
        align=0.0,
        normal_min=0.8,
        sink=0.05,
        **in_view,
    )
    if mite:
        core.subsurf(mite, 1)
    glow_moss = props.tinted_material("opal.glowmoss", rough=0.9, emit=0.8, emit_from_tint=True, sheen=0.5)
    scatter_layer(
        F,
        rng,
        "opal.glowmoss",
        [props.rock(rng, 1, 0.4, 0.3) for _ in range(4)],
        450,
        glow_moss,
        coll,
        ["#2A8A88", "#3AA0A0", "#2C6E8A"],
        size=(0.05, 0.14),
        normal_min=0.55,
        sink=0.02,
        **in_view,
    )
    spores = rng.random((60, 3)) * np.array([22, 2.6, 8]) + np.array([-11, 0.5, -3.0])
    props.instance(
        "opal.spores",
        props.icosphere(0),
        spores,
        scales=0.012 + 0.02 * rng.random(60),
        rng=rng,
        material=core.emission("opal.spores", "#9FFFF0", 12.0),
        coll=coll,
    )

    # Underground lake.
    wz = -3.95
    lake = core.mesh_object(
        "opal.lake", [(-5.0, 0.02, wz), (7.0, 0.02, wz), (7.0, 4.5, wz), (-5.0, 4.5, wz)], [(0, 1, 2, 3)], coll=coll
    )
    core.set_material(lake, shaders.water_material("opal.water", deep="#123A58", glow="#3AD0D8", glow_strength=3.0))
    core.light(
        "opal.lake_glow", "AREA", (0.8, 1.6, wz + 0.15), 160, color="#3AD0D8", size=7, rotation=(180, 0, 0), coll=coll
    )

    # Ruins: a discovery on the far shore.
    ruin_mat = core.principled("opal.ruin", "#5E5F80", rough=0.8, bump=0.5, bump_scale=6)
    for i, (x, y, h, broken) in enumerate([(7.6, 2.4, 3.0, False), (9.4, 2.6, 3.0, True), (11.2, 2.4, 2.9, False)]):
        z = F.floor_at(x, y, 0.0)
        if z is not None:
            ruin_pillar(coll, (x, y, z), h, ruin_mat, rng, broken, name=f"opal.ruin{i}")
    zl = F.floor_at(7.6, 2.4, 0.0)
    if zl is not None:
        lintel = core.loft(
            "opal.lintel",
            [(V((7.0, 2.4, zl + 3.2)), 0.25, 0.32, 4.0), (V((9.2, 2.4, zl + 3.15)), 0.25, 0.32, 4.0)],
            x_hint=(0, 0, 1),
            cap=(0.1, 0.4),
            coll=coll,
        )
        core.subsurf(lintel, 1)
        core.set_material(lintel, ruin_mat)
        glyph = core.ellipsoid("opal.glyph", (8.5, 2.05, zl + 1.9), (0.16, 0.03, 0.24), coll=coll)
        core.set_material(glyph, core.emission("opal.glyph", "#7AE8FF", 3.0))
        core.light("opal.glyph_light", "POINT", (8.5, 1.4, zl + 1.9), 120, color="#9AF0FF", size=0.4, coll=coll)

    shaders.sky_world([(0.0, "#05060C"), (1.0, "#0A0C18")], ambient="#2A3460", ambient_strength=0.8)
    core.light("opal.fill", "AREA", (0.0, -7.0, 1.0), 1100, color="#7A8CFF", size=18, rotation=(90, 0, 0), coll=coll)
    core.light("opal.rim", "AREA", (0.0, 6.5, 3.0), 120, color="#E0A0FF", size=14, rotation=(-80, 0, 0), coll=coll)

    sc = Scene("opal_deep", F, camera_target=(0.0, 1.5, -0.6), width=22.0)
    sc.details = [("crystal_hall", (-6.8, 1.5, -1.0), 9.0)]
    sc.cast = [
        ("pathfinder", "idle_lantern", -9.6, 1.5, 3.5, -24.0),
        ("prospector", "mine_windup", -5.3, 1.4, 0.0, -24.0),
        ("warden", "guard", 7.0, 1.0, 0.0, -30.0),
    ]
    sc.post = dict(bloom=0.55, vignette=0.32)
    return sc


# ---------------------------------------------------------------------------
# Roots of Giants
# ---------------------------------------------------------------------------


def root(name, points, coll, mat, seg=16):
    pts = terrain.catmull(points, step=0.25)
    rings = [(V((x, y, z)), r, r * 0.92) for x, y, z, r in pts]
    ob = core.loft(name, rings, seg=seg, cap=(0.6, 0.9), x_hint=(0, 0, 1), coll=coll)
    core.subsurf(ob, 1)
    core.set_material(ob, mat)
    return ob


def shaft(name, top, bottom, width, coll, color="#FFE2A8", strength=1.4):
    t, b = V(top), V(bottom)
    side = V((1, 0, 0)) * width / 2
    vs = [b - side * 0.6, b + side * 0.6, t + side, t - side]
    ob = core.mesh_object(name, vs, [(0, 1, 2, 3)], coll=coll, smooth=False, recalc=False)
    core.set_material(ob, shaders.shaft_material(name, color, strength))
    ob.visible_shadow = False
    return ob


def roots_of_giants(coll, seed=23, res=0.08):
    rng = np.random.default_rng(seed)
    F = terrain.Field((-13.5, 13.5), (-9.5, 4.5), (-0.6, 8.0), res=res, seed=seed)
    xs = F.xs
    surf = 1.6 + 0.25 * np.sin(xs * 0.3) + 0.15 * F.noise1(2.0) + 0.9 * np.exp(-(((xs + 3.0) / 3.5) ** 2))
    F.set_surface(surf)
    # Hollows follow the paths roots have pushed through the earth.
    F.tunnel(
        [(-6.0, -0.6, 1.25), (-9.0, -2.2, 1.35), (-11.5, -3.6, 1.3), (-14.5, -4.4, 1.3)],
        floor=lambda x: -4.9 + 0.35 * np.tanh((x + 9.0) * 0.5) + 0.06 * np.sin(x * 2),
        wobble=0.18,
        k=0.7,
    )
    F.chamber(1.0, -2.6, 5.6, 2.0, floor=lambda x: -4.1 + 0.12 * np.sin(x * 0.9), k=0.8, wobble=0.25)
    F.tunnel(
        [(5.5, -3.3, 1.3), (8.5, -4.6, 1.4), (11.0, -5.8, 1.3), (14.5, -6.4, 1.3)],
        floor=lambda x: -6.8 + 0.6 * np.tanh(-(x - 7.5) * 0.6) + 0.06 * np.sin(x),
        wobble=0.18,
        k=0.7,
    )
    F.chamber(-2.0, -7.4, 4.0, 1.25, floor=-8.3, wobble=0.22, k=0.5)
    F.tunnel([(-4.6, -4.6, 0.9), (-3.4, -6.2, 0.95)], wobble=0.12, k=0.5)
    F.tunnel([(3.4, -1.0, 0.7), (3.0, 0.4, 0.55), (2.7, 1.6, 0.45)], wobble=0.08, k=0.4)
    F.build(pocket=3.2, pocket_var=0.7, relief=0.34, edge=0.16)
    ground = F.mesh("terrain", coll)
    mat = shaders.terrain_material(
        "roots.terrain",
        strata=[(0.0, "#2A2018"), (0.35, "#4A3424"), (0.65, "#5E4430"), (0.85, "#4A3626"), (1.0, "#30241A")],
        z_range=(-9.5, 1.8),
        cover=("#5A7A2A", "#8AA040"),
        cover_amount=0.6,
        front_dark=0.6,
        bump=0.5,
        lichen=("#E8C060", 0.35, 3.0),
    )
    core.set_material(ground, mat)

    bark = shaders.bark_material("roots.bark", dark="#3A2A1E", light="#7E5E40", moss="#5E7A30", scale=2.6)
    # The giant: a trunk rising out of frame with buttress roots.
    tx, ty = -3.4, 4.6
    tz = F.floor_at(tx, ty, 6.0) or 2.0
    trunk = core.loft(
        "roots.trunk",
        [
            (V((tx, ty, tz - 1.5)), 3.9, 2.6),
            (V((tx, ty, tz + 0.3)), 3.1, 2.3),
            (V((tx + 0.1, ty, tz + 2.0)), 2.4, 2.0),
            (V((tx + 0.2, ty, tz + 9.0)), 2.1, 1.9),
        ],
        seg=32,
        cap=(0.4, 0.4),
        coll=coll,
    )
    core.subsurf(trunk, 1)
    core.set_material(trunk, bark)
    paths = [
        [
            (-3.6, 4.2, 2.4, 0.95),
            (-5.4, 2.6, 0.4, 0.8),
            (-7.6, 2.2, -1.4, 0.65),
            (-10.0, 2.4, -2.6, 0.5),
            (-13.5, 2.6, -3.0, 0.38),
        ],
        [
            (-2.2, 4.0, 2.2, 0.9),
            (0.0, 2.6, 0.6, 0.75),
            (2.0, 2.0, -0.6, 0.62),
            (4.6, 2.3, -1.4, 0.5),
            (7.8, 2.6, -2.3, 0.42),
            (11.0, 3.0, -3.4, 0.33),
            (14.0, 3.0, -4.0, 0.25),
        ],
        [
            (-1.4, 4.6, 1.8, 0.8),
            (1.6, 3.6, -0.2, 0.55),
            (3.8, 3.4, -1.8, 0.45),
            (6.0, 3.6, -3.6, 0.35),
            (8.0, 3.8, -5.6, 0.28),
            (9.4, 3.8, -8.5, 0.2),
        ],
        [
            (-4.8, 3.8, 1.6, 0.7),
            (-5.6, 2.6, -1.6, 0.48),
            (-4.4, 2.8, -4.2, 0.38),
            (-2.8, 3.0, -6.6, 0.3),
            (-1.0, 3.2, -9.0, 0.22),
        ],
        [(-2.6, 1.4, -1.2, 0.32), (-0.6, 0.9, -1.7, 0.36), (1.8, 0.8, -1.2, 0.3), (3.8, 1.0, -0.4, 0.22)],
        [(6.5, 0.9, -2.6, 0.22), (8.4, 1.2, -3.4, 0.3), (10.8, 1.0, -4.3, 0.26), (13.5, 1.2, -4.6, 0.2)],
    ]
    for i, p in enumerate(paths):
        root(f"roots.root{i}", p, coll, bark)
    # Buttress roots arch over the ground before diving in.
    for i, p in enumerate(
        [
            [
                (tx - 1.6, ty - 1.2, tz + 1.4, 0.75),
                (tx - 3.4, ty - 1.6, tz + 0.5, 0.55),
                (tx - 5.2, ty - 1.8, tz - 0.1, 0.42),
                (tx - 6.6, ty - 1.6, tz - 1.0, 0.3),
            ],
            [
                (tx + 1.4, ty - 1.3, tz + 1.3, 0.7),
                (tx + 3.0, ty - 1.9, tz + 0.5, 0.52),
                (tx + 4.6, ty - 2.2, tz - 0.1, 0.38),
                (tx + 5.8, ty - 2.2, tz - 0.9, 0.26),
            ],
            [
                (tx - 0.2, ty - 1.6, tz + 1.2, 0.6),
                (tx - 0.6, ty - 2.6, tz + 0.3, 0.45),
                (tx - 1.0, ty - 3.2, tz - 0.6, 0.3),
            ],
        ]
    ):
        root(f"roots.buttress{i}", p, coll, bark)

    tendril_mat = props.tinted_material("roots.tendril", rough=0.85, sss=0.2)
    in_cave = lambda c, n: c[:, 2] < np.interp(c[:, 0], xs, surf) - 0.6
    scatter_layer(
        F,
        rng,
        "roots.tendrils",
        [props.strand(rng, 1.5, 0.03, 8) for _ in range(8)],
        140,
        tendril_mat,
        coll,
        ["#4A3422", "#5E4430", "#3A2A1C"],
        size=(0.4, 1.4),
        align=0.0,
        normal_max=-0.55,
        y_range=(0.15, 3.2),
        mask=in_cave,
    )
    grass_mat = props.tinted_material("roots.grass", rough=0.7, sss=0.2, sheen=0.3)
    is_surface = lambda c, n: c[:, 2] > np.interp(c[:, 0], xs, surf) - 0.5
    scatter_layer(
        F,
        rng,
        "roots.grass",
        [props.tuft(rng, 9, 0.34, 0.025) for _ in range(6)],
        2000,
        grass_mat,
        coll,
        ["#5A7A2A", "#7A9A36", "#4A6A22", "#9AAA44"],
        size=(0.5, 1.0),
        align=0.6,
        normal_min=0.55,
        y_range=(0.0, 7.9),
        mask=is_surface,
    )
    fern_mat = props.tinted_material("roots.ferns", rough=0.7, sss=0.25, sheen=0.3)
    scatter_layer(
        F,
        rng,
        "roots.ferns",
        [props.tuft(rng, 12, 0.6, 0.05, 0.9) for _ in range(4)],
        140,
        fern_mat,
        coll,
        ["#4E7A2A", "#6A8E34"],
        size=(0.6, 1.2),
        align=0.5,
        normal_min=0.6,
        y_range=(0.0, 7.9),
        mask=is_surface,
    )
    cap_mat = props.tinted_material("roots.fungus", rough=0.5, sss=0.4, emit=0.9, emit_from_tint=True)
    pts, nn = F.scatter(rng, 90, normal_min=0.65, y_range=(0.3, 3.0), mask=in_cave)
    props.instance(
        "roots.fungus",
        [props.mushroom(rng, 0.2, 0.09), props.mushroom(rng, 0.28, 0.12)],
        pts,
        nn,
        0.6 + 0.9 * rng.random(len(pts)),
        align=0.5,
        rng=rng,
        tints=props.tint_palette(rng, ["#D89A2A", "#C8781E", "#E0B040"], len(pts)),
        material=cap_mat,
        coll=coll,
    )
    moss_mat = props.tinted_material("roots.moss", rough=0.95, sheen=0.6)
    scatter_layer(
        F,
        rng,
        "roots.moss",
        [props.rock(rng, 1, 0.4, 0.35) for _ in range(4)],
        700,
        moss_mat,
        coll,
        ["#4A6A26", "#5A7A2E", "#3A5A1E"],
        size=(0.06, 0.15),
        normal_min=0.45,
        y_range=(0.1, 3.4),
        mask=in_cave,
        sink=0.03,
    )
    motes = rng.random((120, 3)) * np.array([22, 2.5, 7]) + np.array([-11, 0.6, -8])
    props.instance(
        "roots.motes",
        props.icosphere(0),
        motes,
        scales=0.012 + 0.018 * rng.random(120),
        rng=rng,
        material=core.emission("roots.motes", "#FFE09A", 10.0),
        coll=coll,
    )

    # Light falls through the shaft beside the trunk.
    shaft("roots.shaft0", (2.9, 1.9, 1.0), (1.4, 1.9, -4.2), 1.5, coll, color="#FFD890", strength=0.45)
    shaft("roots.shaft1", (3.2, 2.1, 0.9), (2.4, 2.1, -4.2), 0.8, coll, color="#FFD890", strength=0.35)
    core.light(
        "roots.shaft_light",
        "SPOT",
        (3.0, 1.8, 2.5),
        900,
        color="#FFE0A0",
        size=0.3,
        spot=(28, 0.6),
        rotation=(0, 12, 0),
        coll=coll,
    )

    shaders.sky_world([(0.0, "#D8E8B0"), (0.7, "#BFE0C8"), (1.0, "#7FB8C8")], ambient="#6A7A60", ambient_strength=0.22)
    core.light(
        "roots.sun", "SUN", (0, 0, 20), 3.0, color="#FFEAC0", size=math.radians(2), rotation=(40, 20, 0), coll=coll
    )
    core.light(
        "roots.cave_fill", "AREA", (0.0, -6.0, -4.0), 520, color="#B8C8A0", size=16, rotation=(90, 0, 0), coll=coll
    )
    for i, (x, y, z) in enumerate([(-9.0, 1.2, -2.6), (-2.0, 1.4, -7.4), (9.4, 1.2, -5.2), (-5.5, 1.4, -0.4)]):
        core.light(f"roots.fungus_light{i}", "POINT", (x, y, z), 140, color="#FFC060", size=0.4, coll=coll)
    hill_layer(
        "roots.far",
        rng,
        (-40, 40),
        36.0,
        screen_z(3.6, 36.0),
        0.8,
        3.0,
        "#9FC0A8",
        coll,
        bumps=[(6, 1.6, 1.4), (12, 1.2, 1.6), (-12, 1.4, 1.2)],
    )
    hill_layer(
        "roots.mid",
        rng,
        (-40, 40),
        20.0,
        screen_z(2.8, 20.0),
        0.7,
        1.8,
        "#6E9A78",
        coll,
        bumps=[(9, 1.0, 1.4), (-9, 1.2, 1.2)],
    )

    sc = Scene("roots_of_giants", F, camera_target=(0.0, 1.5, -1.9), width=22.0)
    sc.details = [("root_hall", (0.6, 1.5, -2.4), 7.5)]
    sc.cast = [
        ("pathfinder", "run", -9.6, 1.35, -1.5, -20.0),
        ("prospector", "idle", 0.4, 1.3, -1.5, -32.0),
        ("warden", "guard", 9.6, 1.2, -4.0, -150.0),
    ]
    sc.post = dict(bloom=0.45, vignette=0.3)
    return sc
