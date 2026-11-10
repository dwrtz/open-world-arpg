"""Key poses for the shared explorer skeleton.

Values are (x, y, z) degrees in armature space. Y is the side-view swing
axis: positive turns a limb clockwise as the camera sees it, so a hanging arm
swings forward with negative Y and the torso leans forward with positive Y.
X spreads limbs sideways (+X moves a left limb out, -X a right limb).
"""

IDLE = {
    "spine": (0, 3, 0),
    "chest": (0, 2, 0),
    "neck": (0, -2, 0),
    "head": (0, -3, 0),
    "upper_arm.R": (-6, -14, 0),
    "forearm.R": (0, -22, 0),
    "hand.R": (0, 52, 0),
    "upper_arm.L": (7, 6, 0),
    "forearm.L": (0, -14, 0),
    "thigh.L": (4, -8, 0),
    "shin.L": (0, 6, 0),
    "thigh.R": (-4, 6, 0),
    "shin.R": (0, 4, 0),
}

IDLE_LANTERN = dict(
    IDLE,
    **{
        "upper_arm.L": (6, -24, 0),
        "forearm.L": (0, -62, 0),
        "hand.L": (0, 82, 0),
    },
)

RUN = {
    "hips": (0, 8, 0),
    "spine": (0, 6, 0),
    "chest": (0, 4, 0),
    "head": (0, -12, 0),
    "upper_arm.R": (-6, 40, 0),
    "forearm.R": (0, -70, 0),
    "hand.R": (0, 40, 0),
    "upper_arm.L": (6, -45, 0),
    "forearm.L": (0, -60, 0),
    "thigh.L": (0, -58, 0),
    "shin.L": (0, 62, 0),
    "thigh.R": (0, 30, 0),
    "shin.R": (0, 70, 0),
    "_offset": (0, 0, 0.04),
}

MINE_WINDUP = {
    "hips": (0, -4, 0),
    "spine": (0, -8, 0),
    "chest": (0, -10, 0),
    "head": (0, 12, 0),
    "upper_arm.R": (-8, -195, 0),
    "forearm.R": (0, 12, 0),
    "hand.R": (0, 38, 0),
    "upper_arm.L": (6, -50, 0),
    "forearm.L": (0, -40, 0),
    "thigh.L": (3, -26, 0),
    "shin.L": (0, 22, 0),
    "thigh.R": (-3, 20, 0),
    "shin.R": (0, 10, 0),
}

MINE_STRIKE = {
    "hips": (0, 10, 0),
    "spine": (0, 12, 0),
    "chest": (0, 8, 0),
    "head": (0, -18, 0),
    "upper_arm.R": (-4, -82, 0),
    "forearm.R": (0, -18, 0),
    "hand.R": (0, 8, 0),
    "upper_arm.L": (6, 28, 0),
    "forearm.L": (0, -50, 0),
    "thigh.L": (3, -34, 0),
    "shin.L": (0, 30, 0),
    "thigh.R": (-3, 24, 0),
    "shin.R": (0, 14, 0),
}

SLASH = {
    "hips": (0, 8, 0),
    "spine": (0, 10, 0),
    "chest": (0, 6, 0),
    "head": (0, -14, 0),
    "upper_arm.R": (-10, -95, 0),
    "forearm.R": (0, -5, 0),
    "hand.R": (0, 50, 0),
    "upper_arm.L": (10, 30, 0),
    "forearm.L": (0, -45, 0),
    "hand.L": (0, 20, 0),
    "thigh.L": (4, -48, 0),
    "shin.L": (0, 40, 0),
    "thigh.R": (-4, 34, 0),
    "shin.R": (0, 12, 0),
}

HAMMER_RAISE = {
    "hips": (0, -2, 0),
    "spine": (0, -6, 0),
    "chest": (0, -8, 0),
    "head": (0, 8, 0),
    "upper_arm.R": (-12, -172, 0),
    "forearm.R": (0, -12, 0),
    "hand.R": (0, 40, 0),
    "upper_arm.L": (12, -40, 0),
    "forearm.L": (0, -50, 0),
    "thigh.L": (5, -24, 0),
    "shin.L": (0, 18, 0),
    "thigh.R": (-5, 18, 0),
    "shin.R": (0, 8, 0),
}

GUARD = {
    "hips": (0, 4, 0),
    "spine": (0, 4, 0),
    "chest": (0, 2, 0),
    "head": (0, -6, 0),
    "upper_arm.R": (-8, -40, 0),
    "forearm.R": (0, -60, 0),
    "hand.R": (0, 10, 0),
    "upper_arm.L": (8, -20, 0),
    "forearm.L": (0, -60, 0),
    "thigh.L": (5, -22, 0),
    "shin.L": (0, 20, 0),
    "thigh.R": (-5, 18, 0),
    "shin.R": (0, 12, 0),
}

POSES = dict(
    idle=IDLE,
    idle_lantern=IDLE_LANTERN,
    run=RUN,
    mine_windup=MINE_WINDUP,
    mine_strike=MINE_STRIKE,
    slash=SLASH,
    hammer_raise=HAMMER_RAISE,
    guard=GUARD,
)
