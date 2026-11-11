"""Export the explorer kit for runtime assembly: one rig, separate part files, and a manifest.

Usage:

    python assets/blender/export_kit.py --out client/assets/explorer

Writes:

- rig.glb: the shared skeleton (all bones and sockets) with animation clips.
- parts/<part>.glb: one equipment or body part, skinned to the same skeleton.
  Each file carries its own copy of the skeleton because glTF skins need one;
  the runtime rebinds the part's skin to the live rig by bone name.
- kit.json: slots, parts, material regions, palettes, presets, sockets,
  effect nodes, clip events and triangle counts.

All parts are built on one body family (the prospector's proportions), so
any part fits any loadout. Effects such as the headlamp and lanterns are
exported as empty nodes named fx.* under their bones; the runtime attaches the
actual lights there, so effects stay independent of meshes.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402

from wylden import core, explorers, parts, poses, rig  # noqa: E402

FPS = 30
LOD_SUBDIV = 1  # subdivision level baked into exported meshes
LOD_DETAIL = 0.55  # segment multiplier for lofts and spheres (renders use 1.0)

# slot, part id, part function, options, extra metadata
KIT = [
    ("head", "head.base", "head", dict(hair=None, beard=False), {}),
    ("hair", "hair.crop", "hair_style", dict(style="crop"), {}),
    ("hair", "hair.tail", "hair_style", dict(style="tail"), {}),
    ("beard", "beard.full", "beard_part", {}, {}),
    ("torso", "torso.work_shirt", "torso", dict(region="cloth_b", hem=0.35, collar=True), {}),
    ("torso", "torso.tunic", "torso", dict(region="cloth_b", hem=0.75), {}),
    ("torso", "torso.tabard", "torso", dict(region="cloth_a", hem=0.85), {}),
    ("arms", "arms.rolled", "arms", dict(region="cloth_a", short=True), {}),
    ("arms", "arms.long", "arms", dict(region="cloth_b"), {}),
    ("hands", "hands.work_gloves", "hands", dict(region="leather", cuff="leather_dark"), {}),
    ("hands", "hands.gauntlets", "hands", dict(region="leather", cuff="metal"), {}),
    ("legs", "legs.trousers", "legs", dict(region="cloth_c"), {}),
    ("feet", "feet.low_boots", "boots", dict(region="leather_dark", height=0.15), {}),
    ("feet", "feet.tall_boots", "boots", dict(region="leather_dark", height=0.26), {}),
    ("feet", "feet.greaves", "boots", dict(region="leather_dark", shaft="metal", height=0.24, cuff="brass"), {}),
    ("belt", "belt.pouch", "belt", dict(region="leather_dark"), {}),
    ("belt", "belt.plain", "belt", dict(region="leather", pouch=False), {}),
    ("over", "over.apron", "apron", dict(region="leather"), {}),
    ("over", "over.breastplate", "breastplate", {}, {}),
    ("shoulders", "shoulders.mantle", "mantle", dict(region="cloth_a"), {}),
    ("shoulders", "shoulders.pauldrons", "pauldrons", {}, {}),
    ("neck", "neck.scarf", "scarf", dict(region="accent"), {}),
    ("hip", "hip.satchel", "satchel", {}, {}),
    ("back", "back.pack", "backpack", dict(region="canvas", roll="cloth_a"), {}),
    ("back", "back.bedroll", "bedroll_back", dict(region="canvas"), {}),
    ("back", "back.shield", "shield_back", dict(face="paint"), {}),
    ("headwear", "headwear.hard_hat", "miner_helmet", {}, {}),
    ("headwear", "headwear.hood", "hood", dict(region="cloth_a"), {"hides": ["hair"]}),
    ("headwear", "headwear.helm", "warden_helm", {}, {"hides": ["hair"]}),
    ("main_hand", "main_hand.pickaxe", "pickaxe", {}, {}),
    ("main_hand", "main_hand.sword", "short_sword", {}, {}),
    ("main_hand", "main_hand.hammer", "hammer", {}, {}),
    ("off_hand", "off_hand.lantern", "lantern_hand", {}, {}),
]

SLOTS = [
    "head",
    "hair",
    "beard",
    "torso",
    "arms",
    "hands",
    "legs",
    "feet",
    "belt",
    "over",
    "shoulders",
    "neck",
    "hip",
    "back",
    "headwear",
    "main_hand",
    "off_hand",
]

BASE = {"head": "head.base", "legs": "legs.trousers"}
PRESETS = {
    "miner": dict(
        palette="prospector",
        clip="mine",
        parts={
            **BASE,
            "hair": "hair.crop",
            "torso": "torso.work_shirt",
            "arms": "arms.rolled",
            "hands": "hands.work_gloves",
            "feet": "feet.low_boots",
            "belt": "belt.pouch",
            "over": "over.apron",
            "back": "back.pack",
            "headwear": "headwear.hard_hat",
            "main_hand": "main_hand.pickaxe",
        },
    ),
    "scout": dict(
        palette="pathfinder",
        clip="walk",
        parts={
            **BASE,
            "hair": "hair.crop",
            "torso": "torso.tunic",
            "arms": "arms.long",
            "hands": "hands.work_gloves",
            "feet": "feet.tall_boots",
            "belt": "belt.plain",
            "shoulders": "shoulders.mantle",
            "neck": "neck.scarf",
            "hip": "hip.satchel",
            "back": "back.bedroll",
            "headwear": "headwear.hood",
            "main_hand": "main_hand.sword",
            "off_hand": "off_hand.lantern",
        },
    ),
    "guard": dict(
        palette="warden",
        clip="idle",
        parts={
            **BASE,
            "beard": "beard.full",
            "torso": "torso.tabard",
            "arms": "arms.long",
            "hands": "hands.gauntlets",
            "feet": "feet.greaves",
            "belt": "belt.pouch",
            "over": "over.breastplate",
            "shoulders": "shoulders.pauldrons",
            "back": "back.shield",
            "headwear": "headwear.helm",
            "main_hand": "main_hand.hammer",
        },
    ),
    "delver": dict(
        palette="delver",
        clip="slash",
        parts={
            **BASE,
            "hair": "hair.tail",
            "torso": "torso.work_shirt",
            "arms": "arms.rolled",
            "hands": "hands.work_gloves",
            "feet": "feet.low_boots",
            "belt": "belt.pouch",
            "shoulders": "shoulders.mantle",
            "neck": "neck.scarf",
            "back": "back.shield",
            "main_hand": "main_hand.sword",
            "off_hand": "off_hand.lantern",
        },
    ),
}


def palettes():
    pal = {k: dict(v) for k, v in explorers.PALETTES.items()}
    pal["delver"] = dict(pal["prospector"], cloth_a="#6A3E7A", accent="#E2C25A", paint="#6A3E7A", hair="#2A2222")
    pal["moss"] = dict(pal["pathfinder"], cloth_a="#4E6E34", cloth_b="#D9CBB0", accent="#D2552A", skin="#C98E68")
    return pal


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------

LIMBS = ("thigh", "shin", "upper_arm", "forearm")


def mirror(pose):
    """Swap left and right limb rotations (abduction flips sign); hands and torso stay."""
    out = {}
    for k, (x, y, z) in pose.items():
        if k.startswith("_"):
            out[k] = (x, y, z)
            continue
        base, _, side = k.rpartition(".")
        if base in LIMBS and side in ("L", "R"):
            out[f"{base}.{'R' if side == 'L' else 'L'}"] = (-x, y, -z)
        else:
            out[k] = (x, y, z)
    return out


WALK_CONTACT = {
    "hips": (0, 4, 0),
    "spine": (0, 3, 0),
    "head": (0, -4, 0),
    "thigh.L": (2, -26, 0),
    "shin.L": (0, 6, 0),
    "thigh.R": (-2, 20, 0),
    "shin.R": (0, 22, 0),
    "upper_arm.L": (6, 18, 0),
    "forearm.L": (0, -20, 0),
    "upper_arm.R": (-6, -20, 0),
    "forearm.R": (0, -30, 0),
    "hand.R": (0, 45, 0),
}
WALK_PASS = {
    "hips": (0, 4, 0),
    "spine": (0, 3, 0),
    "head": (0, -4, 0),
    "thigh.L": (2, -4, 0),
    "shin.L": (0, 8, 0),
    "thigh.R": (-2, -14, 0),
    "shin.R": (0, 48, 0),
    "upper_arm.L": (6, 2, 0),
    "forearm.L": (0, -20, 0),
    "upper_arm.R": (-6, -4, 0),
    "forearm.R": (0, -30, 0),
    "hand.R": (0, 45, 0),
}
IDLE_BREATH = dict(poses.IDLE, chest=(0, 4.5, 0), neck=(0, -3, 0), head=(0, -5, 0))

CLIPS = {
    # name: (keys [(frame, pose)], loop, events [(frame, name)])
    "idle": ([(0, poses.IDLE), (30, IDLE_BREATH), (60, poses.IDLE)], True, []),
    "walk": (
        [(0, WALK_CONTACT), (8, WALK_PASS), (16, mirror(WALK_CONTACT)), (24, mirror(WALK_PASS)), (32, WALK_CONTACT)],
        True,
        [(0, "footstep"), (16, "footstep")],
    ),
    "mine": (
        [
            (0, poses.MINE_WINDUP),
            (10, poses.MINE_WINDUP),
            (16, poses.MINE_STRIKE),
            (24, poses.MINE_STRIKE),
            (36, poses.MINE_WINDUP),
        ],
        True,
        [(16, "impact")],
    ),
    "slash": ([(0, poses.GUARD), (6, poses.SLASH), (14, poses.SLASH), (30, poses.GUARD)], True, [(6, "hit")]),
}


def bake_clips(arm):
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    arm.animation_data_create()
    meta = {}
    for name, (keys, loop, events) in CLIPS.items():
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        arm.animation_data.action = act
        for frame, pose in keys:
            rig.apply_pose(arm, pose)
            for pb in arm.pose.bones:
                pb.keyframe_insert("rotation_quaternion", frame=frame)
                if pb.name == "root":
                    pb.keyframe_insert("location", frame=frame)
        end = keys[-1][0]
        meta[name] = dict(duration=end / FPS, loop=loop, events=[dict(t=f / FPS, name=n) for f, n in events])
    arm.animation_data.action = None
    rig.clear_pose(arm)
    bpy.context.view_layer.update()
    return meta


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_glb(objs, path, animations=False):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_animations=animations,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_skins=True,
        export_def_bones=False,
        export_rest_position_armature=True,
        export_reset_pose_bones=True,
        export_lights=False,
        export_cameras=False,
        export_yup=True,
        export_texcoords=False,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        export_extras=False,
    )


def triangles(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        o.evaluated_get(dg).to_mesh_clear()
    return n


def merge_part(objs, arm, name):
    """Bake each object's modifiers (except the armature) and join them into one skinned mesh."""
    meshes = [o for o in objs if o.type == "MESH"]
    for o in meshes:
        for m in o.modifiers:
            if m.type == "ARMATURE":
                m.show_viewport = False
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.convert(target="MESH")
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    ob.modifiers.new("Armature", "ARMATURE").object = arm
    ob.parent = arm
    return ob


