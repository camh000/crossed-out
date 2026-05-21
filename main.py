import asyncio
import pygame
import random
from game.board import Board, PLAYER_X, OPPONENT_O, EMPTY
from game.opponent import OpponentAI
from systems.animator import Animator
from systems.cardsystem import CardSystem
from systems.roguelite import RogueliteEngine
from save.savesetup import save_progression, get_unlocked_cards
from config.constants import (
    SCREEN_W, SCREEN_H, BG_COLOR, TEXT_COLOR, TEXT_SUB,
    ACCENT_GOLD, ACCENT_GREEN, ACCENT_RED, COLOR_X, COLOR_O,
    CARD_W, CARD_H, AI_MOVE_DELAY_MS,
)
from config.cards import pick_random, get_by_name, ALL_CARDS
from config.bosses import BOSS_LIST
from renders.rendering import (
    draw_card, draw_score, draw_tokens,
    draw_centered_text, draw_big_centered_text, draw_centered_multiline_text,
    draw_joker_chip, get_vignette, get_cell_shadow,
)


# Layout constants for the joker row that replaced the old hand-card area.
JOKER_W = CARD_W // 2 + 10           # ~92 px wide
JOKER_H = 90                          # tall enough for a name + stack badge
JOKER_GAP = 10
JOKER_ROW_Y = SCREEN_H - JOKER_H - 24  # 24 px from bottom

# Blind boss: marks placed this many moves ago (or longer) render as "?".
# Tuned so recent tactical context stays visible while older marks turn
# into a memory burden. Scales naturally with grid size — bigger boards
# play out more moves before a line forms, so more marks reach the
# fade threshold at once.
BLIND_FADE_AGE = 6


