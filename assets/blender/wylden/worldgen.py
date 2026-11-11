"""Hierarchical side-view world generation.

Follows the hierarchy in docs/world-generation.md:

1. World plan: a seeded surface line (where the biome has one) and bounds.
2. Landmarks and routes: biome rules grow landmarks from a start, each placed
   relative to a parent within a walkable slope, so the main structure is
   connected by construction. Optional loops join further pairs. Routes never
   cut through a third landmark, and every chamber keeps a solid slab under
   its floor. Sealed discoveries are placed apart from all routes.
3. Feature constraints: an edge-compatible WFC solves solid/air contours on a
   0.75 m tile grid around that scaffold. Tiles are the 3x3 sub-cell patterns
   that hold one clean contour (92 of 512); neighbouring tiles must share
   identical edge profiles. Planned air and deep rock are fixed; a free band
   around every boundary is solved, with weights that follow the scaffold.
4. Terrain: the solved sub-cells become a signed distance field for
   terrain.Field, resampled at mining-cell resolution.
5. Dressing happens in biomes.py, placed from landmarks and floors.
6. Validation and repair: seeded checks confirm tile compatibility, walkable
   reach of every routed landmark (clearance, steps, jumps, drops, swimming),
   and that sealed discoveries stay sealed. Specks under six sub-cells are
   cleaned up; failing solutions are re-solved, failing plans re-planned.

Coordinates: x right, z up, metres. Grids are indexed [z, x] with z ascending.
"""

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, label

TILE = 0.75
SUB = 3
CELL = TILE / SUB

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@dataclass
class Landmark:
    name: str
    role: str
    x: float
    floor: float
    rx: float
    rz: float
    connect: bool = True
    basin: float = 0.0  # depth of a central dip in the floor (lakes)

    @property
    def z(self):
        return self.floor + self.rz * 0.7


@dataclass
class Route:
    a: str
    b: str
    pts: np.ndarray  # (N, 2) centreline at walking height
    radius: float
    kind: str = "main"  # main | loop | light
    walk: bool = True


@dataclass
class Plan:
    bounds: tuple  # x0, x1, z0, z1
    surface: object = None  # callable x -> z, or None underground
    landmarks: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    seed: int = 0
    notes: list = field(default_factory=list)

    def landmark(self, name):
        return next(lm for lm in self.landmarks if lm.name == name)

    def by_role(self, role):
        return [lm for lm in self.landmarks if lm.role == role]


def surface_line(rng, x0, x1, base, amp, scale, bumps=()):
    """Seeded smooth surface as a callable."""
    xs = np.linspace(x0 - 2, x1 + 2, 400)
    z = np.full_like(xs, base)
    for f, a in ((scale, 1.0), (scale / 2.4, 0.4), (scale / 6.0, 0.12)):
        ph = rng.random() * 2 * math.pi
        z += amp * a * np.sin(xs / f + ph)
    for bx, bw, bh in bumps:
        z += bh * np.exp(-(((xs - bx) / bw) ** 2))
    return lambda x: np.interp(x, xs, z)


class PlanError(RuntimeError):
    pass


def _edge_cost(a, b, max_slope):
    dx = abs(a.x - b.x) - (a.rx + b.rx) * 0.6
    dz = abs(a.floor - b.floor)
    run = max(dx, 0.3)
    slope = dz / run
    if slope > max_slope:
        return None
    return math.hypot(abs(a.x - b.x), dz) * (1.0 + 1.5 * slope)


def _crosses(route, others, margin=0.25):
    """True when a route passes through another landmark's chamber or the solid slab under its floor."""
    px, pz = route.pts[:, 0], route.pts[:, 1]
    for lm in others:
        if lm.role == "surface":
            continue
        inside_x = np.abs(px - lm.x) < lm.rx + route.radius * 0.6
        band = (pz - route.radius < lm.floor + lm.rz * 1.7 + margin) & (pz + route.radius > lm.floor - 1.0)
        if np.any(inside_x & band):
            return True
    return False


