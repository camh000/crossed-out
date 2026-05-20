from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config.bosses import BossDef


@dataclass
class Player:
    tokens: int = 0
    score: int = 0
    # Stack counters for active passive effects (point_mult, diagonal_power,
    # token_bonus, skip_opponent, sacrifice_charges, free_rerolls,
    # shop_offer_extra, ...). Repopulated each game by
    # `CardSystem.apply_passive_buffs`.
    upgrades: dict[str, int] = field(default_factory=dict)
    # Cells the player has placed (or had placed by triggers) this game.
    # Used by Sacrifice to undo, and by triggers that need to mirror /
    # explode around the most recent move.
    cells_played: list[tuple[int, int]] = field(default_factory=list)
    # The owned jokers — every entry is a CardDef.name. Order is purchase
    # order; duplicates allowed (the stack count comes from
    # passive_cards.count(name)).
    passive_cards: list[str] = field(default_factory=list)
    # Marks placed by the Blind Shot joker this game. A completed X line
    # containing any of these gets double ink.
    blind_shot_marks: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class RunState:
    level: int = 1
    grid_size: int = 3
    games_in_level: int = 0
    games_per_level: int = 2
    total_score: int = 0
    score_this_level: int = 0
    # Per-level cumulative ink targets — the run-end win check on level 3
    # uses these.
    score_targets: list[int] = field(default_factory=lambda: [6, 12, 20])
    # Per-boss ante targets — failing the boss ante ends the run.
    ante_targets: list[int] = field(default_factory=lambda: [8, 30, 100])
    current_target: int = 0
    ante_target: int = 0
    is_boss: bool = False
    boss_index: int = 0
    shop_phase: bool = False
    run_complete: bool = False
    won_run: bool = False
    current_boss: Optional["BossDef"] = None
    current_boss_setup: Optional[str] = None
    game_result: str | None = None
    draw_multiplier: float = field(default_factory=lambda: 1.0)
    # Lives system — start with 3, lose one on a game loss or a second
    # draw within the same game. 0 = run failed immediately.
    lives: int = 3
    max_lives: int = 3
    # Phoenix joker: once per run, when you would lose the run, restore
    # 1 life instead. Flag tracks "have we already burnt the revival?".
    phoenix_used: bool = False
    # Cap on owned jokers. Shop refuses to sell more once reached.
    joker_cap: int = 5
    # Per-game scratch state, reset in start_game.
    draws_this_game: int = 0
    score_this_game: int = 0
    # Last evaluated score breakdown — for the UI to show "ink × mult".
    # `last_total` is THIS evaluation's contribution (not cumulative);
    # the score count-up animation interpolates 0 → last_total.
    # `last_line_contributions` is a list of per-line dicts produced by
    # CardSystem.line_contributions — the result panel paints labels at
    # each line's midpoint to show where the ink came from.
    last_ink: int = 0
    last_mult: float = 1.0
    last_total: int = 0
    last_line_contributions: list = field(default_factory=list)
    player: Player = field(default_factory=Player)

    def get_grid_size(self) -> int:
        return [3, 5, 7][min(self.level - 1, 2)]

    def get_target(self) -> int:
        return self.score_targets[min(self.level - 1, 2)]

    def get_ante_target(self) -> int:
        return self.ante_targets[min(self.level - 1, 2)]

    def get_multiplier(self) -> int:
        return [1, 2, 3][min(self.level - 1, 2)]

    def next_level(self) -> bool:
        # Decide pass/fail BEFORE advancing — get_target() depends on
        # self.level, and we want to score the level we just finished, not
        # the one we're about to enter.
        completed_target = self.get_target()
        passed = self.score_this_level >= completed_target
        self.level += 1
        self.games_in_level = 0
        self.is_boss = False
        self.current_boss = None
        self.shop_phase = True
        self.score_this_level = 0
        if self.level > 3:
            self.run_complete = True
            self.won_run = passed
            return False
        return True

    def reset_level(self):
        self.games_in_level = 0
        self.is_boss = False
        self.shop_phase = False
        self.score_this_level = 0
        self.player.cells_played = []
        self.draw_multiplier = 1.0
        # passive_cards persist across levels — they're the player's build.
