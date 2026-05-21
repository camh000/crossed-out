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
        "One random cell is silently turned into a wall — it looks empty but no mark will stick there. Plan around the unseen gap.",
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
    # --- Expanded boss pool ------------------------------------------------
    BossDef(
        "The Tide",
        "Lines reform.",
        "Every X line you complete erases itself one AI move later. You keep the ink but lose the cells.",
        "tide",
    ),
    BossDef(
        "Echo",
        "Every move resounds.",
        "Every time you place an X, the AI gets an extra O placement. Doubled response pressure.",
        "echo",
    ),
    BossDef(
        "Spotlight",
        "Only the lit zone counts.",
        "Only lines entirely inside a roving 3x3 zone score. The zone moves after every move you make.",
        "spotlight",
    ),
    BossDef(
        "Inverse",
        "Centre lines hurt you.",
        "Any X line passing through the centre cell scores NEGATIVE this round. Play to the edges.",
        "inverse",
    ),
    BossDef(
        "Tax Man",
        "Tokens drain.",
        "You lose one token every move you take this round. No board mechanic — just resource bleed.",
        "taxman",
    ),
    BossDef(
        "The Vandal",
        "Marks vanish.",
        "Every third AI move, one random non-edge X cell is erased. Stack X's on the edges or play them in pairs so a strike doesn't break a line.",
        "vandal",
    ),
    BossDef(
        "Twins",
        "Two opponents.",
        "Two AIs play O against you. Each player turn is answered by two O placements.",
        "twins",
    ),
    BossDef(
        "Hourglass",
        "The board shrinks.",
        "Every four AI moves, a random empty cell becomes a permanent wall.",
        "hourglass",
    ),
    BossDef(
        "Quicksand",
        "Marks decay.",
        "Any mark left for 3 moves with no adjacent same-side neighbour is erased.",
        "quicksand",
    ),
    BossDef(
        "Hivemind",
        "The opponent sees ahead.",
        "AI plays at 100% tactical strength — blocks every threat, never misplays.",
        "hivemind",
    ),
    # --- Creative drop ------------------------------------------------------
    BossDef(
        "The Cartographer",
        "The map is alive.",
        "Every six of your moves, two random marks on the board swap positions. Plan lines that survive the reshuffle.",
        "cartographer",
    ),
    BossDef(
        "The Architect",
        "Walls everywhere.",
        "Game starts with a spiral maze of walls inset from the edges. Play down the middle.",
        "architect",
    ),
    BossDef(
        "Plague Doctor",
        "Every line is sickly.",
        "The board glows green and ink runs thin: every X line you score this round counts for HALF ink. Stack heavy buffs to compensate.",
        "plague_doctor",
    ),
    BossDef(
        "Hot Potato",
        "Don't touch the lit cell.",
        "One random cell pulses red each turn. Placing on it costs 5 ink. The lit cell rotates after every move.",
        "hot_potato",
    ),
]


BOSS_MAP: dict[str, BossDef] = {b.mechanic: b for b in BOSS_LIST}