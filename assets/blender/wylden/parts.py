"""Modular explorer parts.

Every part is a function ``part(B, **options)`` that builds meshes against the
shared skeleton held by the Builder ``B`` and binds them to named bones. Parts
only reference joints, bones and semantic material regions, so any body
proportions and any palette can be combined with any compatible part.
"""

import math

from mathutils import Matrix, Vector

from . import core, rig

V = Vector


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Material regions
# ---------------------------------------------------------------------------

REGION_STYLE = {
    "skin": dict(rough=0.5, sss=0.12),
    "hair": dict(rough=0.6, sheen=0.4, bump=0.25, bump_scale=90),
    "eye": dict(rough=0.15, coat=1.0),
    "cloth_a": dict(rough=0.85, sheen=0.5, bump=0.12, bump_scale=160),
    "cloth_b": dict(rough=0.85, sheen=0.5, bump=0.12, bump_scale=160),
    "cloth_c": dict(rough=0.85, sheen=0.4, bump=0.12, bump_scale=160),
    "accent": dict(rough=0.8, sheen=0.5, bump=0.12, bump_scale=160),
    "canvas": dict(rough=0.9, sheen=0.3, bump=0.25, bump_scale=120),
    "leather": dict(rough=0.55, coat=0.15, bump=0.2, bump_scale=60),
    "leather_dark": dict(rough=0.6, coat=0.1, bump=0.2, bump_scale=60),
    "metal": dict(metal=1.0, rough=0.3, bump=0.04, bump_scale=30),
    "brass": dict(metal=1.0, rough=0.28),
    "wood": dict(rough=0.65, bump=0.3, bump_scale=50),
    "paint": dict(rough=0.38, coat=0.4, bump=0.03, bump_scale=30),
    "sole": dict(rough=0.8),
}


class Builder:
    """Collects a character's parts around one armature."""

    def __init__(self, name, body, palette, coll):
        self.name = name
        self.coll = coll
        self.palette = palette
        self.J = rig.joints(body)
        self.sk = rig.skeleton(self.J)
        self.arm = rig.build_armature(f"{name}.rig", self.sk, coll)
        self.s = self.J["scale"]
        self.parts = []
        self.lights = []
        self._mats = {}
        self.hidden_slots = set()

    def mat(self, region):
        if region not in self._mats:
            if region == "glow":
                self._mats[region] = core.emission(f"{self.name}.glow", self.palette.get("glow", "#ffd9a0"), 18.0)
            elif region == "lens":
                self._mats[region] = core.emission(f"{self.name}.lens", self.palette.get("lens", "#fff2d6"), 40.0)
            else:
                style = REGION_STYLE[region]
                self._mats[region] = core.principled(f"{self.name}.{region}", self.palette[region], **style)
        return self._mats[region]

    def add(self, ob, bones, region, sub=2, thick=None, offset=1.0):
        ob.name = f"{self.name}.{ob.name}"
        rig.bind(ob, self.arm, self.sk, bones)
        if thick:
            core.solidify(ob, thick, offset)
        if sub:
            core.subsurf(ob, sub)
        core.set_material(ob, self.mat(region))
        if ob.users_collection and ob.users_collection[0] is not self.coll:
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            self.coll.objects.link(ob)
        self.parts.append(ob)
        return ob

    def attach(self, ob, bone):
        """Parent a non-deforming object (light, empty) to a bone at its rest pose."""
        b = self.arm.data.bones[bone]
        ob.parent = self.arm
        ob.parent_type = "BONE"
        ob.parent_bone = bone
        rest = self.arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
        ob.matrix_parent_inverse = rest.inverted()
        if ob.users_collection and ob.users_collection[0] is not self.coll:
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            self.coll.objects.link(ob)
        return ob

    def frame(self, side):
        """Tool frame at a grip: (origin, u along handle, w up-ish, lateral)."""
        g = self.J[f"grip.{side}"]
        u = rig.handle_dir(self.J, side)
        lat = V((0, 1, 0))
        w = u.cross(lat).normalized()
        return g, u, w, lat


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------


def head(B, hair="crop", beard=False, brows=True):
    J, s = B.J, B.s
    hs = J["head_size"]
    c = J["head_c"]
    r = 0.19 * s * hs
    B.add(core.ellipsoid("head", c, (r * 1.02, r * 0.94, r * 1.03)), "head", "skin")
    B.add(core.ellipsoid("jaw", c + V((0.045, 0, -0.085)) * s, (r * 0.74, r * 0.76, r * 0.6)), "head", "skin")
    B.add(core.ellipsoid("nose", c + V((r * 1.0, 0, -0.035 * s)), (0.05 * s, 0.034 * s, 0.042 * s)), "head", "skin")
    for sy in (-1, 1):
        B.add(
            core.ellipsoid(f"ear{sy}", c + V((-0.02 * s, sy * r * 0.9, -0.02 * s)), (0.04 * s, 0.022 * s, 0.055 * s)),
            "head",
            "skin",
        )
        d = V((0.84, sy * 0.42, 0.1)).normalized()
        p = c + V((d.x * r * 1.0, d.y * r * 0.92, d.z * r * 1.0))
        rot = d.to_track_quat("X", "Z").to_matrix()
        B.add(core.ellipsoid(f"eye{sy}", p, (0.016 * s, 0.026 * s, 0.038 * s), rot=rot), "head", "eye", sub=1)
        if brows:
            bp = p + V((0.012, 0, 0.055)) * s
            B.add(core.ellipsoid(f"brow{sy}", bp, (0.02 * s, 0.032 * s, 0.012 * s), rot=rot), "head", "hair", sub=1)
    neck = J["neck"]
    B.add(
        core.loft(
            "neck",
            [
                (neck - V((0, 0, 0.03 * s)), 0.065 * s, 0.07 * s),
                (J["head_base"] + V((0.01, 0, 0.05)) * s, 0.06 * s, 0.065 * s),
            ],
            cap=(None, None),
        ),
        ["neck", "chest"],
        "skin",
    )
    if hair and "hair" not in B.hidden_slots:
        hair_style(B, hair)
    if beard:
        B.add(core.ellipsoid("beard", c + V((0.085, 0, -0.13)) * s, (0.115 * s, 0.135 * s, 0.13 * s)), "head", "hair")
        B.add(core.ellipsoid("beard_tip", c + V((0.12, 0, -0.24)) * s, (0.07 * s, 0.08 * s, 0.07 * s)), "head", "hair")
        for sy in (-1, 1):
            B.add(
                core.ellipsoid(
                    f"moustache{sy}", c + V((0.175, sy * 0.045, -0.07)) * s, (0.035 * s, 0.06 * s, 0.025 * s)
                ),
                "head",
                "hair",
            )


