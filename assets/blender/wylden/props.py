"""Environment kit: prop templates and merged, tinted instancing.

Props are small numpy meshes. ``instance`` places many copies into a single
mesh with a per-instance ``tint`` color attribute, so a biome can scatter
thousands of grass tufts, crystals or pebbles cheaply and shade them with one
material.
"""

import math

import bpy
import numpy as np

from . import core


class Template:
    def __init__(self, verts, faces):
        self.v = np.asarray(verts, dtype=np.float64)
        self.f = [tuple(f) for f in faces]

    def __add__(self, other):
        off = len(self.v)
        return Template(np.vstack([self.v, other.v]), self.f + [tuple(i + off for i in f) for f in other.f])

    def transformed(self, m=None, s=1.0, t=(0, 0, 0)):
        v = self.v * s
        if m is not None:
            v = v @ np.asarray(m).T
        return Template(v + np.asarray(t), self.f)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def align_up(n):
    """Rotation taking +Z to unit vector n."""
    n = np.asarray(n, dtype=np.float64)
    n = n / (np.linalg.norm(n) + 1e-12)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, n)
    c = float(np.dot(z, n))
    if np.linalg.norm(v) < 1e-8:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def prism(sides=6, radius=0.1, length=0.6, tip=0.25, base_scale=0.9):
    """Pointed crystal along +Z."""
    v, f = [], []
    for z, r in ((0.0, radius * base_scale), (length, radius)):
        for i in range(sides):
            a = 2 * math.pi * i / sides
            v.append((r * math.cos(a), r * math.sin(a), z))
    v.append((0, 0, length + tip))
    v.append((0, 0, -0.05))
    top, bot = len(v) - 2, len(v) - 1
    for i in range(sides):
        j = (i + 1) % sides
        f.append((i, j, sides + j, sides + i))
        f.append((sides + i, sides + j, top))
        f.append((j, i, bot))
    return Template(v, f)


def cone(sides=7, radius=0.1, height=0.5, droop=0.0):
    v = [
        (radius * math.cos(2 * math.pi * i / sides), radius * math.sin(2 * math.pi * i / sides), 0.0)
        for i in range(sides)
    ]
    v.append((droop, 0, height))
    v.append((0, 0, -0.02))
    f = [(i, (i + 1) % sides, sides) for i in range(sides)] + [((i + 1) % sides, i, sides + 1) for i in range(sides)]
    return Template(v, f)


def icosphere(subdiv=1):
    t = (1 + 5**0.5) / 2
    v = [
        (-1, t, 0),
        (1, t, 0),
        (-1, -t, 0),
        (1, -t, 0),
        (0, -1, t),
        (0, 1, t),
        (0, -1, -t),
        (0, 1, -t),
        (t, 0, -1),
        (t, 0, 1),
        (-t, 0, -1),
        (-t, 0, 1),
    ]
    f = [
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    ]
    v = [np.array(p, dtype=float) / np.linalg.norm(p) for p in v]
    for _ in range(subdiv):
        cache, nf = {}, []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = (v[a] + v[b]) / 2
                v.append(m / np.linalg.norm(m))
                cache[key] = len(v) - 1
            return cache[key]

        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return Template(np.array(v), f)


def rock(rng, subdiv=1, jitter=0.25, squash=0.6):
    t = icosphere(subdiv)
    v = t.v * (1 + jitter * (rng.random((len(t.v), 1)) - 0.5))
    v[:, 2] *= squash
    v[:, 2] = np.maximum(v[:, 2], -0.25)
    return Template(v, t.f)


def tuft(rng, blades=7, height=0.35, width=0.03, spread=0.5):
    v, f = [], []
    for i in range(blades):
        a = 2 * math.pi * i / blades + rng.random() * 0.6
        h = height * (0.6 + 0.6 * rng.random())
        lean = spread * (0.4 + 0.6 * rng.random())
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy, dx
        b = len(v)
        w = width * (0.7 + 0.6 * rng.random())
        v += [
            (px * w, py * w, 0),
            (-px * w, -py * w, 0),
            (dx * lean * h * 0.45 + px * w * 0.6, dy * lean * h * 0.45 + py * w * 0.6, h * 0.55),
            (dx * lean * h * 0.45 - px * w * 0.6, dy * lean * h * 0.45 - py * w * 0.6, h * 0.55),
            (dx * lean * h, dy * lean * h, h),
        ]
        f += [(b, b + 1, b + 3, b + 2), (b + 2, b + 3, b + 4)]
    return Template(v, f)


def strand(rng, length=1.0, width=0.05, segments=6):
    """Hanging ribbon along -Z (moss strands, root hairs)."""
    v, f = [], []
    sway = rng.normal(0, 0.08, segments + 1).cumsum()
    for i in range(segments + 1):
        t = i / segments
        w = width * (1 - 0.85 * t)
        x = sway[i] * length * 0.3
        v += [(x - w, 0, -t * length), (x + w, 0, -t * length)]
    for i in range(segments):
        a = 2 * i
        f.append((a, a + 1, a + 3, a + 2))
    return Template(v, f)


def mushroom(rng, height=0.25, cap=0.12):
    stem = cylinder(8, cap * 0.28, height * 0.9)
    c = icosphere(1)
    v = c.v.copy()
    v[:, 2] = np.maximum(v[:, 2], -0.15) * 0.55
    capt = Template(v * cap, c.f).transformed(t=(0, 0, height * 0.9))
    return stem + capt


