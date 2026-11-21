"""Sprite-stack renderer: slices blitted as sprites, then anti-aliased and lit.

How a frame is made
  1. G-buffer by sprite blits. Every layer of every stack is an ordinary 2D sprite: it is
     rotated by the yaw, squashed by sin(elevation) and drawn one step higher than the
     layer below. Each voxel layer is one voxel thick, so the slice is repeated up the
     screen to fill its side walls. Sprites carry voxel ids instead of colour, and a
     per-pixel height test lets separate stacks (a character and its backpack) interleave.
  2. Lighting per voxel. Each visible voxel gets a top-face and a side-face colour from its
     baked normal and ambient occlusion: sky/ground ambient, a shadowed key light, point
     lights, specular and emission. Shadows come from the same slices: sheared along the
     light direction and max-combined into a height map.
  3. Anti-aliasing. Slices are sampled nearest-neighbour at a supersampled resolution and
     box-filtered down, which keeps texels flat and crisp but gives every edge smooth
     coverage (the look a 'sharp bilinear' shader gives in real time).
  4. Floor, reflection (the stack drawn again downward), bloom, tone mapping.
"""
import math

import numpy as np
from PIL import Image

f4 = np.float32


def srgb2lin(c):
    c = np.asarray(c, f4)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(f4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055).astype(f4)


def _norm(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)


def box_blur(a, r):
    """Separable box blur (cumsum), edge-clamped. a: [H, W] or [H, W, C]."""
    if r <= 0:
        return a
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r + 1, r)
        p = np.pad(a, pad, mode='edge')
        c = np.cumsum(p, axis=axis, dtype=np.float64)
        n = a.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        a = ((hi - lo) / (2 * r + 1)).astype(f4)
    return a


def gauss_blur(a, r):
    for _ in range(3):
        a = box_blur(a, max(1, int(round(r * 0.6))))
    return a


