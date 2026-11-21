"""Voxel authoring toolkit for sprite-stack assets.

A Vox is a small volume of palette-indexed voxels, indexed [z, y, x]:
  x = right / the asset's facing direction, y = depth (toward the viewer at yaw 0), z = up.
Each horizontal layer (fixed z) is one slice sprite of the stack.

Shapes take float coordinates in voxel units. Voxel (i, j, k) covers [i, i+1) and its
centre is at i + 0.5. Boxes are lo-inclusive / hi-exclusive.
"""
import colorsys
import json
import math
import os

import numpy as np
from PIL import Image

from .palette import PALETTE

f4 = np.float32


def ramp_rgb(rgb, step):
    """Pixel-art ramp: positive steps go lighter and warmer, negative darker and cooler."""
    if step == 0:
        return tuple(int(c) for c in rgb)
    r, g, b = [c / 255.0 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    a = abs(step)
    target = (50 / 360.0) if step > 0 else (250 / 360.0)
    d = ((target - h + 0.5) % 1.0) - 0.5
    h = (h + d * min(0.07 * a, 0.3)) % 1.0
    if step > 0:
        v = v + (1 - v) * min(0.24 * a, 0.9)
        s = s * (1 - 0.12 * a)
    else:
        v = v * max(1 - 0.17 * a, 0.1)
        s = min(1.0, s * (1 + 0.08 * a))
    r, g, b = colorsys.hsv_to_rgb(h, max(0, min(1, s)), max(0, min(1, v)))
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def _blur1(a, axis, ground=False):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (1, 1)
    if ground:  # treat below the asset as solid, above as air
        p = np.pad(a, pad, mode='edge')
        idx = [slice(None)] * a.ndim
        idx[axis] = -1
        p[tuple(idx)] = 0
    else:
        p = np.pad(a, pad, mode='constant')

    def sl(s):
        return tuple(s if i == axis else slice(None) for i in range(a.ndim))
    return (p[sl(slice(0, -2))] + 2 * p[sl(slice(1, -1))] + p[sl(slice(2, None))]) * 0.25


def blur3(a, passes=1, grounded=True):
    a = a.astype(f4)
    for _ in range(passes):
        a = _blur1(a, 0, ground=grounded)
        a = _blur1(a, 1)
        a = _blur1(a, 2)
    return a


def _fib_sphere(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1).astype(f4)


class Baked:
    """Render-ready arrays for one asset. Flat voxel order is [k, j, i]; entry 0 is 'empty'."""

    def __init__(self, vox):
        Z, Y, X = vox.idx.shape
        self.name = vox.name
        self.dims = (X, Y, Z)
        self.pivot = vox.pivot
        self.lights = list(vox.lights)
        self.sockets = dict(vox.sockets)
        occ = vox.idx > 0
        self.occ = occ
        n = Z * Y * X
        lut = np.zeros((len(vox.mats), 7, 3), f4)
        emit = np.zeros(len(vox.mats), f4)
        spec = np.zeros(len(vox.mats), f4)
        gloss = np.ones(len(vox.mats), f4)
        for mi, m in enumerate(vox.mats):
            if m is None:
                continue
            for s in range(-3, 4):
                lut[mi, s + 3] = ramp_rgb(m['rgb'], s)
            emit[mi], spec[mi], gloss[mi] = m['emit'], m['spec'], m['gloss']
        sh = np.clip(vox.shade, -3, 3).astype(np.int64) + 3
        rgb = lut[vox.idx, sh]                                  # [Z,Y,X,3] 0..255
        self.rgb8 = np.where(occ[..., None], rgb, 0).astype(np.uint8)
        self.albedo = np.zeros((n + 1, 3), f4)
        self.albedo[1:] = (rgb.reshape(-1, 3) / 255.0)
        self.emit = np.zeros(n + 1, f4); self.emit[1:] = emit[vox.idx].ravel()
        self.spec = np.zeros(n + 1, f4); self.spec[1:] = spec[vox.idx].ravel()
        self.gloss = np.ones(n + 1, f4); self.gloss[1:] = gloss[vox.idx].ravel()
        # smooth normals from the blurred occupancy field
        d = blur3(occ, 2, grounded=vox.grounded)
        gz, gy, gx = np.gradient(d)
        nrm = -np.stack([gx, gy, gz], -1)
        ln = np.linalg.norm(nrm, axis=-1, keepdims=True)
        nrm = np.where(ln > 1e-4, nrm / np.maximum(ln, 1e-6), np.array([0, 0, 1], f4))
        self.normal = np.zeros((n + 1, 3), f4); self.normal[1:] = nrm.reshape(-1, 3)
        self.normal[0] = (0, 0, 1)
        # centres
        k, j, i = np.meshgrid(np.arange(Z), np.arange(Y), np.arange(X), indexing='ij')
        self.center = np.zeros((n + 1, 3), f4)
        self.center[1:] = np.stack([i.ravel() + 0.5, j.ravel() + 0.5, k.ravel() + 0.5], 1)
        # which voxels have air directly above (their top face can be seen)
        above = np.zeros_like(occ); above[:-1] = occ[1:]
        self.open_top = np.zeros(n + 1, bool); self.open_top[1:] = (occ & ~above).ravel()
        self.ao = np.ones(n + 1, f4)
        self.ao[1:] = self._bake_ao(occ, nrm, vox.grounded).ravel()
        self.ids = np.where(occ, np.arange(1, n + 1).reshape(Z, Y, X), 0).astype(np.int32)
        self.layers = [z for z in range(Z) if occ[z].any()]

    @staticmethod
    def _bake_ao(occ, nrm, grounded):
        Z, Y, X = occ.shape
        P = 7
        op = np.pad(occ, P, mode='constant')
        if grounded:
            op[:P] = True
        nb = np.zeros_like(occ)
        nb[1:] |= ~occ[:-1]; nb[:-1] |= ~occ[1:]
        nb[:, 1:] |= ~occ[:, :-1]; nb[:, :-1] |= ~occ[:, 1:]
        nb[:, :, 1:] |= ~occ[:, :, :-1]; nb[:, :, :-1] |= ~occ[:, :, 1:]
        nb[-1] = True; nb[:, 0] = True; nb[:, -1] = True; nb[:, :, 0] = True; nb[:, :, -1] = True
        if not grounded:
            nb[0] = True
        surf = occ & nb
        zi, yi, xi = np.nonzero(surf)
        ao = np.ones(occ.shape, f4)
        if len(zi) == 0:
            return ao
        n = nrm[zi, yi, xi]
        c = np.stack([xi, yi, zi], 1).astype(f4) + 0.5 + n * 0.75
        acc = np.zeros(len(zi), f4); wsum = np.zeros(len(zi), f4)
        for dvec in _fib_sphere(48):
            w = np.maximum(0.0, n @ dvec)
            hit = np.zeros(len(zi), f4)
            for t, fall in ((1.0, 1.0), (2.0, 0.85), (3.2, 0.6), (5.0, 0.4)):
                p = np.floor(c + dvec * t).astype(np.int64) + P
                h = op[np.clip(p[:, 2], 0, Z + 2 * P - 1), np.clip(p[:, 1], 0, Y + 2 * P - 1),
                       np.clip(p[:, 0], 0, X + 2 * P - 1)]
                hit = np.maximum(hit, h * fall)
            acc += w * hit; wsum += w
        a = 1.0 - acc / np.maximum(wsum, 1e-4)
        ao[zi, yi, xi] = np.clip(a, 0, 1) ** 1.3
        return ao


class Vox:
    def __init__(self, X, Y, Z, name='asset', grounded=True):
        self.name = name
        self.idx = np.zeros((Z, Y, X), np.uint8)
        self.shade = np.zeros((Z, Y, X), np.int8)
        self.mats = [None]
        self._mid = {}
        z, y, x = np.meshgrid(np.arange(Z) + 0.5, np.arange(Y) + 0.5, np.arange(X) + 0.5, indexing='ij')
        self.x, self.y, self.z = x.astype(f4), y.astype(f4), z.astype(f4)
        self.pivot = (X / 2.0, Y / 2.0)
        self.grounded = grounded
        self.lights = []     # dicts: pos (local voxel coords), rgb (0..1 linear-ish), radius, power
        self.sockets = {}    # name -> (x, y, z) local attachment points

    # ---- materials -------------------------------------------------------------------
    def mat(self, name, rgb=None, emit=None, spec=None, gloss=None):
        """Return the material index for `name`, registering it from the shared palette.
        Pass rgb/emit/spec/gloss to define or override a material locally."""
        if name in self._mid and rgb is None:
            return self._mid[name]
        base = dict(PALETTE.get(name, {}))
        if rgb is not None:
            base['rgb'] = tuple(rgb)
        if 'rgb' not in base:
            raise KeyError(f'unknown material {name!r}; add it to palette.py or pass rgb=')
        m = {'name': name, 'rgb': base['rgb'], 'emit': base.get('emit', 0.0),
             'spec': base.get('spec', 0.04), 'gloss': base.get('gloss', 10.0)}
        if emit is not None: m['emit'] = emit
        if spec is not None: m['spec'] = spec
        if gloss is not None: m['gloss'] = gloss
        if name in self._mid:
            self.mats[self._mid[name]] = m
        else:
            self.mats.append(m)
            self._mid[name] = len(self.mats) - 1
        return self._mid[name]

    def recolor(self, mapping):
        """Palette swap: {'material': (r, g, b) or 'other_palette_material'}."""
        for name, to in mapping.items():
            if name not in self._mid:
                continue
            m = self.mats[self._mid[name]]
            if isinstance(to, str):
                p = PALETTE[to]
                m.update(rgb=p['rgb'], emit=p.get('emit', 0.0), spec=p.get('spec', 0.04), gloss=p.get('gloss', 10.0))
            else:
                m['rgb'] = tuple(to)
        return self

    # ---- masks -----------------------------------------------------------------------
    @property
    def occ(self):
        return self.idx > 0

    def is_mat(self, *names):
        m = np.zeros(self.idx.shape, bool)
        for nme in names:
            if nme in self._mid:
                m |= self.idx == self._mid[nme]
        return m

    def m_box(self, lo, hi):
        return ((self.x >= lo[0]) & (self.x < hi[0]) & (self.y >= lo[1]) & (self.y < hi[1])
                & (self.z >= lo[2]) & (self.z < hi[2]))

    def m_ellipsoid(self, c, r):
        return (((self.x - c[0]) / r[0]) ** 2 + ((self.y - c[1]) / r[1]) ** 2 + ((self.z - c[2]) / r[2]) ** 2) <= 1.0

    def m_rbox(self, lo, hi, r=1.5):
        """Box with rounded corners (radius r)."""
        cx, cy, cz = [(lo[i] + hi[i]) / 2 for i in range(3)]
        hx, hy, hz = [max((hi[i] - lo[i]) / 2 - r, 0) for i in range(3)]
        dx = np.maximum(np.abs(self.x - cx) - hx, 0)
        dy = np.maximum(np.abs(self.y - cy) - hy, 0)
        dz = np.maximum(np.abs(self.z - cz) - hz, 0)
        return (dx * dx + dy * dy + dz * dz) <= r * r

    def m_cyl(self, cxy, r, z0, z1, r1=None, axis='z'):
        """Cylinder / cone frustum along an axis. cxy is the centre in the other two axes
        (x,y for 'z'; y,z for 'x'; x,z for 'y'); radius goes r -> r1 from z0 to z1."""
        a = {'z': self.z, 'x': self.x, 'y': self.y}[axis]
        u, v = {'z': (self.x, self.y), 'x': (self.y, self.z), 'y': (self.x, self.z)}[axis]
        t = np.clip((a - z0) / max(z1 - z0, 1e-6), 0, 1)
        rr = r if r1 is None else r + (r1 - r) * t
        return ((u - cxy[0]) ** 2 + (v - cxy[1]) ** 2 <= rr * rr) & (a >= z0) & (a < z1)

    def m_capsule(self, p0, p1, r, r1=None):
        """Rounded segment from p0 to p1 (x, y, z); radius r -> r1."""
        p0 = np.array(p0, f4); p1 = np.array(p1, f4)
        d = p1 - p0
        L2 = float(d @ d) or 1e-6
        t = np.clip(((self.x - p0[0]) * d[0] + (self.y - p0[1]) * d[1] + (self.z - p0[2]) * d[2]) / L2, 0, 1)
        dx = self.x - (p0[0] + d[0] * t); dy = self.y - (p0[1] + d[1] * t); dz = self.z - (p0[2] + d[2] * t)
        rr = r if r1 is None else r + (r1 - r) * t
        return dx * dx + dy * dy + dz * dz <= rr * rr

    def m_exposed_top(self, depth=1):
        """Occupied voxels with air above (within `depth` voxels of an upward-facing surface)."""
        occ = self.occ
        m = np.zeros_like(occ)
        cur = occ.copy()
        for _ in range(depth):
            above = np.zeros_like(occ); above[:-1] = cur[1:]
            top = cur & ~above
            m |= top
            cur = cur & ~top
        return m

    def m_surface(self):
        occ = self.occ
        p = np.pad(occ, 1, mode='constant')
        inner = (p[:-2, 1:-1, 1:-1] & p[2:, 1:-1, 1:-1] & p[1:-1, :-2, 1:-1] & p[1:-1, 2:, 1:-1]
                 & p[1:-1, 1:-1, :-2] & p[1:-1, 1:-1, 2:])
        return occ & ~inner

    # ---- noise -----------------------------------------------------------------------
    def rand(self, seed=0):
        return np.random.default_rng(seed).random(self.idx.shape, dtype=f4)

    def noise(self, scale=6.0, seed=0, octaves=1):
        """Smooth value noise in 0..1 with features about `scale` voxels wide."""
        out = np.zeros(self.idx.shape, f4); amp = 1.0; tot = 0.0
        for o in range(octaves):
            sc = scale / (2 ** o)
            rng = np.random.default_rng(seed * 131 + o * 17 + 5)
            Z, Y, X = self.idx.shape
            gz, gy, gx = int(Z / sc) + 3, int(Y / sc) + 3, int(X / sc) + 3
            g = rng.random((gz, gy, gx), dtype=f4)
            fz, fy, fx = self.z / sc, self.y / sc, self.x / sc
            iz, iy, ix = fz.astype(int), fy.astype(int), fx.astype(int)
            tz, ty, tx = fz - iz, fy - iy, fx - ix
            tz = tz * tz * (3 - 2 * tz); ty = ty * ty * (3 - 2 * ty); tx = tx * tx * (3 - 2 * tx)
            v = 0
            for dz in (0, 1):
                for dy in (0, 1):
                    for dx in (0, 1):
                        w = (tz if dz else 1 - tz) * (ty if dy else 1 - ty) * (tx if dx else 1 - tx)
                        v = v + w * g[iz + dz, iy + dy, ix + dx]
            out += v * amp; tot += amp; amp *= 0.5
        return out / tot

    # ---- edits -----------------------------------------------------------------------
    def fill(self, mask, mat, shade=0):
        """Set voxels in mask to material (name), replacing whatever is there."""
        self.idx[mask] = self.mat(mat)
        self.shade[mask] = shade
        return mask

    def add(self, mask, mat, shade=0):
        """Like fill, but only into empty space."""
        return self.fill(mask & ~self.occ, mat, shade)

    def paint(self, mask, mat=None, shade=None, add=None):
        """Recolor existing voxels in mask: change material, set shade, or add to shade."""
        m = mask & self.occ
        if mat is not None:
            self.idx[m] = self.mat(mat)
        if shade is not None:
            self.shade[m] = shade
        if add is not None:
            self.shade[m] = np.clip(self.shade[m].astype(int) + add, -3, 3)
        return m

    def carve(self, mask):
        self.idx[mask] = 0
        self.shade[mask] = 0
        return mask

    def box(self, lo, hi, mat, shade=0):
        return self.fill(self.m_box(lo, hi), mat, shade)

    def rbox(self, lo, hi, mat, r=1.5, shade=0):
        return self.fill(self.m_rbox(lo, hi, r), mat, shade)

    def ellipsoid(self, c, r, mat, shade=0):
        return self.fill(self.m_ellipsoid(c, r), mat, shade)

    def cyl(self, cxy, r, z0, z1, mat, r1=None, axis='z', shade=0):
        return self.fill(self.m_cyl(cxy, r, z0, z1, r1, axis), mat, shade)

    def capsule(self, p0, p1, r, mat, r1=None, shade=0):
        return self.fill(self.m_capsule(p0, p1, r, r1), mat, shade)

    def speckle(self, mats, amount=0.18, step=-1, seed=0, scale=None):
        """Texture: shift the shade of a share of the voxels of the given material(s).
        With scale, uses smooth noise so the variation forms clusters instead of dither."""
        if isinstance(mats, str):
            mats = [mats]
        r = self.noise(scale, seed) if scale else self.rand(seed)
        if scale:
            thr = np.quantile(r[self.occ], 1 - amount) if self.occ.any() else 1
            m = (r >= thr)
        else:
            m = r < amount
        return self.paint(m & self.is_mat(*mats), add=step)

    def grade(self, mats, lo=-1, hi=1, axis='z'):
        """Shade gradient along an axis across the extent of the given material(s)."""
        if isinstance(mats, str):
            mats = [mats]
        m = self.is_mat(*mats)
        if not m.any():
            return m
        a = {'z': self.z, 'x': self.x, 'y': self.y}[axis]
        a0, a1 = a[m].min(), a[m].max()
        t = (a - a0) / max(a1 - a0, 1e-6)
        s = np.rint(lo + (hi - lo) * t).astype(np.int8)
        self.shade[m] = np.clip(self.shade[m].astype(int) + s[m], -3, 3)
        return m

    def mirror_y(self):
        """Make the model symmetric left/right by copying the y < centre half onto the other."""
        Y = self.idx.shape[1]
        h = Y // 2
        self.idx[:, Y - h:, :] = self.idx[:, :h, :][:, ::-1, :]
        self.shade[:, Y - h:, :] = self.shade[:, :h, :][:, ::-1, :]
        return self

    def blit(self, other, at=(0, 0, 0), replace=True):
        """Copy another Vox in, with its (0,0,0) corner placed at integer offset `at`."""
        ox, oy, oz = [int(round(a)) for a in at]
        Z, Y, X = other.idx.shape
        SZ, SY, SX = self.idx.shape
        z0, y0, x0 = max(oz, 0), max(oy, 0), max(ox, 0)
        z1, y1, x1 = min(oz + Z, SZ), min(oy + Y, SY), min(ox + X, SX)
        if z1 <= z0 or y1 <= y0 or x1 <= x0:
            return self
        src = other.idx[z0 - oz:z1 - oz, y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        ssh = other.shade[z0 - oz:z1 - oz, y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        remap = np.zeros(len(other.mats), np.uint8)
        for i, m in enumerate(other.mats):
            if m is not None:
                remap[i] = self.mat(m['name'], m['rgb'], m['emit'], m['spec'], m['gloss']) if m['name'] not in self._mid else self._mid[m['name']]
        dst = self.idx[z0:z1, y0:y1, x0:x1]; dsh = self.shade[z0:z1, y0:y1, x0:x1]
        m = src > 0
        if not replace:
            m &= dst == 0
        dst[m] = remap[src][m]; dsh[m] = ssh[m]
        for L in other.lights:
            p = L['pos']
            self.lights.append({**L, 'pos': (p[0] + ox, p[1] + oy, p[2] + oz)})
        return self

    def light(self, pos, rgb, radius=18.0, power=1.0):
        """Attach a point light (local voxel coords) that travels with the asset."""
        self.lights.append({'pos': tuple(pos), 'rgb': tuple(rgb), 'radius': radius, 'power': power})

    def socket(self, name, pos):
        self.sockets[name] = tuple(pos)

    def bounds(self):
        zs, ys, xs = np.nonzero(self.occ)
        return (xs.min(), ys.min(), zs.min()), (xs.max() + 1, ys.max() + 1, zs.max() + 1)

    def count(self):
        return int(self.occ.sum())

    def bake(self):
        return Baked(self)

    # ---- export ----------------------------------------------------------------------
    def save_sheet(self, path_base, cols=None):
        """Write the stack as sprite sheets: <base>.png (albedo slices, bottom layer first),
        <base>_n.png (normal in rgb, ambient occlusion in alpha), <base>_m.png (r = emissive,
        g = specular, b = gloss) and <base>.json (layout + materials)."""
        b = self.bake()
        X, Y, Z = b.dims
        cols = cols or max(1, min(Z, int(math.ceil(math.sqrt(Z * (Y / X))))))
        rows = int(math.ceil(Z / cols))
        alb = np.zeros((rows * Y, cols * X, 4), np.uint8)
        nrm = np.zeros((rows * Y, cols * X, 4), np.uint8)
        mat = np.zeros((rows * Y, cols * X, 4), np.uint8)
        n3 = b.normal[1:].reshape(Z, Y, X, 3); ao = b.ao[1:].reshape(Z, Y, X)
        em = b.emit[1:].reshape(Z, Y, X); sp = b.spec[1:].reshape(Z, Y, X); gl = b.gloss[1:].reshape(Z, Y, X)
        for k in range(Z):
            r, c = divmod(k, cols)
            sl = (slice(r * Y, r * Y + Y), slice(c * X, c * X + X))
            o = b.occ[k]
            alb[sl][..., :3] = b.rgb8[k]; alb[sl][..., 3] = o * 255
            nrm[sl][..., :3] = np.where(o[..., None], (n3[k] * 0.5 + 0.5) * 255, 0)
            nrm[sl][..., 3] = np.where(o, ao[k] * 255, 0)
            mat[sl][..., 0] = np.clip(em[k] / 4.0, 0, 1) * 255 * o
            mat[sl][..., 1] = np.clip(sp[k], 0, 1) * 255 * o
            mat[sl][..., 2] = np.clip(gl[k] / 64.0, 0, 1) * 255 * o
            mat[sl][..., 3] = o * 255
        os.makedirs(os.path.dirname(path_base) or '.', exist_ok=True)
        Image.fromarray(alb).save(path_base + '.png')
        Image.fromarray(nrm).save(path_base + '_n.png')
        Image.fromarray(mat).save(path_base + '_m.png')
        meta = {'name': self.name, 'size': [X, Y], 'layers': Z, 'cols': cols, 'rows': rows,
                'pivot': list(self.pivot), 'voxels': self.count(),
                'materials': [m['name'] for m in self.mats if m],
                'lights': self.lights, 'sockets': self.sockets}
        with open(path_base + '.json', 'w') as f:
            json.dump(meta, f, indent=1)
        return meta