def grow(rng, surface, bounds, start, steps, max_slope=0.9, gap=0.7, tries=300, radius=(0.95, 1.08)):
    """Grow the main structure from a start landmark.

    Each step places a landmark relative to a parent already in the graph:
    on a given side, a wall-to-wall gap away, with a floor change that keeps the
    joining route within max_slope. The route is added with it, so the main
    structure is connected by construction. Steps with connect=False place
    sealed discoveries (no route).
    """
    x0, x1, z0, z1 = bounds
    placed = [start]
    routes = []
    for sp in steps:
        parent = next(lm for lm in placed if lm.name == sp["from"])
        for _ in range(tries):
            side = sp.get("side") or (1 if rng.random() < 0.5 else -1)
            rx, rz = rng.uniform(*sp["rx"]), rng.uniform(*sp["rz"])
            g = rng.uniform(*sp["gap"])
            prx = 0.0 if parent.role == "surface" else parent.rx
            x = parent.x + side * (prx + g + rx)
            if "x" in sp:
                x = float(np.clip(x, *sp["x"]))
            if "depth" in sp:
                floor = float(surface(x)) - rng.uniform(*sp["depth"])
            else:
                floor = parent.floor + rng.uniform(*sp["dz"])
            lm = Landmark(sp["name"], sp["role"], x, floor, rx, rz, sp.get("connect", True), 0.0)
            if "basin" in sp:
                lm.basin = rng.uniform(*sp["basin"])
            margin = -rx * 0.5 if sp["role"] == "exit" else 0.3
            if not (x0 + rx * 0.5 + margin <= x <= x1 - rx * 0.5 - margin) and sp["role"] != "exit":
                continue
            if lm.floor - lm.basin - 1.2 < z0 or lm.floor + lm.rz * 1.7 > z1:
                continue
            if surface is not None and lm.floor + 1.7 * lm.rz > float(surface(x)) - sp.get("crust", 2.2):
                continue
            clearance = sp.get("clearance", gap if lm.connect else 1.9)
            if any(
                abs(lm.x - o.x) < lm.rx + o.rx + clearance and abs(lm.z - o.z) < lm.rz + o.rz + clearance
                for o in placed
                if o.role != "surface"
            ):
                continue
            if not lm.connect and any(
                np.min(route_sdf(r, np.array([lm.x]), np.array([lm.z]))) < lm.rx + 1.6 for r in routes
            ):
                continue
            rt = None
            if lm.connect:
                if _edge_cost(parent, lm, max_slope) is None:
                    continue
                lo, hi = (parent, lm) if parent.x <= lm.x else (lm, parent)
                rt = route_between(rng, lo, hi, rng.uniform(*radius))
                if _crosses(rt, [o for o in placed if o is not parent]) or any(_crosses(r, [lm]) for r in routes):
                    continue
            placed.append(lm)
            if rt is not None:
                routes.append(rt)
            break
        else:
            raise PlanError(f"could not grow {sp['name']} from {parent.name}")
    return placed, routes


def add_loops(rng, landmarks, routes, n=1, max_slope=0.9, radius=(0.95, 1.08)):
    """Optional loops: the cheapest extra walkable edges that cut through nothing."""
    joined = {frozenset((r.a, r.b)) for r in routes}
    nodes = [lm for lm in landmarks if lm.connect and lm.role != "surface"]
    cands = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            c = _edge_cost(a, b, max_slope)
            if c is not None and frozenset((a.name, b.name)) not in joined:
                cands.append((c, a, b))
    cands.sort(key=lambda t: t[0])
    out = []
    for _, a, b in cands:
        if len(out) >= n:
            break
        lo, hi = (a, b) if a.x <= b.x else (b, a)
        rt = route_between(rng, lo, hi, rng.uniform(*radius), "loop")
        if not _crosses(rt, [o for o in landmarks if o is not a and o is not b]):
            out.append(rt)
    return out


