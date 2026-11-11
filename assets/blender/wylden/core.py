"""Scene, mesh, material and render helpers shared by the Wylden asset scripts.

Everything here is deterministic: the same inputs produce the same geometry,
so renders can be regenerated from source.
"""

import math

import bpy  # noqa: I001  (bpy must load before bmesh when run as a module)
import bmesh
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def empty(name, location=(0, 0, 0), coll=None):
    ob = bpy.data.objects.new(name, None)
    ob.location = location
    return link(ob, coll)


# ---------------------------------------------------------------------------
# Mesh construction
# ---------------------------------------------------------------------------

# Segment multiplier for lofts and spheres. 1.0 for renders; exports for the
# runtime lower it to fit phone triangle budgets.
DETAIL = 1.0


def _seg(n, minimum=6):
    return max(minimum, int(round(n * DETAIL)))


def mesh_object(name, verts, faces, coll=None, smooth=True, recalc=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    return link(ob, coll)


def superellipse(n, rx, ry, p=2.0, phase=0.0):
    pts = []
    e = 2.0 / p
    for i in range(n):
        a = phase + 2.0 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        pts.append((rx * math.copysign(abs(c) ** e, c), ry * math.copysign(abs(s) ** e, s)))
    return pts


def _frames(centers, x_hint):
    n = len(centers)
    hint = Vector(x_hint).normalized()
    out = []
    for i in range(n):
        a = centers[max(i - 1, 0)]
        b = centers[min(i + 1, n - 1)]
        t = (b - a).normalized()
        x = hint - hint.dot(t) * t
        if x.length < 1e-5:
            alt = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            x = alt - alt.dot(t) * t
        x.normalize()
        out.append((t, x, t.cross(x)))
    return out


def loft(name, rings, seg=16, cap=(0.6, 0.6), x_hint=(1, 0, 0), coll=None, smooth=True):
    """Sweep superellipse cross sections along a path.

    rings: sequence of (center, rx, ry[, p[, (ox, oy)]]) where rx spans the
    x_hint direction, ry the side direction, p is the superellipse exponent
    (2 = ellipse, larger = boxier) and (ox, oy) offsets the section.
    cap: dome depth (fraction of the smaller radius) for the start and end
    caps, or None to leave that end open.
    """
    seg = _seg(seg)
    centers = [Vector(r[0]) for r in rings]
    frames = _frames(centers, x_hint)
    verts, faces = [], []
    for (c, *rest), (_t, x, y) in zip(rings, frames):
        rx, ry = rest[0], rest[1]
        p = rest[2] if len(rest) > 2 else 2.0
        ox, oy = rest[3] if len(rest) > 3 else (0.0, 0.0)
        c = Vector(c)
        for px, py in superellipse(seg, rx, ry, p):
            verts.append(c + x * (px + ox) + y * (py + oy))
    nr = len(rings)
    for i in range(nr - 1):
        for j in range(seg):
            a = i * seg + j
            b = i * seg + (j + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    for end, dome in ((0, cap[0]), (nr - 1, cap[1])):
        if dome is None:
            continue
        c, rx, ry = Vector(rings[end][0]), rings[end][1], rings[end][2]
        t = frames[end][0]
        sign = -1 if end == 0 else 1
        tip = c + t * sign * dome * min(rx, ry)
        ci = len(verts)
        verts.append(tip)
        base = end * seg
        for j in range(seg):
            a, b = base + j, base + (j + 1) % seg
            faces.append((a, b, ci) if end == nr - 1 else (b, a, ci))
    ob = mesh_object(name, verts, faces, coll=coll, smooth=smooth)
    _loft_uvs(ob, centers, seg, nr, cap)
    return ob


def _loft_uvs(ob, centers, seg, nr, cap):
    """u runs around the section (0..1), v along the path in metres."""
    me = ob.data
    if len(me.polygons) != (nr - 1) * seg + sum(seg for c in cap if c is not None):
        return
    dist = [0.0]
    for a, b in zip(centers, centers[1:]):
        dist.append(dist[-1] + (b - a).length)
    uv = me.uv_layers.new(name="UVMap")
    k = 0
    for i in range(nr - 1):
        for j in range(seg):
            coords = (
                (j / seg, dist[i]),
                ((j + 1) / seg, dist[i]),
                ((j + 1) / seg, dist[i + 1]),
                (j / seg, dist[i + 1]),
            )
            poly = me.polygons[k]
            for li, co in zip(poly.loop_indices, coords):
                uv.data[li].uv = co
            k += 1
    for end, dome in ((0, cap[0]), (nr - 1, cap[1])):
        if dome is None:
            continue
        for j in range(seg):
            poly = me.polygons[k]
            for li in poly.loop_indices:
                uv.data[li].uv = (j / seg, dist[end])
            k += 1


def shell(name, center, radii, keep, seg=32, rings=20, rot=None, coll=None):
    """UV-sphere surface trimmed by keep(unit_vector) -> bool, then scaled.

    Used for hair, hoods, helmets and pauldrons: thicken with solidify().
    """
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=_seg(seg, 8), v_segments=_seg(rings, 5), radius=1.0)
    doomed = [v for v in bm.verts if not keep(v.co.normalized())]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ rot.to_4x4()
    m = m @ Matrix.Diagonal((radii[0], radii[1], radii[2], 1.0))
    bm.transform(m)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    return link(ob, coll)


def ellipsoid(name, center, radii, seg=24, rings=14, rot=None, coll=None):
    return shell(name, center, radii, lambda u: True, seg=seg, rings=rings, rot=rot, coll=coll)


def box(name, center, size, coll=None, rot=None):
    hx, hy, hz = (s / 2 for s in size)
    vs = [Vector((x, y, z)) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    m = Matrix.Translation(Vector(center)) @ (rot.to_4x4() if rot else Matrix())
    vs = [m @ v for v in vs]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return mesh_object(name, vs, faces, coll=coll, smooth=False)


def subsurf(ob, levels=2):
    m = ob.modifiers.new("Subdivision", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    return m


def solidify(ob, thickness, offset=1.0):
    m = ob.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    m.use_even_offset = True
    return m


def bevel(ob, width, segments=2):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    return m


def set_material(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(hex_or_tuple, alpha=1.0):
    if isinstance(hex_or_tuple, str):
        h = hex_or_tuple.lstrip("#")
        rgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
        return tuple(srgb_to_linear(c) for c in rgb) + (alpha,)
    if len(hex_or_tuple) == 3:
        return tuple(hex_or_tuple) + (alpha,)
    return tuple(hex_or_tuple)


def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    return mat


def principled(
    name,
    color,
    rough=0.6,
    metal=0.0,
    emit=None,
    emit_strength=0.0,
    sss=0.0,
    sheen=0.0,
    coat=0.0,
    bump=0.0,
    bump_scale=40.0,
    specular=0.5,
    transmission=0.0,
    alpha=1.0,
):
    mat = new_material(name)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    i = bsdf.inputs
    i["Base Color"].default_value = rgba(color)
    i["Roughness"].default_value = rough
    i["Metallic"].default_value = metal
    i["Specular IOR Level"].default_value = specular
    if sss:
        i["Subsurface Weight"].default_value = sss
        i["Subsurface Radius"].default_value = (0.4, 0.15, 0.08)
        i["Subsurface Scale"].default_value = 0.05
    if sheen:
        i["Sheen Weight"].default_value = sheen
    if coat:
        i["Coat Weight"].default_value = coat
    if transmission:
        i["Transmission Weight"].default_value = transmission
    if emit is not None:
        i["Emission Color"].default_value = rgba(emit)
        i["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        i["Alpha"].default_value = alpha
    if bump:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = bump_scale
        tex.inputs["Detail"].default_value = 6.0
        bn = nt.nodes.new("ShaderNodeBump")
        bn.inputs["Strength"].default_value = bump
        bn.inputs["Distance"].default_value = 0.02
        nt.links.new(tex.outputs["Fac"], bn.inputs["Height"])
        nt.links.new(bn.outputs["Normal"], i["Normal"])
    return mat


def emission(name, color, strength):
    mat = new_material(name)
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba(color)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# Lights, camera, world
# ---------------------------------------------------------------------------


def light(name, kind, location, energy, color="#ffffff", size=0.5, rotation=None, coll=None, spot=None):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = rgba(color)[:3]
    if kind == "AREA":
        data.size = size
    elif kind in ("POINT", "SPOT"):
        data.shadow_soft_size = size
    elif kind == "SUN":
        data.angle = size
    if kind == "SPOT" and spot:
        data.spot_size = math.radians(spot[0])
        data.spot_blend = spot[1]
    ob = bpy.data.objects.new(name, data)
    ob.location = location
    if rotation is not None:
        ob.rotation_euler = [math.radians(a) for a in rotation]
    return link(ob, coll)


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def ortho_camera(name, target, width, pitch_deg=12.0, distance=40.0, coll=None):
    """Orthographic side camera looking along +Y, tilted down by pitch_deg."""
    cam = bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = width
    cam.clip_start = 0.1
    cam.clip_end = 500.0
    ob = bpy.data.objects.new(name, cam)
    p = math.radians(pitch_deg)
    t = Vector(target)
    ob.location = t + Vector((0.0, -math.cos(p), math.sin(p))) * distance
    ob.rotation_euler = (math.radians(90.0 - pitch_deg), 0.0, 0.0)
    link(ob, coll)
    bpy.context.scene.camera = ob
    return ob


def gradient_world(top, bottom, strength=1.0, name="World"):
    world = bpy.data.worlds.new(name)
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = rgba(bottom)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = rgba(top)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = world
    return world


def flat_world(color, strength=1.0):
    world = bpy.data.worlds.new("World")
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = rgba(color)
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = world
    return world


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def setup_render(width, height, samples=64, look="AgX - Medium High Contrast", exposure=0.0, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x = width
    sc.render.resolution_y = height
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = look
    except TypeError:
        pass
    sc.view_settings.exposure = exposure
    return sc


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def post_process(path, bloom=0.35, threshold=0.72, radius=0.012, vignette=0.22, out=None):
    """Display-space bloom and vignette, applied after the AgX transform."""
    import numpy as np
    from PIL import Image, ImageFilter

    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(np.float32) / 255.0
    h, w, _ = a.shape
    if bloom > 0:
        lum = a.max(axis=2, keepdims=True)
        bright = np.clip((lum - threshold) / (1.0 - threshold), 0.0, 1.0) * a
        bimg = Image.fromarray((bright * 255).astype(np.uint8))
        r = max(2, int(radius * w))
        glow = np.zeros_like(a)
        for k, wgt in ((r, 0.5), (r * 3, 0.35), (r * 8, 0.25)):
            glow += np.asarray(bimg.filter(ImageFilter.GaussianBlur(k))).astype(np.float32) / 255.0 * wgt
        a = 1.0 - (1.0 - a) * (1.0 - np.clip(glow * bloom * 2.0, 0, 1))
    if vignette > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
        a *= (1.0 - vignette * np.clip(d - 0.35, 0, 1) ** 1.5 / 0.65**1.5)[..., None]
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(out or path)
    return out or path
