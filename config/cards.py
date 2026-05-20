from dataclasses import dataclass, field
from typing import Literal

CARD_TYPE = Literal["action", "buff", "bonus", "power", "defensive", "strategy"]


@dataclass
class CardDef:
    name: str
    cost: int
    desc: str
    card_type: CARD_TYPE
    rarity: float = 1.0
    # Persistent cards stay in the player's `passive_cards` list and have
    # their buff re-applied every game. One-shot cards (`persistent=False`)
    # do their effect immediately when played and leave the hand.
    persistent: bool = False


ALL_CARDS: list[CardDef] = [
    CardDef("Double Strike", 3, "Place two X this turn on chosen row/col", "action"),
    CardDef("Diagonal Power", 4, "+0.5 mult per copy on diagonal X lines", "buff", persistent=True),
    CardDef("O Flipper", 2, "Before game: flip 1 O to X", "action"),
    CardDef("Cell Lock", 3, "Choose 1 cell opponent can't place", "action"),
    CardDef("Reroll", 2, "Shuffle 1 card back into deck, draw new", "action"),
    CardDef("Point Multiplier", 5, "+3 ink per X line, per copy", "buff", persistent=True),
    CardDef("Token Bonus", 3, "+3 tokens on win, per copy", "bonus", persistent=True),
    CardDef("Blind Shot", 4, "Place X on a random edge; line containing it scores 2x ink", "action", 1.5),
    CardDef("Board Control", 5, "Floor: at least size*size ink, per copy", "buff", 1.3, persistent=True),
    CardDef("Card Draw", 2, "Draw 2 extra cards now", "action"),
    CardDef("Sacrifice", -1, "Remove last X you played", "defensive"),
    CardDef("Wildcard", 4, "Lines with one O count as your line, per copy", "buff", persistent=True),
    CardDef("Overload", 3, "Destroy adjacent opponent O's after X placed", "action"),
    CardDef("Ghost Board", 5, "3 hidden walls; revealed after first game", "strategy", 1.4),
    CardDef("Final Count", 6, "Boss games: ink x2 per copy", "power", 1.6, persistent=True),
    CardDef("Quick Draw", 1, "AI skips its next move (stacks)", "action"),
    CardDef("Deep Grid", 3, "+1 ink per X line, per copy", "bonus", persistent=True),
    CardDef("Fortress", 4, "One random cell locked as wall forever", "action"),
    CardDef("Chain Reaction", 5, "Flip O's adjacent to every X line", "buff", 1.5),
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
