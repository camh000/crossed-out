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
    # Plague Doctor boss — set of cells you've placed an X on for the
    # FIRST time this game. Lines that contain any of these cells score
    # 0 ink. Cleared in start_game on Plague Doctor games.
    first_placed_cells: set[tuple[int, int]] = field(default_factory=set)
    # Last cell you placed an X on (the player's most-recent move).
    # Read by the Last Word glyph and similar "most-recent" effects.
    last_x_cell: tuple[int, int] | None = None


@dataclass
class RunState:
    level: int = 1
    grid_size: int = 3
    games_in_level: int = 0
    games_per_level: int = 2
    total_score: int = 0
    score_this_level: int = 0
    # Per-level cumulative ink targets — beating these advances the run.
    # 7 entries for the 7-level base run; endless mode extends past the
    # tail via a 1.3x-per-level formula in `get_target`.
    score_targets: list[int] = field(default_factory=lambda: [6, 12, 20, 35, 55, 80, 120])
    # Per-boss ante targets — failing the boss ante ends the run. Same
    # shape as score_targets; endless extension uses 1.4x per level.
    ante_targets: list[int] = field(default_factory=lambda: [8, 30, 100, 200, 400, 700, 1100])
    current_target: int = 0
    ante_target: int = 0
    is_boss: bool = False
    boss_index: int = 0
    # Per-run shuffled order of boss mechanics — populated by
    # RogueliteEngine.start_new_run. Each boss encounter pops the next
    # mechanic from this list so a run sees a varied set of bosses
    # instead of always picking the first entry in BOSS_LIST.
    boss_order: list[str] = field(default_factory=list)
    # Per-run set of glyph names that have appeared in the shop. The
    # shop sampler biases toward unseen glyphs so a run gradually
    # surfaces the whole pool. Reset to empty once every card has been
    # seen at least once.
    seen_shop_offers: set[str] = field(default_factory=set)
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
    # How many levels make up a "complete" base run. Past this the run
    # ends and (on a win) the player can opt into endless mode.
    max_base_level: int = 7
    # When True, next_level never auto-ends — only running out of lives
    # or failing a boss ante stops the run.
    endless_mode: bool = False
    # Has the first-run tutorial overlay been shown? Persisted via
    # save/savesetup.py so it only fires on a fresh save.
    intro_seen: bool = False
    # Streak counter — incremented on a game win, reset on a loss.
    # Read by future glyphs (Streamline-style) that scale with momentum.
    consecutive_wins: int = 0
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

    # Grid sizes per base-run level. Endless extends with +1 row/col
    # every 2 levels past the base — see get_grid_size.
    _GRID_SIZES: tuple[int, ...] = (3, 5, 7, 7, 9, 9, 9)

    def get_grid_size(self) -> int:
        idx = self.level - 1
        if idx < len(self._GRID_SIZES):
            return self._GRID_SIZES[idx]
        # Endless: grow +1 every 2 levels past the base run.
        return self._GRID_SIZES[-1] + (self.level - len(self._GRID_SIZES)) // 2

    def get_target(self) -> int:
        idx = self.level - 1
        if idx < len(self.score_targets):
            return self.score_targets[idx]
        # Endless: 1.3x per level past the table.
        return int(self.score_targets[-1] * (1.3 ** (idx - len(self.score_targets) + 1)))

    def get_ante_target(self) -> int:
        idx = self.level - 1
        if idx < len(self.ante_targets):
            return self.ante_targets[idx]
        # Endless: 1.4x per level past the table.
        return int(self.ante_targets[-1] * (1.4 ** (idx - len(self.ante_targets) + 1)))

    def get_multiplier(self) -> int:
        # Multiplier = level number, all the way up. Simple and scales
        # endlessly.
        return max(1, self.level)

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
        # Endless mode never auto-ends — only zero lives or a failed
        # ante stops the run. The "did they pass the level target" check
        # only matters at the base-run finish line.
        if self.endless_mode:
            return True
        if self.level > self.max_base_level:
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