def hair_style(B, style):
    J, s = B.J, B.s
    c = J["head_c"]
    r = 0.19 * s * J["head_size"]

    def crop(u):
        if u.x > 0.38:
            return u.z > 0.5 - 0.15 * abs(u.y)
        if abs(u.y) > 0.75 and u.x > -0.1:
            return u.z > -0.25
        return u.z > -0.15 - 0.55 * _clamp(-u.x, 0, 1)

    sh = core.shell("hair", c + V((-0.012, 0, 0.012)) * s, (r * 1.08, r * 1.0, r * 1.08), crop)
    B.add(sh, "head", "hair", thick=0.03 * s)
    # Fringe tuft gives the profile a readable brow line.
    B.add(
        core.ellipsoid(
            "fringe",
            c + V((0.11, -0.02, 0.15)) * s,
            (0.09 * s, 0.12 * s, 0.05 * s),
            rot=Matrix.Rotation(math.radians(-20), 3, "Y"),
        ),
        "head",
        "hair",
    )
    if style == "bun":
        B.add(core.ellipsoid("bun", c + V((-0.19, 0, 0.1)) * s, (0.085 * s, 0.085 * s, 0.085 * s)), "head", "hair")
    if style == "tail":
        pts = [
            c + V((-0.19, 0, 0.05)) * s,
            c + V((-0.27, 0, -0.08)) * s,
            c + V((-0.3, 0, -0.24)) * s,
            c + V((-0.27, 0, -0.38)) * s,
        ]
        rad = [0.06, 0.07, 0.055, 0.02]
        B.add(core.loft("tail", [(p, rr * s, rr * s) for p, rr in zip(pts, rad)], x_hint=(0, 0, 1)), ["head"], "hair")


def torso(B, region="cloth_b", hem=0.6, collar=False, belly_region=None):
    J, s, w = B.J, B.s, B.J["build"]
    bel = J["belly"]
    P, Sp, C, N = (J[k].z for k in ("pelvis", "spine", "chest", "neck"))
    rings = []
    if hem > 0:
        rings.append((V((0.01 * s, 0, P - 0.26 * s * hem)), (0.163 + 0.03 * hem) * s * w, (0.168 + 0.03 * hem) * s * w))
    rings += [
        (V((0, 0, P - 0.07 * s)), 0.16 * s * w, 0.172 * s * w),
        (V((0.005 * s, 0, P + 0.05 * s)), (0.148 + 0.05 * bel) * s * w, 0.165 * s * w),
        (V(((0.012 + 0.04 * bel) * s, 0, Sp + 0.05 * s)), (0.155 + 0.07 * bel) * s * w, 0.178 * s * w),
        (V((0.006 * s, 0, C + 0.05 * s)), 0.162 * s * w, 0.2 * s * w, 2.4),
        (V((-0.01 * s, 0, N - 0.035 * s)), 0.13 * s * w, 0.205 * s * w, 3.0),
        (V((-0.01 * s, 0, N + 0.005 * s)), 0.075 * s, 0.085 * s),
    ]
    bones = ["hips", "spine", "chest"] + (["thigh.L", "thigh.R"] if hem > 0.3 else [])
    B.add(core.loft("torso", rings, seg=20, cap=(0.4, None)), bones, region)
    if collar:
        B.add(
            core.loft(
                "collar",
                [(V((0, 0, N - 0.03 * s)), 0.11 * s, 0.13 * s), (V((-0.01 * s, 0, N + 0.05 * s)), 0.095 * s, 0.11 * s)],
                seg=18,
                cap=(None, None),
            ),
            ["chest", "neck"],
            region,
            thick=0.02 * s,
        )


def arms(B, region="cloth_b", short=False, skin="skin"):
    J, s, w = B.J, B.s, B.J["build"]
    for side, sy in (("L", 1), ("R", -1)):
        sh, el, wr = J[f"shoulder.{side}"], J[f"elbow.{side}"], J[f"wrist.{side}"]
        top = sh + V((0, -sy * 0.03 * s, 0.03 * s))
        upper = [
            (top, 0.08 * s * w, 0.075 * s * w),
            (sh, 0.078 * s * w, 0.074 * s * w),
            (sh.lerp(el, 0.5), 0.066 * s * w, 0.064 * s * w),
            (el, 0.06 * s * w, 0.058 * s * w),
        ]
        lower = [
            (el.lerp(wr, 0.5), 0.056 * s * w, 0.054 * s * w),
            (wr - (wr - el).normalized() * 0.015 * s, 0.05 * s * w, 0.048 * s * w),
        ]
        if short:
            B.add(
                core.loft(
                    f"sleeve.{side}", upper + [(el + (wr - el) * 0.12, 0.062 * s * w, 0.06 * s * w)], cap=(0.6, 0.2)
                ),
                [f"upper_arm.{side}", f"forearm.{side}"],
                region,
            )
            B.add(
                core.loft(f"forearm.{side}", [(el, 0.052 * s * w, 0.05 * s * w)] + lower, cap=(0.5, 0.3)),
                [f"upper_arm.{side}", f"forearm.{side}"],
                skin,
            )
        else:
            B.add(
                core.loft(f"sleeve.{side}", upper + lower, cap=(0.6, 0.3)),
                [f"upper_arm.{side}", f"forearm.{side}"],
                region,
            )


