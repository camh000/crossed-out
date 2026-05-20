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
]


def get_by_name(name: str) -> CardDef | None:
    for c in ALL_CARDS:
        if c.name == name:
            return c
    return None


def pick_random(count: int = 3) -> list[str]:
    import random
    return [c.name for c in random.sample(ALL_CARDS, min(count, len(ALL_CARDS)))]
