"""Biome scenes: generation rules, dressing, stations, lighting and cast.

Each biome supplies rules to worldgen (which landmarks exist, how they grow
from one another, which are sealed) and a seed. The solved world drives the
terrain, and every station, landmark prop, light and explorer is placed
relative to generated landmarks, routes and floors. The fixed inputs are the
rules, the seed and the camera window.
"""

import math
from dataclasses import dataclass, field

import numpy as np
from mathutils import Vector

from . import core, props, shaders, terrain, worldgen

V = Vector
PITCH = 10.0


@dataclass
class Scene:
    name: str
    field: terrain.Field
    camera_target: tuple
    width: float
    details: list = field(default_factory=list)  # (suffix, target, width)
    solution: object = None
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
    uv = ob.data.uv_layers.new(name="UVMap")
    for li, co in zip(ob.data.polygons[0].loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = co
    core.set_material(ob, shaders.shaft_material(name, color, strength))
    ob.visible_shadow = False
    return ob


# ---------------------------------------------------------------------------
# Generation rules (worldgen plans)
# ---------------------------------------------------------------------------


def _steps(specs, parents):
    for sp, par in zip(specs, parents):
        sp["from"] = par
    return specs


def moss_rules(rng):
    """Surface meadow; a mouth drops to a forge hall, then an ember seam, a descent east and a lower gallery.
    A sealed pocket near the seam waits for mining to open it."""
    b = (-13.5, 13.5, -11.25, 3.75)
    surf = worldgen.surface_line(rng, b[0], b[1], base=1.0, amp=0.45, scale=4.0, bumps=[(-11.5, 2.6, 1.0)])
    mx = rng.uniform(-11.8, -10.4)
    mouth = worldgen.Landmark("mouth", "surface", mx, float(surf(mx)), 0.0, 0.0)
    steps = _steps(
        [
            dict(name="forge", role="station", side=1, gap=(5.0, 7.0), depth=(5.4, 6.2), rx=(3.8, 4.6), rz=(1.6, 1.9)),
            dict(name="seam", role="deposit", side=1, gap=(1.2, 2.4), dz=(-0.9, 0.3), rx=(1.8, 2.3), rz=(1.2, 1.5)),
            dict(
                name="east",
                role="exit",
                side=1,
                gap=(1.2, 3.5),
                dz=(-3.6, -2.6),
                rx=(1.6, 2.0),
                rz=(1.0, 1.2),
                x=(11.8, 13.4),
            ),
            dict(
                name="gallery", role="passage", side=-1, gap=(0.8, 2.6), dz=(-0.5, 0.5), rx=(3.0, 4.0), rz=(1.0, 1.25)
            ),
            dict(
                name="pocket",
                role="discovery",
                gap=(0.6, 2.0),
                dz=(1.6, 2.8),
                rx=(1.5, 1.9),
                rz=(0.9, 1.1),
                connect=False,
                crust=1.2,
            ),
        ],
        ["mouth", "forge", "seam", "east", "seam"],
    )
    lms, routes = worldgen.grow(rng, surf, b, mouth, steps)
    routes += worldgen.add_loops(rng, lms, routes, n=1)
    return worldgen.Plan(b, surf, lms, routes)


def opal_rules(rng):
    """No surface. A high western ledge leads down to a crystal grotto, a lake hall with a basin, a ruin
    chamber and an eastern exit. A sealed cistern lies below the grotto."""
    b = (-13.5, 13.5, -8.25, 7.5)
    west = worldgen.Landmark("west", "exit", -12.6, rng.uniform(1.4, 2.6), rng.uniform(1.6, 2.0), rng.uniform(1.0, 1.2))
    steps = _steps(
        [
            dict(name="grotto", role="crystal", side=1, gap=(1.4, 2.6), dz=(-2.6, -1.8), rx=(2.3, 2.8), rz=(2.3, 2.8)),
            dict(
                name="lake",
                role="lake",
                side=1,
                gap=(0.4, 1.2),
                dz=(-1.0, 0.0),
                rx=(3.0, 3.6),
                rz=(3.2, 3.8),
                basin=(1.0, 1.4),
            ),
            dict(name="ruins", role="ruins", side=1, gap=(0.4, 1.2), dz=(-0.2, 0.9), rx=(2.0, 2.5), rz=(2.3, 2.7)),
            dict(
                name="east",
                role="exit",
                side=1,
                gap=(0.6, 2.0),
                dz=(-1.6, -0.2),
                rx=(1.5, 1.9),
                rz=(1.0, 1.2),
                x=(11.8, 13.4),
            ),
            dict(
                name="cistern",
                role="discovery",
                gap=(0.4, 2.4),
                dz=(-4.6, -3.6),
                rx=(1.8, 2.3),
                rz=(0.8, 1.0),
                connect=False,
            ),
        ],
        ["west", "grotto", "lake", "ruins", "grotto"],
    )
    lms, routes = worldgen.grow(rng, None, b, west, steps)
    routes += worldgen.add_loops(rng, lms, routes, n=1)
    return worldgen.Plan(b, None, lms, routes)


def opal_water(sol):
    """Water fills the lake's basin up to just below its rim."""
    lake = sol.plan.landmark("lake")
    level = lake.floor - 0.15
    X, Z = np.meshgrid(sol.xs, sol.zs)
    return (~sol.solid) & (Z <= level) & (np.abs(X - lake.x) < lake.rx * 0.95) & (Z >= lake.floor - lake.basin - 1.0)


def roots_rules(rng):
    """A giant's trunk on the surface. One way down beside it reaches a root hall; a hollow lies under the
    trunk, a deep grove beyond it, and exits east and west. A crack from the hollow lets light in."""
    b = (-13.5, 13.5, -10.5, 4.5)
    surf = worldgen.surface_line(rng, b[0], b[1], base=1.6, amp=0.3, scale=4.5)
    tx = rng.uniform(-3.5, -1.0)
    trunk = worldgen.Landmark("trunk", "surface", tx, float(surf(tx)), 0.0, 0.0)
    steps = _steps(
        [
            dict(name="hall", role="hall", side=1, gap=(4.0, 5.5), depth=(5.0, 5.8), rx=(3.0, 3.6), rz=(1.6, 1.9)),
            dict(name="hollow", role="hollow", side=-1, gap=(1.2, 2.6), dz=(-1.4, -0.4), rx=(2.2, 2.8), rz=(1.3, 1.6)),
            dict(
                name="east",
                role="exit",
                side=1,
                gap=(1.0, 3.0),
                dz=(-3.0, -1.8),
                rx=(1.6, 2.0),
                rz=(1.1, 1.3),
                x=(11.8, 13.4),
            ),
            dict(name="grove", role="grove", side=-1, gap=(0.4, 1.4), dz=(-3.4, -2.4), rx=(2.2, 2.6), rz=(1.1, 1.4)),
            dict(
                name="west",
                role="exit",
                side=-1,
                gap=(0.4, 2.0),
                dz=(-0.6, 0.8),
                rx=(1.5, 1.9),
                rz=(1.0, 1.2),
                x=(-13.4, -11.8),
            ),
        ],
        ["trunk", "hall", "hall", "hollow", "grove"],
    )
    lms, routes = worldgen.grow(rng, surf, b, trunk, steps)
    routes += worldgen.add_loops(rng, lms, routes, n=1)
    hollow = next(lm for lm in lms if lm.name == "hollow")
    cx = hollow.x + rng.uniform(0.3, 0.6) * hollow.rx
    crack = [(cx, hollow.floor + hollow.rz * 1.2), (cx + rng.normal(0, 0.3), float(surf(cx)) + 1.0)]
    routes.append(worldgen.route_path("hollow", "sky", crack, 0.42, "light", walk=False))
    return worldgen.Plan(b, surf, lms, routes)


# ---------------------------------------------------------------------------
# Placement helpers
# ---------------------------------------------------------------------------

VIEW_X = (-11.0, 11.0)


def frame(sol, top_pad=2.4, bottom_pad=0.8, min_width=22.0):
    """Camera target and width showing the window's surface (or highest ceiling) down to its lowest routed floor."""
    plan = sol.plan
    xs = np.linspace(*VIEW_X, 60)
    near = [
        lm for lm in plan.landmarks if VIEW_X[0] - 1.5 < lm.x < VIEW_X[1] + 1.5 and lm.role != "surface" and lm.connect
    ]
    bottom = min(lm.floor - lm.basin for lm in near) - bottom_pad
    if plan.surface is not None:
        top = float(np.max(plan.surface(xs))) + top_pad
    else:
        top = max(lm.floor + lm.rz * 1.7 for lm in near) + 0.9
    width = max(min_width, (top - bottom) * 16 / 9)
    zc = (top + bottom) / 2 - 1.5 * math.sin(math.radians(PITCH))
    return (0.0, 1.5, zc), width


def wall_at(F, x, y, z, direction, limit=6.0, step=0.05):
    """First solid x marching from (x, z) in direction (+1 or -1) at depth y."""
    xs = x + direction * np.arange(0.0, limit, step)
    vals = F.sample(np.stack([xs, np.full_like(xs, y), np.full_like(xs, z)], axis=1))
    hit = np.nonzero(vals > 0)[0]
    return float(xs[hit[0]]) if len(hit) else None


def find_wall(F, lm, y, prefer, heights=(0.9, 1.3, 1.7)):
    """A wall of landmark lm at chest height, preferring one side. Returns (x, z, side)."""
    for side in (prefer, -prefer):
        for h in heights:
            wx = wall_at(F, lm.x, y, lm.floor + h, side, limit=lm.rx + 1.6)
            if wx is not None:
                return wx, lm.floor + h, side
    return None


def route_point(sol, a, b, t):
    rt = next(r for r in sol.plan.routes if {r.a, r.b} == {a, b})
    pts = rt.pts if rt.a == a else rt.pts[::-1]
    return pts[int(np.clip(t, 0, 1) * (len(pts) - 1))]


def build_field(sol, y_range, res, seed, **build):
    x0, x1, z0, z1 = sol.plan.bounds
    F = terrain.Field((x0, x1), (z0, z1), y_range, res=res, seed=seed)
    F.from_solution(sol)
    F.build(**build)
    return F


def crystal_site(coll, name, rng, pos, normal, size, mat, tints, light_color, light_power, cluster=6):
    cl = props.crystal_cluster(rng, cluster, size, 6, 0.6)
    props.instance(
        name,
        cl,
        np.array([pos]),
        np.array([normal]),
        1.0,
        rng=rng,
        tints=props.tint_palette(rng, tints, 1, 0.02),
        material=mat,
        coll=coll,
    )
    n = np.asarray(normal, dtype=float)
    lp = np.asarray(pos) + n * 0.5 * size + np.array([0, -0.8, 0.15])
    core.light(f"{name}.light", "POINT", tuple(lp), light_power * size, color=light_color, size=0.4, coll=coll)


# ---------------------------------------------------------------------------
# Moss & Ember
# ---------------------------------------------------------------------------


def moss_and_ember(coll, seed=7, res=0.08):
    sol = worldgen.solve(moss_rules, seed, start_role="surface", plans=40)
    plan = sol.plan
    rng = np.random.default_rng(seed + 1)
    F = build_field(sol, (-0.6, 7.5), res, seed, pocket=3.0, pocket_var=0.6, relief=0.3, edge=0.12)
    xs = F.xs
    surf = plan.surface(xs)
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
        z_range=(plan.bounds[2], 1.4),
        cover=("#4E7A2E", "#86A63A"),
        cover_amount=0.75,
        veins=dict(color="#FF7A1E", strength=9.0, scale=0.8, width=0.022, amount=0.3, region_scale=0.35),
        front_dark=0.62,
        bump=0.45,
    )
    core.set_material(ground, mat)
    mouth, forge, seam, pocket = (plan.landmark(n) for n in ("mouth", "forge", "seam", "pocket"))

    # Surface cover and trees.
    grass_mat = props.tinted_material("me.grass", rough=0.7, sss=0.2, sheen=0.3)
    leaf_mat = props.tinted_material("me.leaf", rough=0.75, sss=0.25, sheen=0.3)
    bark = shaders.bark_material("me.bark", dark="#3A2A22", light="#6A4E3A", moss="#5E8A34")
    is_surface = lambda c, n: c[:, 2] > np.interp(c[:, 0], xs, surf) - 0.5
    in_cave = lambda c, n: c[:, 2] < np.interp(c[:, 0], xs, surf) - 0.6
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
    tx = [x for x in rng.uniform(-12.5, 12.5, 14) if abs(x - mouth.x) > 2.6][:7]
    for i, x in enumerate(tx):
        y = rng.uniform(4.8, 7.2)
        z = F.floor_at(x, y, 4.0)
        if z is None:
            continue
        tints = props.tint_palette(rng, ["#4F7A2C", "#6B9236", "#3E6526", "#8AA43E"], 16)
        tree(
            f"me.tree{i}",
            rng,
            V((x, y, z - 0.2)),
            rng.uniform(1.9, 2.8),
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
    pts, nn = F.scatter(rng, 30, normal_min=0.7, y_range=(0.3, 2.6), mask=in_cave)
    props.instance(
        "me.mushrooms",
        [props.mushroom(rng, 0.22, 0.1), props.mushroom(rng, 0.3, 0.13)],
        pts,
        nn,
        0.6 + 0.8 * rng.random(len(pts)),
        align=0.5,
        rng=rng,
        tints=props.tint_palette(rng, ["#D2552A", "#E0782E", "#B8402A"], len(pts)),
        material=cap_mat,
        coll=coll,
    )

    # Ember crystals: the seam wall the prospector works, the sealed pocket, and a few seeded wall sites.
    ember_mat = props.tinted_material(
        "me.ember_crystal", rough=0.25, emit=2.6, emit_from_tint=True, transmission=0.3, coat=0.6
    )
    ember = ["#FF5A12", "#FF7A1A"]
    wall = find_wall(F, seam, 1.3, 1 if pocket.x >= seam.x else -1)
    if wall is None:
        wall = (seam.x + seam.rx, seam.floor + 1.0, 1)
    wx, wz, side = wall
    crystal_site(
        coll, "me.seam", rng, (wx + 0.05 * side, 1.2, wz + 0.1), (-side, 0, 0.15), 1.0, ember_mat, ember, "#FF8A30", 180
    )
    pz = F.floor_at(pocket.x, 1.4, pocket.floor + 0.8)
    if pz is not None:
        crystal_site(coll, "me.pocket", rng, (pocket.x, 1.4, pz), (0, 0, 1), 0.8, ember_mat, ember, "#FF8A30", 180)
    wall_pts, wall_n = F.scatter(
        rng, 3, y_range=(0.8, 2.4), mask=lambda c, n: in_cave(c, n) & (np.abs(n[:, 0]) > 0.7) & (np.abs(c[:, 0]) < 10.5)
    )
    for i, (p, n) in enumerate(zip(wall_pts, wall_n)):
        crystal_site(
            coll, f"me.vein{i}", rng, tuple(p), tuple(n), rng.uniform(0.5, 0.7), ember_mat, ember, "#FF8A30", 180
        )

    # Crafting station in the forge hall.
    fx = forge.x - forge.rx * 0.35
    fz = F.floor_at(fx, 1.9, forge.floor + 1.5)
    furnace(coll, (fx, 1.9, fz), rng)
    ax = fx + 1.9
    anvil(coll, (ax, 1.5, F.floor_at(ax, 1.5, forge.floor + 1.5)))
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
    target, width = frame(sol)
    core.light(
        "me.cave_fill",
        "AREA",
        (0.5, -6.0, target[2] - 1.0),
        260,
        color="#7FA0D8",
        size=14,
        rotation=(90, 0, 0),
        coll=coll,
    )
    mp = route_point(sol, "mouth", "forge", 0.35)
    core.light(
        "me.mouth_fill",
        "AREA",
        (mp[0], -3.0, mp[1] + 1.5),
        120,
        color="#FFC890",
        size=4,
        rotation=(70, 0, -20),
        coll=coll,
    )

    # Parallax hills sit on the horizon behind the surface.
    s_mean = float(np.mean(plan.surface(np.linspace(*VIEW_X, 40))))
    hill_layer(
        "me.hills_far",
        rng,
        (-40, 40),
        40.0,
        screen_z(s_mean + 1.4, 40.0),
        0.9,
        7.0,
        "#B98AA0",
        coll,
        bumps=[(-6, 4, 1.2), (14, 5, 1.6)],
    )
    hill_layer(
        "me.hills_mid",
        rng,
        (-40, 40),
        22.0,
        screen_z(s_mean + 0.7, 22.0),
        0.7,
        4.0,
        "#7A6E8E",
        coll,
        bumps=[(8, 2.5, 0.9)],
    )
    hill_layer("me.hills_near", rng, (-40, 40), 12.0, screen_z(s_mean + 0.2, 12.0), 0.55, 2.2, "#4E5E6A", coll)

    sc = Scene("moss_and_ember", F, camera_target=target, width=width, solution=sol)
    sc.details = [("forge", (fx + 0.9, 1.5, forge.floor + 1.2), 7.5)]
    pp = route_point(sol, "mouth", "forge", 0.45)
    sc.cast = [
        ("prospector", "mine_strike", wx - side * 1.0, 1.3, seam.floor + 1.2, -18.0 if side > 0 else -162.0),
        ("warden", "hammer_raise", fx + 1.05, 1.2, forge.floor + 1.5, -22.0),
        ("pathfinder", "idle_lantern", float(pp[0]), 1.4, float(pp[1]) + 0.3, -28.0),
    ]
    return sc


# ---------------------------------------------------------------------------
# The Opal Deep
# ---------------------------------------------------------------------------


def opal_deep(coll, seed=11, res=0.08):
    sol = worldgen.solve(opal_rules, seed, water_fn=opal_water, start_role="exit", plans=40)
    plan = sol.plan
    rng = np.random.default_rng(seed + 1)
    F = build_field(sol, (-0.6, 6.5), res, seed, pocket=3.4, pocket_var=0.8, relief=0.38, edge=0.14, back_relief=0.55)
    ground = F.mesh("terrain", coll)
    mat = shaders.terrain_material(
        "opal.terrain",
        strata=[(0.0, "#2A2E4A"), (0.3, "#3A3E62"), (0.55, "#4A4E74"), (0.8, "#3E4468"), (1.0, "#343858")],
        z_range=(plan.bounds[2], plan.bounds[3]),
        cover=("#4A5A82", "#5E6E96"),
        cover_amount=0.35,
        front_dark=0.5,
        bump=0.55,
        lichen=("#4FE0D0", 0.3, 5.0),
        rock_scale=1.1,
    )
    core.set_material(ground, mat)
    west, grotto, lake, ruins = (plan.landmark(n) for n in ("west", "grotto", "lake", "ruins"))

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
    colors = ["#7FE8F0", "#C8A0FF", "#FF9ACF"]
    sites = [
        (grotto.x + 0.45 * grotto.rx, grotto, "floor", 1.6),
        (grotto.x - 0.3 * grotto.rx, grotto, "ceil", 1.1),
        (lake.x - 0.82 * lake.rx, lake, "floor", 1.0),
        (lake.x + 0.1 * lake.rx, lake, "ceil", 1.5),
        (ruins.x + 0.5 * ruins.rx, ruins, "ceil", 0.9),
        (west.x + 0.6 * west.rx, west, "floor", 0.8),
    ]
    big = None
    for i, (x, lm, where, s) in enumerate(sites):
        if where == "ceil":
            z, n = F.ceiling_at(x, 2.0, lm.floor + 1.0), (0, 0, -1)
        else:
            z, n = F.floor_at(x, 2.0, lm.floor + 1.0), (0, 0, 1)
        if z is None:
            continue
        crystal_site(
            coll, f"opal.big{i}", rng, (x, 2.0, z - 0.05 * n[2]), n, s, crystal_mat, opal, colors[i % 3], 320, cluster=7
        )
        if i == 0:
            big = (x, z)
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
    target, width = frame(sol)
    spores = rng.random((60, 3)) * np.array([22, 2.6, 8]) + np.array([-11, 0.5, target[2] - 4.0])
    props.instance(
        "opal.spores",
        props.icosphere(0),
        spores,
        scales=0.012 + 0.02 * rng.random(60),
        rng=rng,
        material=core.emission("opal.spores", "#9FFFF0", 12.0),
        coll=coll,
    )

    # The lake fills the generated basin.
    level = lake.floor - 0.15
    cols = np.nonzero(sol.water.any(axis=0))[0]
    if len(cols):
        lx0, lx1 = sol.xs[cols[0]] - 0.3, sol.xs[cols[-1]] + 0.3
        water = core.mesh_object(
            "opal.lake",
            [(lx0, 0.02, level), (lx1, 0.02, level), (lx1, 4.5, level), (lx0, 4.5, level)],
            [(0, 1, 2, 3)],
            coll=coll,
        )
        core.set_material(
            water, shaders.water_material("opal.water", deep="#123A58", glow="#3AD0D8", glow_strength=3.0)
        )
        core.light(
            "opal.lake_glow",
            "AREA",
            ((lx0 + lx1) / 2, 1.6, level + 0.15),
            160,
            color="#3AD0D8",
            size=max(2.0, lx1 - lx0),
            rotation=(180, 0, 0),
            coll=coll,
        )

    # Ruins: the discovery in the eastern chamber.
    ruin_mat = core.principled("opal.ruin", "#5E5F80", rough=0.8, bump=0.5, bump_scale=6)
    tops = []
    for i, (k, broken) in enumerate([(-0.55, False), (0.15, True), (0.75, False)]):
        x = ruins.x + k * ruins.rx
        z = F.floor_at(x, 2.4, ruins.floor + 1.0)
        c = F.ceiling_at(x, 2.4, ruins.floor + 1.0)
        if z is None:
            continue
        h = min(3.0, (c - z - 0.4) if c else 3.0)
        ruin_pillar(coll, (x, 2.4, z), h, ruin_mat, rng, broken, name=f"opal.ruin{i}")
        tops.append((x, z + h, broken))
    standing = [t for t in tops if not t[2]]
    if len(standing) >= 2:
        (xa, za, _), (xb, zb, _) = standing[0], standing[1]
        zt = min(za, zb) + 0.2
        lintel = core.loft(
            "opal.lintel",
            [(V((xa - 0.6, 2.4, zt)), 0.25, 0.32, 4.0), (V((xb + 0.6, 2.4, zt - 0.05)), 0.25, 0.32, 4.0)],
            x_hint=(0, 0, 1),
            cap=(0.1, 0.4),
            coll=coll,
        )
        core.subsurf(lintel, 1)
        core.set_material(lintel, ruin_mat)
        gx, gz = (xa + xb) / 2, (za + zt) / 2 - 1.0
        glyph = core.ellipsoid("opal.glyph", (gx, 2.05, gz), (0.16, 0.03, 0.24), coll=coll)
        core.set_material(glyph, core.emission("opal.glyph", "#7AE8FF", 3.0))
        core.light("opal.glyph_light", "POINT", (gx, 1.4, gz), 120, color="#9AF0FF", size=0.4, coll=coll)

    shaders.sky_world([(0.0, "#05060C"), (1.0, "#0A0C18")], ambient="#2A3460", ambient_strength=0.8)
    core.light(
        "opal.fill",
        "AREA",
        (0.0, -7.0, target[2] + 1.5),
        1100,
        color="#7A8CFF",
        size=18,
        rotation=(90, 0, 0),
        coll=coll,
    )
    core.light(
        "opal.rim", "AREA", (0.0, 6.5, target[2] + 3.5), 120, color="#E0A0FF", size=14, rotation=(-80, 0, 0), coll=coll
    )

    sc = Scene("opal_deep", F, camera_target=target, width=width, solution=sol)
    sc.post = dict(bloom=0.55, vignette=0.32)
    pp = route_point(sol, "west", "grotto", 0.55)
    bx = big[0] if big else grotto.x
    sc.cast = [
        ("pathfinder", "idle_lantern", float(pp[0]), 1.5, float(pp[1]) + 0.3, -24.0),
        ("prospector", "mine_windup", bx - 1.1, 1.4, grotto.floor + 1.2, -24.0),
        ("warden", "guard", ruins.x - 0.2 * ruins.rx, 1.0, ruins.floor + 1.2, -30.0),
    ]
    mid = ((float(pp[0]) + bx) / 2, 1.5, (float(pp[1]) + grotto.floor) / 2 + 0.4)
    sc.details = [("crystal_hall", mid, 9.0)]
    return sc


# ---------------------------------------------------------------------------
# Roots of Giants
# ---------------------------------------------------------------------------


def roots_of_giants(coll, seed=23, res=0.08):
    sol = worldgen.solve(roots_rules, seed, start_role="surface", plans=40)
    plan = sol.plan
    rng = np.random.default_rng(seed + 1)
    F = build_field(sol, (-0.6, 8.0), res, seed, pocket=3.2, pocket_var=0.7, relief=0.34, edge=0.14)
    xs = F.xs
    surf = plan.surface(xs)
    ground = F.mesh("terrain", coll)
    mat = shaders.terrain_material(
        "roots.terrain",
        strata=[(0.0, "#2A2018"), (0.35, "#4A3424"), (0.65, "#5E4430"), (0.85, "#4A3626"), (1.0, "#30241A")],
        z_range=(plan.bounds[2], 1.8),
        cover=("#5A7A2A", "#8AA040"),
        cover_amount=0.6,
        front_dark=0.6,
        bump=0.5,
        lichen=("#E8C060", 0.35, 3.0),
    )
    core.set_material(ground, mat)
    trunk_lm, hall, hollow, grove = (plan.landmark(n) for n in ("trunk", "hall", "hollow", "grove"))
    crack = next(r for r in plan.routes if r.kind == "light")

    bark = shaders.bark_material("roots.bark", dark="#3A2A1E", light="#7E5E40", moss="#5E7A30", scale=2.6)
    # The giant stands behind the playable pocket, its foot beside the way down.
    tx, ty = trunk_lm.x - 1.2, 4.8
    tz = F.floor_at(tx, ty, 6.0) or float(plan.surface(tx))
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
    # Roots run along every walkable route, hugging the ceiling, as if they pushed the hollows open.
    for i, rt in enumerate(r for r in plan.routes if r.walk):
        pts = rt.pts[:: max(1, len(rt.pts) // 7)]
        y = rng.uniform(1.9, 3.0)
        r0, r1 = rng.uniform(0.45, 0.65), rng.uniform(0.22, 0.32)
        ctrl = [
            (
                p[0],
                y + rng.normal(0, 0.2),
                p[1] + rt.radius * 0.6 + rng.normal(0, 0.12),
                r0 + (r1 - r0) * k / max(1, len(pts) - 1),
            )
            for k, p in enumerate(pts)
        ]
        root(f"roots.root{i}", ctrl, coll, bark)
    # Two tap roots drop from the trunk through the crust into the hollow.
    for i, dx in enumerate((-0.8, 0.9)):
        top = (tx + dx * 1.6, ty - 1.4, tz + 0.6, 0.8)
        bot = (hollow.x + dx * hollow.rx * 0.6, 2.4, hollow.floor + hollow.rz * 1.2, 0.35)
        mid = ((top[0] + bot[0]) / 2 + rng.normal(0, 0.4), 2.8, (top[2] + bot[2]) / 2, 0.55)
        root(f"roots.tap{i}", [top, mid, bot], coll, bark)
    for i, side in enumerate((-1, 1, -0.2)):
        b0 = (tx + side * 1.5, ty - 1.3, tz + 1.3, 0.72)
        pts = [b0]
        for k in range(1, 4):
            pts.append(
                (
                    b0[0] + side * 1.7 * k + rng.normal(0, 0.2),
                    ty - 1.3 - 0.35 * k * (1 + abs(side)),
                    tz + 1.3 - 0.75 * k,
                    0.72 - 0.15 * k,
                )
            )
        root(f"roots.buttress{i}", pts, coll, bark)

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
    target, width = frame(sol)
    motes = rng.random((120, 3)) * np.array([22, 2.5, 7]) + np.array([-11, 0.6, target[2] - 5.0])
    props.instance(
        "roots.motes",
        props.icosphere(0),
        motes,
        scales=0.012 + 0.018 * rng.random(120),
        rng=rng,
        material=core.emission("roots.motes", "#FFE09A", 10.0),
        coll=coll,
    )

    # Light falls down the generated crack into the hollow.
    (bx, _), (cx, cz) = crack.pts[0], crack.pts[-1]
    floor_z = hollow.floor
    shaft("roots.shaft0", (cx, 1.9, cz - 0.6), (bx - 0.6, 1.9, floor_z), 1.5, coll, color="#FFD890", strength=0.45)
    shaft(
        "roots.shaft1", (cx + 0.3, 2.1, cz - 0.7), (bx + 0.4, 2.1, floor_z), 0.8, coll, color="#FFD890", strength=0.35
    )
    tilt = math.degrees(math.atan2(cx - bx, cz - floor_z))
    core.light(
        "roots.shaft_light",
        "SPOT",
        (cx, 1.8, cz + 0.5),
        900,
        color="#FFE0A0",
        size=0.3,
        spot=(28, 0.6),
        rotation=(0, tilt, 0),
        coll=coll,
    )

    shaders.sky_world([(0.0, "#D8E8B0"), (0.7, "#BFE0C8"), (1.0, "#7FB8C8")], ambient="#6A7A60", ambient_strength=0.22)
    core.light(
        "roots.sun", "SUN", (0, 0, 20), 3.0, color="#FFEAC0", size=math.radians(2), rotation=(40, 20, 0), coll=coll
    )
    core.light(
        "roots.cave_fill",
        "AREA",
        (0.0, -6.0, target[2] - 1.5),
        520,
        color="#B8C8A0",
        size=16,
        rotation=(90, 0, 0),
        coll=coll,
    )
    for i, lm in enumerate(lm for lm in plan.landmarks if lm.role not in ("surface",)):
        core.light(
            f"roots.fungus_light{i}", "POINT", (lm.x, 1.3, lm.floor + 0.9), 140, color="#FFC060", size=0.4, coll=coll
        )
    s_mean = float(np.mean(plan.surface(np.linspace(*VIEW_X, 40))))
    hill_layer(
        "roots.far",
        rng,
        (-40, 40),
        36.0,
        screen_z(s_mean + 2.0, 36.0),
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
        screen_z(s_mean + 1.2, 20.0),
        0.7,
        1.8,
        "#6E9A78",
        coll,
        bumps=[(9, 1.0, 1.4), (-9, 1.2, 1.2)],
    )

    sc = Scene("roots_of_giants", F, camera_target=target, width=width, solution=sol)
    sc.post = dict(bloom=0.45, vignette=0.3)
    sc.cast = [
        ("pathfinder", "run", grove.x - 0.3 * grove.rx, 1.35, grove.floor + 1.2, -20.0),
        ("prospector", "idle", bx - 0.5, 1.3, hollow.floor + 1.2, -32.0),
        ("warden", "guard", hall.x + 0.3 * hall.rx, 1.2, hall.floor + 1.2, -150.0),
    ]
    sc.details = [("root_hall", (bx, 1.5, hollow.floor + 1.5), 7.5)]
    return sc