def hands(B, region="skin", cuff=None):
    J, s = B.J, B.s
    for side in ("L", "R"):
        el, wr = J[f"elbow.{side}"], J[f"wrist.{side}"]
        f = (wr - el).normalized()
        x = V((1, 0, 0))
        x = (x - x.dot(f) * f).normalized()
        rings = [
            (wr - f * 0.01 * s, 0.04 * s, 0.034 * s),
            (wr + f * 0.04 * s, 0.056 * s, 0.038 * s),
            (wr + f * 0.085 * s, 0.054 * s, 0.037 * s),
            (wr + f * 0.12 * s, 0.034 * s, 0.028 * s),
        ]
        B.add(core.loft(f"hand.{side}", rings, cap=(0.4, 0.8), x_hint=x), f"hand.{side}", region)
        t0 = wr + f * 0.03 * s + x * 0.035 * s
        B.add(
            core.loft(
                f"thumb.{side}",
                [(t0, 0.02 * s, 0.02 * s), (t0 + (x * 0.025 + f * 0.04) * s, 0.017 * s, 0.017 * s)],
                cap=(0.5, 0.9),
            ),
            f"hand.{side}",
            region,
        )
        if cuff:
            B.add(
                core.loft(
                    f"cuff.{side}",
                    [(wr - f * 0.05 * s, 0.062 * s, 0.06 * s), (wr + f * 0.012 * s, 0.058 * s, 0.056 * s)],
                    cap=(None, None),
                ),
                [f"forearm.{side}"],
                cuff,
                thick=0.012 * s,
            )


def legs(B, region="cloth_c"):
    J, s, w = B.J, B.s, B.J["build"]
    for side in ("L", "R"):
        hp, kn, an = J[f"hip.{side}"], J[f"knee.{side}"], J[f"ankle.{side}"]
        rings = [
            (hp + V((0, 0, 0.07)) * s, 0.11 * s * w, 0.1 * s * w),
            (hp, 0.108 * s * w, 0.098 * s * w),
            (hp.lerp(kn, 0.5), 0.092 * s * w, 0.086 * s * w),
            (kn, 0.074 * s * w, 0.071 * s * w),
            (kn.lerp(an, 0.5), 0.07 * s * w, 0.066 * s * w),
            (an + V((0, 0, 0.05)) * s, 0.062 * s, 0.06 * s),
        ]
        B.add(core.loft(f"leg.{side}", rings, cap=(0.5, 0.5)), [f"thigh.{side}", f"shin.{side}"], region)


def boots(B, region="leather_dark", shaft=None, height=0.17, cuff="leather"):
    J, s = B.J, B.s
    for side in ("L", "R"):
        an, toe = J[f"ankle.{side}"], J[f"toe.{side}"]
        top = an + V((-0.01, 0, height)) * s
        B.add(
            core.loft(
                f"boot_shaft.{side}",
                [(top, 0.076 * s, 0.073 * s), (an + V((-0.01, 0, -0.02)) * s, 0.072 * s, 0.07 * s)],
                cap=(None, 0.7),
            ),
            [f"shin.{side}", f"foot.{side}"],
            shaft or region,
        )
        if cuff:
            B.add(
                core.loft(
                    f"boot_cuff.{side}",
                    [
                        (top + V((0, 0, -0.035)) * s, 0.086 * s, 0.083 * s),
                        (top + V((0, 0, 0.012)) * s, 0.083 * s, 0.08 * s),
                    ],
                    cap=(None, None),
                ),
                f"shin.{side}",
                cuff,
                thick=0.012 * s,
            )
        heel = an + V((-0.065, 0, -0.045)) * s
        mid = an + V((0.05, 0, -0.042)) * s
        foot = [
            (heel, 0.045 * s, 0.05 * s),
            (mid, 0.05 * s, 0.058 * s),
            (toe + V((-0.035, 0, 0.005)) * s, 0.04 * s, 0.056 * s),
            (toe + V((0.005, 0, 0.0)) * s, 0.032 * s, 0.05 * s),
        ]
        B.add(core.loft(f"boot_foot.{side}", foot, cap=(0.6, 0.8), x_hint=(0, 0, 1)), f"foot.{side}", region)
        sole = [
            (V((heel.x - 0.012 * s, heel.y, 0.012 * s)), 0.012 * s, 0.054 * s, 4.0),
            (V((toe.x + 0.012 * s, toe.y, 0.012 * s)), 0.012 * s, 0.054 * s, 4.0),
        ]
        B.add(core.loft(f"sole.{side}", sole, cap=(0.8, 1.5), x_hint=(0, 0, 1)), f"foot.{side}", "sole")


