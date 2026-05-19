from dataclasses import dataclass, field
from typing import Literal

CARD_TYPE = Literal["action", "buff", "bonus", "power"]


@dataclass
class CardDef:
    name: str
    cost: int
    desc: str
    card_type: CARD_TYPE
    rarity: float = 1.0


ALL_CARDS: list[CardDef] = [
    CardDef("Double Strike", 3, "Place two X this turn on chosen row/col", "action"),
    CardDef("Diagonal Power", 4, "Diagonal lines score 2x this game", "buff"),
    CardDef("O Flipper", 2, "Before game: flip 1 O to X", "action"),
    CardDef("Cell Lock", 3, "Choose 1 cell opponent can't place", "action"),
    CardDef("Reroll", 2, "Shuffle 1 card back into deck, draw new", "action"),
    CardDef("Point Multiplier", 5, "Each line scored counts as +1 bonus", "buff"),
    CardDef("Token Bonus", 3, "After game: +3 tokens earned", "bonus"),
    CardDef("Blind Shot", 4, "Place X blind; if completes, double points", "action", 1.5),
    CardDef("Board Control", 5, "Minimum 50% max possible score this game", "buff", 1.3),
    CardDef("Card Draw", 2, "Draw 2 cards this turn", "action"),
    CardDef("Sacrifice", -1, "Remove X to block line; opponent loses turn", "defensive"),
    CardDef("Wildcard", 4, "Lines with exactly 1 O count as your line", "buff"),
    CardDef("Overload", 3, "Destroy adjacent opponent O's after X placed", "action"),
    CardDef("Ghost Board", 5, "3 hidden walls; revealed after first game", "strategy", 1.4),
    CardDef("Final Count", 6, "Boss game: lines score as length x 2", "power", 1.6),
    CardDef("Quick Draw", 1, "Skip opponent's next move", "action"),
    CardDef("Deep Grid", 3, "Gain +1 token per line this game", "bonus"),
    CardDef("Fortress", 4, "One random cell locked as wall forever", "action"),
    CardDef("Chain Reaction", 5, "Each line clears and deals 1 X damage to adjacent", "buff", 1.5),
    CardDef("Ricochet", 3, "X placed on edge bounces to opposite edge", "action"),
]


def get_by_name(name: str) -> CardDef | None:
    for c in ALL_CARDS:
        if c.name == name:
            return c
    return None


def pick_random(count: int = 3) -> list[str]:
    import random
    return [c.name for c in random.sample(ALL_CARDS, min(count, len(ALL_CARDS)))]