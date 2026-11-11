"""Render Wylden concept art from the parametric sources.

Usage (with the `bpy` module from PyPI, or Blender's own Python):

    python assets/blender/render.py lineup  --out assets/renders/concept
    python assets/blender/render.py poses   --out assets/renders/concept
    python assets/blender/render.py loadouts --out assets/renders/concept
    python assets/blender/render.py moss_and_ember --out assets/renders/concept
    python assets/blender/render.py all --out assets/renders/concept --quality final
    python assets/blender/render.py opal_deep --plan-only

Every image is rebuilt from scripts and seeds. Biome layouts come from
worldgen (landmark growth, WFC contours, validation); each biome render also
writes <biome>_worldgen.json and <biome>_worldgen.png describing the solved
world. --plan-only writes those two files without building the 3D scene.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402

from wylden import biomes, core, explorers, poses, rig, worldgen  # noqa: E402

QUALITY = {
    "draft": dict(scale=0.5, samples=24),
    "final": dict(scale=1.0, samples=48),
}


def studio(target=(0, 0, 1.0), back=5.0, color="#2B3142"):
    core.gradient_world("#5A6A8A", "#1A1E28", 0.45)
    prof = [(-40, 0.0), (-10, 0.0), (0, 0.0), (back - 3.0, 0.0)]
    for i in range(1, 9):
        a = math.radians(90 * i / 8)
        prof.append((back - 3.0 + 3.0 * math.sin(a), 3.0 - 3.0 * math.cos(a)))
    prof.append((back, 14.0))
    verts, faces = [], []
    for x in (-30, 30):
        verts += [(x, y, z) for y, z in prof]
    n = len(prof)
    faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    cyc = core.mesh_object("cyclorama", verts, faces)
    core.set_material(cyc, core.principled("cyclorama", color, rough=0.9))
    for name, loc, e, col, sz in [
        ("key", (3.5, -5.0, 4.5), 1100, "#FFE7CF", 3),
        ("rim", (-3.5, 1.2, 3.0), 700, "#9CC8FF", 2.5),
        ("fill", (-4.0, -6.0, 1.5), 260, "#CFE0FF", 5),
        ("top", (0, 0, 7), 220, "#FFFFFF", 4),
    ]:
        lt = core.light(name, "AREA", loc, e, color=col, size=sz)
        core.look_at(lt, target)


def place(B, pose):
    rig.apply_pose(B.arm, poses.POSES[pose])


def render_lineup(out, q):
    core.reset_scene()
    for i, (kind, pose) in enumerate([("prospector", "idle"), ("pathfinder", "idle_lantern"), ("warden", "guard")]):
        B = explorers.explorer(kind, location=((i - 1) * 1.45, 0, 0), yaw=-28)
        place(B, pose)
    studio()
    core.ortho_camera("cam", (0, 0, 1.02), 5.2, pitch_deg=5)
    core.setup_render(int(1920 * q["scale"]), int(1080 * q["scale"]), samples=q["samples"])
    p = core.render(out / "explorers_lineup.png")
    core.post_process(p, bloom=0.25, vignette=0.25)


def render_poses(out, q):
    core.reset_scene()
    spec = [
        ("prospector", "mine_windup"),
        ("prospector", "mine_strike"),
        ("pathfinder", "run"),
        ("pathfinder", "slash"),
        ("warden", "hammer_raise"),
        ("warden", "guard"),
    ]
    for i, (kind, pose) in enumerate(spec):
        B = explorers.explorer(kind, name=f"{kind}.{pose}", location=((i - 2.5) * 1.55, 0, 0), yaw=-22)
        place(B, pose)
    studio()
    core.ortho_camera("cam", (-0.15, 0, 1.0), 10.4, pitch_deg=5)
    core.setup_render(int(2400 * q["scale"]), int(900 * q["scale"]), samples=q["samples"])
    p = core.render(out / "explorers_poses.png")
    core.post_process(p, bloom=0.25, vignette=0.2)


def render_loadouts(out, q):
    """One body, four equipment and palette combinations assembled on the same rig."""
    core.reset_scene()
    body = explorers.BODIES["prospector"]
    base = explorers.PALETTES["prospector"]
    lo_p = explorers.LOADOUTS["prospector"]
    lo_f = explorers.LOADOUTS["pathfinder"]
    lo_w = explorers.LOADOUTS["warden"]
    combos = [
        ("miner", lo_p, base, "idle"),
        (
            "scout",
            [e for e in lo_f if e[0] != "head"] + [("head", "head", dict(hair="crop"))],
            dict(base, cloth_a="#3C6E9A", cloth_b="#D9CBB0", accent="#E0A43A"),
            "idle_lantern",
        ),
        (
            "guard",
            [e for e in lo_w if e[0] not in ("head",)] + [("head", "head", dict(hair=None, beard=False))],
            dict(base, cloth_a="#2F6B4A", cloth_b="#2F6B4A", paint="#C9A23A", accent="#2F6B4A"),
            "guard",
        ),
        (
            "delver",
            [e for e in lo_p if e[0] not in ("headwear", "back", "main_hand", "over")]
            + [
                ("shoulders", "mantle", dict(region="cloth_a")),
                ("back", "shield_back", dict(face="paint")),
                ("main_hand", "hammer", {}),
                ("neck", "scarf", dict(region="accent")),
            ],
            dict(base, cloth_a="#6A3E7A", accent="#E2C25A", paint="#6A3E7A", hair="#2A2222"),
            "idle",
        ),
    ]
    for i, (name, lo, pal, pose) in enumerate(combos):
        B = explorers.assemble(name, body, pal, lo, location=((i - 1.5) * 1.45, 0, 0), yaw=-28)
        place(B, pose)
    studio()
    core.ortho_camera("cam", (0, 0, 1.0), 6.6, pitch_deg=5)
    core.setup_render(int(1920 * q["scale"]), int(1080 * q["scale"]), samples=q["samples"])
    p = core.render(out / "explorers_loadouts.png")
    core.post_process(p, bloom=0.25, vignette=0.25)


RULES = {
    "moss_and_ember": dict(rules=biomes.moss_rules, seed=7, start="surface"),
    "opal_deep": dict(rules=biomes.opal_rules, seed=11, start="exit", water=biomes.opal_water),
    "roots_of_giants": dict(rules=biomes.roots_rules, seed=23, start="surface"),
}


def write_worldgen(name, sol, out):
    """Report and diagnostic for a solved world: plan, WFC solution and validation results."""
    plan, r = sol.plan, sol.report
    report = dict(
        biome=name,
        plan_seed=plan.seed,
        tile_m=r["tile_m"],
        cell_m=r["cell_m"],
        grid_tiles=r["grid"],
        tile_patterns=r["tiles"],
        attempts=[{k: v for k, v in e.items() if k != "landmarks"} for e in r["log"]],
        landmarks=[
            dict(
                name=lm.name,
                role=lm.role,
                x=round(lm.x, 2),
                floor=round(lm.floor, 2),
                rx=round(lm.rx, 2),
                rz=round(lm.rz, 2),
                reachable=r["landmarks"][lm.name]["reachable"],
                air_connected=r["landmarks"][lm.name]["air_connected"],
                routed=lm.connect,
            )
            for lm in plan.landmarks
        ],
        routes=[
            dict(
                a=rt.a,
                b=rt.b,
                kind=rt.kind,
                walk=rt.walk,
                radius=round(rt.radius, 2),
                length_m=round(float(sum(((rt.pts[1:] - rt.pts[:-1]) ** 2).sum(1) ** 0.5)), 1),
            )
            for rt in plan.routes
        ],
        checks=dict(
            tiles_compatible=r["compatible"],
            sealed_intact=r["sealed_intact"],
            valid=r["valid"],
            islands_removed=r["islands_removed"],
            standable_cells=r["standable_cells"],
            reached_cells=r["reached_cells"],
        ),
    )
    (out / f"{name}_worldgen.json").write_text(json.dumps(report, indent=2, default=float) + "\n")
    worldgen.diagnostic(sol, out / f"{name}_worldgen.png", title=f"{name} · plan seed {plan.seed}")


def plan_only(name, out):
    spec = RULES[name]
    sol = worldgen.solve(spec["rules"], spec["seed"], water_fn=spec.get("water"), start_role=spec["start"], plans=40)
    write_worldgen(name, sol, out)


def render_biome(name, out, q):
    core.reset_scene()
    coll = core.collection(name)
    t = time.time()
    sc = getattr(biomes, name)(coll)
    print(f"[{name}] environment built in {time.time() - t:.1f}s")
    write_worldgen(name, sc.solution, out)
    for kind, pose, x, y, z_from, yaw in sc.cast:
        z = sc.field.floor_at(x, y, z_from)
        B = explorers.explorer(kind, name=f"{name}.{kind}", location=(x, y, z - 0.02), yaw=yaw)
        place(B, pose)
    cam = core.ortho_camera("cam", sc.camera_target, sc.width, pitch_deg=biomes.PITCH, distance=60)
    core.setup_render(
        int(1920 * q["scale"]), int(1080 * q["scale"]), samples=q["samples"], exposure=sc.post.get("exposure", 0.0)
    )
    p = core.render(out / f"{name}.png")
    core.post_process(p, bloom=sc.post.get("bloom", 0.45), vignette=sc.post.get("vignette", 0.3))
    # Close-ups reuse the built scene: only the camera moves.
    for suffix, target, width in sc.details:
        pitch = math.radians(biomes.PITCH)
        cam.data.ortho_scale = width
        cam.location = biomes.V(target) + biomes.V((0.0, -math.cos(pitch), math.sin(pitch))) * 60
        core.setup_render(
            int(1280 * q["scale"]), int(720 * q["scale"]), samples=q["samples"], exposure=sc.post.get("exposure", 0.0)
        )
        p = core.render(out / f"{name}_{suffix}.png")
        core.post_process(p, bloom=sc.post.get("bloom", 0.45) * 0.8, vignette=sc.post.get("vignette", 0.3))


TARGETS = {
    "lineup": render_lineup,
    "poses": render_poses,
    "loadouts": render_loadouts,
}
BIOMES = ("moss_and_ember", "opal_deep", "roots_of_giants")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=list(TARGETS) + list(BIOMES) + ["all"])
    ap.add_argument("--out", default="assets/renders/concept")
    ap.add_argument("--quality", choices=list(QUALITY), default="draft")
    ap.add_argument("--plan-only", action="store_true", help="write worldgen reports for biomes without rendering")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    q = QUALITY[a.quality]
    names = list(TARGETS) + list(BIOMES) if a.target == "all" else [a.target]
    for n in names:
        t = time.time()
        if a.plan_only:
            if n in RULES:
                plan_only(n, out)
            continue
        if n in TARGETS:
            TARGETS[n](out, q)
        else:
            render_biome(n, out, q)
        print(f"[{n}] done in {time.time() - t:.1f}s")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    main(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
