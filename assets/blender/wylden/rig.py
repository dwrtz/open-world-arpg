"""Shared explorer skeleton: stable bone names, sockets, binding and posing.

Conventions
-----------
* Characters are built facing +X with +Z up; the side camera looks along +Y,
  so the character's right side (-Y) faces the viewer.
* Every body family uses the same bone names. Proportions move the joints,
  never rename them, so clips and equipment stay compatible.
* Sockets are bones prefixed ``socket.``. Equipment binds to a socket's
  parent bone and is authored relative to the socket's rest position.
* Poses are rotations in armature space (degrees about X, Y, Z). Rotating
  about +Y by a positive angle turns a limb clockwise as seen by the camera.
"""

import math
from dataclasses import dataclass

import bpy
from mathutils import Euler, Matrix, Vector

from . import core

BONE_NAMES = (
    "root",
    "hips",
    "spine",
    "chest",
    "neck",
    "head",
    "upper_arm.L",
    "forearm.L",
    "hand.L",
    "upper_arm.R",
    "forearm.R",
    "hand.R",
    "thigh.L",
    "shin.L",
    "foot.L",
    "thigh.R",
    "shin.R",
    "foot.R",
    "socket.grip.L",
    "socket.grip.R",
    "socket.back",
    "socket.head",
    "socket.hip.L",
)

GRIP_ANGLE = 70.0  # handle leaves the fist this many degrees counter-clockwise of the forearm


@dataclass
class Body:
    """Constrained proportion parameters for the explorer body family."""

    height: float = 1.0
    build: float = 1.0
    head: float = 1.0
    legs: float = 1.0
    arms: float = 1.0
    belly: float = 0.0

    def validate(self):
        ranges = dict(
            height=(0.85, 1.15),
            build=(0.85, 1.25),
            head=(0.9, 1.15),
            legs=(0.85, 1.15),
            arms=(0.9, 1.1),
            belly=(0.0, 1.0),
        )
        for k, (lo, hi) in ranges.items():
            v = getattr(self, k)
            if not lo <= v <= hi:
                raise ValueError(f"Body.{k}={v} outside tested range [{lo}, {hi}]")
        return self


def joints(body: Body):
    b = body.validate()
    s, w = b.height, b.build
    J = {}
    ankle_z = 0.09
    knee_z = ankle_z + 0.33 * b.legs
    hip_z = knee_z + 0.36 * b.legs
    pelvis_z = hip_z + 0.05
    spine_z = pelvis_z + 0.13
    chest_z = spine_z + 0.17
    neck_z = chest_z + 0.17
    head_base = neck_z + 0.08
    head_c = head_base + 0.17 * b.head
    head_top = head_c + 0.22 * b.head
    J["ground"] = Vector((0, 0, 0))
    J["pelvis"] = Vector((0, 0, pelvis_z))
    J["spine"] = Vector((0, 0, spine_z))
    J["chest"] = Vector((0, 0, chest_z))
    J["neck"] = Vector((0, 0, neck_z))
    J["head_base"] = Vector((0, 0, head_base))
    J["head_c"] = Vector((0.01, 0, head_c))
    J["head_top"] = Vector((0, 0, head_top))
    for side, sy in (("L", 1), ("R", -1)):
        sh = Vector((-0.01, sy * 0.215 * w, neck_z - 0.045))
        el = sh + Vector((-0.02, sy * 0.03 * w, -0.27 * b.arms))
        wr = el + Vector((0.035, sy * 0.01 * w, -0.24 * b.arms))
        J[f"shoulder.{side}"] = sh
        J[f"elbow.{side}"] = el
        J[f"wrist.{side}"] = wr
        fdir = (wr - el).normalized()
        J[f"hand_end.{side}"] = wr + fdir * 0.13
        J[f"grip.{side}"] = wr + fdir * 0.065
        J[f"hip.{side}"] = Vector((0.0, sy * 0.1 * w, hip_z))
        J[f"knee.{side}"] = Vector((0.015, sy * 0.105 * w, knee_z))
        J[f"ankle.{side}"] = Vector((0.0, sy * 0.105 * w, ankle_z))
        J[f"toe.{side}"] = Vector((0.17, sy * 0.105 * w, 0.035))
    J["back"] = Vector((-0.17 * w - 0.03 * b.belly, 0, chest_z + 0.04))
    J["hip_socket.L"] = Vector((0.0, 0.2 * w, pelvis_z - 0.02))
    J["belly"] = b.belly
    J["build"] = w
    J["head_size"] = b.head
    for k, v in J.items():
        if isinstance(v, Vector):
            J[k] = v * s
    J["scale"] = s
    return J


def handle_dir(J, side):
    """Rest direction a held tool's handle leaves the fist."""
    f = (J[f"wrist.{side}"] - J[f"elbow.{side}"]).normalized()
    return (Matrix.Rotation(math.radians(-GRIP_ANGLE), 3, "Y") @ f).normalized()