def downsample(a, k):
    if k == 1:
        return a
    H, W = a.shape[:2]
    return a.reshape(H // k, k, W // k, k, *a.shape[2:]).mean(axis=(1, 3))


class Camera:
    def __init__(self, yaw=30.0, elev=38.0, scale=5.0, look=(0, 0, 0), size=(1280, 720)):
        self.yaw, self.elev, self.scale = yaw, elev, scale
        self.look = look
        self.size = size


class Obj:
    def __init__(self, baked, pos=(0, 0, 0), yaw=0.0, label=None):
        self.b = baked
        self.pos = np.array(pos, f4)
        self.yaw = yaw
        self.label = label
        self.gap = 0.0          # extra space between layers, in voxels (exploded view)
        self.thick = 1.0        # drawn thickness of each layer, in voxels
        self.kmax = None        # draw only layers below this index (assembly animations)
        self.layer_off = None   # [Z, 3] per-layer world offset (dx, dy, dz): sway, drop-in
        self.albedo = None      # optional replacement albedo table (palette swap)
        self.shadow = True
        self.reflect = True
        self.lit = True


class Scene:
    def __init__(self):
        self.objs = []
        self.lights = []                      # dict(pos=(x,y,z) world, rgb, radius, power)
        self.key_dir = (-0.55, 0.45, 0.72)    # toward the light; camera frame: x right, y toward viewer, z up
        self.key_frame = 'camera'             # 'camera' = light fixed while the turntable spins, or 'world'
        self.key_rgb = (1.0, 0.94, 0.84)
        self.key_power = 1.25
        self.sky_rgb = (0.42, 0.52, 0.72)
        self.ground_rgb = (0.20, 0.16, 0.14)
        self.ambient = 0.55
        self.floor = None                     # dict(kind='dais', radius=.., ...) or dict(kind='plane', ...)
        self.bg = dict(inner=(26, 44, 66), outer=(5, 8, 16), center=(0.5, 0.46), dots=True)
        self.exposure = 1.0
        self.bloom = 0.7
        self.soft = 5                         # shadow samples
        self.face_mix = 0.12                  # how much top/side faces pull away from the smooth normal
        self.bands = 0                        # >0: quantise diffuse light into this many steps
        self.emit_gain = 1.0

    def add(self, baked, pos=(0, 0, 0), yaw=0.0, label=None, **kw):
        o = Obj(baked, pos, yaw, label)
        for k, v in kw.items():
            setattr(o, k, v)
        self.objs.append(o)
        return o

    def light(self, pos, rgb, radius=20.0, power=1.0):
        L = dict(pos=tuple(pos), rgb=tuple(rgb), radius=radius, power=power)
        self.lights.append(L)
        return L

    # ---- id layout -------------------------------------------------------------------
    def _prepare(self):
        base = 0
        for o in self.objs:
            n = o.b.ids.size
            if getattr(o, '_base', None) != base or getattr(o, '_imgs', None) is None:
                o._base = base
                o._imgs = {}
                for k in o.b.layers:
                    a = o.b.ids[k]
                    o._imgs[k] = Image.fromarray(np.where(a > 0, (a + base) * 2, 0).astype(np.int32))
                    o._imgs[k].load()
                o._occ = {k: Image.fromarray((o.b.occ[k] * 255).astype(np.uint8)) for k in o.b.layers}
            base += n
        self._total = base

    def _layer_z(self, o, k):
        z0 = float(o.pos[2]) + k * (1.0 + o.gap)
        dx = dy = 0.0
        if o.layer_off is not None:
            dx, dy, dz = o.layer_off[k]
            z0 += float(dz)
        return z0, z0 + o.thick, float(dx), float(dy)


def _rot(x, y, a):
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def _gbuffer(scene, cam, S, W, H, cx, cy, mirror=False):
    """Blit every layer of every stack. Returns (id buffer, height buffer)."""
    idb = np.zeros((H, W), np.int32)
    zb = np.full((H, W), -1e9, f4)
    th = math.radians(cam.yaw)
    se, ce = math.sin(math.radians(cam.elev)), math.cos(math.radians(cam.elev))
    lx, ly, lz = cam.look
    rise = S * ce
    for o in scene.objs:
        if mirror and not o.reflect:
            continue
        X, Y, Z = o.b.dims
        px, py = o.b.pivot
        phi = th + math.radians(o.yaw)
        cph, sph = math.cos(phi), math.sin(phi)
        oxr, oyr = _rot(float(o.pos[0]) - lx, float(o.pos[1]) - ly, th)
        xs, ys = [], []
        for (i, j) in ((0, 0), (X, 0), (0, Y), (X, Y)):
            rx, ry = _rot(i - px, j - py, phi)
            xs.append(cx + S * (rx + oxr)); ys.append(cy + S * se * (ry + oyr))
        bx0, by0 = int(math.floor(min(xs))) - 1, int(math.floor(min(ys))) - 1
        bw, bh = int(math.ceil(max(xs))) - bx0 + 2, int(math.ceil(max(ys))) - by0 + 2
        a = cph / S; b = sph / (S * se)
        d = -sph / S; e = cph / (S * se)
        for k in o.b.layers:
            if o.kmax is not None and k >= o.kmax:
                continue
            z0, z1, dxw, dyw = scene._layer_z(o, k)
            bx, by = bx0, by0
            if dxw or dyw:
                sxr, syr = _rot(dxw, dyw, th)
                bx += int(round(S * sxr)); by += int(round(S * se * syr))
                ox2, oy2 = oxr + int(round(S * sxr)) / S, oyr + int(round(S * se * syr)) / (S * se)
            else:
                ox2, oy2 = oxr, oyr
            u0 = (bx - cx) / S - ox2; v0 = (by - cy) / (S * se) - oy2
            c = cph * u0 + sph * v0 + px
            f = -sph * u0 + cph * v0 + py
            arr = np.asarray(o._imgs[k].transform((bw, bh), Image.AFFINE, (a, b, c, d, e, f), Image.NEAREST))
            rows = np.flatnonzero(arr.any(1))
            if rows.size == 0:
                continue
            cols = np.flatnonzero(arr.any(0))
            r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
            sub = arr[r0:r1, c0:c1]
            mask = sub > 0
            if mirror:
                zlo, zhi = -z1, -z0
            else:
                zlo, zhi = z0, z1
            o0 = int(round(rise * (zlo - lz))); o1 = int(round(rise * (zhi - lz)))
            r = max(1, o1 - o0)
            h, w = sub.shape
            loc = np.zeros((h + r - 1, w), np.int32)
            for j in range(1, r):
                np.copyto(loc[r - j:r - j + h], sub, where=mask)
            np.copyto(loc[0:h], sub if mirror else (sub | 1), where=mask)
            ys0 = by + r0 - o1; xs0 = bx + c0
            ya, yb = max(ys0, 0), min(ys0 + loc.shape[0], H)
            xa, xb = max(xs0, 0), min(xs0 + w, W)
            if ya >= yb or xa >= xb:
                continue
            L = loc[ya - ys0:yb - ys0, xa - xs0:xb - xs0]
            rid = idb[ya:yb, xa:xb]; rz = zb[ya:yb, xa:xb]
            m = (L > 0) & (rz <= zhi)
            np.copyto(rid, L, where=m)
            np.copyto(rz, f4(zhi), where=m)
    return idb, zb


class _Shadow:
    """Height-map shadows built from the same slices, sheared along the light."""

    def __init__(self, scene, Lw, n_samples, extent, rw=2):
        self.rw = rw
        self.G = extent
        N = int(2 * extent * rw) + 1
        self.N = N
        rng = np.random.default_rng(7)
        dirs = [np.array(Lw, f4)]
        for i in range(max(0, n_samples - 1)):
            ang = 2 * math.pi * i / max(1, n_samples - 1)
            j = np.array([math.cos(ang), math.sin(ang), 0], f4) * 0.075
            dirs.append(_norm(np.array(Lw, f4) + j))
        self.dirs = dirs
        self.H = [np.zeros((N, N), f4) for _ in dirs]
        self.low = np.zeros((N, N), f4)
        for o in scene.objs:
            if not o.shadow:
                continue
            X, Y, Z = o.b.dims
            px, py = o.b.pivot
            psi = math.radians(o.yaw)
            cps, sps = math.cos(psi), math.sin(psi)
            xs, ys = [], []
            for (i, j) in ((0, 0), (X, 0), (0, Y), (X, Y)):
                rx, ry = _rot(i - px, j - py, psi)
                xs.append(rx); ys.append(ry)
            for k in o.b.layers:
                if o.kmax is not None and k >= o.kmax:
                    continue
                z0, z1, dxw, dyw = scene._layer_z(o, k)
                wx0 = float(o.pos[0]) + dxw; wy0 = float(o.pos[1]) + dyw
                bx = int(math.floor((min(xs) + wx0 + extent) * rw)) - 1
                by = int(math.floor((min(ys) + wy0 + extent) * rw)) - 1
                bw = int(math.ceil((max(xs) - min(xs)) * rw)) + 3
                bh = int(math.ceil((max(ys) - min(ys)) * rw)) + 3
                u0 = bx / rw - extent - wx0; v0 = by / rw - extent - wy0
                a = cps / rw; b = sps / rw; c = cps * u0 + sps * v0 + px
                d = -sps / rw; e = cps / rw; f = -sps * u0 + cps * v0 + py
                m = np.asarray(o._occ[k].transform((bw, bh), Image.AFFINE, (a, b, c, d, e, f), Image.NEAREST)) > 0
                if not m.any():
                    continue
                if z0 < 2.5:
                    self._paste(self.low, m, bx, by, 1.0)
                for Hm, Ld in zip(self.H, self.dirs):
                    shx, shy = Ld[0] / Ld[2] * rw, Ld[1] / Ld[2] * rw
                    steps = int(math.ceil(max(abs(shx), abs(shy)) * (z1 - z0))) + 1
                    for t in np.linspace(z0, z1, steps + 1)[1:] if steps > 1 else [z1]:
                        self._paste(Hm, m, bx - int(round(t * shx)), by - int(round(t * shy)), z1)

    def _paste(self, Hm, m, bx, by, val):
        N = self.N
        h, w = m.shape
        ya, yb, xa, xb = max(by, 0), min(by + h, N), max(bx, 0), min(bx + w, N)
        if ya >= yb or xa >= xb:
            return
        reg = Hm[ya:yb, xa:xb]
        np.maximum(reg, np.where(m[ya - by:yb - by, xa - bx:xb - bx], f4(val), 0), out=reg)

    def lit(self, P, tol=0.6):
        """Fraction of light reaching points P [n, 3] (world)."""
        acc = np.zeros(len(P), f4)
        for Hm, Ld in zip(self.H, self.dirs):
            u = np.rint((P[:, 0] - P[:, 2] * Ld[0] / Ld[2] + self.G) * self.rw).astype(np.int64)
            v = np.rint((P[:, 1] - P[:, 2] * Ld[1] / Ld[2] + self.G) * self.rw).astype(np.int64)
            ok = (u >= 0) & (u < self.N) & (v >= 0) & (v < self.N)
            hv = Hm[np.clip(v, 0, self.N - 1), np.clip(u, 0, self.N - 1)]
            acc += np.where(ok, hv <= P[:, 2] + tol, True)
        return acc / len(self.H)

    def lightmap(self, scene, lights, Lw, fz=0.0, use_shadow=True):
        """Floor lighting baked into a world-space texture: ambient with contact darkening,
        the shadowed key light and every point light. Sampled bilinearly per floor pixel."""
        N = self.N
        if use_shadow:
            s = np.zeros((N, N), f4)
            for Hm, Ld in zip(self.H, self.dirs):
                du = int(round(-fz * Ld[0] / Ld[2] * self.rw)); dv = int(round(-fz * Ld[1] / Ld[2] * self.rw))
                s += np.roll(Hm, (-dv, -du), (0, 1)) <= fz + 0.6
            s = gauss_blur(s / len(self.H), 1.2)
            contact = np.clip(gauss_blur(self.low, 3.0), 0, 1)
        else:
            s = np.ones((N, N), f4); contact = np.zeros((N, N), f4)
        g = (np.arange(N, dtype=f4) / self.rw) - self.G
        wx, wy = np.meshgrid(g, g)
        sky = np.array(scene.sky_rgb, f4)
        key = np.array(scene.key_rgb, f4) * scene.key_power
        light = sky * (scene.ambient * (1 - 0.6 * contact))[..., None] + key * (max(0.0, float(Lw[2])) * s)[..., None]
        for L in lights:
            lp = L['pos']
            dz_ = lp[2] - fz
            d2 = (wx - lp[0]) ** 2 + (wy - lp[1]) ** 2 + dz_ * dz_
            att = np.maximum(0.0, 1 - d2 / (L['radius'] ** 2)) ** 2 * L['power']
            nl = np.clip(dz_ / np.sqrt(np.maximum(d2, 1e-3)), 0, 1) * 0.8 + 0.2
            light = light + np.array(L['rgb'], f4) * (att * nl)[..., None]
        return light.astype(f4)

    def sample(self, tex, wx, wy):
        fu = np.clip((wx + self.G) * self.rw, 0, self.N - 1.001)
        fv = np.clip((wy + self.G) * self.rw, 0, self.N - 1.001)
        iu = fu.astype(np.int64); iv = fv.astype(np.int64)
        tu = fu - iu; tv = fv - iv
        return (tex[iv, iu] * (1 - tu) * (1 - tv) + tex[iv, iu + 1] * tu * (1 - tv)
                + tex[iv + 1, iu] * (1 - tu) * tv + tex[iv + 1, iu + 1] * tu * tv)


def _world_tables(scene):
    T = scene._total + 1
    P = np.zeros((T, 3), f4); Nw = np.zeros((T, 3), f4); Nw[:, 2] = 1
    alb = np.zeros((T, 3), f4); ao = np.ones(T, f4); emit = np.zeros(T, f4)
    spec = np.zeros(T, f4); gloss = np.ones(T, f4); lit = np.ones(T, bool); otop = np.zeros(T, bool)
    lights = list(scene.lights)
    for o in scene.objs:
        b = o.b
        n = b.ids.size
        sl = slice(o._base + 1, o._base + n + 1)
        psi = math.radians(o.yaw)
        cx_, cy_ = b.center[1:, 0] - b.pivot[0], b.center[1:, 1] - b.pivot[1]
        P[sl, 0], P[sl, 1] = _rot(cx_, cy_, psi)
        P[sl, 0] += o.pos[0]; P[sl, 1] += o.pos[1]
        kk = (b.center[1:, 2] - 0.5)
        P[sl, 2] = o.pos[2] + kk * (1.0 + o.gap) + 0.5 * o.thick
        if o.layer_off is not None:
            ki = kk.astype(np.int64)
            P[sl, 0] += o.layer_off[ki, 0]; P[sl, 1] += o.layer_off[ki, 1]; P[sl, 2] += o.layer_off[ki, 2]
        Nw[sl, 0], Nw[sl, 1] = _rot(b.normal[1:, 0], b.normal[1:, 1], psi)
        Nw[sl, 2] = b.normal[1:, 2]
        alb[sl] = srgb2lin(o.albedo[1:] if o.albedo is not None else b.albedo[1:])
        ao[sl] = b.ao[1:]; emit[sl] = b.emit[1:]; spec[sl] = b.spec[1:]; gloss[sl] = b.gloss[1:]
        lit[sl] = o.lit
        otop[sl] = b.open_top[1:]
        for L in b.lights:
            lx_, ly_ = _rot(L['pos'][0] - b.pivot[0], L['pos'][1] - b.pivot[1], psi)
            kz = L['pos'][2]
            lights.append(dict(pos=(lx_ + float(o.pos[0]), ly_ + float(o.pos[1]), float(o.pos[2]) + kz * (1.0 + o.gap)),
                               rgb=L['rgb'], radius=L['radius'], power=L['power'] * getattr(o, 'light_gain', 1.0)))
    return P, Nw, alb, ao, emit, spec, gloss, lit, otop, lights


def _shade(scene, cam, shadow, mode, vis=None):
    """Per-voxel colours for top faces and side faces. Returns (table [2*(T+1), 3], glow table)."""
    P, Nw, alb, ao, emit, spec, gloss, litflag, otop, lights = _world_tables(scene)
    T_full = len(P)
    if vis is not None:      # shade only the voxels that made it to the screen
        P, Nw, alb, ao, emit, spec, gloss, litflag, otop = (a[vis] for a in (P, Nw, alb, ao, emit, spec, gloss, litflag, otop))
    T = len(P)
    th = math.radians(cam.yaw)
    el = math.radians(cam.elev)
    Lc = _norm(np.array(scene.key_dir, f4))
    if scene.key_frame == 'camera':
        lx_, ly_ = _rot(float(Lc[0]), float(Lc[1]), -th)
        Lw = np.array([lx_, ly_, Lc[2]], f4)
    else:
        Lw = Lc
    vx, vy = _rot(0.0, math.cos(el), -th)
    Vw = np.array([vx, vy, math.sin(el)], f4)
    Hk = _norm(Lw + Vw)
    key = np.array(scene.key_rgb, f4) * scene.key_power
    sky = np.array(scene.sky_rgb, f4); grd = np.array(scene.ground_rgb, f4)
    out = np.zeros((T, 2, 3), f4)
    glow = np.zeros((T, 2, 3), f4)
    up = np.array([0, 0, 1], f4)
    fm = scene.face_mix
    for face in (0, 1):
        if face == 1:
            N = _norm(Nw * (1 - fm) + up * fm)
        else:
            N = _norm(Nw * np.array([1, 1, 1 - fm * 0.8], f4))
        Pp = P + N * 0.9
        s = shadow.lit(Pp) if shadow is not None else np.ones(T, f4)
        ndl = np.maximum(0.0, N @ Lw)
        if scene.bands:
            q = np.floor(ndl * scene.bands + 0.5) / scene.bands
            ndl = ndl * 0.35 + q * 0.65
        hemi = (N[:, 2] * 0.5 + 0.5)[:, None]
        amb = (grd * (1 - hemi) + sky * hemi) * scene.ambient * ao[:, None]
        light = amb + key * (ndl * s)[:, None]
        sp = key * (spec * np.power(np.maximum(0.0, N @ Hk), gloss) * s)[:, None]
        for L in lights:
            lp = np.array(L['pos'], f4)
            dv = lp - Pp
            dist = np.linalg.norm(dv, axis=1)
            att = np.maximum(0.0, 1 - (dist / L['radius']) ** 2) ** 2 * L['power']
            nl = np.maximum(0.0, np.einsum('ij,ij->i', N, dv) / np.maximum(dist, 1e-3)) * 0.8 + 0.2
            c = np.array(L['rgb'], f4)
            light += c * (att * nl * (0.45 + 0.55 * ao))[:, None]
            hv = _norm(dv / np.maximum(dist, 1e-3)[:, None] + Vw)
            sp += c * (spec * np.power(np.maximum(0.0, np.einsum('ij,ij->i', N, hv)), gloss) * att)[:, None]
        g = alb * (emit * scene.emit_gain)[:, None]
        gb = alb * (np.maximum(emit - 0.5, 0) * scene.emit_gain)[:, None]      # only strong emitters bloom
        if mode == 'albedo':
            col = alb.copy()
        elif mode == 'normal':
            col = srgb2lin(N * 0.5 + 0.5)
        elif mode == 'ao':
            col = srgb2lin(np.repeat(ao[:, None], 3, 1))
        elif mode == 'light':
            col = (light + sp) * 0.5 + g
        else:
            col = alb * light + sp + g
            col = np.where(litflag[:, None], col, alb)
        out[:, face] = col
        glow[:, face] = gb if mode in ('lit', 'light') else 0
    out[:, 1] = np.where(otop[:, None], out[:, 1], out[:, 0])
    if vis is not None:
        full = np.zeros((T_full, 2, 3), f4); fullg = np.zeros((T_full, 2, 3), f4)
        full[vis] = out; fullg[vis] = glow
        out, glow = full, fullg
    out[0] = 0; glow[0] = 0
    return out.reshape(-1, 3), glow.reshape(-1, 3), Lw, lights


def _background(scene, W, H):
    bg = scene.bg
    yy, xx = np.mgrid[0:H, 0:W].astype(f4)
    cxn, cyn = bg.get('center', (0.5, 0.46))
    d = np.sqrt(((xx / W - cxn) * 1.0) ** 2 + ((yy / H - cyn) * (H / W) * 1.5) ** 2) / 0.62
    t = np.clip(d, 0, 1)[..., None] ** 1.25
    inner = srgb2lin(np.array(bg['inner'], f4) / 255); outer = srgb2lin(np.array(bg['outer'], f4) / 255)
    col = inner * (1 - t) + outer * t
    if bg.get('dots', True):
        dots = (((xx.astype(int) % 4) == 1) & ((yy.astype(int) % 4) == 1))[..., None]
        col = col * np.where(dots, 0.72, 1.0)
    return col.astype(f4)


def render(scene, cam, ss=3, mode='lit', shadows=True, reflections=True, pixel=0, transparent=False):
    """Render to an 8-bit RGB (or RGBA if transparent) image.

    mode: 'lit' | 'albedo' (unlit) | 'normal' | 'ao' | 'light' (lighting on grey)
    pixel: >0 renders the classic un-antialiased stack at 1/pixel resolution and scales it
           up with nearest neighbour (one screen step per layer, hard rotated texels)."""
    W, H = cam.size
    if pixel:
        small = Camera(cam.yaw, cam.elev, cam.scale / pixel, cam.look, (W // pixel, H // pixel))
        img = render(scene, small, ss=1, mode=mode, shadows=shadows, reflections=reflections, transparent=transparent)
        return np.repeat(np.repeat(img, pixel, 0), pixel, 1)
    scene._prepare()
    S = cam.scale * ss
    Ws, Hs = W * ss, H * ss
    cx, cy = Ws / 2.0, Hs / 2.0
    th = math.radians(cam.yaw)
    se, ce = math.sin(math.radians(cam.elev)), math.cos(math.radians(cam.elev))
    lx, ly, lz = cam.look
    idb, zb = _gbuffer(scene, cam, S, Ws, Hs, cx, cy)
    unlit = mode in ('albedo', 'normal', 'ao')
    floor = scene.floor
    extent = (floor.get('radius', 60) + 24) if floor else 96
    Lc = _norm(np.array(scene.key_dir, f4))
    if scene.key_frame == 'camera':
        a_, b_ = _rot(float(Lc[0]), float(Lc[1]), -th)
        Lw0 = np.array([a_, b_, Lc[2]], f4)
    else:
        Lw0 = Lc
    extent = getattr(scene, 'extent', None) or extent
    shadow = _Shadow(scene, Lw0, scene.soft if shadows else 1, extent) if not unlit else None
    floor = scene.floor
    mark = np.zeros(scene._total + 1, bool)
    mark[idb >> 1] = True
    idm = zm = None
    if floor is not None and reflections and mode == 'lit' and float(floor.get('gloss', 0.34)) > 0:
        fz_ = float(floor.get('z', 0.0))
        hw, hh = (Ws + 1) // 2, (Hs + 1) // 2
        for o in scene.objs:
            o.pos[2] -= fz_
        mcam = Camera(cam.yaw, cam.elev, cam.scale, (lx, ly, lz - fz_), (hw, hh))
        idm, zm = _gbuffer(scene, mcam, S / 2.0, hw, hh, cx / 2.0, cy / 2.0, mirror=True)
        for o in scene.objs:
            o.pos[2] += fz_
        mark[idm >> 1] = True
    mark[0] = False
    table, glowt, Lw, lights = _shade(scene, cam, shadow if shadows else None, mode, vis=np.flatnonzero(mark))
    col = table[idb]
    glow = glowt[idb]
    cov = (idb > 0)
    alpha = cov.astype(f4)

    if floor is not None:
        fz = float(floor.get('z', 0.0))
        kind = floor.get('kind', 'dais')
        fcx, fcy = floor.get('center', (0.0, 0.0))
        R = float(floor.get('radius', 60))
        base = srgb2lin(np.array(floor.get('rgb', (34, 40, 58)), f4) / 255)
        ring = srgb2lin(np.array(floor.get('ring_rgb', (52, 60, 84)), f4) / 255)
        rim = srgb2lin(np.array(floor.get('rim_rgb', (214, 160, 84)), f4) / 255)
        rg = float(floor.get('rim_glow', 0.3))
        gl0 = float(floor.get('gloss', 0.34))
        # world position on the floor plane for every pixel no stack covers
        ys_, xs_ = np.nonzero(~cov)
        xr = ((xs_ + 0.5) - cx) / S
        dy_ = ((ys_ + 0.5) - cy) / S
        yr = (dy_ + (fz - lz) * ce) / se
        c_, s_ = math.cos(-th), math.sin(-th)
        wx = (xr * c_ - yr * s_ + lx).astype(f4)
        wy = (xr * s_ + yr * c_ + ly).astype(f4)
        rr = np.sqrt((wx - fcx) ** 2 + (wy - fcy) ** 2)
        top = (rr <= R) if kind == 'dais' else np.ones(len(rr), bool)
        ti = np.flatnonzero(top)
        ty, tx, twx, twy = ys_[ti], xs_[ti], wx[ti], wy[ti]
        t = rr[ti] / R
        falb = np.broadcast_to(base, (len(ti), 3)).copy()
        gloss_m = np.full(len(ti), gl0, f4)
        edge = None
        if kind == 'dais':
            ang = np.arctan2(twy - fcy, twx - fcx)
            band = (t > 0.80) & (t <= 0.925)
            ticks = band & (np.mod(ang, math.pi / 18) < math.pi / 36) & (t > 0.815) & (t <= 0.91)
            falb[band] = ring * 0.55
            falb[ticks] = ring * 1.05
            groove = ((t > 0.788) & (t <= 0.80)) | ((t > 0.925) & (t <= 0.937)) | ((t > 0.42) & (t <= 0.427))
            falb[groove] = base * 0.4
            edge = t > 0.972
            falb[edge] = rim
            gloss_m[band | groove] = gl0 * 0.35
            gloss_m[edge] = 0.0
            falb *= (1.0 - 0.25 * np.clip(t, 0, 1) ** 3)[:, None]
        else:
            tile = floor.get('tile', 0)
            if tile:
                chk = ((np.floor(twx / tile) + np.floor(twy / tile)) % 2) < 1
                falb[chk] *= 0.86
        if unlit:
            if mode == 'albedo':
                fcol = falb
            elif mode == 'ao':
                fcol = np.ones_like(falb)
            else:
                fcol = np.broadcast_to(srgb2lin(np.array([0.5, 0.5, 1.0], f4)), falb.shape).copy()
            fglow = np.zeros_like(falb)
        else:
            lm = shadow.lightmap(scene, lights, Lw, fz, use_shadow=shadows)
            light = np.stack([shadow.sample(lm[..., c], twx, twy) for c in range(3)], 1)
            fcol = falb * light if mode == 'lit' else light * 0.5
            fglow = np.zeros_like(falb)
            if edge is not None:
                fglow[edge] = rim * rg
                fcol[edge] += rim * rg
            # reflection: the same stacks drawn again, downward
            if idm is not None:
                fade = np.where(idm > 0, 1.0 / (1.0 + np.maximum(0.0, -zm) / 6.0), 0.0).astype(f4)
                rcol = box_blur(table[idm] * fade[..., None], max(1, int(round(S * 0.2))))   # ~0.4 voxel soft
                fcol += rcol[ty // 2, tx // 2] * gloss_m[:, None]
        col[ty, tx] = fcol
        glow[ty, tx] = fglow
        alpha[ty, tx] = 1.0
        # side wall of the dais
        if kind == 'dais':
            Tk = float(floor.get('thickness', 4.0))
            ni = np.flatnonzero(~top)
            fxr, fyr = _rot(fcx - lx, fcy - ly, th)
            xc = xr[ni] - fxr
            inside = np.abs(xc) < R
            yw = fyr + np.sqrt(np.maximum(R * R - xc * xc, 0))
            zz = (yw * se - dy_[ni]) / ce + lz
            side = inside & (zz < fz) & (zz >= fz - Tk)
            si = ni[side]
            if len(si):
                nxr = xc[side] / R
                nyr = np.sqrt(np.maximum(1 - nxr * nxr, 0))
                depth = (fz - zz[side]) / Tk
                band_ = (depth < 0.34)[:, None]
                if unlit:
                    scol = np.where(band_, rim, base * 0.55) if mode == 'albedo' else np.full((len(si), 3), 0.5, f4)
                    sg = np.zeros((len(si), 3), f4)
                else:
                    Lr = np.array([*_rot(float(Lw[0]), float(Lw[1]), th), float(Lw[2])], f4)
                    ndl = np.maximum(0.0, nxr * Lr[0] + nyr * Lr[1])
                    wall = np.where(band_, rim, base * 0.5)
                    scol = wall * (np.array(scene.sky_rgb, f4) * scene.ambient * 0.6
                                   + np.array(scene.key_rgb, f4) * scene.key_power * ndl[:, None])
                    sg = np.where(band_, rim * rg, 0).astype(f4)
                    scol = scol + sg
                col[ys_[si], xs_[si]] = scol
                glow[ys_[si], xs_[si]] = sg
                alpha[ys_[si], xs_[si]] = 1.0

    # ---- resolve: box filter = anti-aliasing ------------------------------------------
    col = downsample(col * alpha[..., None], ss)
    a = downsample(alpha, ss)
    glow = downsample(glow, ss)
    if transparent:
        rgb = np.where(a[..., None] > 1e-4, col / np.maximum(a[..., None], 1e-4), 0)
        rgb = _tonemap(rgb * scene.exposure)
        return np.dstack([(lin2srgb(rgb) * 255 + 0.5).astype(np.uint8), (a * 255 + 0.5).astype(np.uint8)])
    bg = _background(scene, W, H)
    img = col + bg * (1 - a[..., None])
    if scene.bloom > 0 and mode in ('lit', 'light') and glow.max() > 0:
        g4 = downsample(glow[:H - H % 4, :W - W % 4], 4)
        b1 = gauss_blur(g4, 3)
        b2 = gauss_blur(g4, 10)
        b = b1 * 0.5 + b2 * 0.45
        b = np.asarray(Image.fromarray((np.clip(b / 8.0, 0, 1) * 65535).astype(np.uint16)[..., 0]).resize((W, H), Image.BILINEAR)) if False else _up(b, W, H)
        img = img + b * scene.bloom
    img = _tonemap(img * scene.exposure)
    return (lin2srgb(img) * 255 + 0.5).astype(np.uint8)


def _up(b, W, H):
    out = np.zeros((H, W, 3), f4)
    for c in range(3):
        out[..., c] = np.asarray(Image.fromarray(b[..., c].astype(f4), mode='F').resize((W, H), Image.BILINEAR))
    return out


def _tonemap(c):
    # gentle filmic shoulder: linear in the mids, soft roll-off for lamps and highlights
    wp = 3.2
    return c * (1 + c / (wp * wp)) / (1 + c)  * 1.42


def project(cam, p, ss=1):
    """World point -> final-resolution screen (x, y)."""
    W, H = cam.size
    th = math.radians(cam.yaw)
    se, ce = math.sin(math.radians(cam.elev)), math.cos(math.radians(cam.elev))
    lx, ly, lz = cam.look
    xr, yr = _rot(p[0] - lx, p[1] - ly, th)
    return W / 2 + cam.scale * xr, H / 2 + cam.scale * (yr * se - (p[2] - lz) * ce)
