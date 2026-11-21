"""Giant root: a "Roots of Giants" set piece. A thick gnarled root arches out of the
ground and back in; the opening runs along x, so the arch reads from the +y side.

build(seed=4)

The root is a variable-radius tube along a spline with two thinner strands wound round
it (the gnarl), nudged by noise. Bark gets twisted longitudinal grooves, dark seams
where the strands meet the trunk, and a few knots. A side root is snapped off toward the
camera showing pale heartwood, and amber sap bleeds from it with a small warm light.
"""
import math

import numpy as np

from stack.voxel import Vox

DIMS = (44, 24, 36)
CY = 11.0

# centreline control points: x, y, z, radius  (left foot -> apex -> right foot)
SPINE = [
    (6.2, CY + 1.0, -4.0, 5.0),
    (7.0, CY + 0.6, 6.0, 4.7),
    (9.2, CY - 0.4, 16.6, 4.2),
    (13.6, CY - 1.2, 25.4, 3.8),
    (20.6, CY - 0.8, 29.8, 3.5),
    (28.2, CY + 0.6, 27.4, 3.6),
    (33.8, CY + 1.4, 19.0, 4.0),
    (36.8, CY + 1.0, 7.5, 4.5),
    (37.8, CY + 0.4, -4.0, 5.0),
]


def _spline(ctrl, n):
    """Catmull-Rom through the control rows; returns n + 1 samples."""
    P = np.array(ctrl, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    segs = len(P) - 3
    out = []
    for i in range(n + 1):
        u = i / n * segs
        k = min(int(u), segs - 1)
        t = u - k
        p0, p1, p2, p3 = P[k:k + 4]
        out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)