def belt(B, region="leather", buckle="brass", pouch=True):
    J, s, w = B.J, B.s, B.J["build"]
    bel = J["belly"]
    P = J["pelvis"].z
    rx, ry = (0.158 + 0.05 * bel) * s * w, 0.172 * s * w
    B.add(
        core.loft(
            "belt",
            [(V((0.006 * s, 0, P + 0.015 * s)), rx, ry), (V((0.006 * s, 0, P + 0.07 * s)), rx, ry)],
            seg=24,
            cap=(None, None),
        ),
        ["hips", "spine"],
        region,
        thick=0.014 * s,
    )
    B.add(
        core.loft(
            "buckle",
            [
                (V((rx + 0.016 * s, 0, P + 0.043 * s)), 0.03 * s, 0.035 * s, 4.0),
                (V((rx + 0.026 * s, 0, P + 0.043 * s)), 0.03 * s, 0.035 * s, 4.0),
            ],
            x_hint=(0, 0, 1),
            cap=(0.3, 0.3),
        ),
        "hips",
        buckle,
        sub=1,
    )
    if pouch:
        c = V((0.03 * s, -ry - 0.015 * s, P - 0.03 * s))
        B.add(
            core.loft(
                "pouch",
                [
                    (c - V((0, 0, 0.06)) * s, 0.06 * s, 0.03 * s, 3.0),
                    (c + V((0, 0, 0.06)) * s, 0.06 * s, 0.03 * s, 3.0),
                ],
                cap=(0.5, 0.3),
            ),
            "hips",
            region,
        )
        B.add(
            core.loft(
                "pouch_flap",
                [
                    (c + V((0, -0.004, 0.035)) * s, 0.064 * s, 0.034 * s, 3.0),
                    (c + V((0, -0.004, 0.068)) * s, 0.064 * s, 0.034 * s, 3.0),
                ],
                cap=(0.3, 0.3),
            ),
            "hips",
            "leather_dark",
        )


def apron(B, region="leather"):
    J, s, w = B.J, B.s, B.J["build"]
    P, C = J["pelvis"].z, J["chest"].z
    top = V((0.17 * s * w, 0, C + 0.02 * s))
    bot = V((0.2 * s * w, 0, P - 0.26 * s))
    rings = [
        (top, 0.012 * s, 0.13 * s * w, 3.0),
        (V((0.175 * s * w + 0.04 * s * J["belly"], 0, P + 0.05 * s)), 0.012 * s, 0.16 * s * w, 3.0),
        (bot, 0.012 * s, 0.16 * s * w, 3.0),
    ]
    B.add(
        core.loft("apron", rings, cap=(0.4, 0.4), x_hint=(1, 0, 0)),
        ["chest", "spine", "hips", "thigh.L", "thigh.R"],
        region,
    )


def pauldrons(B, region="metal", trim="brass"):
    J, s = B.J, B.s
    for side, sy in (("L", 1), ("R", -1)):
        sh = J[f"shoulder.{side}"]
        c = sh + V((0, sy * 0.025, 0.035)) * s
        B.add(
            core.shell(f"pauldron.{side}", c, (0.125 * s, 0.115 * s, 0.11 * s), lambda u: u.z > -0.25),
            f"upper_arm.{side}",
            region,
            thick=0.022 * s,
        )
        B.add(
            core.shell(
                f"pauldron2.{side}",
                c - V((0, -sy * 0.01, 0.06)) * s,
                (0.12 * s, 0.112 * s, 0.1 * s),
                lambda u: -0.1 < u.z < 0.55,
            ),
            f"upper_arm.{side}",
            region,
            thick=0.018 * s,
        )
        B.add(
            core.ellipsoid(f"rivet.{side}", c + V((0, sy * 0.105, 0.04)) * s, (0.018 * s,) * 3),
            f"upper_arm.{side}",
            trim,
            sub=1,
        )


def breastplate(B, region="metal"):
    J, s, w = B.J, B.s, B.J["build"]
    Sp, C, N = J["spine"].z, J["chest"].z, J["neck"].z
    rings = [
        (V((0.012 * s, 0, Sp + 0.0 * s)), 0.172 * s * w, 0.19 * s * w),
        (V((0.02 * s, 0, C + 0.05 * s)), 0.18 * s * w, 0.215 * s * w, 2.4),
        (V((-0.005 * s, 0, N - 0.04 * s)), 0.15 * s * w, 0.2 * s * w, 2.8),
        (V((-0.01 * s, 0, N + 0.01 * s)), 0.1 * s * w, 0.12 * s * w),
    ]
    B.add(core.loft("breastplate", rings, seg=20, cap=(None, None)), ["spine", "chest"], region, thick=0.02 * s)


def mantle(B, region="cloth_a"):
    J, s, w = B.J, B.s, B.J["build"]
    N = J["neck"].z
    rings = [
        (V((-0.01 * s, 0, N + 0.05 * s)), 0.09 * s, 0.1 * s),
        (V((-0.02 * s, 0, N - 0.03 * s)), 0.175 * s * w, 0.25 * s * w),
        (V((-0.03 * s, 0, N - 0.12 * s)), 0.205 * s * w, 0.285 * s * w),
        (V((-0.04 * s, 0, N - 0.2 * s)), 0.215 * s * w, 0.295 * s * w),
    ]
    B.add(core.loft("mantle", rings, seg=24, cap=(None, None)), ["chest", "neck"], region, thick=0.016 * s)


