"""Explorer loadouts: body proportions, palettes and part selections.

A loadout is plain data. ``assemble`` turns one into a rigged character, so
the same body can wear any compatible combination of parts and colors.
"""

import math

import bpy

from . import core, parts, rig

PALETTES = {
    "prospector": dict(
        skin="#E2A47C",
        hair="#7C3A1C",
        eye="#17131A",
        cloth_a="#D38A2B",
        cloth_b="#6E8B74",
        cloth_c="#3D4A5E",
        accent="#B8442E",
        canvas="#9A9364",
        leather="#8A5530",
        leather_dark="#4B2F20",
        metal="#A3ABB3",
        brass="#C99B45",
        wood="#8C5B33",
        paint="#E9B23A",
        sole="#2A211C",
        glow="#FFC77A",
        lens="#FFF1D2",
    ),
    "pathfinder": dict(
        skin="#9A6648",
        hair="#231C1C",
        eye="#120F14",
        cloth_a="#2C7C78",
        cloth_b="#E6D8B8",
        cloth_c="#4A4E66",
        accent="#C7432F",
        canvas="#9A9364",
        leather="#7A4E31",
        leather_dark="#3F2A1F",
        metal="#C3CBD3",
        brass="#C9A050",
        wood="#7A5232",
        paint="#2C7C78",
        sole="#241D19",
        glow="#FFB35C",
        lens="#FFF1D2",
    ),
    "warden": dict(
        skin="#EEC19C",
        hair="#B9B2A6",
        eye="#17131A",
        cloth_a="#7A2232",
        cloth_b="#7A2232",
        cloth_c="#30364A",
        accent="#A8323F",
        canvas="#8C8660",
        leather="#6A4329",
        leather_dark="#3A271B",
        metal="#AEB8C2",
        brass="#D3A54B",
        wood="#6E4A2C",
        paint="#2F5D8C",
        sole="#221C18",
        glow="#FFC77A",
        lens="#FFF1D2",
    ),
}

BODIES = {
    "prospector": rig.Body(height=0.97, build=1.12, head=1.06, legs=0.92, arms=1.0, belly=0.6),
    "pathfinder": rig.Body(height=1.04, build=0.9, head=1.0, legs=1.1, arms=1.02, belly=0.0),
    "warden": rig.Body(height=1.1, build=1.2, head=1.0, legs=1.0, arms=1.04, belly=0.3),
}

# slot -> (part function name, options). Order matters only for visibility
# rules: headwear that hides hair must come before the head.
LOADOUTS = {
    "prospector": [
        ("headwear", "miner_helmet", {}),
        ("head", "head", dict(hair="crop", beard=False)),
        ("torso", "torso", dict(region="cloth_b", hem=0.35, collar=True)),
        ("arms", "arms", dict(region="cloth_a", short=True)),
        ("hands", "hands", dict(region="leather", cuff="leather_dark")),
        ("legs", "legs", dict(region="cloth_c")),
        ("feet", "boots", dict(region="leather_dark", height=0.15)),
        ("belt", "belt", dict(region="leather_dark")),
        ("over", "apron", dict(region="leather")),
        ("back", "backpack", dict(region="canvas", roll="cloth_a")),
        ("main_hand", "pickaxe", {}),
    ],
    "pathfinder": [
        ("headwear", "hood", dict(region="cloth_a")),
        ("head", "head", dict(hair="crop")),
        ("torso", "torso", dict(region="cloth_b", hem=0.75)),
        ("arms", "arms", dict(region="cloth_b")),
        ("hands", "hands", dict(region="leather_dark", cuff="leather")),
        ("legs", "legs", dict(region="cloth_c")),
        ("feet", "boots", dict(region="leather_dark", height=0.26)),
        ("belt", "belt", dict(region="leather", pouch=False)),
        ("shoulders", "mantle", dict(region="cloth_a")),
        ("neck", "scarf", dict(region="accent")),
        ("hip", "satchel", {}),
        ("back", "bedroll_back", dict(region="canvas")),
        ("main_hand", "short_sword", {}),
        ("off_hand", "lantern_hand", {}),
    ],
    "warden": [
        ("headwear", "warden_helm", {}),
        ("head", "head", dict(hair=None, beard=True)),
        ("torso", "torso", dict(region="cloth_a", hem=0.85)),
        ("arms", "arms", dict(region="cloth_c")),
        ("hands", "hands", dict(region="leather", cuff="metal")),
        ("legs", "legs", dict(region="cloth_c")),
        ("feet", "boots", dict(region="leather_dark", shaft="metal", height=0.24, cuff="brass")),
        ("over", "breastplate", {}),
        ("belt", "belt", dict(region="leather", pouch=True)),
        ("shoulders", "pauldrons", {}),
        ("back", "shield_back", dict(face="paint")),
        ("main_hand", "hammer", {}),
    ],
}


def assemble(name, body, palette, loadout, coll=None, location=(0, 0, 0), yaw=-25.0):
    coll = coll or core.collection(name)
    B = parts.Builder(name, body, palette, coll)
    for _slot, fn, opts in loadout:
        getattr(parts, fn)(B, **opts)
    B.arm.location = location
    B.arm.rotation_euler = (0, 0, math.radians(yaw))
    bpy.context.view_layer.update()
    return B


def explorer(kind, name=None, location=(0, 0, 0), yaw=-25.0, palette=None, body=None, loadout=None, coll=None):
    return assemble(
        name or kind,
        body or BODIES[kind],
        palette or PALETTES[kind],
        loadout or LOADOUTS[kind],
        coll=coll,
        location=location,
        yaw=yaw,
    )
