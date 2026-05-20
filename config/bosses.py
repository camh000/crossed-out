from dataclasses import dataclass


@dataclass
class BossDef:
    name: str
    tagline: str
    desc: str
    mechanic: str


BOSS_LIST: list[BossDef] = [
    BossDef(
        "The Blind",
        "You don't see their moves.",
        "Opponent O marks are hidden (showed as '?'). Your own X's stay visible. The board is revealed at game end.",
        "blind",
    ),
    BossDef(
        "Double Cross",
        "Neither side wins easily.",
        "Both player and opponent score. The first to complete any line wins the round.",
        "doublecross",
    ),
    BossDef(
        "Weighted",
        "Not all lines are equal.",
        "Each cell has a point value (1-5). Lines score the sum of values, not just length.",
        "weighted",
    ),
    BossDef(
        "Poison",
        "Tread carefully.",
        "Three cells are randomly poisoned. Placing on a poisoned cell removes your mark next turn. Poison cells are visible.",
        "poison",
    ),
    BossDef(
        "Swap",
        "Positions reverse every three moves.",
        "After every 3 moves, all X and O marks swap positions on the board.",
        "swap",
    ),
    BossDef(
        "Ghost",
        "A wall appears...",
        "One cell per game becomes an invisible wall that blocks lines. Its location is revealed after the first normal game.",
        "ghost_wall",
    ),
    BossDef(
        "Mirror",
        "Play against yourself.",
        "You fill the board for both sides. Lines scored for X and O are both counted. Maximize your net score (X - O).",
        "mirror",
    ),
    BossDef(
        "Time Lord",
        "You have only 5 seconds.",
        "You have 5 seconds per move. If you don't act, the opponent claims a random empty cell for free.",
        "timed",
    ),
]


BOSS_MAP: dict[str, BossDef] = {b.mechanic: b for b in BOSS_LIST}