def scarf(B, region="accent"):
    J, s = B.J, B.s
    N = J["neck"].z
    B.add(
        core.loft(
            "scarf",
            [(V((0, 0, N - 0.02 * s)), 0.11 * s, 0.12 * s), (V((-0.005 * s, 0, N + 0.06 * s)), 0.095 * s, 0.105 * s)],
            seg=18,
            cap=(None, None),
        ),
        ["chest", "neck"],
        region,
        thick=0.035 * s,
    )
    pts = [
        (-0.09, -0.05, 0.0),
        (-0.2, -0.07, -0.07),
        (-0.33, -0.06, -0.09),
        (-0.46, -0.05, -0.06),
        (-0.58, -0.05, -0.1),
        (-0.66, -0.05, -0.17),
    ]
    widths = [0.055, 0.055, 0.052, 0.05, 0.047, 0.042]
    rings = [(V((x * s, y * s, N + z * s)), wd * s, 0.012 * s, 2.5) for (x, y, z), wd in zip(pts, widths)]
    B.add(core.loft("scarf_tail", rings, cap=(0.3, 0.3), x_hint=(0, 0, 1)), "chest", region)


# ---------------------------------------------------------------------------
# Headwear
# ---------------------------------------------------------------------------


def miner_helmet(B, region="paint", trim="leather_dark", lamp=True):
    J, s = B.J, B.s
    c = J["head_c"]
    r = 0.19 * s * J["head_size"]
    cc = c + V((0, 0, 0.035)) * s
    B.add(core.shell("helmet", cc, (r * 1.16, r * 1.1, r * 1.12), lambda u: u.z > 0.12), "head", region, thick=0.02 * s)
    bz = cc.z + r * 1.12 * 0.12
    B.add(
        core.loft(
            "brim",
            [
                (V((cc.x - 0.01 * s, 0, bz + 0.004 * s)), r * 1.34, r * 1.24),
                (V((cc.x - 0.01 * s, 0, bz - 0.012 * s)), r * 1.36, r * 1.26),
            ],
            seg=28,
            cap=(0.15, 0.15),
        ),
        "head",
        region,
    )
    B.add(
        core.loft(
            "ridge",
            [
                (cc + V((r * 0.95, 0, r * 0.6)), 0.03 * s, 0.03 * s),
                (cc + V((r * 0.3, 0, r * 1.12)), 0.035 * s, 0.035 * s),
                (cc + V((-r * 0.5, 0, r * 1.0)), 0.035 * s, 0.035 * s),
                (cc + V((-r * 1.05, 0, r * 0.45)), 0.03 * s, 0.03 * s),
            ],
            x_hint=(0, 1, 0),
        ),
        "head",
        region,
    )
    if lamp:
        base = cc + V((r * 1.08, 0, r * 0.5))
        B.add(
            core.loft(
                "lamp",
                [(base - V((0.02, 0, 0)) * s, 0.04 * s, 0.04 * s), (base + V((0.05, 0, 0)) * s, 0.05 * s, 0.05 * s)],
                x_hint=(0, 0, 1),
                cap=(0.4, 0.0),
            ),
            "head",
            "brass",
        )
        B.add(
            core.ellipsoid("lens", base + V((0.052, 0, 0)) * s, (0.012 * s, 0.042 * s, 0.042 * s)),
            "head",
            "lens",
            sub=1,
        )
        sp = core.light(
            f"{B.name}.headlamp",
            "SPOT",
            base + V((0.08, 0, 0)) * s,
            140,
            color="#ffe2b0",
            size=0.03,
            spot=(48, 0.5),
            rotation=(0, -80, 0),
        )
        B.attach(sp, "head")
        B.lights.append(sp)


def hood(B, region="cloth_a"):
    J, s = B.J, B.s
    B.hidden_slots.add("hair")
    c = J["head_c"]
    r = 0.19 * s * J["head_size"]

    def keep(u):
        if u.z < -0.8:
            return False
        return not (u.x > 0.3 - 0.25 * max(0.0, -u.z) and -0.7 < u.z < 0.62)

    B.add(
        core.shell("hood", c + V((-0.03, 0, 0.02)) * s, (r * 1.24, r * 1.18, r * 1.22), keep),
        "head",
        region,
        thick=0.022 * s,
    )
    pts = [
        c + V((-0.19, 0, 0.13)) * s,
        c + V((-0.3, 0, 0.06)) * s,
        c + V((-0.38, 0, -0.04)) * s,
        c + V((-0.43, 0, -0.12)) * s,
    ]
    rad = [0.1, 0.07, 0.045, 0.012]
    B.add(
        core.loft("hood_tip", [(p, rr * s, rr * s * 0.8) for p, rr in zip(pts, rad)], x_hint=(0, 0, 1)), "head", region
    )


def warden_helm(B, region="metal", crest="accent", trim="brass"):
    J, s = B.J, B.s
    B.hidden_slots.add("hair")
    c = J["head_c"]
    r = 0.19 * s * J["head_size"]

    def keep(u):
        if u.z < -0.45:
            return False
        return not (u.x > 0.5 and -0.45 < u.z < 0.28)

    cc = c + V((-0.005, 0, 0.02)) * s
    B.add(core.shell("helm", cc, (r * 1.14, r * 1.08, r * 1.14), keep), "head", region, thick=0.022 * s)
    B.add(
        core.loft(
            "helm_band",
            [(cc + V((0, 0, r * 0.18)), r * 1.17, r * 1.11), (cc + V((0, 0, r * 0.34)), r * 1.15, r * 1.09)],
            seg=28,
            cap=(None, None),
        ),
        "head",
        trim,
        thick=0.012 * s,
    )
    B.add(
        core.loft(
            "noseguard",
            [
                (cc + V((r * 1.14, 0, r * 0.3)), 0.012 * s, 0.022 * s, 3.0),
                (cc + V((r * 1.2, 0, -r * 0.25)), 0.012 * s, 0.02 * s, 3.0),
            ],
            x_hint=(1, 0, 0),
            cap=(0.3, 0.5),
        ),
        "head",
        region,
        sub=1,
    )
    arc = []
    for a in range(70, -170, -20):
        t = math.radians(a)
        arc.append(cc + V((math.cos(t) * r * 1.2, 0, math.sin(t) * r * 1.22 + 0.02 * s)))
    widths = [0.04, 0.06, 0.075, 0.085, 0.09, 0.09, 0.085, 0.08, 0.07, 0.055, 0.04, 0.025]
    rings = [(p, wd * s, 0.028 * s) for p, wd in zip(arc, widths)]
    B.add(core.loft("crest", rings, cap=(0.6, 0.6), x_hint=(0, 0, 1)), "head", crest)