def cylinder(sides, radius, height, top_scale=1.0):
    v = []
    for z, r in ((0.0, radius), (height, radius * top_scale)):
        for i in range(sides):
            a = 2 * math.pi * i / sides
            v.append((r * math.cos(a), r * math.sin(a), z))
    v += [(0, 0, 0), (0, 0, height)]
    f = [(i, (i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
    f += [((i + 1) % sides, i, 2 * sides) for i in range(sides)]
    f += [(sides + i, sides + (i + 1) % sides, 2 * sides + 1) for i in range(sides)]
    return Template(v, f)


def crystal_cluster(rng, count=5, size=1.0, sides=6, spread=0.5):
    out = None
    for i in range(count):
        L = size * (0.35 + 0.65 * rng.random()) * (1.0 if i else 1.4)
        r = size * (0.06 + 0.05 * rng.random()) * (1.0 if i else 1.3)
        p = prism(sides, r, L, tip=r * 2.2)
        tilt = (rng.random() * spread * 1.2) * (0 if i == 0 else 1)
        m = rot_z(rng.random() * 2 * math.pi) @ rot_x(tilt)
        off = (rng.normal(0, size * 0.06), rng.normal(0, size * 0.06), 0)
        p = p.transformed(m, 1.0, off)
        out = p if out is None else out + p
    return out


# ---------------------------------------------------------------------------
# Instancing
# ---------------------------------------------------------------------------


def instance(
    name,
    templates,
    positions,
    normals=None,
    scales=1.0,
    align=1.0,
    yaw=True,
    rng=None,
    tints=None,
    material=None,
    coll=None,
    smooth=True,
    extra_rot=None,
):
    """Merge many transformed copies of templates into one mesh object."""
    rng = rng or np.random.default_rng(0)
    if isinstance(templates, Template):
        templates = [templates]
    n = len(positions)
    scales = np.broadcast_to(np.asarray(scales, dtype=float), (n,))
    all_v, all_f, all_c = [], [], []
    off = 0
    for i in range(n):
        t = templates[i % len(templates)] if len(templates) > 1 else templates[0]
        if len(templates) > 1:
            t = templates[rng.integers(len(templates))]
        m = np.eye(3)
        if yaw:
            m = rot_z(rng.random() * 2 * math.pi)
        if extra_rot is not None:
            m = extra_rot(i) @ m
        if normals is not None and align > 0:
            nn = np.asarray(normals[i]) * align + np.array([0, 0, 1.0]) * (1 - align)
            m = align_up(nn) @ m
        v = (t.v * scales[i]) @ m.T + positions[i]
        all_v.append(v)
        all_f += [tuple(j + off for j in f) for f in t.f]
        if tints is not None:
            all_c.append(np.repeat(np.asarray(tints[i])[None, :], len(v), axis=0))
        off += len(v)
    if not all_v:
        return None
    verts = np.vstack(all_v)
    ob = core.mesh_object(name, verts, all_f, coll=coll, smooth=smooth, recalc=False)
    if tints is not None:
        attr = ob.data.color_attributes.new(name="tint", type="FLOAT_COLOR", domain="POINT")
        cols = np.vstack(all_c)
        if cols.shape[1] == 3:
            cols = np.hstack([cols, np.ones((len(cols), 1))])
        attr.data.foreach_set("color", cols.astype(np.float32).ravel())
    if material is not None:
        core.set_material(ob, material)
    return ob


def tint_palette(rng, hexes, n, jitter=0.08):
    base = np.array([core.rgba(h)[:3] for h in hexes])
    pick = base[rng.integers(len(base), size=n)]
    return np.clip(pick * (1 + rng.normal(0, jitter, (n, 1))), 0, 1)


def tinted_material(
    name,
    rough=0.7,
    emit=0.0,
    sss=0.0,
    transmission=0.0,
    coat=0.0,
    metal=0.0,
    sheen=0.0,
    emit_from_tint=False,
    alpha=1.0,
    iridescent=None,
):
    """Principled material whose base color (and optionally emission) reads the 'tint' attribute."""
    mat = core.new_material(name)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "tint"
    col = at.outputs["Color"]
    if iridescent:
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.35
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp
        cr.elements[0].color = core.rgba(iridescent[0])
        cr.elements[1].color = core.rgba(iridescent[-1])
        for k, h in enumerate(iridescent[1:-1], start=1):
            e = cr.elements.new(k / (len(iridescent) - 1))
            e.color = core.rgba(h)
        nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 0.85
        nt.links.new(col, mix.inputs[6])
        nt.links.new(ramp.outputs["Color"], mix.inputs[7])
        col = mix.outputs[2]
    nt.links.new(col, bsdf.inputs["Base Color"])
    i = bsdf.inputs
    i["Roughness"].default_value = rough
    i["Metallic"].default_value = metal
    if sss:
        i["Subsurface Weight"].default_value = sss
        i["Subsurface Scale"].default_value = 0.05
    if transmission:
        i["Transmission Weight"].default_value = transmission
    if coat:
        i["Coat Weight"].default_value = coat
    if sheen:
        i["Sheen Weight"].default_value = sheen
    if emit:
        if emit_from_tint:
            nt.links.new(col, i["Emission Color"])
        else:
            i["Emission Color"].default_value = (1, 1, 1, 1)
        i["Emission Strength"].default_value = emit
    if alpha < 1:
        i["Alpha"].default_value = alpha
    return mat


def solid_material(name, **kw):
    return core.principled(name, **kw)


def link_to(ob, coll):
    if ob is None:
        return None
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob


def bpy_obj(name):
    return bpy.data.objects.get(name)
