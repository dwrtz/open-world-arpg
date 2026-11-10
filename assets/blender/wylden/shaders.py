"""Procedural shaders for terrain, bark, water, light shafts and the sky.

The terrain shader reads world position and normal so one material covers a
whole cross section: strata by depth, cover (moss, grass, lichen) on
up-facing surfaces, a darker cut face toward the camera, crevice occlusion,
and optional glowing veins.
"""

from . import core


class Graph:
    def __init__(self, nt):
        self.nt = nt

    def node(self, kind, inputs=None, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            sock = n.inputs[k]
            if hasattr(v, "is_output") or hasattr(v, "links"):
                self.nt.links.new(v, sock)
            else:
                sock.default_value = v
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def maprange(self, value, a, b, c=0.0, d=1.0, clamp=True, smooth=True):
        if a > b:
            a, b, c, d = b, a, d, c
        n = self.node("ShaderNodeMapRange", {"Value": value, "From Min": a, "From Max": b, "To Min": c, "To Max": d})
        n.clamp = clamp
        if smooth:
            n.interpolation_type = "SMOOTHSTEP"
        return n.outputs["Result"]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        for idx, v in ((0, fac), (6, a), (7, b)):
            if hasattr(v, "is_output") or hasattr(v, "links"):
                self.nt.links.new(v, n.inputs[idx])
            else:
                n.inputs[idx].default_value = core.rgba(v) if idx else v
        return n.outputs[2]

    def math(self, op, a, b=0.0, clamp=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for idx, v in ((0, a), (1, b)):
            if hasattr(v, "is_output") or hasattr(v, "links"):
                self.nt.links.new(v, n.inputs[idx])
            else:
                n.inputs[idx].default_value = v
        return n.outputs[0]

    def ramp(self, fac, stops):
        n = self.nt.nodes.new("ShaderNodeValToRGB")
        cr = n.color_ramp
        cr.elements[0].position, cr.elements[0].color = stops[0][0], core.rgba(stops[0][1])
        cr.elements[1].position, cr.elements[1].color = stops[-1][0], core.rgba(stops[-1][1])
        for pos, col in stops[1:-1]:
            e = cr.elements.new(pos)
            e.color = core.rgba(col)
        self.link(fac, n.inputs["Fac"])
        return n.outputs["Color"]


def _clear(nt):
    for n in list(nt.nodes):
        nt.nodes.remove(n)


def terrain_material(
    name,
    strata,
    z_range,
    cover=None,
    cover_amount=0.5,
    front_dark=0.4,
    veins=None,
    bump=0.5,
    rock_scale=1.4,
    cover_up=(0.5, 0.82),
    lichen=None,
    rough=0.85,
    ao_strength=0.75,
):
    """strata: [(t, hex)] from deep (0) to shallow (1) over z_range.
    cover: (hex_a, hex_b) for up-facing surfaces.
    veins: dict(color, strength, scale, width, amount) for glowing fissures.
    lichen: (hex, amount) glowing speckles on walls.
    """
    mat = core.new_material(name)
    nt = mat.node_tree
    _clear(nt)
    g = Graph(nt)
    out = g.node("ShaderNodeOutputMaterial")
    bsdf = g.node("ShaderNodeBsdfPrincipled", {"Roughness": rough})
    geo = g.node("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    nrm = g.node("ShaderNodeSeparateXYZ", {"Vector": geo.outputs["Normal"]})
    sp = g.node("ShaderNodeSeparateXYZ", {"Vector": pos})
    warp = g.node("ShaderNodeTexNoise", {"Vector": pos, "Scale": 0.35, "Detail": 3.0})
    zw = g.math("ADD", sp.outputs["Z"], g.math("MULTIPLY", g.math("SUBTRACT", warp.outputs["Fac"], 0.5), 2.2))
    t = g.maprange(zw, z_range[0], z_range[1], smooth=False)
    base = g.ramp(t, strata)
    # Rock breakup: large plates and fine grit.
    vor = g.node("ShaderNodeTexVoronoi", {"Vector": pos, "Scale": rock_scale, "Randomness": 0.9})
    grit = g.node("ShaderNodeTexNoise", {"Vector": pos, "Scale": 6.0, "Detail": 8.0})
    plate = g.maprange(vor.outputs["Distance"], 0.0, 0.6, 0.78, 1.12)
    gv = g.maprange(grit.outputs["Fac"], 0.3, 0.7, 0.85, 1.12)
    shade = g.math("MULTIPLY", plate, gv)
    col = g.mix(
        1.0,
        base,
        g.node("ShaderNodeCombineColor", {"Red": shade, "Green": shade, "Blue": shade}).outputs[0],
        blend="MULTIPLY",
    )
    up = g.maprange(nrm.outputs["Z"], cover_up[0], cover_up[1])
    front = g.maprange(g.math("MULTIPLY", nrm.outputs["Y"], -1.0), 0.4, 0.8)
    if cover:
        cn = g.node("ShaderNodeTexNoise", {"Vector": pos, "Scale": 1.6, "Detail": 6.0})
        breakup = g.maprange(cn.outputs["Fac"], 0.62 - cover_amount * 0.4, 0.7 - cover_amount * 0.4)
        cmask = g.math("MULTIPLY", up, breakup, clamp=True)
        cmask = g.math("MULTIPLY", cmask, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", front, 0.85)), clamp=True)
        cn2 = g.node("ShaderNodeTexNoise", {"Vector": pos, "Scale": 4.0, "Detail": 4.0})
        ccol = g.mix(g.maprange(cn2.outputs["Fac"], 0.35, 0.65), cover[0], cover[1])
        col = g.mix(cmask, col, ccol)
    else:
        cmask = None
    if front_dark:
        col = g.mix(g.math("MULTIPLY", front, front_dark), col, "#000000")
    ao = g.node("ShaderNodeAmbientOcclusion", {"Color": col, "Distance": 0.7}, samples=8)
    col = g.mix(ao_strength, col, ao.outputs["Color"])
    g.link(col, bsdf.inputs["Base Color"])
    emission = None
    if veins:
        vv = g.node(
            "ShaderNodeTexVoronoi",
            {"Vector": pos, "Scale": veins.get("scale", 1.2), "Randomness": 1.0},
            feature="DISTANCE_TO_EDGE",
        )
        line = g.maprange(vv.outputs["Distance"], veins.get("width", 0.03), 0.0)
        region_n = g.node(
            "ShaderNodeTexNoise", {"Vector": pos, "Scale": veins.get("region_scale", 0.45), "Detail": 2.0}
        )
        amt = veins.get("amount", 0.5)
        region = g.maprange(region_n.outputs["Fac"], 0.62 - amt * 0.25, 0.7 - amt * 0.25)
        vmask = g.math("MULTIPLY", line, region, clamp=True)
        if cmask is not None:
            vmask = g.math("MULTIPLY", vmask, g.math("SUBTRACT", 1.0, cmask), clamp=True)
        vmask = g.math(
            "MULTIPLY", vmask, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", front, veins.get("front", 1.0))), clamp=True
        )
        emission = (vmask, veins["color"], veins.get("strength", 8.0))
    if lichen:
        ln = g.node("ShaderNodeTexVoronoi", {"Vector": pos, "Scale": 9.0, "Randomness": 1.0})
        dots = g.maprange(ln.outputs["Distance"], 0.12, 0.05)
        lr = g.node("ShaderNodeTexNoise", {"Vector": pos, "Scale": 0.6})
        lreg = g.maprange(lr.outputs["Fac"], 0.55 - lichen[1] * 0.2, 0.62 - lichen[1] * 0.2)
        lmask = g.math("MULTIPLY", dots, lreg, clamp=True)
        lmask = g.math("MULTIPLY", lmask, g.math("SUBTRACT", 1.0, front), clamp=True)
        if emission:
            emission = (g.math("MAXIMUM", emission[0], lmask), emission[1], emission[2])
        else:
            emission = (lmask, lichen[0], lichen[2] if len(lichen) > 2 else 4.0)
    if emission:
        fac, ecol, strength = emission
        bsdf.inputs["Emission Color"].default_value = core.rgba(ecol)
        g.link(g.math("MULTIPLY", fac, strength), bsdf.inputs["Emission Strength"])
    b1 = g.node("ShaderNodeBump", {"Strength": bump, "Distance": 0.08, "Height": vor.outputs["Distance"]})
    b2 = g.node(
        "ShaderNodeBump",
        {"Strength": bump * 0.5, "Distance": 0.02, "Height": grit.outputs["Fac"], "Normal": b1.outputs["Normal"]},
    )
    g.link(b2.outputs["Normal"], bsdf.inputs["Normal"])
    g.link(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def bark_material(name, dark="#3B2A20", light="#7A5A40", moss=None, scale=3.0, glow=None):
    """Fibrous bark running along a loft's length (uses the loft UVs: u around, v along)."""
    mat = core.new_material(name)
    nt = mat.node_tree
    _clear(nt)
    g = Graph(nt)
    out = g.node("ShaderNodeOutputMaterial")
    bsdf = g.node("ShaderNodeBsdfPrincipled", {"Roughness": 0.82})
    uv = g.node("ShaderNodeUVMap")
    geo = g.node("ShaderNodeNewGeometry")
    mp = g.node("ShaderNodeMapping", {"Vector": uv.outputs["UV"], "Scale": (1.0, 0.12, 1.0)})
    wave = g.node(
        "ShaderNodeTexWave",
        {"Vector": mp.outputs["Vector"], "Scale": scale, "Distortion": 6.0, "Detail": 4.0, "Detail Scale": 1.5},
        wave_type="BANDS",
        bands_direction="X",
    )
    cracks = g.node("ShaderNodeTexNoise", {"Vector": mp.outputs["Vector"], "Scale": scale * 2.0, "Detail": 6.0})
    fac = g.math(
        "MULTIPLY",
        g.maprange(wave.outputs["Fac"], 0.15, 0.85),
        g.maprange(cracks.outputs["Fac"], 0.3, 0.6, 0.6, 1.0),
        clamp=True,
    )
    col = g.mix(fac, dark, light)
    if moss:
        nrm = g.node("ShaderNodeSeparateXYZ", {"Vector": geo.outputs["Normal"]})
        n = g.node("ShaderNodeTexNoise", {"Vector": geo.outputs["Position"], "Scale": 1.5, "Detail": 5.0})
        m = g.math(
            "MULTIPLY", g.maprange(nrm.outputs["Z"], 0.35, 0.8), g.maprange(n.outputs["Fac"], 0.45, 0.55), clamp=True
        )
        col = g.mix(m, col, moss)
    ao = g.node("ShaderNodeAmbientOcclusion", {"Color": col, "Distance": 0.6}, samples=8)
    col = g.mix(0.7, col, ao.outputs["Color"])
    g.link(col, bsdf.inputs["Base Color"])
    if glow:
        bsdf.inputs["Emission Color"].default_value = core.rgba(glow[0])
        g.link(
            g.math("MULTIPLY", g.maprange(wave.outputs["Fac"], 0.08, 0.0), glow[1]), bsdf.inputs["Emission Strength"]
        )
    b = g.node("ShaderNodeBump", {"Strength": 0.9, "Distance": 0.05, "Height": fac})
    g.link(b.outputs["Normal"], bsdf.inputs["Normal"])
    g.link(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def water_material(name, deep="#0B2A3A", glow=None, glow_strength=0.0):
    mat = core.new_material(name)
    nt = mat.node_tree
    _clear(nt)
    g = Graph(nt)
    out = g.node("ShaderNodeOutputMaterial")
    bsdf = g.node(
        "ShaderNodeBsdfPrincipled",
        {"Roughness": 0.04, "Base Color": core.rgba(deep), "Specular IOR Level": 0.8, "Coat Weight": 0.5},
    )
    geo = g.node("ShaderNodeNewGeometry")
    n = g.node("ShaderNodeTexNoise", {"Vector": geo.outputs["Position"], "Scale": 2.5, "Detail": 3.0})
    b = g.node("ShaderNodeBump", {"Strength": 0.08, "Distance": 0.02, "Height": n.outputs["Fac"]})
    g.link(b.outputs["Normal"], bsdf.inputs["Normal"])
    if glow:
        lw = g.node("ShaderNodeLayerWeight", {"Blend": 0.4})
        bsdf.inputs["Emission Color"].default_value = core.rgba(glow)
        g.link(
            g.math("MULTIPLY", g.math("SUBTRACT", 1.0, lw.outputs["Facing"]), glow_strength),
            bsdf.inputs["Emission Strength"],
        )
    g.link(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def shaft_material(name, color="#FFE6B0", strength=1.2, axis="Z"):
    """Additive light shaft: emission fading along the object's local axis and edges."""
    mat = core.new_material(name)
    nt = mat.node_tree
    _clear(nt)
    g = Graph(nt)
    out = g.node("ShaderNodeOutputMaterial")
    tc = g.node("ShaderNodeTexCoord")
    sp = g.node("ShaderNodeSeparateXYZ", {"Vector": tc.outputs["Generated"]})
    along = g.math(
        "MULTIPLY", g.maprange(sp.outputs[axis], 0.0, 0.85), g.maprange(sp.outputs[axis], 1.0, 0.9), clamp=True
    )
    across = sp.outputs["X"] if axis != "X" else sp.outputs["Y"]
    edge = g.math("MULTIPLY", g.maprange(across, 0.0, 0.45), g.maprange(across, 1.0, 0.55), clamp=True)
    fac = g.math("MULTIPLY", along, edge)
    em = g.node("ShaderNodeEmission", {"Color": core.rgba(color)})
    g.link(g.math("MULTIPLY", fac, strength), em.inputs["Strength"])
    tr = g.node("ShaderNodeBsdfTransparent")
    add = g.node("ShaderNodeAddShader")
    g.link(em.outputs[0], add.inputs[0])
    g.link(tr.outputs[0], add.inputs[1])
    lp = g.node("ShaderNodeLightPath")
    mixs = g.node("ShaderNodeMixShader")
    g.link(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
    g.link(tr.outputs[0], mixs.inputs[1])
    g.link(add.outputs[0], mixs.inputs[2])
    g.link(mixs.outputs[0], out.inputs["Surface"])
    return mat


def sky_world(stops, ambient="#1A2030", ambient_strength=0.3, strength=1.0, name="Sky"):
    """Gradient sky seen by the camera; a separate dim ambient lights the scene."""
    world = core.bpy.data.worlds.new(name)
    nt = world.node_tree
    _clear(nt)
    g = Graph(nt)
    out = g.node("ShaderNodeOutputWorld")
    tc = g.node("ShaderNodeTexCoord")
    sp = g.node("ShaderNodeSeparateXYZ", {"Vector": tc.outputs["Window"]})
    sky = g.ramp(sp.outputs["Y"], stops)
    bg_cam = g.node("ShaderNodeBackground", {"Color": sky, "Strength": strength})
    bg_amb = g.node("ShaderNodeBackground", {"Color": core.rgba(ambient), "Strength": ambient_strength})
    lp = g.node("ShaderNodeLightPath")
    mixs = g.node("ShaderNodeMixShader")
    g.link(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
    g.link(bg_amb.outputs[0], mixs.inputs[1])
    g.link(bg_cam.outputs[0], mixs.inputs[2])
    g.link(mixs.outputs[0], out.inputs["Surface"])
    core.bpy.context.scene.world = world
    return world


def flat_shade(name, color, strength=1.0):
    """Unlit silhouette color for distant parallax layers."""
    return core.emission(name, color, strength)