# ---------------------------------------------------------------------------
# Back gear
# ---------------------------------------------------------------------------


def backpack(B, region="canvas", strap="leather", roll="cloth_c", lantern=True):
    J, s, w = B.J, B.s, B.J["build"]
    C, N = J["chest"].z, J["neck"].z
    bx = J["back"].x - 0.1 * s
    rings = [
        (V((bx, 0, C - 0.22 * s)), 0.11 * s, 0.17 * s * w, 3.5),
        (V((bx - 0.01 * s, 0, C + 0.05 * s)), 0.12 * s, 0.18 * s * w, 3.5),
        (V((bx, 0, C + 0.25 * s)), 0.105 * s, 0.165 * s * w, 3.5),
    ]
    B.add(core.loft("pack", rings, cap=(0.35, 0.5)), "chest", region)
    B.add(
        core.loft(
            "pack_flap",
            [
                (V((bx - 0.005 * s, 0, C + 0.12 * s)), 0.126 * s, 0.17 * s * w, 3.5),
                (V((bx, 0, C + 0.29 * s)), 0.11 * s, 0.168 * s * w, 3.5),
            ],
            cap=(None, 0.6),
        ),
        "chest",
        "leather",
        thick=0.01 * s,
    )
    B.add(
        core.loft(
            "pack_pocket",
            [
                (V((bx - 0.13 * s, 0, C - 0.16 * s)), 0.04 * s, 0.11 * s * w, 3.0),
                (V((bx - 0.13 * s, 0, C - 0.02 * s)), 0.04 * s, 0.11 * s * w, 3.0),
            ],
            cap=(0.6, 0.4),
        ),
        "chest",
        region,
    )
    ry = 0.26 * s * w
    rz = C + 0.36 * s
    B.add(
        core.loft(
            "bedroll",
            [(V((bx + 0.005 * s, -ry, rz)), 0.075 * s, 0.075 * s), (V((bx + 0.005 * s, ry, rz)), 0.075 * s, 0.075 * s)],
            cap=(0.3, 0.3),
        ),
        "chest",
        roll,
    )
    for y in (-0.6, 0.6):
        B.add(
            core.loft(
                f"roll_band{y}",
                [
                    (V((bx + 0.005 * s, y * ry - 0.012 * s, rz)), 0.081 * s, 0.081 * s),
                    (V((bx + 0.005 * s, y * ry + 0.012 * s, rz)), 0.081 * s, 0.081 * s),
                ],
                cap=(None, None),
            ),
            "chest",
            strap,
            thick=0.006 * s,
        )
    for sy in (-1, 1):
        y = sy * 0.12 * s * w
        pts = [
            V((bx + 0.05 * s, y, C + 0.22 * s)),
            V((-0.02 * s, y, N + 0.03 * s)),
            V((0.13 * s, y, N - 0.06 * s)),
            V((0.17 * s * w, y * 0.95, C + 0.0 * s)),
            V((0.165 * s * w, y * 0.9, C - 0.12 * s)),
        ]
        B.add(
            core.loft(f"strap{sy}", [(p, 0.008 * s, 0.03 * s, 3.0) for p in pts], x_hint=(1, 0, 0.4), cap=(0.2, 0.2)),
            "chest",
            strap,
            sub=1,
        )
    if lantern:
        lc = V((bx + 0.02 * s, -0.22 * s * w, C - 0.1 * s))
        _lantern(B, lc, "chest", hang=0.0)


def _lantern(B, top, bone, hang=0.06):
    s = B.s
    t = top - V((0, 0, hang)) * s
    ring = [
        t + V((math.cos(a) * 0.025, 0, math.sin(a) * 0.03 + 0.03)) * s
        for a in [math.radians(d) for d in range(-90, 271, 30)]
    ]
    B.add(
        core.loft("lantern_ring", [(p, 0.006 * s, 0.006 * s) for p in ring], x_hint=(0, 1, 0), cap=(None, None)),
        bone,
        "brass",
        sub=1,
    )
    B.add(
        core.loft(
            "lantern_cap", [(t, 0.012 * s, 0.012 * s), (t - V((0, 0, 0.04)) * s, 0.055 * s, 0.055 * s)], cap=(0.3, 0.2)
        ),
        bone,
        "brass",
        sub=1,
    )
    B.add(
        core.loft(
            "lantern_glass",
            [
                (t - V((0, 0, 0.04)) * s, 0.042 * s, 0.042 * s),
                (t - V((0, 0, 0.1)) * s, 0.048 * s, 0.048 * s),
                (t - V((0, 0, 0.15)) * s, 0.042 * s, 0.042 * s),
            ],
            cap=(0.0, 0.0),
        ),
        bone,
        "glow",
        sub=1,
    )
    for a in range(0, 360, 90):
        d = V((math.cos(math.radians(a + 45)), math.sin(math.radians(a + 45)), 0)) * 0.05 * s
        B.add(
            core.loft(
                f"lantern_bar{a}",
                [
                    (t + d - V((0, 0, 0.035)) * s, 0.006 * s, 0.006 * s),
                    (t + d - V((0, 0, 0.155)) * s, 0.006 * s, 0.006 * s),
                ],
                cap=(0.5, 0.5),
            ),
            bone,
            "brass",
            sub=0,
        )
    B.add(
        core.loft(
            "lantern_base",
            [(t - V((0, 0, 0.15)) * s, 0.058 * s, 0.058 * s), (t - V((0, 0, 0.175)) * s, 0.05 * s, 0.05 * s)],
            cap=(0.2, 0.3),
        ),
        bone,
        "brass",
        sub=1,
    )
    pl = core.light(f"{B.name}.lantern_light", "POINT", t - V((0, 0, 0.1)) * s, 60, color="#ffb35c", size=0.05)
    B.attach(pl, bone)
    B.lights.append(pl)


