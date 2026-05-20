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
        "Your memory fades.",
        "Marks fade behind '?' after 6 moves on the board. Recent moves stay visible; older ones become a memory test. Reveal at game end.",
        "blind",
    ),
    BossDef(
        "Double Cross",
        "Every line counts for you.",
        "Every line on the board this round — yours and the opponent's — adds to your ink instead of subtracting.",
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
        "You place every mark on the board — both X and O. Maximise your net score (X lines minus O lines).",
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