class GameEngine:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("CROSSED OUT")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        # pygame-ce on pygbag/WASM does a fresh font-file lookup on
        # every pygame.font.SysFont call — and we make dozens per
        # frame. Without caching, the transition + shop screens (which
        # render multiple cards each with cost / name / desc fonts)
        # spike frame time so badly that taps lag for 100+ ms.  Cache
        # font instances globally so each (family, size, bold) combo
        # is only created once.
        if not getattr(pygame.font, "_cx_cache_installed", False):
            _real_sysfont = pygame.font.SysFont
            _font_cache: dict = {}

            def _cached_sysfont(name, size, bold=False, italic=False):
                key = (name, int(size), bool(bold), bool(italic))
                f = _font_cache.get(key)
                if f is None:
                    f = _real_sysfont(name, size, bold, italic)
                    _font_cache[key] = f
                return f

            try:
                pygame.font.SysFont = _cached_sysfont
                pygame.font._cx_cache_installed = True
            except Exception:
                pass  # MagicMock-stubbed font module in tests — no-op.

        self.font = pygame.font.SysFont("sans-serif", 20)
        self.big_font = pygame.font.SysFont("consolas", 56)

        self.engine = RogueliteEngine()
        self.card_system = CardSystem()

        self.state = "menu"
        self.board = Board()
        self.hover_pos = None
        self.starter_cards = []
        self.shop_cards = []
        self.shop_full_flash_until = 0   # millisecond timestamp for "Full" flash

        # countdown state
        self.countdown_start = None

        # result display
        self.showing_result = False

        # transient "grid grew on draw" overlay
        self.draw_message_until = 0
        self.draw_message_cell = None

        # Set by evaluate_and_settle when a game ends the whole run
        # (zero lives or boss ante failure). The click-to-advance handler
        # checks this and routes to finish_run instead of the next game.
        self._pending_run_end = False

        # Animation envelopes — polled by the renderer.
        self.animator = Animator()

        # When set, _tick_ai_move pops this and runs the AI's response
        # to the player's last move. None means no AI move is pending.
        self._ai_move_at: int | None = None

        # Wall-clock anchor for the staged score reveal in the result
        # panel: ink counts up first (0-400 ms), mult pops in
        # (400-600 ms), total counts up last (500-1100 ms). Computed
        # from `pygame.time.get_ticks() - self._result_anim_start`.
        self._result_anim_start: int | None = None

        # Wall-clock anchor for the boss-intro entrance: title pops at
        # 0 ms, name slides in at 150 ms, desc fades at 400 ms.
        self._boss_intro_start: int | None = None

        # Per-boss scratch state. Reset in start_game.
        self._spotlight_anchor: tuple[int, int] | None = None
        self._tide_clear_deadlines: list[tuple[int, list[tuple[int, int]]]] = []

        # Joker inspect modal — when set to a card name, draw() paints a
        # large card view over everything. In the shop state the modal
        # also shows a "Sell" button.
        self._inspecting_joker: str | None = None
        # Boss inspect target — set when the codex's bosses tab is tapped.
        # Mutually exclusive with _inspecting_joker.
        self._inspecting_boss: str | None = None
        # Codex tab — "glyphs" or "bosses".
        self._codex_tab: str = "glyphs"

    def new_run(self):
        self.engine.start_new_run()
        # Fresh board for a fresh run — without this, growth from the
        # previous run would carry over into the new one's first game.
        self.board.reset(self.engine.state.get_grid_size())
        # Starter joker pool — 3 random offers; the click handler in the
        # transition state picks one to seed passive_cards.
        self.starter_cards = pick_random(3)
        self.state = "transition"

    def start_game(self):
        pl = self.engine.state
        pl.games_in_level += 1
        gs = pl.get_grid_size()
        # Growth carries across both games AND levels. The line-length
        # target advances with the level (3 → 5 → 7), and the bounding
        # box expands rightward/downward if the player hadn't already
        # grown past the new base size. The board never shrinks.
        self.board.advance_to_size(gs)
        pl.current_target = pl.get_target()
        # Per-game scratch resets.
        pl.player.score = 0
        pl.score_this_game = 0
        pl.draws_this_game = 0
        pl.last_ink = 0
        pl.last_mult = 1.0
        pl.player.blind_shot_marks = []
        pl.player.cells_played = []
        pl.game_result = None
        # Re-seed every passive joker's stack into the upgrade counters.
        self.card_system.apply_passive_buffs(pl.player)

        # Cursed Coin — drains 1 life every game start, per copy. The
        # life is lost without animation (it's the price of the curse,
        # not a defeat). If the curse drops you to zero, the game ends.
        cursed = pl.player.upgrades.get("cursed_coin", 0)
        if cursed > 0:
            pl.lives = max(0, pl.lives - cursed)
            if pl.lives <= 0:
                self._pending_run_end = True
                self.finish_run(won=False)
                return

        # every 3rd game is a boss — set the boss state BEFORE firing
        # game-start triggers so on_game_start handlers see is_boss=True
        # (some triggers may want to behave differently in boss games).
        if pl.games_in_level % 3 == 0:
            # Per-run boss order is a shuffled list of mechanics. We walk
            # it via boss_index which increments each boss encounter.
            # The old code used (games_in_level // 3 - 1) which always
            # evaluated to 0 since games_in_level resets per level, so
            # the player only ever saw BOSS_LIST[0] — The Blind.
            order = pl.boss_order or [b.mechanic for b in BOSS_LIST]
            mechanic = order[pl.boss_index % len(order)]
            pl.boss_index += 1
            boss = next(b for b in BOSS_LIST if b.mechanic == mechanic)
            pl.current_boss = boss
            base_ante = pl.get_ante_target()
            # Shield — reduces the boss ante target by 20% per copy
            # (multiplicative). Capped to at least 1.
            shield = pl.player.upgrades.get("shield", 0)
            if shield > 0:
                base_ante = max(1, int(base_ante * (0.8 ** shield)))
            pl.ante_target = base_ante
            self.engine.current_boss_mechanic = boss.mechanic

            # apply boss-specific setup
            empty = self.board.get_empty_cells()
            if boss.mechanic == "poison":
                self.board.poison_cells = random.sample(empty, min(3, len(empty)))
            if boss.mechanic == "weighted":
                self.board.weights = self.board.get_weights()
            if boss.mechanic == "timed":
                self.countdown_start = pygame.time.get_ticks()
            if boss.mechanic == "swap":
                self.board.swap_counter = 0
            if boss.mechanic == "spotlight":
                self._spotlight_move()
            else:
                self._spotlight_anchor = None
            # Reset Tide schedule + Hourglass counter on every boss start.
            self._tide_clear_deadlines = []
            pl.player.upgrades.pop("hourglass_counter", None)

            pl.is_boss = True
            self.state = "boss_intro"
            self._boss_intro_start = pygame.time.get_ticks()
        else:
            pl.ante_target = 0
            pl.is_boss = False
            pl.current_boss = None
            self.engine.current_boss_mechanic = None
            pl.shop_phase = False
            self.state = "countdown"
            self.countdown_start = pygame.time.get_ticks()

        # Fire on_game_start triggers (Cell Lock, Fortress, Ghost Board,
        # Blind Shot, Double Strike, Quick Draw) AFTER boss setup so any
        # walls / pre-placed X's land on the post-boss-setup board.
        before_marks = self.board.move_count
        fired = self.card_system.fire_game_start(self.board, pl.player)
        self._animate_new_marks(before_move_count=before_marks)
        self._animate_jokers(fired)

    def do_shop(self):
        pl = self.engine.state
        pl.shop_phase = True
        # Reset shop-only consumables, then let the on_shop_open jokers
        # (Reroll, Card Draw) seed them for this visit.
        pl.player.upgrades["free_rerolls"] = 0
        pl.player.upgrades["shop_offer_extra"] = 0
        self.card_system.fire_shop_open(pl.player)
        offer_count = 4 + pl.player.upgrades.get("shop_offer_extra", 0)
        self.shop_cards = self._sample_shop_offers(offer_count)
        self.state = "shop"

    def _sample_shop_offers(self, count: int) -> list[str]:
        """Pick `count` glyphs for the shop, biasing toward those the
        player hasn't seen this run. Once every glyph has been offered
        at least once, the seen set resets — so the bias never starves
        a long run of new offers."""
        pl = self.engine.state
        all_names = [c.name for c in ALL_CARDS]
        if not all_names:
            return []
        # If the seen-set has saturated, recycle so we keep biasing
        # toward fresh-this-cycle picks instead of stalling.
        if len(pl.seen_shop_offers) >= len(all_names):
            pl.seen_shop_offers = set()
        unseen = [n for n in all_names if n not in pl.seen_shop_offers]
        seen = [n for n in all_names if n in pl.seen_shop_offers]
        # Prefer unseen first, then top up from seen.
        random.shuffle(unseen)
        random.shuffle(seen)
        picked = (unseen + seen)[:count]
        pl.seen_shop_offers.update(picked)
        return picked

    def finish_run(self, won: bool):
        save_progression(
            won=won,
            tokens_earned=self.engine.state.player.tokens,
            levels_reached=self.engine.state.level,
            cards_unlocked=get_unlocked_cards(),
        )
        self.engine.state.won_run = won
        self.engine.state.run_complete = True
        self.state = "gameover"

    def _board_layout(self) -> tuple[int, int, int]:
        """Cell size and pixel offset for rendering the current board."""
        rows = max(1, self.board.rows)
        cols = max(1, self.board.cols)
        avail = int(min((SCREEN_W - 120) / cols, (SCREEN_H - 300) / rows))
        avail = max(1, avail)
        off_x = (SCREEN_W - cols * avail) // 2
        off_y = 100
        return avail, off_x, off_y

    def _cell_under(self, mx: int, my: int) -> tuple[int, int] | None:
        avail, off_x, off_y = self._board_layout()
        c = int((mx - off_x) // avail)
        r = int((my - off_y) // avail)
        if (r, c) in self.board.valid_cells:
            return (r, c)
        return None

    def _animate_new_marks(self, before_move_count: int) -> None:
        """Walk the board and fire a `mark:r,c` placement animation for
        every cell whose `placed_at` stamp is strictly newer than the
        supplied move_count. Catches placements from both direct calls
        (player click, AI move) and trigger handlers (Ricochet, Blind
        Shot, Double Strike). Idempotent — re-firing for an already
        animating cell is a no-op."""
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                placed = self.board.placed_at[r][c]
                if placed > before_move_count:
                    self.animator.start(f"mark:{r},{c}", 150)

    def _animate_jokers(self, fired_names: list[str]) -> None:
        """Glow each joker chip whose trigger actually fired. The
        move-count suffix lets the same joker glow again on a later
        trigger without being suppressed by the first being still-active."""
        for name in fired_names:
            self.animator.start(
                f"joker_glow:{name}:{self.board.move_count}", 600,
            )

    def _tick_ai_move(self) -> None:
        """Run the AI's response if one was scheduled and its delay has
        elapsed. Called once per frame at the top of run()'s loop."""
        if self._ai_move_at is None:
            return
        if pygame.time.get_ticks() < self._ai_move_at:
            return
        self._ai_move_at = None
        pl = self.engine.state
        before = self.board.move_count
        # Boss-specific extra AI moves. Echo and Twins both run the AI
        # an extra time on top of the normal move; Hivemind boosts the
        # AI's tactical depth via fade_age=None even on Blind.
        extras = 0
        if pl.is_boss and pl.current_boss:
            if pl.current_boss.mechanic in ("echo", "twins"):
                extras = 1
        for i in range(1 + extras):
            ai = OpponentAI(self.board, fade_age=self._ai_fade_age())
            if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "hivemind":
                ai.difficulty = 1.0  # always-optimal heuristic
            move = ai.get_best_move()
            if move:
                self.board.place_at(move[0], move[1], OPPONENT_O)
                self.card_system.fire_ai_placed(self.board, pl.player, move[0], move[1])
        self._animate_new_marks(before_move_count=before)
        # Vandal boss: erase a random non-edge X cell each AI turn.
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "vandal":
            self._vandal_strike()
        # Hourglass boss: every 4 AI moves, drop a wall on a random empty cell.
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "hourglass":
            counter = pl.player.upgrades.get("hourglass_counter", 0) + 1
            pl.player.upgrades["hourglass_counter"] = counter
            if counter % 4 == 0:
                self._hourglass_drop_wall()
        # Quicksand boss: decay marks not reinforced by an adjacent same-side mark.
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "quicksand":
            self._quicksand_tick()
        # Tide boss: clear any cells whose erase deadline has passed.
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "tide":
            self._tide_tick()
        # Poison ticks after the AI's turn — same as the old synchronous
        # flow, just deferred along with the move.
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "poison":
            self.board.tick_poison()
        if self._should_evaluate():
            self.evaluate_and_settle()

    def _spotlight_move(self) -> None:
        """Spotlight boss helper — pick a new random top-left anchor for
        a 3x3 zone that fits inside the playable region."""
        rows = [r for (r, _) in self.board.valid_cells]
        cols = [c for (_, c) in self.board.valid_cells]
        rmin, rmax = min(rows), max(rows)
        cmin, cmax = min(cols), max(cols)
        if rmax - rmin < 2 or cmax - cmin < 2:
            self._spotlight_anchor = (rmin, cmin)
            return
        self._spotlight_anchor = (
            random.randint(rmin, rmax - 2),
            random.randint(cmin, cmax - 2),
        )

    def _spotlight_contains(self, line_cells) -> bool:
        """True if every cell of the line is inside the active Spotlight."""
        anchor = getattr(self, "_spotlight_anchor", None)
        if anchor is None:
            return True
        ar, ac = anchor
        for (r, c) in line_cells:
            if not (ar <= r <= ar + 2 and ac <= c <= ac + 2):
                return False
        return True

    def _board_centre(self) -> tuple[int, int]:
        rows = [r for (r, _) in self.board.valid_cells]
        cols = [c for (_, c) in self.board.valid_cells]
        return ((min(rows) + max(rows)) // 2, (min(cols) + max(cols)) // 2)

    def _vandal_strike(self) -> None:
        """Vandal boss helper — erase one random non-edge X cell."""
        rows = [r for (r, _) in self.board.valid_cells]
        cols = [c for (_, c) in self.board.valid_cells]
        rmin, rmax = min(rows), max(rows)
        cmin, cmax = min(cols), max(cols)
        candidates = [
            (r, c) for (r, c) in self.board.valid_cells
            if self.board.grid[r][c] == PLAYER_X
            and r not in (rmin, rmax) and c not in (cmin, cmax)
        ]
        if not candidates:
            return
        victim = random.choice(candidates)
        self.board.remove_at(victim[0], victim[1])
        self.animator.start(f"mark:{victim[0]},{victim[1]}", 200)

    def _hourglass_drop_wall(self) -> None:
        """Hourglass boss — random empty cell becomes a wall."""
        empty = [p for p in self.board.get_empty_cells() if p not in self.board.wall_cells]
        if not empty:
            return
        target = random.choice(empty)
        self.board.wall_cells.append(target)
        self.animator.start(f"grid_grow_row:{target[0]}", 400)

    def _quicksand_tick(self) -> None:
        """Quicksand boss — every cell that's stayed N=3 turns without an
        adjacent same-side neighbour is erased."""
        for (r, c) in list(self.board.valid_cells):
            val = self.board.grid[r][c]
            if val == EMPTY:
                continue
            placed = self.board.placed_at[r][c]
            if placed < 0 or self.board.move_count - placed < 3:
                continue
            same_neighbour = False
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if (nr, nc) in self.board.valid_cells and self.board.grid[nr][nc] == val:
                        same_neighbour = True
                        break
                if same_neighbour:
                    break
            if not same_neighbour:
                self.board.remove_at(r, c)

    def _tide_tick(self) -> None:
        """Tide boss — any cell on a completed line scheduled for erasure
        clears once its deadline arrives. The deadlines are stored on
        `self._tide_clear_deadlines` as a list of (move_count, [cells])."""
        deadline_list = getattr(self, "_tide_clear_deadlines", [])
        keep: list = []
        for (when, cells) in deadline_list:
            if self.board.move_count >= when:
                for (r, c) in cells:
                    if (r, c) in self.board.valid_cells and self.board.grid[r][c] != EMPTY:
                        self.board.remove_at(r, c)
            else:
                keep.append((when, cells))
        self._tide_clear_deadlines = keep

    def _ai_fade_age(self) -> int | None:
        """The Blind boss is symmetric — the AI sees the same faded board
        the player does. Other games leave the AI omniscient."""
        pl = self.engine.state
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "blind":
            return BLIND_FADE_AGE
        return None

    def _should_evaluate(self) -> bool:
        """Game ends only when the board is full. Both sides play out
        the whole bounding box and the outcome is decided by the line
        count over the final state. This generalises what Mirror boss
        used to do as a special case — first-line endings made the AI's
        forced-draw behaviour on small grids feel like a solved game."""
        return self.board.is_full()

    def evaluate_and_settle(self):
        pl = self.engine.state
        is_boss = bool(pl.is_boss and pl.current_boss)

        # Fire on_line_completed triggers (Chain Reaction) BEFORE scoring,
        # so the line-extending flips count toward this game's ink. Track
        # any new marks the triggers placed and the joker names that fired
        # so the renderer can animate them in.
        x_lines_for_triggers = [
            cells for (val, cells) in self.board.get_lines() if val == PLAYER_X
        ]
        before_marks = self.board.move_count
        for line in x_lines_for_triggers:
            fired = self.card_system.fire_line_completed(self.board, pl.player, line)
            self._animate_jokers(fired)
        self._animate_new_marks(before_move_count=before_marks)

        # Bump the per-game X-line count BEFORE scoring so Crescendo
        # (Mult +0.2 per line scored this game) reflects the current
        # round's lines, and First Strike's "first line" flag flips
        # AFTER this evaluation.
        boss_mech = pl.current_boss.mechanic if pl.current_boss else None
        spotlight = self._spotlight_anchor if boss_mech == "spotlight" else None
        centre = self._board_centre() if boss_mech == "inverse" else None
        x_line_count = sum(1 for (v, _) in self.board.get_lines() if v == PLAYER_X)
        pl.player.upgrades["lines_scored"] = (
            pl.player.upgrades.get("lines_scored", 0) + x_line_count
        )

        # Single ink × mult scoring pass for the current board state.
        ink, mult, total = self.card_system.score_breakdown(
            self.board, pl.player, pl.get_multiplier(),
            is_boss=is_boss,
            boss_mechanic=boss_mech,
            spotlight_zone=spotlight,
            centre=centre,
            lives=pl.lives,
        )
        pl.last_ink = ink
        pl.last_mult = mult
        # Capture THIS evaluation's total separately from the running
        # game total so the score count-up animates from 0 to the value
        # contributed by this round (not the cumulative).
        pl.last_total = total
        # Per-line contribution breakdown for the result panel — colour-
        # codes each completed line on the board with a "+N" or "-N" so
        # the player sees exactly where the score came from.
        pl.last_line_contributions = self.card_system.line_contributions(
            self.board, pl.player,
            is_boss=is_boss,
            boss_mechanic=boss_mech,
            spotlight_zone=spotlight,
            centre=centre,
        )
        # First Strike: flip the "first X line scored" flag after this
        # evaluation so subsequent games stop applying the +20 bonus.
        if x_line_count > 0:
            pl.player.upgrades["first_x_line_done"] = 1
        pl.score_this_game += total
        pl.player.score += total
        pl.total_score += total
        pl.score_this_level += total

        # Outcome by lines (mechanic-aware).
        outcome = self._boss_outcome() if is_boss else self._normal_outcome()

        # Boss ante check — a mechanical win that doesn't hit the ink
        # target counts as a loss and ends the run.
        ante_failed = False
        if is_boss and outcome == "win" and pl.score_this_game < pl.ante_target:
            outcome = "lose"
            ante_failed = True

        if outcome == "draw":
            if pl.draws_this_game >= 1:
                # Second draw within the same game converts to a loss.
                outcome = "lose"
            else:
                pl.draws_this_game += 1
                pl.draw_multiplier *= 0.5
                rows_before = self.board.rows
                cols_before = self.board.cols
                row_shift, col_shift = self.board.grow_row_and_column()
                if row_shift or col_shift:
                    pl.player.cells_played = [
                        (r + row_shift, c + col_shift) for (r, c) in pl.player.cells_played
                    ]
                    pl.player.blind_shot_marks = [
                        (r + row_shift, c + col_shift) for (r, c) in pl.player.blind_shot_marks
                    ]
                # Identify the newly-added row and column index so the
                # grid-grow animation can highlight those cells.
                new_row_idx = 0 if row_shift == 1 else rows_before
                new_col_idx = 0 if col_shift == 1 else cols_before
                self.animator.start(f"grid_grow_row:{new_row_idx}", 500)
                self.animator.start(f"grid_grow_col:{new_col_idx}", 500)
                self.board.game_over = False
                self.showing_result = False
                pl.game_result = "draw"
                self.draw_message_until = pygame.time.get_ticks() + 1500
                self.draw_message_cell = None
                return "draw"

        # Sacrifice rescue — if the player owns a Sacrifice joker with a
        # charge left, consume the charge, undo the last X they placed,
        # and treat this as if the loss never happened (the game becomes
        # a continuing draw on the post-undo board). Only applies to
        # non-ante losses — losing the ante means the round is over.
        if outcome == "lose" and not ante_failed:
            if self.card_system.try_sacrifice_save(self.board, pl.player):
                self.board.game_over = False
                self.showing_result = False
                pl.game_result = "draw"
                self.draw_message_until = pygame.time.get_ticks() + 1500
                return "saved"

        if outcome == "win":
            base_reward = 2
            token_bonus_stacks = pl.player.upgrades.get("token_bonus", 0)
            pl.player.tokens += max(1, round(base_reward * pl.draw_multiplier))
            pl.player.tokens += 3 * token_bonus_stacks
            # Vampire: +N tokens paid on win, accumulated over AI moves.
            vamp = pl.player.upgrades.get("vampire_tokens", 0)
            if vamp:
                pl.player.tokens += vamp
            # Pacifist: +2 tokens if you destroyed ZERO O's this game.
            pacifist = pl.player.upgrades.get("pacifist", 0)
            if pacifist > 0 and pl.player.upgrades.get("os_destroyed", 0) == 0:
                pl.player.tokens += 2 * pacifist
            pl.draw_multiplier = 1.0
            # Streak counter — read by any future momentum-scaling glyph.
            pl.consecutive_wins += 1
        else:  # lose
            pl.draw_multiplier = 1.0
            pl.consecutive_wins = 0
            # Patience: if a game ends with the board full and you
            # scored zero X lines, gain a life back. Caps at max_lives.
            patience = pl.player.upgrades.get("patience", 0)
            zero_lines = sum(
                1 for (v, _) in self.board.get_lines() if v == PLAYER_X
            ) == 0
            if patience > 0 and zero_lines and pl.lives < pl.max_lives:
                pl.lives += 1
            else:
                lost_pip_idx = pl.lives - 1
                pl.lives -= 1
                self.animator.start(f"life_lost:{lost_pip_idx}", 500)

        pl.game_result = outcome
        self.showing_result = True
        self.board.game_over = True

        # Staged result reveal: panel slides up; ink, mult, and total
        # count in sequence. Anchor the wall-clock timer here so the
        # renderer can compute each sub-phase's progress on read.
        self._result_anim_start = pygame.time.get_ticks()
        self.animator.start("result_panel", 400)

        # Highlight every completed line on the board with a coloured
        # streak — gold for your X lines, red for the AI's O lines. The
        # animation id encodes the side so the renderer can pick the
        # right colour without re-scanning the board.
        for contrib in pl.last_line_contributions:
            cells_str = "-".join(f"{r},{c}" for r, c in contrib["cells"])
            line_id = f"line_glow:{contrib['side']}:{cells_str}"
            self.animator.start(line_id, 800)

        # Run-ending failure modes — ante failure on a boss, or zero lives.
        if ante_failed or pl.lives <= 0:
            # Phoenix: first time per run that we'd lose, restore a life.
            if (
                pl.player.upgrades.get("phoenix", 0) > 0
                and not pl.phoenix_used
                and pl.lives <= 0
            ):
                pl.phoenix_used = True
                pl.lives = 1
            else:
                self._pending_run_end = True
        return outcome

    def _normal_outcome(self) -> str:
        xp = self.board.count_lines_for(PLAYER_X)
        op = self.board.count_lines_for(OPPONENT_O)
        if xp > op:
            return "win"
        if xp < op:
            return "lose"
        return "draw"

    def _boss_outcome(self) -> str:
        """Outcome rule per boss mechanic. Scoring already happened in
        evaluate_and_settle; this only decides win/lose/draw before the
        ante check applies."""
        pl = self.engine.state
        boss = pl.current_boss
        xp = self.board.count_lines_for(PLAYER_X)
        op = self.board.count_lines_for(OPPONENT_O)

        # Mirror is the only mechanic that requires the board to be full
        # before resolving — _should_evaluate already gates on that.
        if xp > op:
            return "win"
        if xp < op:
            return "lose"
        if self.board.is_full():
            return "draw"
        # Reached when _should_evaluate triggered on a line but counts
        # somehow ended even — treat as draw to expand and continue.
        return "draw"

    def draw(self):
        surf = pygame.display.get_surface()
        surf.fill(BG_COLOR)
        # Soft radial darken at the screen edges — one cached blit. May
        # return None on a runtime that can't render the SRCALPHA layer
        # (e.g. some pygame-ce / WASM combinations); skip if so.
        vignette = get_vignette(SCREEN_W, SCREEN_H)
        if vignette is not None:
            surf.blit(vignette, (0, 0))

        pl = self.engine.state

        if self.state == "menu":
            draw_big_centered_text(surf, "CROSSED OUT", self.big_font, ACCENT_GOLD, 180)
            draw_centered_text(surf, "A Roguelite Tic-Tac-Toe Game", self.font, TEXT_SUB, 260)

            btn_h = pygame.font.SysFont("consolas", 32).render("START NEW RUN", True, (0, 0, 0))
            btn = pygame.Rect(SCREEN_W // 2 - 160, SCREEN_H // 2 - 30, 320, 60)
            pygame.draw.rect(surf, ACCENT_GREEN, btn, border_radius=10)
            surf.blit(btn_h, (SCREEN_W // 2 - btn_h.get_width() // 2, btn.centery - 16))

            # CODEX button — opens a browser of every glyph and every
            # boss modifier, so players can study what's in the pool.
            codex_btn_h = pygame.font.SysFont("consolas", 22).render("CODEX", True, TEXT_COLOR)
            codex_btn = pygame.Rect(SCREEN_W // 2 - 120, SCREEN_H // 2 + 60, 240, 50)
            pygame.draw.rect(surf, (40, 40, 70), codex_btn, border_radius=10)
            pygame.draw.rect(surf, ACCENT_GOLD, codex_btn, 2, border_radius=10)
            surf.blit(codex_btn_h, (SCREEN_W // 2 - codex_btn_h.get_width() // 2,
                                    codex_btn.centery - codex_btn_h.get_height() // 2))

            desc = self.font.render("Click [X] on the grid to play. Tap glyphs to inspect them.", True, TEXT_SUB)
            surf.blit(desc, (SCREEN_W // 2 - desc.get_width() // 2, SCREEN_H // 2 + 140))

        elif self.state == "codex":
            self._draw_codex(surf)

        elif self.state == "transition":
            lv = pl.level
            gs = pl.get_grid_size()
            draw_big_centered_text(surf, f"Level {lv}", self.big_font, ACCENT_GOLD, 150)
            draw_centered_text(surf, f"{gs}x{gs} Grid", self.font, TEXT_COLOR, 240)
            pick_text = self.font.render("Choose a starting card:", True, TEXT_SUB)
            surf.blit(pick_text, (SCREEN_W // 2 - pick_text.get_width() // 2, 400))

            card_y = 460
            sx = SCREEN_W // 2 - (3 * CARD_W + 2 * 12) // 2
            for i, name in enumerate(self.starter_cards):
                card = get_by_name(name)
                cx = sx + i * (CARD_W + 12)
                draw_card(
                    surf, name, card.cost if card else 0, card.desc if card else "",
                    cx, card_y, CARD_W, CARD_H,
                    is_highlighted=(self.hover_pos == f"starter:{i}"),
                    can_afford=True,
                )

        elif self.state == "boss_intro":
            boss = pl.current_boss
            # Staged entrance: title pops, name slides in from the left,
            # description fades up. Eased windows off a single wall-clock
            # anchor stamped when the boss_intro state was entered.
            elapsed = (
                pygame.time.get_ticks() - self._boss_intro_start
                if self._boss_intro_start is not None else 9999
            )
            title_t = max(0.0, min(1.0, elapsed / 250))
            name_t = max(0.0, min(1.0, (elapsed - 150) / 350))
            desc_t = max(0.0, min(1.0, (elapsed - 400) / 500))

            # Title pop: scale 1.3 → 1.0 as title_t goes 0..1.
            title_scale = 1.3 - 0.3 * (1 - (1 - title_t) ** 3)  # ease-out cubic
            title_size = max(24, int(56 * title_scale))
            title_font = pygame.font.SysFont("consolas", title_size)
            title_surf = title_font.render("BOSS GAME", True, ACCENT_RED)
            surf.blit(title_surf, (SCREEN_W // 2 - title_surf.get_width() // 2, 150))

            # Name slide: x position interpolates from -200 to centered.
            if name_t > 0:
                name_font = pygame.font.SysFont("consolas", 36)
                name_surf = name_font.render(boss.name, True, ACCENT_GOLD)
                target_x = SCREEN_W // 2 - name_surf.get_width() // 2
                eased = 1 - (1 - name_t) ** 3
                slide_x = int(-200 + (target_x + 200) * eased)
                surf.blit(name_surf, (slide_x, 260))

            # Description fade-in via set_alpha on a solid surface
            # (cheaper than SRCALPHA per-pixel under WASM).
            if desc_t > 0:
                from renders.rendering import _wrap_lines
                desc_alpha = int(255 * desc_t)
                lines = _wrap_lines(boss.desc, self.font, SCREEN_W - 80)
                line_h = self.font.get_linesize()
                for i, line in enumerate(lines[:6]):
                    line_surf = self.font.render(line, True, TEXT_SUB)
                    line_surf.set_alpha(desc_alpha)
                    surf.blit(line_surf,
                              (SCREEN_W // 2 - line_surf.get_width() // 2,
                               330 + i * line_h))

            # Continue prompt only after the entrance finishes.
            if desc_t >= 1.0:
                cont = self.font.render("Click to continue", True, TEXT_SUB)
                surf.blit(cont, (SCREEN_W // 2 - cont.get_width() // 2, SCREEN_H - 80))

        elif self.state in ("countdown", "game"):
            # countdown for normal games
            if self.state == "countdown":
                if self.countdown_start:
                    remaining = 3 - (pygame.time.get_ticks() - self.countdown_start) / 1000
                    if remaining <= 0:
                        self.state = "game"
                    else:
                        draw_big_centered_text(surf, f"{max(0, int(remaining))}", self.big_font, ACCENT_GOLD, SCREEN_H // 2 - 40)
                        draw_centered_text(surf, "GET READY", pygame.font.SysFont("sans-serif", 20), TEXT_SUB, SCREEN_H // 2 + 40)
                return

            avail, off_x, off_y = self._board_layout()

            # draw playable cells (sparse — only valid_cells)
            new_cell_glow = (
                self.draw_message_cell
                if self.draw_message_until and pygame.time.get_ticks() < self.draw_message_until
                else None
            )
            cell_shadow = get_cell_shadow(avail)
            for (r, c) in self.board.valid_cells:
                x = off_x + c * avail
                y = off_y + r * avail
                pygame.draw.rect(surf, (28, 28, 48), (x, y, avail, avail), border_radius=4)
                # 1-px top highlight / bottom shadow — cells feel pressed.
                if cell_shadow is not None:
                    surf.blit(cell_shadow, (x, y))

                # Empty poison cells get a green warning square even when
                # nothing is placed yet, so the player can see the hazard.
                if (
                    pl.current_boss
                    and pl.current_boss.mechanic == "poison"
                    and (r, c) in self.board.poison_cells
                ):
                    ps = avail // 5
                    pygame.draw.rect(surf, (80, 180, 60), (x + avail // 2 - ps // 2, y + avail // 2 - ps // 2, ps, ps), border_radius=3)

                val = self.board.grid[r][c]
                # Blind boss: marks fade behind a "?" once they've been
                # on the board for BLIND_FADE_AGE moves. Recent moves
                # stay visible (so the player can still play tactically);
                # older ones become a memory test. On grown grids, more
                # moves elapse → more marks are obscured at any time, so
                # the difficulty scales naturally with board size.
                blind_hide = False
                if (
                    pl.is_boss
                    and pl.current_boss
                    and pl.current_boss.mechanic == "blind"
                    and not self.showing_result
                    and val != 0
                ):
                    placed = self.board.placed_at[r][c]
                    age = self.board.move_count - placed if placed >= 0 else 0
                    blind_hide = age >= BLIND_FADE_AGE
                if blind_hide:
                    q_font = pygame.font.SysFont("consolas", max(20, avail // 2), bold=True)
                    q_surf = q_font.render("?", True, TEXT_SUB)
                    surf.blit(
                        q_surf,
                        (x + avail // 2 - q_surf.get_width() // 2, y + avail // 2 - q_surf.get_height() // 2),
                    )
                elif val != 0:
                    color = COLOR_X if val == PLAYER_X else COLOR_O
                    # Scale the mark in from 0 → 1 over its placement
                    # animation. eased() returns 1.0 if the animation is
                    # done or absent, so this is a no-op for old marks.
                    scale = self.animator.eased(f"mark:{r},{c}")
                    if val == PLAYER_X:
                        m_full = avail // 4
                        # Stroke endpoints retract from the cell centre
                        # so the X "grows" outward as scale goes 0 → 1.
                        cx = x + avail // 2
                        cy = y + avail // 2
                        half = (avail // 2 - m_full) * scale
                        pygame.draw.line(surf, color,
                                         (cx - half, cy - half), (cx + half, cy + half), 4)
                        pygame.draw.line(surf, color,
                                         (cx - half, cy + half), (cx + half, cy - half), 4)
                    else:
                        radius = max(1, int((avail // 3) * scale))
                        pygame.draw.circle(surf, color,
                                           (x + avail // 2, y + avail // 2), radius, 4)

                # Weighted boss: print each cell's weight in the corner.
                if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "weighted":
                    try:
                        w = self.board.weights[r][c]
                    except (IndexError, AttributeError):
                        w = 1
                    if w > 1:
                        wf = pygame.font.SysFont("consolas", 14).render(str(w), True, ACCENT_GOLD)
                        surf.blit(wf, (x + 4, y + 4))

                # hover highlight — pulses subtly so the player notices it.
                if self.hover_pos == (r, c) and not self.showing_result:
                    import math as _math
                    pulse = (1 + _math.sin(pygame.time.get_ticks() / 220.0)) / 2
                    border_w = 2 + int(pulse * 2)
                    pygame.draw.rect(surf, ACCENT_GOLD,
                                     (x, y, avail, avail), border_w, border_radius=4)
                # newly-added cell glow during the draw transition
                if new_cell_glow == (r, c):
                    pygame.draw.rect(surf, ACCENT_GOLD, (x, y, avail, avail), 3, border_radius=4)
                # grid-grow flash: cells in a newly-added row/col light up
                # for ~500 ms so the player sees the board expanded.
                row_anim = self.animator.eased(f"grid_grow_row:{r}")
                col_anim = self.animator.eased(f"grid_grow_col:{c}")
                grow_t = min(row_anim, col_anim) if row_anim < 1.0 or col_anim < 1.0 else 1.0
                if grow_t < 1.0:
                    fade = 1.0 - grow_t
                    pygame.draw.rect(
                        surf,
                        (int(ACCENT_GOLD[0] * fade + 28 * (1 - fade)),
                         int(ACCENT_GOLD[1] * fade + 28 * (1 - fade)),
                         int(ACCENT_GOLD[2] * fade + 48 * (1 - fade))),
                        (x, y, avail, avail), 2, border_radius=4,
                    )

            # Line glow pass — pulses a coloured streak through every
            # completed line. Gold for your X lines (positive ink), red
            # for the AI's O lines (negative ink, unless Double Cross is
            # active in which case both score). Eases out so it 'fires'
            # then settles — same animation backs the line streaks
            # drawn during the result panel.
            for anim_id in list(self.animator.entries):
                if not anim_id.startswith("line_glow:"):
                    continue
                t = self.animator.eased(anim_id)
                if t >= 1.0:
                    continue
                bright = 1.0 - t
                # IDs use the form `line_glow:X:r,c-r,c-r,c`.
                _, side, cells_str = anim_id.split(":", 2)
                # Per-side target colour. X = gold; O = red.
                if side == "X":
                    target = (255, 200, 80)
                else:
                    target = (255, 90, 90)
                glow_col = (
                    int(BG_COLOR[0] + (target[0] - BG_COLOR[0]) * bright),
                    int(BG_COLOR[1] + (target[1] - BG_COLOR[1]) * bright),
                    int(BG_COLOR[2] + (target[2] - BG_COLOR[2]) * bright),
                )
                cells = [
                    tuple(int(n) for n in pair.split(","))
                    for pair in cells_str.split("-")
                ]
                if len(cells) < 2:
                    continue
                r0, c0 = cells[0]
                r1, c1 = cells[-1]
                start_px = (off_x + c0 * avail + avail // 2,
                            off_y + r0 * avail + avail // 2)
                end_px = (off_x + c1 * avail + avail // 2,
                          off_y + r1 * avail + avail // 2)
                pygame.draw.line(surf, glow_col, start_px, end_px, 8)

            # While the result panel is up, paint each completed line
            # with a steady streak (so the player can study WHICH lines
            # scored), and float a "+N" / "-N" label at the line's
            # midpoint showing its contribution to ink.
            if self.showing_result and pl.last_line_contributions:
                badge_font = pygame.font.SysFont("consolas", max(18, avail // 4), bold=True)
                for contrib in pl.last_line_contributions:
                    cells = contrib["cells"]
                    if len(cells) < 2:
                        continue
                    r0, c0 = cells[0]
                    r1, c1 = cells[-1]
                    start_px = (off_x + c0 * avail + avail // 2,
                                off_y + r0 * avail + avail // 2)
                    end_px = (off_x + c1 * avail + avail // 2,
                              off_y + r1 * avail + avail // 2)
                    if contrib["side"] == "X":
                        streak_col = (255, 200, 80)
                        sign = "+"
                    else:
                        streak_col = (255, 90, 90)
                        # Double Cross flips O to positive contribution.
                        sign = "+" if contrib["contribution"] >= 0 else "-"
                    pygame.draw.line(surf, streak_col, start_px, end_px, 5)
                    # Midpoint label with the signed contribution. We
                    # render onto a small dark-rect "chip" for legibility
                    # over both empty cells and placed marks.
                    mx_ = (start_px[0] + end_px[0]) // 2
                    my_ = (start_px[1] + end_px[1]) // 2
                    label = f"{sign}{abs(contrib['contribution'])}"
                    ls = badge_font.render(label, True, streak_col)
                    bw, bh = ls.get_width() + 12, ls.get_height() + 4
                    pygame.draw.rect(
                        surf, (8, 8, 16),
                        (mx_ - bw // 2, my_ - bh // 2, bw, bh),
                        border_radius=4,
                    )
                    pygame.draw.rect(
                        surf, streak_col,
                        (mx_ - bw // 2, my_ - bh // 2, bw, bh),
                        1, border_radius=4,
                    )
                    surf.blit(ls, (mx_ - ls.get_width() // 2, my_ - ls.get_height() // 2))

            # score display
            draw_score(surf, pl.player.score, pl.current_target, 20, 30)
            draw_tokens(surf, pl.player.tokens, SCREEN_W - 200, 30)
            lv_txt = self.font.render(f"Level {pl.level}", True, TEXT_COLOR)
            surf.blit(lv_txt, (20, 10))
            # Lives — text + pip row in the centre of the top bar. Unicode
            # heart glyphs render inconsistently in the browser, so use a
            # plain "Lives: N" label with filled circles for clarity.
            lives_label = pygame.font.SysFont("sans-serif", 22).render(
                f"Lives: {pl.lives}/{pl.max_lives}", True, TEXT_COLOR,
            )
            label_w = lives_label.get_width()
            pip_r = 8
            pip_gap = 6
            pips_w = pl.max_lives * (pip_r * 2) + (pl.max_lives - 1) * pip_gap
            total_w = label_w + 10 + pips_w
            block_x = SCREEN_W // 2 - total_w // 2
            surf.blit(lives_label, (block_x, 14))
            pips_x = block_x + label_w + 10
            for i in range(pl.max_lives):
                cx = pips_x + pip_r + i * (pip_r * 2 + pip_gap)
                cy = 14 + lives_label.get_height() // 2
                # Life-loss animation: the pip we just lost briefly
                # pulses bright, shakes ±3 px, then settles to hollow.
                lost_id = f"life_lost:{i}"
                if self.animator.is_active(lost_id):
                    t = self.animator.eased(lost_id)
                    # 0..0.4: bright red, full circle, slight grow.
                    # 0.4..1.0: shrink + hollow out.
                    import math as _math
                    shake = int(3 * _math.sin(t * _math.pi * 6))
                    if t < 0.4:
                        bright = (255, 140, 140)
                        grow_r = int(pip_r * (1.0 + 0.5 * (1.0 - t / 0.4)))
                        pygame.draw.circle(surf, bright, (cx + shake, cy), grow_r)
                    else:
                        fade_t = (t - 0.4) / 0.6
                        # Fade fill alpha and shrink slightly.
                        radius = int(pip_r * (1.0 - 0.3 * fade_t))
                        pygame.draw.circle(surf, (60, 60, 80), (cx + shake, cy), pip_r)
                        pygame.draw.circle(surf, ACCENT_RED, (cx + shake, cy), pip_r, 2)
                        if radius > 0:
                            faded = (
                                int(ACCENT_RED[0] * (1.0 - fade_t)),
                                int(ACCENT_RED[1] * (1.0 - fade_t)),
                                int(ACCENT_RED[2] * (1.0 - fade_t)),
                            )
                            pygame.draw.circle(surf, faded, (cx + shake, cy), radius)
                elif i < pl.lives:
                    pygame.draw.circle(surf, ACCENT_RED, (cx, cy), pip_r)
                else:
                    pygame.draw.circle(surf, (60, 60, 80), (cx, cy), pip_r)
                    pygame.draw.circle(surf, ACCENT_RED, (cx, cy), pip_r, 2)
            if pl.current_boss:
                boss_txt = self.font.render(f"BOSS: {pl.current_boss.name}", True, ACCENT_RED)
                surf.blit(boss_txt, (SCREEN_W - 10 - boss_txt.get_width(), 60))
                if pl.ante_target > 0:
                    ante_color = ACCENT_GREEN if pl.score_this_game >= pl.ante_target else ACCENT_RED
                    ante_txt = self.font.render(
                        f"Ante: {pl.score_this_game} / {pl.ante_target}", True, ante_color,
                    )
                    surf.blit(ante_txt, (SCREEN_W - 10 - ante_txt.get_width(), 85))

            # timed boss countdown
            if (
                pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "timed"
                and self.countdown_start and not self.board.game_over
                and not self.showing_result
            ):
                elapsed = (pygame.time.get_ticks() - self.countdown_start) / 1000
                remaining = 5 - elapsed
                if remaining > 0:
                    ts = pygame.font.SysFont("consolas", 48).render(f"{remaining:.0f}", True, ACCENT_RED)
                    surf.blit(ts, (SCREEN_W // 2 - ts.get_width() // 2, 60))
                else:
                    before_marks = self.board.move_count
                    ai = OpponentAI(self.board, fade_age=self._ai_fade_age())
                    move = ai.get_best_move()
                    if move:
                        self.board.place_at(move[0], move[1], OPPONENT_O)
                    self._animate_new_marks(before_move_count=before_marks)
                    self.countdown_start = pygame.time.get_ticks()
                    if self._should_evaluate():
                        self.evaluate_and_settle()
            # joker row — read-only display of owned passive cards.
            self._draw_joker_row(surf, pl)

            # transient "DRAW! Grid grows" banner — shows briefly after a draw
            # while play continues on the now-expanded board.
            if self.draw_message_until and pygame.time.get_ticks() < self.draw_message_until:
                penalty_pct = int(round((1 - pl.draw_multiplier) * 100))
                banner = pygame.font.SysFont("consolas", 36).render("DRAW! Grid grows...", True, ACCENT_GOLD)
                surf.blit(banner, (SCREEN_W // 2 - banner.get_width() // 2, 30))
                sub = self.font.render(f"Win reward reduced by {penalty_pct}%", True, TEXT_SUB)
                surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 70))

            # result panel (win/lose only — draws keep the game going).
            # Sits in the gap between the board and the joker row so it
            # never overlaps placed marks. Slides up from below when
            # first shown and stages the score reveal: ink counts up,
            # then mult pops, then total counts up.
            if self.showing_result:
                result = pl.game_result
                txt_map = {"win": ("VICTORY!", ACCENT_GREEN), "lose": ("DEFEAT!", ACCENT_RED)}
                if result in txt_map:
                    txt, col = txt_map[result]
                    board_bottom = off_y + self.board.rows * avail
                    panel_top_base = board_bottom + 12
                    panel_h = max(120, JOKER_ROW_Y - panel_top_base - 12)
                    panel_w = SCREEN_W - 40
                    panel_x = (SCREEN_W - panel_w) // 2

                    # Slide-in: panel y offset eases panel_h → 0 over 400 ms.
                    slide = 1.0 - self.animator.eased("result_panel")
                    panel_top = int(panel_top_base + slide * panel_h)

                    pygame.draw.rect(
                        surf, (12, 12, 24), (panel_x, panel_top, panel_w, panel_h),
                        border_radius=10,
                    )
                    pygame.draw.rect(
                        surf, col, (panel_x, panel_top, panel_w, panel_h), 2,
                        border_radius=10,
                    )
                    title_font = pygame.font.SysFont("consolas", 40)
                    ts = title_font.render(txt, True, col)
                    surf.blit(ts, (SCREEN_W // 2 - ts.get_width() // 2, panel_top + 8))

                    # Staged score reveal — read elapsed time off the
                    # anchor stamped in evaluate_and_settle.
                    elapsed = (
                        pygame.time.get_ticks() - self._result_anim_start
                        if self._result_anim_start is not None else 9999
                    )
                    ink_t = max(0.0, min(1.0, elapsed / 400))
                    mult_t = max(0.0, min(1.0, (elapsed - 400) / 200))
                    total_t = max(0.0, min(1.0, (elapsed - 500) / 600))
                    # ease-out-quart for the counters; pop for mult.
                    ink_eased = 1 - (1 - ink_t) ** 4
                    total_eased = 1 - (1 - total_t) ** 4

                    displayed_ink = int(ink_eased * pl.last_ink)
                    displayed_total = int(total_eased * getattr(pl, "last_total", pl.score_this_game))

                    # Render ink first; mult appears at +400ms; total at +500ms.
                    score_font = pygame.font.SysFont("consolas", 26)
                    ink_surf = score_font.render(f"Ink {displayed_ink}", True, ACCENT_GOLD)
                    surf.blit(ink_surf, (SCREEN_W // 2 - ink_surf.get_width() // 2, panel_top + 58))

                    if mult_t > 0:
                        # Pop scale 1.4 → 1.0 during mult_t 0..1.
                        scale = 1.0 + 0.4 * (1.0 - mult_t)
                        mult_size = max(16, int(20 * scale))
                        mult_font = pygame.font.SysFont("consolas", mult_size)
                        mult_surf = mult_font.render(f"x  Mult {pl.last_mult:g}", True, ACCENT_GOLD)
                        surf.blit(mult_surf,
                                  (SCREEN_W // 2 - mult_surf.get_width() // 2, panel_top + 92))

                    if total_t > 0:
                        total_font = pygame.font.SysFont("consolas", 30, bold=True)
                        total_surf = total_font.render(
                            f"= {displayed_total}", True, ACCENT_GREEN if result == "win" else ACCENT_RED,
                        )
                        surf.blit(total_surf,
                                  (SCREEN_W // 2 - total_surf.get_width() // 2, panel_top + 130))

                    # Per-line breakdown — fades in after the total
                    # finishes. A compact "Your lines (+N) / Opponent
                    # lines (-M)" summary plus per-line chips so the
                    # player sees exactly where the score came from.
                    if total_t >= 1.0 and pl.last_line_contributions:
                        breakdown_font = pygame.font.SysFont("consolas", 16)
                        line_y = panel_top + 170
                        # Aggregate by side for the summary line.
                        x_total = sum(
                            c["contribution"] for c in pl.last_line_contributions
                            if c["side"] == "X"
                        )
                        o_total = sum(
                            c["contribution"] for c in pl.last_line_contributions
                            if c["side"] == "O"
                        )
                        x_count = sum(1 for c in pl.last_line_contributions if c["side"] == "X")
                        o_count = sum(1 for c in pl.last_line_contributions if c["side"] == "O")
                        parts: list[tuple[str, tuple[int, int, int]]] = []
                        if x_count:
                            parts.append((f"Your lines x{x_count}:  +{x_total} ink", (255, 200, 80)))
                        if o_count:
                            sign = "+" if o_total >= 0 else ""
                            parts.append(
                                (f"Opp lines x{o_count}:  {sign}{o_total} ink", (255, 90, 90))
                            )
                        for text, col in parts:
                            sfc = breakdown_font.render(text, True, col)
                            surf.blit(sfc, (SCREEN_W // 2 - sfc.get_width() // 2, line_y))
                            line_y += sfc.get_height() + 4

                    # Footer (reason / continue) only after staging done.
                    staging_done = total_t >= 1.0
                    if staging_done and self._pending_run_end:
                        reason = (
                            "Failed boss ante" if pl.is_boss and pl.score_this_game < pl.ante_target
                            else "Out of lives"
                        )
                        rs = self.font.render(reason, True, ACCENT_RED)
                        surf.blit(rs, (SCREEN_W // 2 - rs.get_width() // 2, panel_top + 170))
                        end_txt = self.font.render(
                            "Run failed — click to return to menu", True, TEXT_SUB,
                        )
                        surf.blit(end_txt, (SCREEN_W // 2 - end_txt.get_width() // 2, panel_top + panel_h - 28))
                    elif staging_done:
                        cont = self.font.render("Click to continue", True, TEXT_SUB)
                        surf.blit(cont, (SCREEN_W // 2 - cont.get_width() // 2, panel_top + panel_h - 28))

        elif self.state == "shop":
            draw_centered_text(surf, "SHOP", pygame.font.SysFont("consolas", 40), ACCENT_GOLD, 50)
            draw_tokens(surf, pl.player.tokens, SCREEN_W - 200, 30)
            # Joker cap progress in the top-left.
            cap_txt = self.font.render(
                f"Glyphs: {len(pl.player.passive_cards)}/{pl.joker_cap}", True, TEXT_COLOR,
            )
            surf.blit(cap_txt, (20, 40))
            full_now = len(pl.player.passive_cards) >= pl.joker_cap
            if full_now and pygame.time.get_ticks() < self.shop_full_flash_until:
                flash = pygame.font.SysFont("consolas", 24).render(
                    "GLYPH SLOTS FULL", True, ACCENT_RED,
                )
                surf.blit(flash, (SCREEN_W // 2 - flash.get_width() // 2, 110))

            if self.shop_cards:
                sx = (SCREEN_W - (len(self.shop_cards) * CARD_W + max(0, len(self.shop_cards) - 1) * 12)) // 2
                for i, name in enumerate(self.shop_cards):
                    card = get_by_name(name)
                    cost_val = card.cost if card else 0
                    cx = sx + i * (CARD_W + 12)
                    cy_base = SCREEN_H // 2 - CARD_H // 2 - 20
                    # Hover lift — render the hovered card 8 px higher.
                    lift = 8 if self.hover_pos == f"shop:{i}" else 0
                    cy = cy_base - lift
                    draw_card(
                        surf, name, cost_val, card.desc if card else "",
                        cx, cy, CARD_W, CARD_H,
                        is_highlighted=(self.hover_pos == f"shop:{i}"),
                        can_afford=(pl.player.tokens >= cost_val and not full_now),
                    )

            # Owned jokers shown below the shop offers so the player can see
            # what they already have while deciding.
            self._draw_joker_row(surf, pl)

            # Action buttons sit ABOVE the glyph row (which lives at
            # y=JOKER_ROW_Y). Before, they were at y=SCREEN_H-100=1180
            # which collided with the glyph row at y=1166 — clicks
            # landed on whichever was drawn first and felt random.
            btn_y = JOKER_ROW_Y - 70
            reroll_btn = pygame.Rect(SCREEN_W // 2 - 220, btn_y, 200, 56)
            pygame.draw.rect(surf, (60, 60, 100), reroll_btn, border_radius=8)
            pygame.draw.rect(surf, ACCENT_GOLD, reroll_btn, 2, border_radius=8)
            free = pl.player.upgrades.get("free_rerolls", 0)
            reroll_label = f"Reroll (FREE x{free})" if free > 0 else "Reroll (2)"
            rt = pygame.font.SysFont("sans-serif", 18).render(reroll_label, True, TEXT_COLOR)
            surf.blit(rt, (reroll_btn.centerx - rt.get_width() // 2, reroll_btn.centery - rt.get_height() // 2))

            continue_btn = pygame.Rect(SCREEN_W // 2 + 20, btn_y, 200, 56)
            pygame.draw.rect(surf, ACCENT_GREEN, continue_btn, border_radius=8)
            cont_t = pygame.font.SysFont("sans-serif", 20).render("Continue", True, (0, 0, 0))
            surf.blit(cont_t, (continue_btn.centerx - cont_t.get_width() // 2, continue_btn.centery - cont_t.get_height() // 2))

        elif self.state == "gameover":
            pl = self.engine.state
            won = pl.won_run
            # Three flavours: base-win, base-fail, endless-end.
            if pl.endless_mode:
                title = "ENDLESS RUN ENDED"
                col = ACCENT_GOLD
            elif won:
                title = "RUN COMPLETE!"
                col = ACCENT_GREEN
            else:
                title = "RUN FAILED!"
                col = ACCENT_RED
            draw_big_centered_text(surf, title, self.big_font, col, 200)
            s1 = pygame.font.SysFont("sans-serif", 24).render(
                f"Score: {pl.total_score}", True, TEXT_COLOR,
            )
            surf.blit(s1, (SCREEN_W // 2 - s1.get_width() // 2, 320))
            level_label = (
                f"Reached level {pl.level}"
                if pl.endless_mode else f"Final Round: {pl.level} / {pl.max_base_level}"
            )
            s2 = pygame.font.SysFont("sans-serif", 20).render(level_label, True, TEXT_SUB)
            surf.blit(s2, (SCREEN_W // 2 - s2.get_width() // 2, 360))

            # Buttons. Always show MAIN MENU. Show CONTINUE ENDLESS only
            # when the player just won the base run (not already in
            # endless, not a failure).
            btn_w, btn_h = 240, 56
            show_endless = won and not pl.endless_mode
            if show_endless:
                endless_btn = pygame.Rect(
                    SCREEN_W // 2 - btn_w // 2, SCREEN_H - 200, btn_w, btn_h,
                )
                pygame.draw.rect(surf, ACCENT_GOLD, endless_btn, border_radius=8)
                eb_t = pygame.font.SysFont("consolas", 20, bold=True).render(
                    "CONTINUE ENDLESS", True, (0, 0, 0),
                )
                surf.blit(eb_t, (endless_btn.centerx - eb_t.get_width() // 2,
                                 endless_btn.centery - eb_t.get_height() // 2))

            btn = pygame.Rect(SCREEN_W // 2 - btn_w // 2, SCREEN_H - 120, btn_w, btn_h)
            pygame.draw.rect(surf, ACCENT_GREEN, btn, border_radius=8)
            btn_txt = self.font.render("MAIN MENU", True, (0, 0, 0))
            surf.blit(btn_txt, (btn.centerx - btn_txt.get_width() // 2,
                                btn.centery - btn_txt.get_height() // 2))

        # Joker inspect modal — drawn last so it sits above every other UI.
        self._draw_inspect_modal(surf, pl)

        pygame.display.flip()

    def handle_click(self, mx, my, mouse_btn):
        pl = self.engine.state

        # Inspect modal (glyph OR boss) takes priority over every
        # state-specific handler. The Sell button is the only
        # interactive zone inside the modal panel; everything else
        # dismisses it.
        if self._inspecting_joker:
            rects = self._inspect_modal_rects()
            if (self.state == "shop"
                    and self._inspecting_joker != "Cursed Coin"
                    and rects["sell"].collidepoint(mx, my)):
                self._sell_inspected_joker()
            else:
                self._inspecting_joker = None
            return
        if self._inspecting_boss:
            self._inspecting_boss = None
            return

        # Joker row taps in playable / shop states open the inspect modal.
        if self.state in ("game", "shop"):
            for name, rect in self._joker_row_rects(pl):
                if rect.collidepoint(mx, my):
                    self._inspecting_joker = name
                    return

        if self.state == "menu":
            btn = pygame.Rect(SCREEN_W // 2 - 160, SCREEN_H // 2 - 30, 320, 60)
            codex_btn = pygame.Rect(SCREEN_W // 2 - 120, SCREEN_H // 2 + 60, 240, 50)
            if btn.collidepoint(mx, my):
                self.new_run()
            elif codex_btn.collidepoint(mx, my):
                self.state = "codex"
                self._codex_tab = "glyphs"

        elif self.state == "codex":
            layout = self._codex_layout()
            if layout["back"].collidepoint(mx, my):
                self.state = "menu"
                return
            if layout["tab_glyphs"].collidepoint(mx, my):
                self._codex_tab = "glyphs"
                return
            if layout["tab_bosses"].collidepoint(mx, my):
                self._codex_tab = "bosses"
                return
            for name, rect in layout["chips"]:
                if rect.collidepoint(mx, my):
                    if self._codex_tab == "glyphs":
                        self._inspecting_joker = name
                    else:
                        self._inspecting_boss = name
                    return

        elif self.state == "transition":
            card_y = 460
            sx = SCREEN_W // 2 - (3 * CARD_W + 2 * 12) // 2
            for i in range(len(self.starter_cards)):
                cx = sx + i * (CARD_W + 12)
                if cx <= mx <= cx + CARD_W and card_y <= my <= card_y + CARD_H:
                    card_name = self.starter_cards[i]
                    card = get_by_name(card_name)
                    # The starter joker is FREE — no token deduction. It
                    # goes straight into passive_cards so its triggers run
                    # from the very first game.
                    pl.player.passive_cards.append(card_name)
                    self.start_game()
                    return
            # Click missed every card — ignore.
            return

        elif self.state == "boss_intro":
            # If the entrance is still playing, the first click skips it.
            if self._boss_intro_start is not None:
                elapsed = pygame.time.get_ticks() - self._boss_intro_start
                if elapsed < 900:
                    self._boss_intro_start = pygame.time.get_ticks() - 900
                    return
            pl.game_result = None
            self.showing_result = False
            # Note: pl.is_boss stays True — start_game set it because this
            # IS the boss game. Clearing it here would hide the mechanic
            # from every runtime check in evaluate_and_settle / rendering.
            self.countdown_start = pygame.time.get_ticks()
            self.state = "game"
            self._boss_intro_start = None

        elif self.state == "gameover":
            btn_w, btn_h = 240, 56
            # CONTINUE ENDLESS button — only when the player just won
            # the base run (not already endless, not a failure).
            show_endless = pl.won_run and not pl.endless_mode
            if show_endless:
                endless_btn = pygame.Rect(
                    SCREEN_W // 2 - btn_w // 2, SCREEN_H - 200, btn_w, btn_h,
                )
                if endless_btn.collidepoint(mx, my):
                    # Flip into endless mode and route back to the shop —
                    # they just beat a boss, so shop is the natural next
                    # step. Clear the run-end flags so the shop's
                    # Continue button can re-advance the level.
                    pl.endless_mode = True
                    pl.run_complete = False
                    pl.won_run = False
                    self.do_shop()
                    return
            btn = pygame.Rect(SCREEN_W // 2 - btn_w // 2, SCREEN_H - 120, btn_w, btn_h)
            if btn.collidepoint(mx, my):
                self.state = "menu"
            return

        elif self.state == "game":
            # If we're displaying a result overlay: the first click while
            # the staged reveal is still playing snaps to the end frame
            # (player wants to skip ahead). The next click advances
            # state. Compare elapsed against the slowest sub-anim (total
            # finishes at +1100 ms).
            if self.showing_result:
                staging_done = (
                    self._result_anim_start is None
                    or (pygame.time.get_ticks() - self._result_anim_start) >= 1100
                )
                if not staging_done:
                    # Snap staging to its final frame and let the next
                    # click actually dismiss the panel.
                    self._result_anim_start = pygame.time.get_ticks() - 1100
                    self.animator.finish("result_panel")
                    return
                was_boss = pl.is_boss
                run_ending = getattr(self, "_pending_run_end", False)
                self.showing_result = False
                self._result_anim_start = None
                pl.game_result = None
                self.card_system.post_game_cleanup(pl.player)
                if run_ending:
                    self._pending_run_end = False
                    self.finish_run(won=False)
                    return
                if was_boss:
                    self.do_shop()
                else:
                    self.start_game()
                return

            cell = self._cell_under(mx, my)
            if cell is not None and self.board.grid[cell[0]][cell[1]] == 0:
                row, col = cell
                # Capture the move_count BEFORE placement so we can
                # detect all marks landed during this turn (player's X
                # plus any triggered placements from Ricochet / Blind
                # Shot / Double Strike etc).
                before_marks = self.board.move_count
                placed = self.board.place_at(row, col, PLAYER_X)
                if placed:
                    pl.player.cells_played.append((row, col))

                    # Boss side-effects that follow the player's move
                    # directly. Poison TICK happens later, after the AI
                    # responds; only the REGISTER happens here.
                    if pl.is_boss and pl.current_boss:
                        bm = pl.current_boss.mechanic
                        if bm == "swap" and self.board.move_count % 3 == 0:
                            self.board.apply_swap()
                        if bm == "timed":
                            self.countdown_start = pygame.time.get_ticks()
                        if bm == "poison" and (row, col) in self.board.poison_cells:
                            self.board.register_poison_hit(row, col, ttl=2)
                        if bm == "taxman":
                            # Drain 1 token per player turn during Tax Man.
                            pl.player.tokens = max(0, pl.player.tokens - 1)
                        if bm == "spotlight":
                            # Roving zone re-anchors each player move.
                            self._spotlight_move()

                    # Fire on_x_placed jokers (Ricochet, Overload). Any
                    # triggered placements bump move_count and stamp
                    # their cells, so _animate_new_marks catches them.
                    fired = self.card_system.fire_x_placed(self.board, pl.player, row, col)
                    self._animate_new_marks(before_move_count=before_marks)
                    self._animate_jokers(fired)

                    # Tide boss: every X line completed THIS turn is
                    # scheduled for erasure in 1 AI move so the player
                    # gets the score but loses the cells.
                    if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "tide":
                        new_lines = [
                            cells for (val, cells) in self.board.get_lines()
                            if val == PLAYER_X
                        ]
                        if new_lines:
                            deadline = self.board.move_count + 1
                            for line in new_lines:
                                self._tide_clear_deadlines.append((deadline, list(line)))

                    # End immediately if the player just completed a line
                    # (or filled the last cell).
                    if self._should_evaluate():
                        self.evaluate_and_settle()
                        return

                    # Quick Draw consumes a skip stack immediately so the
                    # turn budget is honoured even though the AI move is
                    # deferred to the next frame.
                    skip_stack = pl.player.upgrades.get("skip_opponent", 0)
                    if skip_stack > 0:
                        pl.player.upgrades["skip_opponent"] = skip_stack - 1
                        # Quick Draw: AI skips this turn. Still tick poison
                        # since the "AI turn" is conceptually elapsing.
                        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "poison":
                            self.board.tick_poison()
                        if self._should_evaluate():
                            self.evaluate_and_settle()
                        return

                    # Otherwise schedule the AI's response — the per-frame
                    # tick fires it after AI_MOVE_DELAY_MS so the player
                    # sees their X land before the response.
                    self._ai_move_at = pygame.time.get_ticks() + AI_MOVE_DELAY_MS
                    return

        elif self.state == "shop":
            if self.shop_cards:
                sx = (SCREEN_W - (len(self.shop_cards) * CARD_W + max(0, len(self.shop_cards) - 1) * 12)) // 2
                for i, name in enumerate(self.shop_cards):
                    cx = sx + i * (CARD_W + 12)
                    cy = SCREEN_H // 2 - CARD_H // 2 - 20
                    if cx <= mx <= cx + CARD_W and cy <= my <= cy + CARD_H:
                        card = get_by_name(name)
                        if not card:
                            break
                        # Joker-cap gate — refuse the purchase visually if
                        # the player is at their cap.
                        if len(pl.player.passive_cards) >= pl.joker_cap:
                            self.shop_full_flash_until = pygame.time.get_ticks() + 1200
                            break
                        # Wholesaler — shop discount per copy, min cost 1.
                        discount = pl.player.upgrades.get("shop_discount", 0)
                        effective_cost = max(1 if card.cost > 0 else 0, card.cost - discount)
                        if pl.player.tokens >= effective_cost:
                            pl.player.tokens -= effective_cost
                            pl.player.passive_cards.append(card.name)
                            self.shop_cards.pop(i)
                        break

            # Reroll button — free if free_rerolls remain, else REROLL_COST.
            # Rect must match the draw layout in the shop draw branch.
            btn_y = JOKER_ROW_Y - 70
            reroll_btn = pygame.Rect(SCREEN_W // 2 - 220, btn_y, 200, 56)
            if reroll_btn.collidepoint(mx, my):
                free = pl.player.upgrades.get("free_rerolls", 0)
                if free > 0:
                    pl.player.upgrades["free_rerolls"] = free - 1
                    offer_count = 4 + pl.player.upgrades.get("shop_offer_extra", 0)
                    self.shop_cards = self._sample_shop_offers(offer_count)
                elif pl.player.tokens >= 2:
                    pl.player.tokens -= 2
                    offer_count = 4 + pl.player.upgrades.get("shop_offer_extra", 0)
                    self.shop_cards = self._sample_shop_offers(offer_count)

            cont = pygame.Rect(SCREEN_W // 2 + 20, btn_y, 200, 56)
            if cont.collidepoint(mx, my):
                pl.next_level()
                if pl.run_complete:
                    self.state = "gameover"
                else:
                    self.start_game()

    def _joker_sell_price(self, name: str) -> int:
        """Sell price for a joker — 50% of cost, rounded down. Sacrifice
        (cost -1) and any other free/refunding card sells for 0."""
        card = get_by_name(name)
        if card is None:
            return 0
        return max(0, card.cost // 2)

    def _joker_row_rects(self, pl) -> list[tuple[str, pygame.Rect]]:
        """Hit rects for each owned joker in the row. Used by the click
        handler to detect taps that open the inspect modal."""
        unique: list[str] = []
        seen: set[str] = set()
        for name in pl.player.passive_cards:
            if name not in seen:
                unique.append(name)
                seen.add(name)
        slots = pl.joker_cap
        total_w = slots * JOKER_W + (slots - 1) * JOKER_GAP
        start_x = (SCREEN_W - total_w) // 2
        rects: list[tuple[str, pygame.Rect]] = []
        for i, name in enumerate(unique):
            x = start_x + i * (JOKER_W + JOKER_GAP)
            rects.append((name, pygame.Rect(x, JOKER_ROW_Y, JOKER_W, JOKER_H)))
        return rects

    def _inspect_modal_rects(self) -> dict[str, pygame.Rect]:
        """Layout rects for the joker inspect modal. Single source of
        truth shared between draw() and the click handler."""
        w, h = 480, 600
        x = (SCREEN_W - w) // 2
        y = (SCREEN_H - h) // 2
        return {
            "panel": pygame.Rect(x, y, w, h),
            "sell": pygame.Rect(x + 40, y + h - 80, w - 80, 56),
            "close": pygame.Rect(x + w - 56, y + 12, 40, 40),
        }

    def _draw_joker_row(self, surf, pl):
        """Compact, read-only display of the player's owned jokers.
        Rendered at the bottom of the screen during gameplay and the shop.
        Empty slots up to `joker_cap` are dashed outlines."""
        unique: list[str] = []
        seen: set[str] = set()
        for name in pl.player.passive_cards:
            if name not in seen:
                unique.append(name)
                seen.add(name)
        slots = pl.joker_cap
        total_w = slots * JOKER_W + (slots - 1) * JOKER_GAP
        start_x = (SCREEN_W - total_w) // 2
        for i in range(slots):
            x = start_x + i * (JOKER_W + JOKER_GAP)
            if i < len(unique):
                name = unique[i]
                count = pl.player.passive_cards.count(name)
                # Find any active joker_glow:Name:N for this joker and
                # take the brightest (lowest eased value) — that's the
                # most-recently-fired.
                glow = 0.0
                for anim_id in self.animator.entries:
                    if anim_id.startswith(f"joker_glow:{name}:"):
                        t = self.animator.eased(anim_id)
                        if t < 1.0:
                            glow = max(glow, 1.0 - t)
                draw_joker_chip(
                    surf, name, count, x, JOKER_ROW_Y, JOKER_W, JOKER_H, glow=glow,
                )
            else:
                pygame.draw.rect(
                    surf, (50, 50, 70),
                    (x, JOKER_ROW_Y, JOKER_W, JOKER_H), 1, border_radius=6,
                )

    def _draw_inspect_modal(self, surf, pl) -> None:
        """If a glyph or boss is being inspected, paint the modal: dark
        backdrop, large card with name + (cost for glyphs) + full
        description, and (in the shop state, glyph only) a Sell button.
        Click handling matches against the rects from
        _inspect_modal_rects."""
        if self._inspecting_boss:
            self._draw_boss_inspect(surf)
            return
        if not self._inspecting_joker:
            return
        name = self._inspecting_joker
        card = get_by_name(name)
        if card is None:
            self._inspecting_joker = None
            return
        # Dim the world behind the modal.
        try:
            backdrop = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            backdrop.fill((0, 0, 0, 170))
            surf.blit(backdrop, (0, 0))
        except Exception:
            pass

        rects = self._inspect_modal_rects()
        panel = rects["panel"]
        pygame.draw.rect(surf, (16, 16, 28), panel, border_radius=12)
        pygame.draw.rect(surf, ACCENT_GOLD, panel, 2, border_radius=12)

        # Cost badge (top-left).
        cost_r = 28
        cx, cy = panel.left + 38, panel.top + 38
        pygame.draw.circle(surf, ACCENT_GOLD, (cx, cy), cost_r)
        cost_font = pygame.font.SysFont("consolas", 32, bold=True)
        cs = cost_font.render(str(card.cost), True, (0, 0, 0))
        surf.blit(cs, (cx - cs.get_width() // 2, cy - cs.get_height() // 2))

        # Close X (top-right).
        close = rects["close"]
        pygame.draw.rect(surf, (40, 40, 60), close, border_radius=6)
        x_font = pygame.font.SysFont("consolas", 22, bold=True)
        xs = x_font.render("x", True, TEXT_COLOR)
        surf.blit(xs, (close.centerx - xs.get_width() // 2,
                       close.centery - xs.get_height() // 2))

        # Name (centered, single line).
        name_font = pygame.font.SysFont("sans-serif", 32, bold=True)
        ns = name_font.render(name, True, ACCENT_GOLD)
        surf.blit(ns, (panel.centerx - ns.get_width() // 2, panel.top + 82))

        # Stack count subtitle.
        count = pl.player.passive_cards.count(name)
        sub_font = pygame.font.SysFont("sans-serif", 18)
        sub_text = f"You own: {count}" + (f"x" if count > 1 else "")
        ss = sub_font.render(sub_text, True, TEXT_SUB)
        surf.blit(ss, (panel.centerx - ss.get_width() // 2, panel.top + 124))

        # Trigger labels.
        if card.triggers:
            trig_font = pygame.font.SysFont("consolas", 14)
            trig_text = "Triggers: " + ", ".join(
                t.replace("on_", "") for t in card.triggers
            )
            ts = trig_font.render(trig_text, True, (160, 160, 200))
            surf.blit(ts, (panel.centerx - ts.get_width() // 2, panel.top + 154))

        # Description — wrapped, centered, generous width.
        from renders.rendering import draw_centered_multiline_text
        desc_font = pygame.font.SysFont("sans-serif", 20)
        draw_centered_multiline_text(
            surf, card.desc or "", desc_font, TEXT_COLOR,
            panel.top + 196, max_width=panel.width - 48, max_lines=12,
        )

        # Sell button — only shown in the shop, and only if this joker is
        # sellable. Cursed Coin specifically resists.
        if self.state == "shop" and name != "Cursed Coin":
            sell = rects["sell"]
            price = self._joker_sell_price(name)
            pygame.draw.rect(surf, ACCENT_RED, sell, border_radius=8)
            pygame.draw.rect(surf, (255, 220, 220), sell, 2, border_radius=8)
            label_font = pygame.font.SysFont("consolas", 22, bold=True)
            label = label_font.render(f"SELL  +{price} tokens", True, (0, 0, 0))
            surf.blit(label, (sell.centerx - label.get_width() // 2,
                              sell.centery - label.get_height() // 2))
        elif self.state == "shop" and name == "Cursed Coin":
            # Make the curse explicit — no sell option.
            warn_font = pygame.font.SysFont("consolas", 16, bold=True)
            ws = warn_font.render("Cannot be sold", True, ACCENT_RED)
            surf.blit(ws, (panel.centerx - ws.get_width() // 2,
                           panel.bottom - 50))

    def _codex_layout(self) -> dict:
        """Single source of truth for the codex screen's hit rects.
        Returns: header rects (tab buttons + back), and per-entry chip
        rects for whichever tab is active."""
        chip_w, chip_h = 92, 90
        chip_gap = 10
        cols = 6
        top_y = 200  # below the tab strip
        layout: dict = {
            "back": pygame.Rect(20, 20, 100, 44),
            "tab_glyphs": pygame.Rect(SCREEN_W // 2 - 180, 90, 170, 50),
            "tab_bosses": pygame.Rect(SCREEN_W // 2 + 10, 90, 170, 50),
            "chips": [],
        }
        if self._codex_tab == "glyphs":
            entries = [c.name for c in ALL_CARDS]
        else:
            from config.bosses import BOSS_LIST
            entries = [b.name for b in BOSS_LIST]
        total_row_w = cols * chip_w + (cols - 1) * chip_gap
        start_x = (SCREEN_W - total_row_w) // 2
        for i, name in enumerate(entries):
            row = i // cols
            col = i % cols
            x = start_x + col * (chip_w + chip_gap)
            y = top_y + row * (chip_h + chip_gap)
            layout["chips"].append((name, pygame.Rect(x, y, chip_w, chip_h)))
        return layout

    def _draw_codex(self, surf) -> None:
        """Browser of every glyph and every boss modifier. Reachable from
        the main menu so players can study the full pool before
        committing to a run."""
        draw_big_centered_text(surf, "CODEX", self.big_font, ACCENT_GOLD, 20)

        layout = self._codex_layout()

        # Back button.
        back = layout["back"]
        pygame.draw.rect(surf, (40, 40, 60), back, border_radius=8)
        pygame.draw.rect(surf, ACCENT_GOLD, back, 2, border_radius=8)
        bf = self.font.render("BACK", True, TEXT_COLOR)
        surf.blit(bf, (back.centerx - bf.get_width() // 2,
                       back.centery - bf.get_height() // 2))

        # Tabs.
        for key, rect, label in (
            ("glyphs", layout["tab_glyphs"], "GLYPHS"),
            ("bosses", layout["tab_bosses"], "BOSSES"),
        ):
            active = self._codex_tab == key
            bg = (60, 60, 100) if active else (28, 28, 48)
            border = ACCENT_GOLD if active else (90, 90, 130)
            pygame.draw.rect(surf, bg, rect, border_radius=8)
            pygame.draw.rect(surf, border, rect, 2, border_radius=8)
            ts = pygame.font.SysFont("consolas", 22, bold=True).render(
                label, True, ACCENT_GOLD if active else TEXT_SUB,
            )
            surf.blit(ts, (rect.centerx - ts.get_width() // 2,
                           rect.centery - ts.get_height() // 2))

        # Per-entry chips.
        if self._codex_tab == "glyphs":
            for name, rect in layout["chips"]:
                count = 0  # codex is meta — no stack count
                draw_joker_chip(surf, name, count, rect.x, rect.y, rect.w, rect.h)
        else:
            from config.bosses import BOSS_MAP
            for name, rect in layout["chips"]:
                # Boss "chip" — same dimensions, distinct red border to
                # match the in-game BOSS banner colour.
                pygame.draw.rect(surf, (35, 35, 60), rect, border_radius=6)
                pygame.draw.rect(surf, ACCENT_RED, rect, 2, border_radius=6)
                from renders.rendering import _wrap_lines
                name_font = pygame.font.SysFont("sans-serif", 14, bold=True)
                lines = _wrap_lines(name, name_font, rect.w - 8)
                for li, line in enumerate(lines[:3]):
                    ts = name_font.render(line, True, TEXT_COLOR)
                    surf.blit(ts, (rect.x + 6,
                                   rect.y + 6 + li * name_font.get_linesize()))

    def _draw_boss_inspect(self, surf) -> None:
        """Boss inspect modal — opened from the codex's bosses tab.
        Shows the boss's name, tagline, and mechanic description."""
        name = self._inspecting_boss
        from config.bosses import BOSS_MAP
        boss = None
        for b in BOSS_MAP.values():
            if b.name == name:
                boss = b
                break
        if boss is None:
            self._inspecting_boss = None
            return
        try:
            backdrop = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            backdrop.fill((0, 0, 0, 170))
            surf.blit(backdrop, (0, 0))
        except Exception:
            pass
        rects = self._inspect_modal_rects()
        panel = rects["panel"]
        pygame.draw.rect(surf, (16, 16, 28), panel, border_radius=12)
        pygame.draw.rect(surf, ACCENT_RED, panel, 2, border_radius=12)

        # Close X.
        close = rects["close"]
        pygame.draw.rect(surf, (40, 40, 60), close, border_radius=6)
        x_font = pygame.font.SysFont("consolas", 22, bold=True)
        xs = x_font.render("x", True, TEXT_COLOR)
        surf.blit(xs, (close.centerx - xs.get_width() // 2,
                       close.centery - xs.get_height() // 2))

        # "BOSS" eyebrow + name.
        eye = pygame.font.SysFont("consolas", 16, bold=True).render(
            "BOSS GAME", True, ACCENT_RED,
        )
        surf.blit(eye, (panel.centerx - eye.get_width() // 2, panel.top + 24))
        name_font = pygame.font.SysFont("sans-serif", 34, bold=True)
        ns = name_font.render(boss.name, True, ACCENT_GOLD)
        surf.blit(ns, (panel.centerx - ns.get_width() // 2, panel.top + 56))

        # Tagline.
        tag_font = pygame.font.SysFont("sans-serif", 18, bold=False)
        tg = tag_font.render(boss.tagline, True, TEXT_SUB)
        surf.blit(tg, (panel.centerx - tg.get_width() // 2, panel.top + 108))

        # Mechanic label.
        mech_font = pygame.font.SysFont("consolas", 14)
        mt = mech_font.render(f"mechanic: {boss.mechanic}", True, (160, 160, 200))
        surf.blit(mt, (panel.centerx - mt.get_width() // 2, panel.top + 142))

        # Description.
        from renders.rendering import draw_centered_multiline_text
        desc_font = pygame.font.SysFont("sans-serif", 20)
        draw_centered_multiline_text(
            surf, boss.desc or "", desc_font, TEXT_COLOR,
            panel.top + 180, max_width=panel.width - 48, max_lines=14,
        )

    def _sell_inspected_joker(self) -> None:
        """Remove ONE copy of the inspected joker, credit 50% of its
        cost. Closes the modal. Cursed Coin can't be sold."""
        name = self._inspecting_joker
        if not name or name == "Cursed Coin":
            return
        pl = self.engine.state
        if name not in pl.player.passive_cards:
            self._inspecting_joker = None
            return
        pl.player.tokens += self._joker_sell_price(name)
        pl.player.passive_cards.remove(name)
        # Re-seed upgrade counters since a passive card just left the
        # build — otherwise old stack counts linger.
        self.card_system.apply_passive_buffs(pl.player)
        self._inspecting_joker = None

    def handle_motion(self, mx, my):
        self.hover_pos = None

        if self.state in ("countdown", "game"):
            cell = self._cell_under(mx, my)
            if cell is not None:
                self.hover_pos = cell
        elif self.state == "shop" and self.shop_cards:
            sx = (SCREEN_W - (len(self.shop_cards) * CARD_W + max(0, len(self.shop_cards) - 1) * 12)) // 2
            cy = SCREEN_H // 2 - CARD_H // 2 - 20
            for i in range(len(self.shop_cards)):
                cx = sx + i * (CARD_W + 12)
                # Hit-test against the lifted hover position too (cy - 8).
                if cx <= mx <= cx + CARD_W and (cy - 8) <= my <= cy + CARD_H:
                    self.hover_pos = f"shop:{i}"
                    break

    async def run(self):
        # Async so the browser event loop can yield each frame under
        # pygbag/WebAssembly. On desktop, asyncio.run drives it identically.
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    return
                elif ev.type == pygame.MOUSEMOTION:
                    self.handle_motion(ev.pos[0], ev.pos[1])
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self.handle_click(ev.pos[0], ev.pos[1], 1)

            # Per-frame updates that don't depend on input: AI move
            # scheduling, animation GC.
            self._tick_ai_move()
            self.animator.gc()

            self.draw()
            self.clock.tick(60)
            await asyncio.sleep(0)


async def main():
    await GameEngine().run()


if __name__ == "__main__":
    asyncio.run(main())
