"""Meta-progression persistence: save/load run results and card unlocks."""
import json
import os

SAVE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "crossed_out_save.json",
)

# (win_threshold, card_name) — card unlocks at lifetime win count
_WIN_UNLOCKS: list[tuple[int, str]] = [
    (3, "Double Strike"),
    (5, "O Flipper"),
    (8, "Ghost Board"),
]


def load_progression() -> dict:
    """Return the persisted progression dict, or {} if no save exists."""
    if not os.path.exists(SAVE_PATH):
        return {}
    try:
        with open(SAVE_PATH, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    with open(SAVE_PATH, "w") as f:
        json.dump(data, f, indent=4)


def save_progression(
    *,
    won: bool,
    tokens_earned: int,
    levels_reached: int,
    cards_unlocked: list[str],
) -> dict:
    """Record a finished run and return the merged save data.

    tokens_earned are only banked when the run is won.
    cards_unlocked are merged with prior unlocks and any new threshold-based unlocks.
    """
    existing = load_progression()

    total_runs = existing.get("total_runs", -1) + 1
    wins = existing.get("wins", 0) + (1 if won else 0)
    tokens_banked = tokens_earned if won else 0

    merged_unlocks: list[str] = list(existing.get("cards_unlocked", []))
    for card in cards_unlocked:
        if card not in merged_unlocks:
            merged_unlocks.append(card)
    for threshold, card in _WIN_UNLOCKS:
        if wins >= threshold and card not in merged_unlocks:
            merged_unlocks.append(card)

    data = {
        "won_run": won,
        "tokens_banked": tokens_banked,
        "levels_reached": levels_reached,
        "total_runs": total_runs,
        "wins": wins,
        "cards_unlocked": merged_unlocks,
    }
    _write(data)
    return data


def get_unlocked_cards() -> list[str]:
    """Return the list of currently unlocked cards."""
    return load_progression().get("cards_unlocked", [])