def shield_back(B, face="accent", rim="metal", boss="brass"):
    J, s = B.J, B.s
    c = J["back"] + V((-0.07, 0, -0.02)) * s
    R = 0.31 * s
    rings = [
        (c + V((0.03, 0, 0)) * s, R * 0.97, R * 0.97),
        (c + V((0.0, 0, 0)) * s, R, R),
        (c + V((-0.035, 0, 0)) * s, R * 0.9, R * 0.9),
    ]
    B.add(core.loft("shield", rings, seg=32, cap=(0.2, 0.3), x_hint=(0, 0, 1)), "chest", face)
    B.add(
        core.loft(
            "shield_rim",
            [(c + V((0.012, 0, 0)) * s, R * 1.02, R * 1.02), (c + V((-0.02, 0, 0)) * s, R * 1.02, R * 1.02)],
            seg=32,
            cap=(None, None),
            x_hint=(0, 0, 1),
        ),
        "chest",
        rim,
        thick=0.022 * s,
    )
    B.add(core.ellipsoid("shield_boss", c + V((-0.05, 0, 0)) * s, (0.05 * s, 0.085 * s, 0.085 * s)), "chest", boss)
    for a in range(0, 360, 60):
        p = c + V((-0.042, math.cos(math.radians(a)) * 0.2, math.sin(math.radians(a)) * 0.2)) * s
        B.add(core.ellipsoid(f"shield_stud{a}", p, (0.015 * s, 0.022 * s, 0.022 * s)), "chest", boss, sub=1)
    N, P = J["neck"].z, J["pelvis"].z
    pts = [
        V((-0.12 * s, 0.17 * s, N - 0.0 * s)),
        V((0.06 * s, 0.12 * s, N - 0.02 * s)),
        V((0.19 * s, 0.0, J["chest"].z)),
        V((0.17 * s, -0.12 * s, J["spine"].z)),
        V((0.05 * s, -0.19 * s, P + 0.05 * s)),
    ]
    B.add(
        core.loft("shield_strap", [(p, 0.008 * s, 0.032 * s, 3.0) for p in pts], x_hint=(1, 0, 0.3), cap=(0.2, 0.2)),
        ["chest", "spine"],
        "leather",
        sub=1,
    )


def satchel(B, region="leather", strap="leather_dark"):
    J, s, w = B.J, B.s, B.J["build"]
    P, N = J["pelvis"].z, J["neck"].z
    c = V((0.02 * s, -0.215 * s * w, P - 0.06 * s))
    B.add(
        core.loft(
            "satchel",
            [(c - V((0, 0, 0.08)) * s, 0.1 * s, 0.045 * s, 3.2), (c + V((0, 0, 0.08)) * s, 0.1 * s, 0.045 * s, 3.2)],
            cap=(0.5, 0.2),
        ),
        "hips",
        region,
    )
    B.add(
        core.loft(
            "satchel_flap",
            [
                (c + V((0, -0.006, 0.0)) * s, 0.104 * s, 0.048 * s, 3.2),
                (c + V((0, -0.006, 0.085)) * s, 0.104 * s, 0.048 * s, 3.2),
            ],
            cap=(0.3, 0.25),
        ),
        "hips",
        strap,
    )
    pts = [
        c + V((0, 0, 0.08)) * s,
        V((0.17 * s, -0.12 * s, J["spine"].z)),
        V((0.19 * s, 0.02 * s, J["chest"].z)),
        V((0.07 * s, 0.13 * s, N - 0.02 * s)),
        V((-0.12 * s, 0.15 * s, N - 0.02 * s)),
        V((-0.18 * s, 0.05 * s, J["chest"].z)),
    ]
    B.add(
        core.loft("satchel_strap", [(p, 0.007 * s, 0.026 * s, 3.0) for p in pts], x_hint=(1, 0, 0.3), cap=(0.2, 0.2)),
        ["chest", "spine", "hips"],
        strap,
        sub=1,
    )


def bedroll_back(B, region="cloth_c", strap="leather_dark"):
    J, s, w = B.J, B.s, B.J["build"]
    c = J["back"] + V((-0.03, 0, -0.12)) * s
    L = 0.24 * s * w
    B.add(
        core.loft(
            "roll", [(c + V((0, -L, 0)), 0.08 * s, 0.08 * s), (c + V((0, L, 0)), 0.08 * s, 0.08 * s)], cap=(0.3, 0.3)
        ),
        "chest",
        region,
    )
    for y in (-0.55, 0.55):
        B.add(
            core.loft(
                f"roll_tie{y}",
                [
                    (c + V((0, y * L - 0.012 * s, 0)), 0.086 * s, 0.086 * s),
                    (c + V((0, y * L + 0.012 * s, 0)), 0.086 * s, 0.086 * s),
                ],
                cap=(None, None),
            ),
            "chest",
            strap,
            thick=0.006 * s,
        )


