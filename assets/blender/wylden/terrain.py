"""Side-view cross-section terrain from a scalar material field.

The playable plane (x, z) comes from a solved world (worldgen.Solution): the
WFC sub-cells are smoothed into a signed field and resampled at mining-cell
resolution. Depth (y) is added for visual form only: the playable pocket
keeps the 2D contour near the front, gains relief further back, and closes
against a back wall. Marching cubes turns the field into one organic mesh, so
contours, collision and dressing all derive from the same state.

Positive field values are solid. The camera sits at -Y looking into +Y.
"""

import math

import numpy as np
from scipy.ndimage import gaussian_filter, zoom
from skimage.measure import marching_cubes

from . import core


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def catmull(points, step=0.2):
    """Dense samples along a Catmull-Rom spline through (x, z, r) control points."""
    p = np.asarray(points, dtype=np.float64)
    if len(p) == 1:
        return p
    ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        n = max(2, int(np.linalg.norm(p2[:2] - p1[:2]) / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(
                0.5
                * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            )
    out.append(p[-1])
    return np.array(out)


class Field:
    def __init__(self, x_range, z_range, y_range, res=0.08, seed=1):
        self.res = res
        self.rng = np.random.default_rng(seed)
        self.xs = np.arange(x_range[0], x_range[1] + 1e-6, res)
        self.zs = np.arange(z_range[0], z_range[1] + 1e-6, res)
        self.ys = np.arange(y_range[0], y_range[1] + 1e-6, res)
        self.X2, self.Z2 = np.meshgrid(self.xs, self.zs, indexing="ij")
        self.plan = None
        self.surface = None
        self.solution = None
        self.F = None

    # -- noise ---------------------------------------------------------------

    def noise2(self, scale):
        sig = max(scale / self.res / 2.5, 0.5)
        a = gaussian_filter(self.rng.standard_normal(self.X2.shape), sig, mode="reflect")
        return a / (a.std() + 1e-9)

    def noise1(self, scale):
        sig = max(scale / self.res / 2.5, 0.5)
        a = gaussian_filter(self.rng.standard_normal(self.xs.shape), sig, mode="reflect")
        return a / (a.std() + 1e-9)

    def noise3(self, scale):
        shape = (len(self.xs), len(self.ys), len(self.zs))
        step = max(scale / 2.0, self.res)
        cs = [max(4, int(math.ceil(n * self.res / step)) + 3) for n in shape]
        c = gaussian_filter(self.rng.standard_normal(cs), 0.8, mode="wrap")
        f = [shape[i] / (cs[i] - 3) for i in range(3)]
        big = zoom(c, f, order=3, mode="grid-wrap")
        big = big[: shape[0], : shape[1], : shape[2]]
        if big.shape != shape:
            pad = [(0, shape[i] - big.shape[i]) for i in range(3)]
            big = np.pad(big, pad, mode="edge")
        return (big / (big.std() + 1e-9)).astype(np.float32)

    # -- plan ------------------------------------------------------------------

    def from_solution(self, sol, sigma=1.0):
        """Adopt a solved world: its smoothed WFC sub-cells become the 2D plan field."""
        from scipy.interpolate import RegularGridInterpolator

        signed = sol.signed(sigma)  # [z, x], metres
        interp = RegularGridInterpolator((sol.zs, sol.xs), signed, bounds_error=False, fill_value=None)
        pts = np.stack([self.Z2.ravel(), self.X2.ravel()], axis=1)
        self.plan = interp(pts).reshape(self.X2.shape)
        if sol.plan.surface is not None:
            self.surface = sol.plan.surface(self.xs)
        self.solution = sol
        return self

    # -- build ------------------------------------------------------------------

    def build(
        self,
        pocket=2.8,
        pocket_var=0.8,
        relief=0.35,
        edge=0.22,
        front_round=0.18,
        back_relief=0.45,
        surface_open_back=True,
    ):
        G = (self.surface[:, None] - self.Z2) if self.surface is not None else np.full(self.X2.shape, 1e3)
        S2 = self.plan + edge * (0.6 * self.noise2(0.9) + 0.4 * self.noise2(0.3))
        self.S2 = S2
        Y = self.ys[None, :, None]
        ramp = np.clip(Y / max(pocket, 1e-3), 0.25, 1.0)
        F = S2[:, None, :] + relief * ramp * self.noise3(1.4)
        D = pocket + pocket_var * self.noise2(2.5)
        back = (Y - D[:, None, :]) + back_relief * self.noise3(1.1) * (Y > 0.5)
        if surface_open_back:
            back = np.minimum(G[:, None, :], back)
        F = smax(F, back, 0.6)
        F = smin(F, (Y - 0.0) * 1.0, front_round)
        F = np.pad(F.astype(np.float32), 1, mode="constant", constant_values=-1.0)
        self.F = F
        self.pocket = pocket
        return F

    def mesh(self, name, coll=None):
        r = self.res
        verts, faces, normals, _ = marching_cubes(self.F, level=0.0, spacing=(r, r, r))
        verts = verts + np.array([self.xs[0] - r, self.ys[0] - r, self.zs[0] - r])
        # Orient faces outward (away from solid): compare with the field gradient.
        tri = verts[faces]
        fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        sample = np.linspace(0, len(faces) - 1, min(4000, len(faces))).astype(int)
        cen = tri[sample].mean(axis=1)
        g = np.stack([self.sample(cen + d) - self.sample(cen - d) for d in np.eye(3) * r], axis=1)
        if np.sum(np.einsum("ij,ij->i", fn[sample], g) > 0) > len(sample) / 2:
            faces = faces[:, ::-1]
        ob = core.mesh_object(name, verts, faces, coll=coll, smooth=True, recalc=False)
        self.verts, self.faces = verts, faces
        return ob

    def sample(self, pts):
        """Trilinear field lookup at world points (N, 3)."""
        r = self.res
        ix = (pts[:, 0] - self.xs[0]) / r + 1
        iy = (pts[:, 1] - self.ys[0]) / r + 1
        iz = (pts[:, 2] - self.zs[0]) / r + 1
        F = self.F
        ix = np.clip(ix, 0, F.shape[0] - 1.001)
        iy = np.clip(iy, 0, F.shape[1] - 1.001)
        iz = np.clip(iz, 0, F.shape[2] - 1.001)
        x0, y0, z0 = ix.astype(int), iy.astype(int), iz.astype(int)
        fx, fy, fz = ix - x0, iy - y0, iz - z0
        out = 0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = (fx if dx else 1 - fx) * (fy if dy else 1 - fy) * (fz if dz else 1 - fz)
                    out = out + w * F[x0 + dx, y0 + dy, z0 + dz]
        return out

    def floor_at(self, x, y, z_from, z_min=-50):
        """Highest solid surface at or below z_from, at (x, y)."""
        zs = np.arange(z_from, z_min, -self.res / 2)
        vals = self.sample(np.stack([np.full_like(zs, x), np.full_like(zs, y), zs], axis=1))
        hit = np.nonzero(vals > 0)[0]
        if len(hit) == 0:
            return None
        i = hit[0]
        if i == 0:
            return float(zs[0])
        a, b = vals[i - 1], vals[i]
        return float(zs[i - 1] + (zs[i] - zs[i - 1]) * (0 - a) / (b - a))

    def ceiling_at(self, x, y, z_from, z_max=50):
        zs = np.arange(z_from, z_max, self.res / 2)
        vals = self.sample(np.stack([np.full_like(zs, x), np.full_like(zs, y), zs], axis=1))
        hit = np.nonzero(vals > 0)[0]
        return float(zs[hit[0]]) if len(hit) else None

    def scatter(
        self,
        rng,
        count,
        normal_min=None,
        normal_max=None,
        y_range=(0.2, 3.0),
        x_range=None,
        z_range=None,
        axis=2,
        mask=None,
    ):
        """Random points on mesh faces whose normal component (axis) is within range."""
        tri = self.verts[self.faces]
        fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        area = np.linalg.norm(fn, axis=1) * 0.5
        n = fn / (2 * area[:, None] + 1e-12)
        cen = tri.mean(axis=1)
        ok = (cen[:, 1] >= y_range[0]) & (cen[:, 1] <= y_range[1])
        if normal_min is not None:
            ok &= n[:, axis] >= normal_min
        if normal_max is not None:
            ok &= n[:, axis] <= normal_max
        if x_range:
            ok &= (cen[:, 0] >= x_range[0]) & (cen[:, 0] <= x_range[1])
        if z_range:
            ok &= (cen[:, 2] >= z_range[0]) & (cen[:, 2] <= z_range[1])
        if mask is not None:
            ok &= mask(cen, n)
        idx = np.nonzero(ok)[0]
        if len(idx) == 0:
            return np.zeros((0, 3)), np.zeros((0, 3))
        p = area[idx] / area[idx].sum()
        pick = rng.choice(idx, size=count, p=p)
        u, v = rng.random(count), rng.random(count)
        flip = u + v > 1
        u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
        t = tri[pick]
        pts = t[:, 0] + (t[:, 1] - t[:, 0]) * u[:, None] + (t[:, 2] - t[:, 0]) * v[:, None]
        return pts, n[pick]