def route_between(rng, a, b, r, kind="main", lift=0.95, wander=0.3):
    """Walking-height centreline from a's wall to b's wall (a left of b), smoothed with a spline."""
    ax = a.x if a.role == "surface" else a.x + a.rx * 0.78
    bx = b.x if b.role == "surface" else b.x - b.rx * 0.78
    if bx - ax < 0.8:
        ax, bx = min(a.x, b.x) + 0.1, max(a.x, b.x) - 0.1
    p0 = np.array([ax, a.floor + lift])
    p1 = np.array([bx, b.floor + lift])
    n = max(2, int(abs(bx - ax) / 2.0))
    ctrl = [p0]
    for k in range(1, n):
        t = k / n
        p = p0 + (p1 - p0) * t
        p[1] += rng.normal(0, wander)
        ctrl.append(p)
    ctrl.append(p1)
    pts = _catmull(np.array(ctrl), step=0.3)
    return Route(a.name, b.name, pts, r, kind)


def _catmull(p, step=0.3):
    if len(p) < 3:
        n = max(2, int(np.linalg.norm(p[-1] - p[0]) / step))
        return np.linspace(p[0], p[-1], n)
    ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        n = max(2, int(np.linalg.norm(p2 - p1) / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(
                0.5
                * (
                    2 * p1
                    + (-p0 + p2) * t
                    + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t**3
                )
            )
    out.append(p[-1])
    return np.array(out)


def route_path(name_a, name_b, pts, r, kind="main", walk=True):
    return Route(name_a, name_b, np.asarray(pts, dtype=float), r, kind, walk)


# ---------------------------------------------------------------------------
# Scaffold rasterisation
# ---------------------------------------------------------------------------


def _seg_dist(px, pz, a, b):
    ab = b - a
    L2 = max(float(ab @ ab), 1e-9)
    t = np.clip(((px - a[0]) * ab[0] + (pz - a[1]) * ab[1]) / L2, 0, 1)
    return np.hypot(px - (a[0] + ab[0] * t), pz - (a[1] + ab[1] * t))


def landmark_sdf(lm, X, Z):
    if lm.role == "surface":
        return np.full(X.shape, 1e3)
    cz = lm.floor + lm.rz * 0.7
    ell = (np.sqrt(((X - lm.x) / lm.rx) ** 2 + ((Z - cz) / lm.rz) ** 2) - 1.0) * min(lm.rx, lm.rz)
    floor = lm.floor - lm.basin * np.exp(-(((X - lm.x) / (lm.rx * 0.45)) ** 4))
    return np.maximum(ell, floor - Z)


def route_sdf(rt, X, Z):
    d = np.full(X.shape, 1e3)
    for a, b in zip(rt.pts[:-1], rt.pts[1:]):
        d = np.minimum(d, _seg_dist(X, Z, a, b) - rt.radius)
    return d


def cave_sdf(plan, X, Z):
    """Signed distance to underground air (landmarks and routes), negative inside."""
    d = np.full(X.shape, 1e3)
    for lm in plan.landmarks:
        d = np.minimum(d, landmark_sdf(lm, X, Z))
    for rt in plan.routes:
        d = np.minimum(d, route_sdf(rt, X, Z))
    # Every chamber keeps solid footing: a slab under its floor (below any basin) no route may remove.
    for lm in plan.landmarks:
        if lm.role == "surface":
            continue
        top = lm.floor - lm.basin - 0.1
        slab = np.maximum(np.abs(X - lm.x) - lm.rx * 0.85, np.maximum(Z - top, (top - 0.9) - Z))
        d = np.maximum(d, -slab)
    return d


def sky_sdf(plan, X, Z):
    if plan.surface is None:
        return np.full(X.shape, 1e3)
    return plan.surface(X) - Z


def air_sdf(plan, X, Z):
    return np.minimum(sky_sdf(plan, X, Z), cave_sdf(plan, X, Z))


# ---------------------------------------------------------------------------
# Edge-compatible tiles
# ---------------------------------------------------------------------------


def _one_region(mask):
    if not mask.any():
        return True
    return label(mask)[1] == 1


def _saddle(p):
    for r in range(2):
        for c in range(2):
            a, b, cc, d = p[r, c], p[r, c + 1], p[r + 1, c], p[r + 1, c + 1]
            if a == d and b == cc and a != b:
                return True
    return False


class TileSet:
    """All 3x3 solid/air patterns that hold a single clean contour.

    A pattern qualifies when its solid and air cells are each one 4-connected
    region, it has no diagonal pinch, and each edge crosses the contour at most
    once. Tiles may sit side by side only when the touching edge profiles are
    identical, which keeps contours continuous across tiles.
    """

    def __init__(self):
        pats = []
        for bits in range(512):
            p = np.array([(bits >> k) & 1 for k in range(9)], dtype=bool).reshape(3, 3)
            if not (_one_region(p) and _one_region(~p)) or _saddle(p):
                continue
            if any(int(np.sum(e[1:] != e[:-1])) > 1 for e in (p[0], p[2], p[:, 0], p[:, 2])):
                continue
            pats.append(p)
        self.p = np.array(pats)  # (K, row-from-bottom, col-from-left); True = solid
        K = len(pats)
        self.K = K
        self.air_frac = 1.0 - self.p.reshape(K, -1).mean(1)
        bl = (self.p[:, :, 1:] != self.p[:, :, :-1]).sum((1, 2)) + (self.p[:, 1:, :] != self.p[:, :-1, :]).sum((1, 2))
        self.boundary = bl
        self.base = np.where(bl == 0, 1.0, 1.0 / (1.0 + 0.45 * bl))
        smallest = np.minimum(self.p.reshape(K, -1).sum(1), 9 - self.p.reshape(K, -1).sum(1))
        self.base = np.where((smallest > 0) & (smallest <= 1), self.base * 0.12, self.base)
        rows_flat = np.all(self.p == self.p[:, :, :1], axis=2).all(axis=1)
        self.floor = rows_flat & (bl > 0) & self.p[:, 0, 0] & ~self.p[:, 2, 0]
        self.ceiling = rows_flat & (bl > 0) & ~self.p[:, 0, 0] & self.p[:, 2, 0]
        right, left = self.p[:, :, 2], self.p[:, :, 0]
        top, bottom = self.p[:, 2, :], self.p[:, 0, :]
        self.R = np.all(right[:, None, :] == left[None, :, :], axis=2)  # R[a, b]: b may sit right of a
        self.U = np.all(top[:, None, :] == bottom[None, :, :], axis=2)  # U[a, b]: b may sit above a
        self.SOLID = int(np.nonzero(self.air_frac == 0)[0][0])
        self.AIR = int(np.nonzero(self.air_frac == 1)[0][0])


TILES = None


def tileset():
    global TILES
    if TILES is None:
        TILES = TileSet()
    return TILES


class Contradiction(RuntimeError):
    pass


def _propagate(wave, stack, R, U):
    H, W, _ = wave.shape
    while stack:
        j, i = stack.pop()
        cur = wave[j, i]
        for dj, di, M in ((0, 1, R), (0, -1, R.T), (1, 0, U), (-1, 0, U.T)):
            nj, ni = j + dj, i + di
            if not (0 <= nj < H and 0 <= ni < W):
                continue
            allowed = M[cur].any(axis=0)
            nw = wave[nj, ni] & allowed
            if not nw.any():
                raise Contradiction((nj, ni))
            if (nw != wave[nj, ni]).any():
                wave[nj, ni] = nw
                stack.append((nj, ni))


def wfc(ts, weights, rng, restarts=40):
    """Weighted, entropy-ordered WFC. weights: (H, W, K), zero forbids a tile."""
    H, W, K = weights.shape
    contradictions = 0
    for _ in range(restarts):
        wave = weights > 0
        try:
            _propagate(wave, [(j, i) for j in range(H) for i in range(W)], ts.R, ts.U)
        except Contradiction as exc:
            raise PlanError(f"scaffold constraints contradict at {exc}") from exc
        try:
            while True:
                counts = wave.sum(2)
                open_ = counts > 1
                if not open_.any():
                    return np.argmax(wave, axis=2), contradictions
                w = np.where(wave, weights, 0.0)
                sw = w.sum(2)
                with np.errstate(divide="ignore", invalid="ignore"):
                    ent = np.log(sw) - (w * np.log(np.where(w > 0, w, 1.0))).sum(2) / sw
                ent = np.where(open_, ent + rng.random((H, W)) * 1e-4, np.inf)
                j, i = np.unravel_index(int(np.argmin(ent)), ent.shape)
                pr = w[j, i] / w[j, i].sum()
                k = rng.choice(K, p=pr)
                wave[j, i] = False
                wave[j, i, k] = True
                _propagate(wave, [(j, i)], ts.R, ts.U)
        except Contradiction:
            contradictions += 1
    raise PlanError(f"WFC failed after {restarts} restarts")


# ---------------------------------------------------------------------------
# Solve, validate, repair
# ---------------------------------------------------------------------------


@dataclass
class Solution:
    plan: Plan
    tiles: np.ndarray  # (H, W) tile ids
    solid: np.ndarray  # (H*3, W*3) sub-cells, True = solid
    xs: np.ndarray  # sub-cell centres
    zs: np.ndarray
    constraint: np.ndarray  # (H, W) -1 must-air, 0 free, 1 must-solid
    report: dict
    water: np.ndarray = None  # (H*3, W*3) water cells
    reach: np.ndarray = None  # (H*3, W*3) reached standable cells
    stand: np.ndarray = None

    def signed(self, sigma=1.0):
        """Signed distance in metres on the sub-cell grid (positive inside rock), lightly smoothed."""
        inside = distance_transform_edt(self.solid)
        outside = distance_transform_edt(~self.solid)
        d = (inside - outside) * CELL + np.where(self.solid, -0.5, 0.5) * CELL
        return gaussian_filter(d, sigma, mode="nearest")


def tile_weights(ts, plan, X, Z, must_air=-0.45, must_solid=0.95, sky_band=0.5, softness=0.3, sharp=0.16):
    """Per-cell tile weights from the scaffold.

    Cells well inside planned air are fixed to the air tile, cells well inside rock to the solid
    tile. In between, weights favour tiles whose air fraction matches the scaffold, flat floors
    where the scaffold has a floor, and ceilings where it has a ceiling. The ground surface gets
    a narrower free band than caves so crusts stay whole.
    """
    d_cave, d_sky = cave_sdf(plan, X, Z), sky_sdf(plan, X, Z)
    d = np.minimum(d_cave, d_sky)
    t = 1.0 / (1.0 + np.exp(d / softness))
    w = ts.base[None, None, :] * np.exp(-((ts.air_frac[None, None, :] - t[..., None]) ** 2) / (2 * sharp**2))
    w = w + 1e-4
    gz = np.gradient(d, axis=0)
    near = np.abs(d) < 0.9
    w[near & (gz < -0.25)] *= np.where(ts.floor, 8.0, 1.0)
    w[near & (gz > 0.25)] *= np.where(ts.ceiling, 2.0, 1.0)
    constraint = np.zeros(d.shape, dtype=int)
    constraint[d < must_air] = -1
    constraint[(d_cave > must_solid) & (d_sky > sky_band)] = 1
    w[constraint == -1] = 0
    w[constraint == -1, ts.AIR] = 1
    w[constraint == 1] = 0
    w[constraint == 1, ts.SOLID] = 1
    return w, constraint, d


def assemble(ts, tiles):
    H, W = tiles.shape
    out = np.zeros((H * SUB, W * SUB), dtype=bool)
    for j in range(H):
        for i in range(W):
            out[j * SUB : (j + 1) * SUB, i * SUB : (i + 1) * SUB] = ts.p[tiles[j, i]]
    return out


def remove_islands(solid, min_cells=6):
    """Repair: fill air bubbles and clear rock specks smaller than min_cells sub-cells."""
    out = solid.copy()
    removed = 0
    for target in (True, False):
        mask = out == target
        lab, n = label(mask)
        if n == 0:
            continue
        sizes = np.bincount(lab.ravel())
        for k in range(1, n + 1):
            if sizes[k] < min_cells:
                comp = lab == k
                touches_edge = comp[0].any() or comp[-1].any() or comp[:, 0].any() or comp[:, -1].any()
                if not touches_edge:
                    out[comp] = not target
                    removed += 1
    return out, removed


def check_compatibility(ts, tiles):
    ok_h = ts.R[tiles[:, :-1], tiles[:, 1:]].all()
    ok_v = ts.U[tiles[:-1, :], tiles[1:, :]].all()
    return bool(ok_h and ok_v)


def standable(solid, height=1.8, water=None):
    air = ~solid
    Hs, Ws = solid.shape
    clear = np.zeros(solid.shape, dtype=int)
    for z in range(Hs - 1, -1, -1):
        above = clear[z + 1] if z + 1 < Hs else 0
        clear[z] = np.where(air[z], above + 1, 0)
    need = int(math.ceil(height / CELL))
    below_solid = np.zeros_like(solid)
    below_solid[1:] = solid[:-1]
    st = air & below_solid & (clear >= need)
    if water is not None:
        # Swimming: the cell just above a water column's surface counts as standable.
        top = water & ~np.vstack([water[1:], np.zeros((1, Ws), bool)])
        surf = np.zeros_like(solid)
        surf[1:] = top[:-1]
        st |= surf & air & ~water & (clear >= need)
    return st, clear, need


def reachable(solid, start, water=None, height=1.8, step=2, jump_up=5, jump_far=6, drop=24):
    """Explorer movement: walk/step ±2 cells (0.5 m), jump up 1.25 m or across 1.5 m, drop up to 6 m."""
    st, clear, need = standable(solid, height, water)
    Hs, Ws = solid.shape
    seen = np.zeros_like(st)
    sz, sx = start
    if not st[sz, sx]:
        return seen, st
    seen[sz, sx] = True
    queue = [(sz, sx)]
    while queue:
        z, x = queue.pop()
        cands = []
        for dx in (-1, 1):
            nx = x + dx
            if not 0 <= nx < Ws:
                continue
            for dz in range(-step, step + 1):
                nz = z + dz
                if 0 <= nz < Hs and st[nz, nx]:
                    cands.append((nz, nx))
            # Drop off a ledge.
            if clear[z, nx] >= need:
                for nz in range(z - 1, max(z - drop, 0) - 1, -1):
                    if solid[nz, nx]:
                        break
                    if st[nz, nx]:
                        cands.append((nz, nx))
                        break
        for dx in range(-jump_far, jump_far + 1):
            if abs(dx) < 2:
                continue
            nx = x + dx
            if not 0 <= nx < Ws:
                continue
            for dz in range(-step, jump_up + 1):
                nz = z + dz
                if not (0 <= nz < Hs and st[nz, nx]):
                    continue
                top = max(z, nz)
                lo, hi = sorted((x, nx))
                if top + need <= Hs and not solid[top : top + need, lo : hi + 1].any():
                    cands.append((nz, nx))
        for c in cands:
            if not seen[c]:
                seen[c] = True
                queue.append(c)
    return seen, st


def _cell(sol, x, z):
    i = int(np.clip(np.searchsorted(sol.xs, x), 0, len(sol.xs) - 1))
    j = int(np.clip(np.searchsorted(sol.zs, z), 0, len(sol.zs) - 1))
    return j, i


def landmark_cells(sol, lm, st):
    """Standable cells that count as standing at a landmark."""
    xs, zs = sol.xs, sol.zs
    in_x = np.abs(xs - lm.x) <= max(lm.rx * 0.8, 0.8)
    in_z = (zs >= lm.floor - 0.8 - lm.basin) & (zs <= lm.floor + max(lm.rz, 0.6) + 0.6)
    return st & in_z[:, None] & in_x[None, :]


def solve(plan_fn, seed, water_fn=None, attempts=6, plans=8, start_role=None, return_best=False):
    """Plan, solve with WFC, validate; re-solve on failure and re-plan if needed."""
    ts = tileset()
    log = []
    best, best_score = None, -1
    for p in range(plans):
        plan_seed = seed + 1009 * p
        rng = np.random.default_rng(plan_seed)
        try:
            plan = plan_fn(rng)
        except PlanError as exc:
            log.append(dict(plan_seed=plan_seed, result=f"plan rejected: {exc}"))
            continue
        plan.seed = plan_seed
        x0, x1, z0, z1 = plan.bounds
        W, H = int(round((x1 - x0) / TILE)), int(round((z1 - z0) / TILE))
        txs = x0 + (np.arange(W) + 0.5) * TILE
        tzs = z0 + (np.arange(H) + 0.5) * TILE
        TX, TZ = np.meshgrid(txs, tzs)
        try:
            weights, constraint, _ = tile_weights(ts, plan, TX, TZ)
        except PlanError as exc:
            log.append(dict(plan_seed=plan_seed, result=f"plan rejected: {exc}"))
            continue
        sxs = x0 + (np.arange(W * SUB) + 0.5) * CELL
        szs = z0 + (np.arange(H * SUB) + 0.5) * CELL
        for a in range(attempts):
            wfc_rng = np.random.default_rng(plan_seed * 31 + a)
            try:
                tiles, contradictions = wfc(ts, weights, wfc_rng)
            except PlanError as exc:
                log.append(dict(plan_seed=plan_seed, attempt=a, result=str(exc)))
                break
            solid = assemble(ts, tiles)
            solid, removed = remove_islands(solid)
            sol = Solution(plan, tiles, solid, sxs, szs, constraint, {})
            sol.water = water_fn(sol) if water_fn else None
            result = validate(sol, ts, start_role)
            result.update(plan_seed=plan_seed, attempt=a, restarts=contradictions, islands_removed=removed)
            log.append(result)
            score = sum(v["reachable"] for v in result.get("landmarks", {}).values())
            if score > best_score:
                best, best_score = sol, score
                sol.report = dict(result, log=log, tiles=ts.K, grid=[H, W], tile_m=TILE, cell_m=CELL)
            if result["valid"]:
                sol.report = dict(result, log=log, tiles=ts.K, grid=[H, W], tile_m=TILE, cell_m=CELL)
                return sol
    if return_best and best is not None:
        return best
    raise PlanError(f"no valid world after {plans} plans: {log[-3:]}")


def validate(sol, ts, start_role=None):
    """Seeded checks: tile compatibility, walkable reach of every routed landmark from the start,
    and sealed discoveries that stay sealed (not air-connected to the routed caves)."""
    plan = sol.plan
    compat = check_compatibility(ts, sol.tiles)
    connected = [lm for lm in plan.landmarks if lm.connect]
    start = next((lm for lm in connected if lm.role == start_role), connected[0])
    _, st = reachable(sol.solid, (0, 0), water=sol.water)
    if plan.surface is not None and start.role == "surface":
        # Open ground: any footing with clear sky above is a way in.
        air = ~sol.solid
        sky = np.flip(np.cumprod(np.flip(air, 0), 0), 0).astype(bool)
        starts = np.argwhere(st & sky)
    else:
        starts = np.argwhere(landmark_cells(sol, start, st))
    if not len(starts):
        return dict(valid=False, compatible=compat, reason=f"no standable cell at {start.name}")
    reach = np.zeros_like(st)
    for sz, sx in starts:
        if not reach[sz, sx]:
            r, _ = reachable(sol.solid, (sz, sx), water=sol.water)
            reach |= r
    air = ~sol.solid
    if sol.water is not None:
        air &= ~sol.water
    lab, _ = label(air)
    start_comps = {int(lab[z, x]) for z, x in starts}
    per = {}
    for lm in plan.landmarks:
        cells = landmark_cells(sol, lm, st)
        j, i = _cell(sol, lm.x, lm.floor + 0.6)
        per[lm.name] = dict(
            role=lm.role,
            routed=lm.connect,
            reachable=bool((reach & cells).any()),
            air_connected=bool(air[j, i] and int(lab[j, i]) in start_comps),
        )
    routed_ok = all(v["reachable"] for v in per.values() if v["routed"])
    sealed_ok = all(not v["air_connected"] for v in per.values() if not v["routed"])
    sol.reach, sol.stand = reach, st
    return dict(
        valid=bool(compat and routed_ok and sealed_ok),
        compatible=compat,
        sealed_intact=sealed_ok,
        start=start.name,
        landmarks=per,
        standable_cells=int(st.sum()),
        reached_cells=int(reach.sum()),
    )


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def diagnostic(sol, path, scale=8, title=""):
    """Three panels: scaffold constraints, WFC tiles, and walkable reach."""
    from PIL import Image, ImageDraw

    plan = sol.plan
    H, W = sol.tiles.shape
    h, w = H * SUB * scale, W * SUB * scale
    pad, head = 24, 44
    img = Image.new("RGB", (3 * w + 4 * pad, h + head + 2 * pad), (17, 20, 26))
    dr = ImageDraw.Draw(img)
    x0, x1, z0, z1 = plan.bounds

    def to_px(x, z, ox):
        return ox + (x - x0) / CELL * scale, head + pad + h - (z - z0) / CELL * scale

    def grid_img(rgb):
        im = Image.fromarray(np.flipud(rgb).astype(np.uint8)).resize((w, h), Image.NEAREST)
        return im

    # Panel 1: scaffold.
    c = np.zeros((H, W, 3))
    c[sol.constraint == 1] = (52, 44, 40)
    c[sol.constraint == 0] = (110, 96, 84)
    c[sol.constraint == -1] = (214, 220, 228)
    up = np.kron(c, np.ones((SUB, SUB, 1)))
    ox1 = pad
    img.paste(grid_img(up), (ox1, head + pad))
    for rt in plan.routes:
        pts = [to_px(x, z, ox1) for x, z in rt.pts]
        col = {"main": (227, 160, 74), "loop": (120, 200, 230), "light": (250, 230, 150)}[rt.kind]
        dr.line(pts, fill=col, width=3)
    # Panel 2: WFC tiles.
    ox2 = 2 * pad + w
    ts = tileset()
    cls = np.zeros((H, W, 3))
    cls[:] = (150, 120, 96)
    cls[ts.air_frac[sol.tiles] == 1] = (214, 220, 228)
    cls[ts.air_frac[sol.tiles] == 0] = (52, 44, 40)
    cls[ts.floor[sol.tiles]] = (110, 160, 70)
    sub = np.where(sol.solid[..., None], (52, 44, 40), (214, 220, 228)).astype(float)
    tint = np.kron(cls, np.ones((SUB, SUB, 1)))
    mixed = np.where(sol.solid[..., None], sub * 0.55 + tint * 0.45, sub * 0.8 + tint * 0.2)
    img.paste(grid_img(mixed), (ox2, head + pad))
    for i in range(W + 1):
        X = ox2 + i * SUB * scale
        dr.line([(X, head + pad), (X, head + pad + h)], fill=(30, 34, 42), width=1)
    for j in range(H + 1):
        Y = head + pad + j * SUB * scale
        dr.line([(ox2, Y), (ox2 + w, Y)], fill=(30, 34, 42), width=1)
    # Panel 3: reach.
    ox3 = 3 * pad + 2 * w
    r = np.where(sol.solid[..., None], (52, 44, 40), (200, 206, 214)).astype(float)
    if sol.water is not None:
        r[sol.water] = (70, 150, 190)
    r[sol.stand & ~sol.reach] = (220, 80, 70)
    r[sol.reach] = (110, 200, 90)
    img.paste(grid_img(r), (ox3, head + pad))
    for ox in (ox1, ox3):
        for lm in plan.landmarks:
            px, py = to_px(lm.x, lm.floor + 0.6, ox)
            ok = sol.report.get("landmarks", {}).get(lm.name, {}).get("reachable")
            col = (227, 160, 74) if lm.connect else (200, 140, 255)
            if ox == ox3:
                col = (110, 200, 90) if ok else ((200, 140, 255) if not lm.connect else (220, 80, 70))
            dr.ellipse([px - 7, py - 7, px + 7, py + 7], outline=(17, 20, 26), fill=col, width=2)
            dr.text((px + 10, py - 8), lm.name, fill=(240, 240, 240))
    for ox, label_ in (
        (ox1, "1  scaffold: landmarks, routes, must-air / free / must-solid"),
        (ox2, f"2  WFC solution: {W}x{H} tiles of {TILE} m, {ts.K} tile patterns"),
        (ox3, "3  validation: reachable footing (green), unreached (red)"),
    ):
        dr.text((ox, pad), label_, fill=(230, 232, 236))
    if title:
        dr.text((pad, h + head + pad + 4), title, fill=(150, 156, 166))
    img.save(path)
    return path