# ---------------------------------------------------------------------------
# Held tools and weapons (authored in the grip socket frame)
# ---------------------------------------------------------------------------


def pickaxe(B, side="R", head_region="metal", handle="wood", wrap="leather"):
    g, u, w, lat = B.frame(side)
    s = B.s
    bone = f"socket.grip.{side}"
    L = 0.7 * s
    B.add(
        core.loft(
            "pick_handle",
            [(g - u * 0.1 * s, 0.024 * s, 0.024 * s), (g + u * L, 0.021 * s, 0.021 * s)],
            cap=(0.5, 0.3),
            x_hint=w,
        ),
        bone,
        handle,
    )
    B.add(
        core.loft(
            "pick_grip",
            [(g - u * 0.07 * s, 0.028 * s, 0.028 * s), (g + u * 0.07 * s, 0.028 * s, 0.028 * s)],
            cap=(0.4, 0.4),
            x_hint=w,
        ),
        bone,
        wrap,
    )
    end = g + u * (L - 0.035 * s)
    pts, rad = [], []
    n = 9
    for i in range(n):
        k = -1 + 2 * i / (n - 1)
        pts.append(end + w * (0.3 * s * k) - u * (0.07 * s * k * k))
        taper = 1 - abs(k) ** 1.6
        rad.append(max(0.006, 0.034 * taper + 0.004) * s)
    B.add(
        core.loft("pick_head", [(p, rr * 1.1, rr) for p, rr in zip(pts, rad)], cap=(0.2, 0.2), x_hint=u),
        bone,
        head_region,
    )
    B.add(
        core.loft(
            "pick_collar",
            [(end - u * 0.05 * s, 0.03 * s, 0.03 * s), (end + u * 0.04 * s, 0.03 * s, 0.03 * s)],
            cap=(0.5, 0.5),
            x_hint=w,
        ),
        bone,
        wrap,
    )


def hammer(B, side="R", head_region="metal", handle="wood", trim="brass"):
    g, u, w, lat = B.frame(side)
    s = B.s
    bone = f"socket.grip.{side}"
    L = 0.66 * s
    B.add(
        core.loft(
            "hammer_handle",
            [(g - u * 0.12 * s, 0.025 * s, 0.025 * s), (g + u * L, 0.023 * s, 0.023 * s)],
            cap=(0.5, 0.3),
            x_hint=w,
        ),
        bone,
        handle,
    )
    B.add(core.ellipsoid("hammer_pommel", g - u * 0.13 * s, (0.035 * s,) * 3), bone, trim)
    end = g + u * (L - 0.02 * s)
    B.add(
        core.loft(
            "hammer_head",
            [
                (end - w * 0.13 * s, 0.075 * s, 0.08 * s, 4.0),
                (end + w * 0.0 * s, 0.085 * s, 0.09 * s, 4.0),
                (end + w * 0.15 * s, 0.075 * s, 0.08 * s, 4.0),
            ],
            cap=(0.15, 0.15),
            x_hint=u,
        ),
        bone,
        head_region,
    )
    B.add(
        core.loft(
            "hammer_spike",
            [(end - w * 0.13 * s, 0.04 * s, 0.04 * s), (end - w * 0.3 * s, 0.006 * s, 0.006 * s)],
            cap=(0.2, 0.0),
            x_hint=u,
        ),
        bone,
        head_region,
    )
    for k in (-0.08, 0.08):
        B.add(
            core.loft(
                f"hammer_band{k}",
                [
                    (end + w * (k - 0.012) * s, 0.09 * s, 0.095 * s, 4.0),
                    (end + w * (k + 0.012) * s, 0.09 * s, 0.095 * s, 4.0),
                ],
                cap=(None, None),
                x_hint=u,
            ),
            bone,
            trim,
            sub=1,
            thick=0.004 * s,
        )


def short_sword(B, side="R", blade="metal", guard="brass", grip="leather_dark"):
    g, u, w, lat = B.frame(side)
    s = B.s
    bone = f"socket.grip.{side}"
    B.add(
        core.loft(
            "sword_grip",
            [(g - u * 0.075 * s, 0.02 * s, 0.02 * s), (g + u * 0.075 * s, 0.019 * s, 0.019 * s)],
            cap=(0.3, 0.3),
            x_hint=w,
        ),
        bone,
        grip,
    )
    B.add(core.ellipsoid("sword_pommel", g - u * 0.095 * s, (0.03 * s, 0.03 * s, 0.03 * s)), bone, guard)
    gc = g + u * 0.09 * s
    B.add(
        core.loft(
            "sword_guard",
            [
                (gc - w * 0.09 * s, 0.014 * s, 0.018 * s),
                (gc, 0.02 * s, 0.022 * s),
                (gc + w * 0.09 * s, 0.014 * s, 0.018 * s),
            ],
            cap=(0.8, 0.8),
            x_hint=u,
        ),
        bone,
        guard,
    )
    pts = [g + u * k * s for k in (0.1, 0.25, 0.45, 0.58, 0.66)]
    widths = [0.032, 0.036, 0.036, 0.028, 0.004]
    B.add(
        core.loft(
            "sword_blade",
            [(p, wd * s, 0.007 * s, 2.0, (0.0, 0.0)) for p, wd in zip(pts, widths)],
            cap=(0.3, 0.0),
            x_hint=w,
        ),
        bone,
        blade,
        sub=1,
    )


def lantern_hand(B, side="L"):
    J = B.J
    _lantern(B, J[f"grip.{side}"] + V((0, 0, -0.02)) * B.s, f"hand.{side}", hang=0.0)
