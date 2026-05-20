from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config.bosses import BossDef


@dataclass
class Player:
    tokens: int = 0
    score: int = 0
    deck: list[str] = field(default_factory=list)
    hand: list[str] = field(default_factory=list)
    upgrades: dict[str, int] = field(default_factory=dict)
    # current game state
    cells_played: list[tuple[int, int]] = field(default_factory=list)
    placed_on_turn: int = 0
    can_play_card: bool = True
    # cards bought from the shop that persist across games and re-apply
    # their buff every time start_game runs. One-shot action cards are not
    # added here; only `CardDef.persistent` cards are.
    passive_cards: list[str] = field(default_factory=list)
    # cells placed by the "Blind Shot" card; if any of these cells end up
    # in a completed X line, that line's ink is doubled.
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
    # uses these. main.py overrides these to gameplay-tuned values during
    # the starter-card screen.
    score_targets: list[int] = field(default_factory=lambda: [6, 12, 20])
    # Per-boss ante targets — failing the boss ante ends the run. Tuned so
    # that 1-2 X lines + a couple of buff stacks comfortably hits the
    # level's ante: base ink ranges roughly 3..10 (lvl1), 5..25 (lvl2),
    # 7..50 (lvl3) before multipliers.
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
    # Per-game scratch state, reset in start_game.
    draws_this_game: int = 0
    score_this_game: int = 0
    skip_opponent_moves: int = 0
    # Last evaluated score breakdown — for the UI to show "ink × mult".
    last_ink: int = 0
    last_mult: float = 1.0
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
        # Per-level counters reset so the next level scores from zero.
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
        self.player.hand = []
        self.player.cells_played = []
        self.player.placed_on_turn = 0
        self.player.can_play_card = True
        self.draw_multiplier = 1.0
        # passive_cards persist across levels — they're the player's build.