def skeleton(J):
    up = Vector((0, 0, 0.1))
    sk = {
        "root": (J["ground"], J["ground"] + Vector((0, 0, 0.25)), None),
        "hips": (J["pelvis"] - Vector((0, 0, 0.06)), J["spine"], "root"),
        "spine": (J["spine"], J["chest"], "hips"),
        "chest": (J["chest"], J["neck"], "spine"),
        "neck": (J["neck"], J["head_base"], "chest"),
        "head": (J["head_base"], J["head_top"], "neck"),
    }
    for s in ("L", "R"):
        sk[f"upper_arm.{s}"] = (J[f"shoulder.{s}"], J[f"elbow.{s}"], "chest")
        sk[f"forearm.{s}"] = (J[f"elbow.{s}"], J[f"wrist.{s}"], f"upper_arm.{s}")
        sk[f"hand.{s}"] = (J[f"wrist.{s}"], J[f"hand_end.{s}"], f"forearm.{s}")
        sk[f"thigh.{s}"] = (J[f"hip.{s}"], J[f"knee.{s}"], "hips")
        sk[f"shin.{s}"] = (J[f"knee.{s}"], J[f"ankle.{s}"], f"thigh.{s}")
        sk[f"foot.{s}"] = (J[f"ankle.{s}"], J[f"toe.{s}"], f"shin.{s}")
        g = J[f"grip.{s}"]
        sk[f"socket.grip.{s}"] = (g, g + handle_dir(J, s) * 0.1, f"hand.{s}")
    sk["socket.back"] = (J["back"], J["back"] + Vector((-0.1, 0, 0)), "chest")
    sk["socket.head"] = (J["head_c"], J["head_c"] + up, "head")
    sk["socket.hip.L"] = (J["hip_socket.L"], J["hip_socket.L"] - up, "hips")
    assert tuple(sk) == BONE_NAMES or set(sk) == set(BONE_NAMES)
    return sk


def build_armature(name, sk, coll=None):
    data = bpy.data.armatures.new(name)
    data.display_type = "STICK"
    ob = bpy.data.objects.new(name, data)
    core.link(ob, coll)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    for bname, (head, tail, parent) in sk.items():
        eb = data.edit_bones.new(bname)
        eb.head, eb.tail, eb.roll = head, tail, 0.0
        if parent:
            eb.parent = data.edit_bones[parent]
        eb.use_deform = not bname.startswith("socket.")
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.hide_render = True
    return ob


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (a + ab * t - p).length


def bind(ob, arm, sk, bones, power=8.0):
    """Skin a part to one bone (rigid) or blend it across several by distance."""
    if isinstance(bones, str):
        bones = [bones]
    deform = []
    for b in bones:
        target = sk[b][2] if b.startswith("socket.") else b
        if target not in deform:
            deform.append(target)
    groups = [ob.vertex_groups.new(name=b) for b in deform]
    n = len(ob.data.vertices)
    if len(deform) == 1:
        groups[0].add(range(n), 1.0, "REPLACE")
    else:
        for v in ob.data.vertices:
            ds = [_seg_dist(v.co, sk[b][0], sk[b][1]) for b in deform]
            ws = [1.0 / (d + 0.015) ** power for d in ds]
            tot = sum(ws)
            for g, wgt in zip(groups, ws):
                if wgt / tot > 0.01:
                    g.add([v.index], wgt / tot, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    ob.parent = arm
    return ob


# ---------------------------------------------------------------------------
# Posing
# ---------------------------------------------------------------------------


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)


def apply_pose(arm, pose, plant_feet=True, ground=True):
    """pose: {bone: (x, y, z) degrees in armature space, '_offset': (x, y, z)}."""
    clear_pose(arm)
    pose = dict(pose)
    offset = pose.pop("_offset", (0, 0, 0))
    if plant_feet:
        for s in ("L", "R"):
            key = f"foot.{s}"
            if key not in pose:
                pitch = sum(pose.get(b, (0, 0, 0))[1] for b in ("hips", f"thigh.{s}", f"shin.{s}"))
                pose[key] = (0, -pitch, 0)
    for name, rot in pose.items():
        pb = arm.pose.bones[name]
        r = Euler([math.radians(a) for a in rot], "XYZ").to_quaternion()
        b = pb.bone.matrix_local.to_quaternion()
        pb.rotation_quaternion = b.inverted() @ r @ b
    root = arm.pose.bones["root"]
    rest = root.bone.matrix_local.to_quaternion()
    root.location = rest.inverted() @ Vector(offset)
    bpy.context.view_layer.update()
    if ground:
        lowest = min(
            min(arm.pose.bones[f"foot.{s}"].head.z - 0.09, arm.pose.bones[f"foot.{s}"].tail.z - 0.035)
            for s in ("L", "R")
        )
        root.location = rest.inverted() @ (Vector(offset) - Vector((0, 0, lowest)))
        bpy.context.view_layer.update()
    return arm


def bone_world(arm, name, tail=False):
    pb = arm.pose.bones[name]
    return arm.matrix_world @ (pb.tail if tail else pb.head)