def _frames(pts):
    """Tangent / outward normal / side (about +y) frames along the samples."""
    T = np.gradient(pts[:, :3], axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    B = np.array([0.0, 1.0, 0.0]) - T[:, 1:2] * T
    B /= np.linalg.norm(B, axis=1, keepdims=True)
    N = np.cross(T, B)
    return T, N, B


def _tube(v, pts, frames=None):
    """Distance to a variable-radius tube (negative inside). With frames, also returns
    the position along it (0..1) and the angle round it (0 = outer side of the arch,
    +pi/2 = the +y side, pi = underside)."""
    best = np.full(v.idx.shape, 1e9, np.float32)
    s_at = np.zeros(v.idx.shape, np.float32)
    th = np.zeros(v.idx.shape, np.float32)
    n = len(pts) - 1
    for i in range(n):
        a, b = pts[i], pts[i + 1]
        d = b[:3] - a[:3]
        L2 = float(d @ d) or 1e-6
        t = np.clip(((v.x - a[0]) * d[0] + (v.y - a[1]) * d[1] + (v.z - a[2]) * d[2]) / L2, 0, 1)
        px = v.x - (a[0] + d[0] * t); py = v.y - (a[1] + d[1] * t); pz = v.z - (a[2] + d[2] * t)
        dist = np.sqrt(px * px + py * py + pz * pz) - (a[3] + (b[3] - a[3]) * t)
        m = dist < best
        best = np.where(m, dist, best)
        if frames is not None:
            _, N, B = frames
            s_at = np.where(m, (i + t) / n, s_at)
            ang = np.arctan2(px * B[i][0] + py * B[i][1] + pz * B[i][2],
                             px * N[i][0] + py * N[i][1] + pz * N[i][2])
            th = np.where(m, ang, th)
    return best, s_at, th


def _smin(a, b, k=1.2):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


def _fern(v, base, fronds, rng, length=5.0, start=0.0, arc=2 * math.pi):
    """A tuft of arching fronds: dark at the root, lighter at the drooping tips."""
    for k in range(fronds):
        az = start + arc * (k + rng.uniform(-0.2, 0.2)) / fronds
        L = length * rng.uniform(0.85, 1.15)
        d = np.array([math.cos(az), math.sin(az), 0.0])
        b = np.array(base, float)
        mid = b + d * L * 0.45 + (0, 0, L * 0.8)
        tip = b + d * L + (0, 0, L * 0.45)
        v.add(v.m_capsule(b, mid, 0.8, 0.75), 'fern', shade=-1)
        m2 = v.m_capsule(mid, tip, 0.75, 0.5) & ~v.occ
        v.fill(m2, 'fern', shade=0)
        v.paint(m2 & v.m_ellipsoid(tip, (1.3, 1.3, 1.3)), mat='leaf', shade=1)


def build(seed=4):
    rng = np.random.default_rng(seed)
    v = Vox(*DIMS, name='giant_root')
    v.pivot = (22.0, CY + 1.0)

    # --- the arch: trunk, three wound strands and a few burls --------------------------------
    pts = _spline(SPINE, 48)
    u = np.linspace(0, 1, len(pts))
    pts[:, 3] *= 0.94 + 0.2 * np.sin(u * 17.0 + 1.0) * np.sin(u * 5.0)      # uneven girth
    fr = _frames(pts)
    d_main, s_at, th = _tube(v, pts, fr)
    _, N, B = fr
    d_str = np.full(v.idx.shape, 1e9, np.float32)
    for phase, turns, rr in ((0.6, 1.25, 2.7), (2.7, 1.0, 2.4), (4.6, 1.45, 2.2)):
        phi = phase + turns * 2 * math.pi * u
        c = pts[:, :3] + (N * np.cos(phi)[:, None] + B * np.sin(phi)[:, None]) * (pts[:, 3:4] * 0.8)
        sp = np.hstack([c, (rr * (0.85 + 0.3 * np.sin(u * 9.0 + phase)))[:, None]])
        d2, _, _ = _tube(v, sp)
        d_str = np.minimum(d_str, d2)
    d = _smin(d_main, d_str, 0.8)
    for (bx, by, bz, br) in ((6.2, CY + 3.0, 12.5, 3.8), (25.8, CY + 1.6, 30.6, 3.5), (36.0, CY - 1.0, 15.0, 3.6)):
        burl = np.sqrt((v.x - bx) ** 2 + (v.y - by) ** 2 + (v.z - bz) ** 2) - br
        d = _smin(d, burl, 1.2)
    d = d + (v.noise(6.5, seed) - 0.5) * 1.5 + (v.noise(3.2, seed + 1) - 0.5) * 0.5
    root = d < 0
    v.fill(root, 'bark')

    # --- bark: twisted grooves, strand seams, lit crests ---------------------------------------
    groove = np.cos(5.0 * th + 10.0 * s_at + (v.noise(6, seed + 2) - 0.5) * 1.4)
    on_strand = d_str < d_main
    v.paint(root & ~on_strand & (groove < -0.5), mat='bark_dark', shade=0)
    v.paint(root & ~on_strand & (groove > 0.7), shade=1)
    seam = root & (np.abs(d_main - d_str) < 0.75)
    v.paint(seam, mat='bark_dark', shade=-1)
    v.paint(root & on_strand & (d_str < -1.0) & ~seam, shade=1)        # strand crests
    under = root & (np.cos(th) < -0.55)                                  # the arch's underside
    v.paint(under, add=-1)
    v.paint(root & (v.z < 3), add=-1)

    # --- knots ------------------------------------------------------------------------------
    for (kx, ky, kz, kr) in ((8.0, 16.6, 13.5, 2.3), (30.2, 15.4, 26.0, 2.1), (36.2, 16.4, 12.0, 2.2),
                             (17.5, 5.8, 27.4, 2.0)):
        knot = v.m_ellipsoid((kx, ky, kz), (kr, kr, kr))
        v.fill(knot & ~root, 'bark', shade=0)
        v.paint(knot, mat='bark', shade=0)
        v.paint(knot & ~v.m_ellipsoid((kx, ky, kz), (kr - 0.9,) * 3), mat='bark', shade=1)
        v.paint(v.m_ellipsoid((kx, ky + (0.8 if ky > CY else -0.8), kz), (1.2, 1.4, 1.2)), mat='bark_dark', shade=-1)

    # --- buttress roots running out along the ground ----------------------------------------
    for a, m, b, r0, r1 in (((7.8, 14.0, 7.0), (5.2, 18.2, 3.6), (2.6, 21.0, 0.2), 2.7, 1.4),
                            ((9.4, 14.0, 5.5), (12.2, 18.0, 2.6), (15.0, 21.2, 0.0), 2.4, 1.2),
                            ((6.0, 9.0, 6.0), (4.0, 5.6, 3.0), (2.2, 2.6, 0.2), 2.5, 1.3),
                            ((36.0, 14.6, 7.0), (33.8, 18.4, 3.2), (31.0, 21.4, 0.0), 2.6, 1.3),
                            ((38.4, 14.0, 5.5), (40.2, 17.4, 2.6), (41.6, 20.4, 0.2), 2.4, 1.3),
                            ((37.6, 9.4, 6.0), (39.4, 5.8, 3.0), (41.2, 2.8, 0.2), 2.5, 1.3)):
        rm = (r0 + r1) / 2
        m_ = (v.m_capsule(a, m, r0, rm) | v.m_capsule(m, b, rm, r1)) & ~v.occ
        v.fill(m_, 'bark', shade=0)
        top = m_ & v.m_exposed_top()
        v.paint(top, shade=1)
        v.paint(m_ & (v.z < 1.5), shade=-1)

    # --- the snapped side root: pale heartwood toward the camera -----------------------------
    s0 = np.array([10.2, 13.0, 20.4])
    sd = np.array([-0.5, 0.78, 0.38]); sd /= np.linalg.norm(sd)
    slen = 8.6
    rel = (v.x - s0[0]) * sd[0] + (v.y - s0[1]) * sd[1] + (v.z - s0[2]) * sd[2]
    rx = v.x - (s0[0] + sd[0] * rel); ry = v.y - (s0[1] + sd[1] * rel); rz = v.z - (s0[2] + sd[2] * rel)
    rad = np.sqrt(rx * rx + ry * ry + rz * rz)
    jag = (v.noise(2.6, seed + 3) - 0.5) * 2.6                           # splintered end
    stub = (rad < 3.9 - 0.08 * rel) & (rel > 0) & (rel < slen + jag)
    v.fill(stub & ~root, 'bark', shade=0)
    v.paint(stub & (rad > 2.6) & (rz > 0.8), shade=1)
    v.paint(stub & (rad > 2.6) & (rz < -1.2), shade=-1)
    end = stub & (rel > slen - 2.8) & (rad < 2.7)
    v.paint(end, mat='heartwood', shade=0)
    v.paint(end & (rad < 1.1), shade=-1)                                 # pith
    v.paint(end & (rad > 1.9), shade=1)                                  # pale sapwood ring
    v.paint(stub & (rel > slen - 2.8) & (rad >= 2.7), mat='bark_dark', shade=0)

    # --- amber sap ------------------------------------------------------------------------------
    tip = s0 + sd * (slen - 0.4)
    bark_m = v.is_mat('bark', 'bark_dark')
    skin = v.m_surface()
    front = v.occ.copy(); front[:, :-1, :] &= ~v.occ[:, 1:, :]          # nothing in front of it (+y)
    # bleeding from the lower lip of the break, then a narrow run down the trunk to a fat drop
    v.paint(end & (rz < -1.9) & skin, mat='amber', shade=0)
    for (x0, x1, z0, z1) in ((tip[0] + 1.2, tip[0] + 3.2, 12.0, tip[2] - 2.4),      # under the break
                             (35.0, 37.0, 6.5, 11.0)):                             # weeping knot, far leg
        run = v.m_box((x0, CY, z0), (x1, 30, z1)) & front & bark_m
        v.paint(run, mat='amber', shade=-1)
        zs = v.z[run]
        if zs.size:
            low = run & (v.z < zs.min() + 1.0)
            c = np.array([v.x[low].mean(), v.y[low].mean() + 0.5, zs.min() + 0.2])
            v.fill(v.m_ellipsoid(c, (1.4, 1.3, 1.6)), 'amber', shade=0)
    # a drop hanging under the arch: thin neck, heavy end
    for (hx, hy, z1, ln) in ((21.6, CY + 1.4, 26.4, 4.8),):
        v.fill(v.m_capsule((hx, hy, z1), (hx, hy, z1 - ln), 0.8, 1.3) & ~v.occ, 'amber', shade=0)
        v.paint(v.m_ellipsoid((hx, hy, z1 + 0.6), (1.7, 1.7, 1.2)) & skin & bark_m, mat='amber', shade=-1)
    pool = v.m_ellipsoid((tip[0] + 2.4, tip[1] + 0.6, 0.0), (2.9, 2.2, 1.2))
    v.fill(pool, 'amber', shade=-1)
    v.light((float(tip[0] + 3.0), float(tip[1] + 2.0), float(tip[2] - 8.0)), (1.0, 0.68, 0.28), radius=22, power=0.9)

    # --- hanging rootlets under the arch --------------------------------------------------------
    for (hx, hy, z1, z0) in ((16.4, CY - 0.4, 24.6, 18.6), (26.4, CY + 0.2, 26.4, 20.4)):
        m_ = v.m_capsule((hx, hy, z1), (hx + 0.4, hy + 0.3, z0), 1.0, 0.6) & ~v.occ
        v.fill(m_, 'bark', shade=1)

    # --- earth at the feet, moss, ferns -------------------------------------------------------
    mn = v.noise(5.5, seed + 4)
    for (ex, ey, er) in ((7.0, 12.0, (6.4, 9.4, 3.4)), (37.2, 12.2, (6.0, 9.4, 3.2))):
        earth = v.m_ellipsoid((ex, ey, -0.4 + (mn - 0.5) * 1.6), er) & ~v.occ
        v.fill(earth, 'dirt_dark', shade=0)
    v.paint(v.is_mat('dirt_dark') & (v.z < 1), shade=-1)
    moss = v.m_exposed_top() & v.is_mat('dirt_dark') & (mn > 0.36)
    v.paint(moss, mat='moss', shade=0)
    # moss creeping up the feet and capping the crown of the arch
    feet = v.m_exposed_top(2) & v.is_mat('bark', 'bark_dark') & (v.z < 9) & (mn > 0.52)
    crown = v.m_exposed_top(2) & v.is_mat('bark', 'bark_dark') & (v.z > 20) & (v.noise(7, seed + 5) > 0.5)
    crown &= ~((rad < 5.0) & (rel > 1.0))                               # keep the break clean
    v.paint(feet | crown, mat='moss', shade=0)
    hang = np.zeros_like(crown); hang[:-1] = crown[1:]
    v.paint(hang & v.m_surface() & v.is_mat('bark', 'bark_dark') & (v.y > CY), mat='moss', shade=-1)
    v.paint(v.is_mat('moss') & v.m_exposed_top() & (v.noise(4, seed + 6) > 0.6), mat='moss_light')

    _fern(v, (3.6, 20.6, 0.8), 4, rng, length=5.0, start=1.2)
    _fern(v, (13.4, 21.0, 0.5), 3, rng, length=4.2, start=0.2, arc=math.pi)
    _fern(v, (39.8, 20.2, 0.8), 4, rng, length=5.0, start=0.3)
    _fern(v, (32.6, 3.4, 0.6), 4, rng, length=4.4, start=3.4)
    return v
