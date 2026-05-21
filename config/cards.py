from dataclasses import dataclass, field
from typing import Literal

CARD_TYPE = Literal["action", "buff", "bonus", "power", "defensive", "strategy"]


@dataclass
class CardDef:
    """A joker definition.

    `triggers` lists the lifecycle hooks the joker reacts to. The
    actual effect is dispatched by card name in
    `systems/cardsystem.py`. Pure scoring buffs (Point Multiplier,
    Diagonal Power, Wildcard, Deep Grid, Board Control, Final Count,
    Token Bonus) have an empty `triggers` tuple — the scoring loop
    reads their stack from `Player.upgrades` directly, so no hook
    fire is needed.
    """

    name: str
    cost: int
    desc: str
    card_type: CARD_TYPE
    rarity: float = 1.0
    triggers: tuple[str, ...] = ()


ALL_CARDS: list[CardDef] = [
    # --- Pure scoring buffs (read at score time via Player.upgrades) -----
    CardDef("Point Multiplier", 5, "+3 ink per X line (per copy)", "buff"),
    CardDef("Diagonal Power", 4, "+0.5x mult on diagonal X lines (per copy)", "buff"),
    CardDef("Wildcard", 4, "Lines with exactly one O score as your line (per copy)", "buff"),
    CardDef("Deep Grid", 3, "+1 ink per X line (per copy)", "bonus"),
    CardDef("Board Control", 5, "Floor: at least size*size ink (per copy)", "buff", 1.3),
    CardDef("Final Count", 6, "Boss games: ink x2 (per copy)", "power", 1.6),
    CardDef("Token Bonus", 3, "+3 tokens on every win (per copy)", "bonus"),
    # --- Game-start triggers ---------------------------------------------
    CardDef(
        "Cell Lock", 3,
        "Locks the centre cell each game (per copy: +1 random wall)",
        "action",
        triggers=("on_game_start",),
    ),
    CardDef(
        "Fortress", 4,
        "+1 random wall locked at game start (per copy)",
        "action",
        triggers=("on_game_start",),
    ),
    CardDef(
        "Ghost Board", 5,
        "+3 random walls placed at game start (per copy)",
        "strategy", 1.4,
        triggers=("on_game_start",),
    ),
    CardDef(
        "Blind Shot", 4,
        "Place a free X on a random edge each game; if it's in your winning line, that line's ink doubles",
        "action", 1.5,
        triggers=("on_game_start",),
    ),
    CardDef(
        "Double Strike", 3,
        "Place 1 free X for you at game start (per copy)",
        "action",
        triggers=("on_game_start",),
    ),
    CardDef(
        "Quick Draw", 1,
        "AI skips its first move each game (per copy)",
        "action",
        triggers=("on_game_start",),
    ),
    # --- Per-X triggers --------------------------------------------------
    CardDef(
        "Ricochet", 3,
        "Every X you place on an edge mirrors to the opposite edge",
        "action",
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Overload", 3,
        "Once per game per copy: when you place an X next to O's, destroys them",
        "action",
        triggers=("on_x_placed",),
    ),
    # --- Per-line triggers -----------------------------------------------
    CardDef(
        "Chain Reaction", 5,
        "When you complete an X line, all O's adjacent to that line flip to X",
        "buff", 1.5,
        triggers=("on_line_completed",),
    ),
    # --- Shop triggers (repurposed from hand-era cards) ------------------
    CardDef(
        "Reroll", 2,
        "+1 free shop reroll per visit (per copy)",
        "strategy",
        triggers=("on_shop_open",),
    ),
    CardDef(
        "Card Draw", 2,
        "Shop offers +1 extra card (per copy)",
        "strategy",
        triggers=("on_shop_open",),
    ),
    # --- Defensive save --------------------------------------------------
    CardDef(
        "Sacrifice", 4,
        "Once per game, if you would lose, instead remove your last X and continue (one save per copy)",
        "defensive", 1.4,
        triggers=("on_would_lose_game",),
    ),
    # --- Additional pure scoring buffs (no new triggers) -----------------
    CardDef(
        "Edge Lord", 4,
        "Lines along the outer edge score +50% ink (per copy)",
        "buff",
    ),
    CardDef(
        "Centripetal", 4,
        "Lines through the centre cell score +5 ink (per copy)",
        "buff",
    ),
    CardDef(
        "Long Bow", 5,
        "Lines at the base size score +100% ink on a grown board (per copy)",
        "buff", 1.3,
    ),
    CardDef(
        "First Strike", 3,
        "Your FIRST X line each game scores +20 ink (per copy)",
        "bonus",
    ),
    CardDef(
        "Last Stand", 5,
        "When you have 1 life left, +50% ink (per copy)",
        "power", 1.5,
    ),
    CardDef(
        "Crescendo", 4,
        "Mult +0.2 per X line scored this game (per copy)",
        "buff",
    ),
    CardDef(
        "Magnitude", 4,
        "Mult +1 when the board has grown past 5x5 (per copy)",
        "buff",
    ),
    CardDef(
        "Lethal", 5,
        "Mult +0.5 on boss games (per copy)",
        "power", 1.4,
    ),
    # --- Build-around / set-bonus buffs ----------------------------------
    CardDef(
        "Quartet", 6,
        "If you own 4+ distinct jokers, all X line ink x2",
        "power", 1.6,
    ),
    CardDef(
        "Rich Vein", 4,
        "+10 ink per X line if you own 3+ distinct jokers (per copy)",
        "bonus",
    ),
    CardDef(
        "War Machine", 5,
        "If you destroy 3+ O's this game, double Mult",
        "power", 1.5,
    ),
    CardDef(
        "Pacifist", 3,
        "If you destroy 0 O's this game, +2 tokens on win (per copy)",
        "bonus",
    ),
    # --- On-X-placed triggers --------------------------------------------
    CardDef(
        "Cascade", 5,
        "Placing an X next to two of your X's spawns an extra X on the line's extension",
        "action", 1.4,
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Flame", 3,
        "Once per game per copy: destroys orthogonally adjacent O's when you place an X",
        "action",
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Stutter", 3,
        "Every 3rd X you place is mirrored to the opposite cell",
        "action",
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Magnet", 4,
        "Every X you place pulls the nearest O one cell closer (per copy: pull one more O)",
        "action",
        triggers=("on_x_placed",),
    ),
    # --- On-AI-placed triggers (new hook) --------------------------------
    CardDef(
        "Counter", 3,
        "Your next X line after the AI moves gets +2 ink (per copy)",
        "buff",
        triggers=("on_ai_placed",),
    ),
    CardDef(
        "Vampire", 4,
        "+1 token per O the AI plays this game, paid on win (per copy)",
        "bonus",
        triggers=("on_ai_placed",),
    ),
    CardDef(
        "Interference", 5,
        "Every 4th AI move re-rolls to a random empty cell (per copy reduces the interval)",
        "strategy", 1.4,
        triggers=("on_ai_placed",),
    ),
    # --- Defensive ------------------------------------------------------
    CardDef(
        "Phoenix", 6,
        "Once per run, the first time the run would end, restore 1 life instead",
        "defensive", 1.6,
    ),
    CardDef(
        "Shield", 4,
        "Boss ante target reduced by 20% (per copy, multiplicative)",
        "defensive",
    ),
    CardDef(
        "Patience", 4,
        "Lose a full-board game with no X lines and gain a life instead (per copy)",
        "defensive",
    ),
    # --- Shop / economy --------------------------------------------------
    CardDef(
        "Banker", 4,
        "+1 token per 3 you already hold when the shop opens (per copy)",
        "strategy",
        triggers=("on_shop_open",),
    ),
    CardDef(
        "Wholesaler", 3,
        "Shop card cost -1 (min 1) per copy",
        "strategy",
        triggers=("on_shop_open",),
    ),
    # --- Cursed --------------------------------------------------------
    CardDef(
        "Cursed Coin", 0,
        "Free joker. Drains 1 life every game start. Can't be removed.",
        "strategy", 2.0,
    ),
    # --- Creative drop -------------------------------------------------
    CardDef(
        "Domino", 4,
        "Every X you place also drops an X on the cell directly below it",
        "action",
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Mitosis", 5,
        "When you complete an X line, the line duplicates onto the row below (empty cells only)",
        "buff", 1.5,
        triggers=("on_line_completed",),
    ),
    CardDef(
        "Anti-Matter", 5,
        "After every X you place, any O with 2+ adjacent X's flips to X",
        "buff", 1.4,
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Wormhole", 4,
        "X's placed on the edge teleport to the centre instead (only if centre is empty)",
        "action",
        triggers=("on_x_placed",),
    ),
    CardDef(
        "Echo Chamber", 6,
        "Every completed X line scores twice",
        "power", 1.6,
    ),
    CardDef(
        "Gambit", 3,
        "Lose 5 ink at scoring, but every X line scores +50%",
        "buff", 1.3,
    ),
    CardDef(
        "Doppelganger", 6,
        "At game start, fire one other random owned glyph's game-start handler again",
        "strategy", 1.5,
        triggers=("on_game_start",),
    ),
    CardDef(
        "Last Word", 4,
        "The X line containing your most-recently placed mark gets +25 ink",
        "buff",
    ),
    CardDef(
        "The Editor", 5,
        "At game start, two random O cells are hidden from the AI's perception forever",
        "strategy", 1.4,
        triggers=("on_game_start",),
    ),
    CardDef(
        "Cardinal", 4,
        "Lines along the row or column matching your current level number score +100%",
        "buff",
    ),
]


def get_by_name(name: str) -> CardDef | None:
    for c in ALL_CARDS:
        if c.name == name:
            return c
    return None


def pick_random(count: int = 3) -> list[str]:
    import random
    return [c.name for c in random.sample(ALL_CARDS, min(count, len(ALL_CARDS)))]