def light_to_fx(light, part_id, idx):
    """Replace a Blender light with an fx.* empty under the same bone; return its effect description."""
    fx = bpy.data.objects.new(f"fx.{part_id}.{idx}", None)
    for c in light.users_collection:
        c.objects.link(fx)
    fx.parent = light.parent
    fx.parent_type = light.parent_type
    fx.parent_bone = light.parent_bone
    fx.matrix_parent_inverse = light.matrix_parent_inverse.copy()
    fx.matrix_basis = light.matrix_basis.copy()
    d = light.data
    eff = dict(
        node=fx.name,
        kind=d.type.lower(),
        color=[round(c, 4) for c in d.color],
        power_w=d.energy,
        radius=round(d.shadow_soft_size, 3),
    )
    if d.type == "SPOT":
        eff.update(angle=round(d.spot_size, 4), blend=round(d.spot_blend, 3))
    bpy.data.objects.remove(light)
    return fx, eff


def main(out):
    out = Path(out)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    core.reset_scene()
    core.DETAIL = LOD_DETAIL
    coll = core.collection("kit")
    body = explorers.BODIES["prospector"]
    B = parts.Builder("kit", body, explorers.PALETTES["prospector"], coll)
    arm = B.arm
    arm.name = "explorer"
    arm.data.name = "explorer"
    manifest_parts = {}
    groups = {}
    for slot, pid, fn, opts, extra in KIT:
        n0, l0 = len(B.parts), len(B.lights)
        getattr(parts, fn)(B, **opts)
        objs, lights = B.parts[n0:], B.lights[l0:]
        for o in objs:
            o.name = f"{pid}.{o.name.split('.', 1)[1]}"
            for m in o.modifiers:
                if m.type == "SUBSURF":
                    m.levels = m.render_levels = min(m.levels, LOD_SUBDIV)
        merged = merge_part(objs, arm, pid)
        objs = [merged]
        fxs, effects = [], []
        for i, lt in enumerate(lights):
            fx, eff = light_to_fx(lt, pid, i)
            fxs.append(fx)
            effects.append(eff)
        regions = sorted({s.material.name.split(".", 1)[1] for o in objs for s in o.material_slots if s.material})
        groups[pid] = objs + fxs
        manifest_parts[pid] = dict(
            slot=slot, file=f"parts/{pid}.glb", regions=regions, effects=effects, triangles=triangles(objs), **extra
        )
    clip_meta = bake_clips(arm)
    rig.clear_pose(arm)
    bpy.context.view_layer.update()
    for pid, objs in groups.items():
        export_glb([arm] + objs, out / "parts" / f"{pid}.glb", animations=False)
    export_glb([arm], out / "rig.glb", animations=True)
    pal = palettes()
    manifest = dict(
        body="explorer_a",
        units="metres; +Y up in glTF (Blender +Z); characters face +X",
        rig="rig.glb",
        skeleton=list(rig.BONE_NAMES),
        sockets=[b for b in rig.BONE_NAMES if b.startswith("socket.")],
        slots=SLOTS,
        clips=clip_meta,
        regions=sorted(parts.REGION_STYLE),
        palettes={
            k: {r: v for r, v in p.items() if r in parts.REGION_STYLE or r in ("glow", "lens")} for k, p in pal.items()
        },
        parts=manifest_parts,
        presets=PRESETS,
        lod=dict(subdivision=LOD_SUBDIV, segment_detail=LOD_DETAIL),
    )
    (out / "kit.json").write_text(json.dumps(manifest, indent=1) + "\n")
    total = {k: sum(manifest_parts[p]["triangles"] for p in v["parts"].values()) for k, v in PRESETS.items()}
    print("parts", len(manifest_parts), "preset triangles", total)
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="client/assets/explorer")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    main(a.out)
