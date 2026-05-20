import asyncio
import pygame
import random
from game.board import Board, PLAYER_X, OPPONENT_O
from game.opponent import OpponentAI
from systems.cardsystem import CardSystem
from systems.roguelite import RogueliteEngine
from save.savesetup import save_progression, get_unlocked_cards
from config.constants import (
    SCREEN_W, SCREEN_H, BG_COLOR, TEXT_COLOR, TEXT_SUB,
    ACCENT_GOLD, ACCENT_GREEN, ACCENT_RED, COLOR_X, COLOR_O,
    CARD_W, CARD_H,
)
from config.cards import pick_random, get_by_name
from config.bosses import BOSS_LIST
from renders.rendering import (
    draw_card, draw_score, draw_tokens,
    draw_centered_text, draw_big_centered_text, draw_centered_multiline_text,
    draw_joker_chip,
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

        # every 3rd game is a boss — set the boss state BEFORE firing
        # game-start triggers so on_game_start handlers see is_boss=True
        # (some triggers may want to behave differently in boss games).
        if pl.games_in_level % 3 == 0:
            pl.boss_index = pl.games_in_level // 3 - 1
            boss = BOSS_LIST[pl.boss_index % len(BOSS_LIST)]
            pl.current_boss = boss
            pl.ante_target = pl.get_ante_target()
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

            pl.is_boss = True
            self.state = "boss_intro"
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
        self.card_system.fire_game_start(self.board, pl.player)

    def do_shop(self):
        pl = self.engine.state
        pl.shop_phase = True
        # Reset shop-only consumables, then let the on_shop_open jokers
        # (Reroll, Card Draw) seed them for this visit.
        pl.player.upgrades["free_rerolls"] = 0
        pl.player.upgrades["shop_offer_extra"] = 0
        self.card_system.fire_shop_open(pl.player)
        offer_count = 4 + pl.player.upgrades.get("shop_offer_extra", 0)
        self.shop_cards = pick_random(offer_count)
        self.state = "shop"

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
        # so the line-extending flips count toward this game's ink.
        x_lines_for_triggers = [
            cells for (val, cells) in self.board.get_lines() if val == PLAYER_X
        ]
        for line in x_lines_for_triggers:
            self.card_system.fire_line_completed(self.board, pl.player, line)

        # Single ink × mult scoring pass for the current board state.
        ink, mult, total = self.card_system.score_breakdown(
            self.board, pl.player, pl.get_multiplier(),
            is_boss=is_boss,
            boss_mechanic=pl.current_boss.mechanic if pl.current_boss else None,
        )
        pl.last_ink = ink
        pl.last_mult = mult
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
                row_shift, col_shift = self.board.grow_row_and_column()
                if row_shift or col_shift:
                    pl.player.cells_played = [
                        (r + row_shift, c + col_shift) for (r, c) in pl.player.cells_played
                    ]
                    pl.player.blind_shot_marks = [
                        (r + row_shift, c + col_shift) for (r, c) in pl.player.blind_shot_marks
                    ]
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
            pl.draw_multiplier = 1.0
        else:  # lose
            pl.draw_multiplier = 1.0
            pl.lives -= 1

        pl.game_result = outcome
        self.showing_result = True
        self.board.game_over = True

        # Run-ending failure modes — ante failure on a boss, or zero lives.
        if ante_failed or pl.lives <= 0:
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

        pl = self.engine.state

        if self.state == "menu":
            draw_big_centered_text(surf, "CROSSED OUT", self.big_font, ACCENT_GOLD, 180)
            draw_centered_text(surf, "A Roguelite Tic-Tac-Toe Game", self.font, TEXT_SUB, 260)

            btn_h = pygame.font.SysFont("consolas", 32).render("START NEW RUN", True, (0, 0, 0))
            btn = pygame.Rect(SCREEN_W // 2 - 160, SCREEN_H // 2 - 30, 320, 60)
            pygame.draw.rect(surf, ACCENT_GREEN, btn, border_radius=10)
            surf.blit(btn_h, (SCREEN_W // 2 - btn_h.get_width() // 2, btn.centery - 16))

            desc = self.font.render("Click [X] on the grid to play. Play cards to gain advantage.", True, TEXT_SUB)
            surf.blit(desc, (SCREEN_W // 2 - desc.get_width() // 2, SCREEN_H // 2 + 60))

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
            draw_big_centered_text(surf, "BOSS GAME", self.big_font, ACCENT_RED, 150)
            draw_centered_text(surf, boss.name, pygame.font.SysFont("consolas", 36), ACCENT_GOLD, 260)
            # boss.desc can run several lines long — wrap it to the canvas
            # width so the screen doesn't truncate mid-sentence.
            draw_centered_multiline_text(
                surf, boss.desc, self.font, TEXT_SUB, 330,
                max_width=SCREEN_W - 80,
            )
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
            for (r, c) in self.board.valid_cells:
                x = off_x + c * avail
                y = off_y + r * avail
                pygame.draw.rect(surf, (28, 28, 48), (x, y, avail, avail), border_radius=4)

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
                    if val == PLAYER_X:
                        m = avail // 4
                        pygame.draw.line(surf, color, (x + m, y + m), (x + avail - m, y + avail - m), 4)
                        pygame.draw.line(surf, color, (x + m, y + avail - m), (x + avail - m, y + m), 4)
                    else:
                        pygame.draw.circle(surf, color, (x + avail // 2, y + avail // 2), avail // 3, 4)

                # Weighted boss: print each cell's weight in the corner.
                if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "weighted":
                    try:
                        w = self.board.weights[r][c]
                    except (IndexError, AttributeError):
                        w = 1
                    if w > 1:
                        wf = pygame.font.SysFont("consolas", 14).render(str(w), True, ACCENT_GOLD)
                        surf.blit(wf, (x + 4, y + 4))

                # hover highlight
                if self.hover_pos == (r, c) and not self.showing_result:
                    pygame.draw.rect(surf, ACCENT_GOLD, (x, y, avail, avail), 2, border_radius=4)
                # newly-added cell glow during the draw transition
                if new_cell_glow == (r, c):
                    pygame.draw.rect(surf, ACCENT_GOLD, (x, y, avail, avail), 3, border_radius=4)

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
                if i < pl.lives:
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
                    ai = OpponentAI(self.board, fade_age=self._ai_fade_age())
                    move = ai.get_best_move()
                    if move:
                        self.board.place_at(move[0], move[1], OPPONENT_O)
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
            # never overlaps placed marks.
            if self.showing_result:
                result = pl.game_result
                txt_map = {"win": ("VICTORY!", ACCENT_GREEN), "lose": ("DEFEAT!", ACCENT_RED)}
                if result in txt_map:
                    txt, col = txt_map[result]
                    board_bottom = off_y + self.board.rows * avail
                    panel_top = board_bottom + 12
                    panel_h = max(120, JOKER_ROW_Y - panel_top - 12)
                    panel_w = SCREEN_W - 40
                    panel_x = (SCREEN_W - panel_w) // 2
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
                    ink_mult_text = f"Ink {pl.last_ink}  ×  Mult {pl.last_mult:g}  =  {pl.score_this_game}"
                    bd = pygame.font.SysFont("consolas", 22).render(ink_mult_text, True, ACCENT_GOLD)
                    surf.blit(bd, (SCREEN_W // 2 - bd.get_width() // 2, panel_top + 58))
                    if self._pending_run_end:
                        reason = (
                            "Failed boss ante" if pl.is_boss and pl.score_this_game < pl.ante_target
                            else "Out of lives"
                        )
                        rs = self.font.render(reason, True, ACCENT_RED)
                        surf.blit(rs, (SCREEN_W // 2 - rs.get_width() // 2, panel_top + 88))
                        end_txt = self.font.render(
                            "Run failed — click to return to menu", True, TEXT_SUB,
                        )
                        surf.blit(end_txt, (SCREEN_W // 2 - end_txt.get_width() // 2, panel_top + panel_h - 28))
                    else:
                        cont = self.font.render("Click to continue", True, TEXT_SUB)
                        surf.blit(cont, (SCREEN_W // 2 - cont.get_width() // 2, panel_top + panel_h - 28))

        elif self.state == "shop":
            draw_centered_text(surf, "SHOP", pygame.font.SysFont("consolas", 40), ACCENT_GOLD, 50)
            draw_tokens(surf, pl.player.tokens, SCREEN_W - 200, 30)
            # Joker cap progress in the top-left.
            cap_txt = self.font.render(
                f"Jokers: {len(pl.player.passive_cards)}/{pl.joker_cap}", True, TEXT_COLOR,
            )
            surf.blit(cap_txt, (20, 40))
            full_now = len(pl.player.passive_cards) >= pl.joker_cap
            if full_now and pygame.time.get_ticks() < self.shop_full_flash_until:
                flash = pygame.font.SysFont("consolas", 24).render(
                    "JOKER ROW FULL", True, ACCENT_RED,
                )
                surf.blit(flash, (SCREEN_W // 2 - flash.get_width() // 2, 110))

            if self.shop_cards:
                sx = (SCREEN_W - (len(self.shop_cards) * CARD_W + max(0, len(self.shop_cards) - 1) * 12)) // 2
                for i, name in enumerate(self.shop_cards):
                    card = get_by_name(name)
                    cost_val = card.cost if card else 0
                    cx = sx + i * (CARD_W + 12)
                    cy = SCREEN_H // 2 - CARD_H // 2 - 20
                    draw_card(
                        surf, name, cost_val, card.desc if card else "",
                        cx, cy, CARD_W, CARD_H,
                        is_highlighted=(self.hover_pos == f"shop:{i}"),
                        can_afford=(pl.player.tokens >= cost_val and not full_now),
                    )

            # Owned jokers shown below the shop offers so the player can see
            # what they already have while deciding.
            self._draw_joker_row(surf, pl)

            # Reroll button (free uses indicated when available).
            reroll_btn = pygame.Rect(SCREEN_W // 2 - 230, SCREEN_H - 100, 140, 50)
            pygame.draw.rect(surf, (60, 60, 100), reroll_btn, border_radius=8)
            free = pl.player.upgrades.get("free_rerolls", 0)
            reroll_label = f"Reroll (FREE x{free})" if free > 0 else "Reroll (2)"
            rt = pygame.font.SysFont("sans-serif", 18).render(reroll_label, True, TEXT_COLOR)
            surf.blit(rt, (reroll_btn.centerx - rt.get_width() // 2, reroll_btn.centery - rt.get_height() // 2))

            continue_btn = pygame.Rect(SCREEN_W // 2 - 80, SCREEN_H - 100, 160, 50)
            pygame.draw.rect(surf, ACCENT_GREEN, continue_btn, border_radius=8)
            cont_t = pygame.font.SysFont("sans-serif", 20).render("Continue", True, (0, 0, 0))
            surf.blit(cont_t, (continue_btn.centerx - cont_t.get_width() // 2, continue_btn.centery - cont_t.get_height() // 2))

        elif self.state == "gameover":
            pl = self.engine.state
            won = pl.won_run
            txt = "RUN COMPLETE!" if won else "RUN FAILED!"
            col = ACCENT_GREEN if won else ACCENT_RED
            draw_big_centered_text(surf, txt, self.big_font, col, 200)
            s1 = pygame.font.SysFont("sans-serif", 24).render(f"Score: {pl.total_score}", True, TEXT_COLOR)
            surf.blit(s1, (SCREEN_W // 2 - s1.get_width() // 2, 320))
            s2 = pygame.font.SysFont("sans-serif", 20).render(f"Final Level: {pl.level}  |  Draw Penalty: {100 - int((1 - pl.draw_multiplier) * 100):.0f}%", True, TEXT_SUB)
            surf.blit(s2, (SCREEN_W // 2 - s2.get_width() // 2, 360))
            
            btn_w, btn_h = 200, 50
            btn = pygame.Rect(SCREEN_W // 2 - btn_w // 2, SCREEN_H - 120, btn_w, btn_h)
            hover_color = ACCENT_GOLD if self.hover_pos and btn.collidepoint(pygame.mouse.get_pos()) else ACCENT_GREEN
            pygame.draw.rect(surf, hover_color, btn, border_radius=8)
            btn_txt = self.font.render("MAIN MENU", True, (0, 0, 0))
            surf.blit(btn_txt, (btn.centerx - btn_txt.get_width() // 2, btn.centery - btn_txt.get_height() // 2))

        pygame.display.flip()

    def handle_click(self, mx, my, mouse_btn):
        pl = self.engine.state

        if self.state == "menu":
            btn = pygame.Rect(SCREEN_W // 2 - 160, SCREEN_H // 2 - 30, 320, 60)
            if btn.collidepoint(mx, my):
                self.new_run()

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
            pl.game_result = None
            self.showing_result = False
            # Note: pl.is_boss stays True — start_game set it because this
            # IS the boss game. Clearing it here would hide the mechanic
            # from every runtime check in evaluate_and_settle / rendering.
            self.countdown_start = pygame.time.get_ticks()
            self.state = "game"

        elif self.state == "gameover":
            b_w, b_h = 200, 50
            btn = pygame.Rect(SCREEN_W // 2 - b_w // 2, SCREEN_H - 120, b_w, b_h)
            if btn.collidepoint(mx, my):
                self.state = "menu"
            return

        elif self.state == "game":
            # If we're displaying a result overlay, any click advances to the next phase.
            if self.showing_result:
                was_boss = pl.is_boss
                run_ending = getattr(self, "_pending_run_end", False)
                self.showing_result = False
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
                placed = self.board.place_at(row, col, PLAYER_X)
                if placed:
                    pl.player.cells_played.append((row, col))

                    if pl.is_boss and pl.current_boss:
                        if pl.current_boss.mechanic == "swap" and self.board.move_count % 3 == 0:
                            self.board.apply_swap()
                        if pl.current_boss.mechanic == "timed":
                            self.countdown_start = pygame.time.get_ticks()
                        if pl.current_boss.mechanic == "poison" and (row, col) in self.board.poison_cells:
                            self.board.register_poison_hit(row, col, ttl=2)

                    # Fire on_x_placed jokers (Ricochet, Overload).
                    self.card_system.fire_x_placed(self.board, pl.player, row, col)

                    # End immediately if the player just completed a line
                    # (or filled the last cell).
                    if self._should_evaluate():
                        self.evaluate_and_settle()
                        return

                    # Quick Draw can skip the AI's response.
                    skip_stack = pl.player.upgrades.get("skip_opponent", 0)
                    if skip_stack > 0:
                        pl.player.upgrades["skip_opponent"] = skip_stack - 1
                    else:
                        ai = OpponentAI(self.board, fade_age=self._ai_fade_age())
                        move = ai.get_best_move()
                        if move:
                            self.board.place_at(move[0], move[1], OPPONENT_O)

                    # Poison ticks down after the AI takes its turn.
                    if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "poison":
                        self.board.tick_poison()

                    if self._should_evaluate():
                        self.evaluate_and_settle()
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
                        if pl.player.tokens >= card.cost:
                            pl.player.tokens -= card.cost
                            pl.player.passive_cards.append(card.name)
                            self.shop_cards.pop(i)
                        break

            # Reroll button — free if free_rerolls remain, else REROLL_COST.
            reroll_btn = pygame.Rect(SCREEN_W // 2 - 230, SCREEN_H - 100, 140, 50)
            if reroll_btn.collidepoint(mx, my):
                free = pl.player.upgrades.get("free_rerolls", 0)
                if free > 0:
                    pl.player.upgrades["free_rerolls"] = free - 1
                    offer_count = 4 + pl.player.upgrades.get("shop_offer_extra", 0)
                    self.shop_cards = pick_random(offer_count)
                elif pl.player.tokens >= 2:
                    pl.player.tokens -= 2
                    offer_count = 4 + pl.player.upgrades.get("shop_offer_extra", 0)
                    self.shop_cards = pick_random(offer_count)

            cont = pygame.Rect(SCREEN_W // 2 - 80, SCREEN_H - 100, 160, 50)
            if cont.collidepoint(mx, my):
                pl.next_level()
                if pl.run_complete:
                    self.state = "gameover"
                else:
                    self.start_game()

        elif self.state == "gameover":
            self.state = "menu"

    def _draw_joker_row(self, surf, pl):
        """Compact, read-only display of the player's owned jokers.
        Rendered at the bottom of the screen during gameplay and the shop.
        Empty slots up to `joker_cap` are dashed outlines."""
        # Collect unique jokers preserving purchase order.
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
                draw_joker_chip(surf, name, count, x, JOKER_ROW_Y, JOKER_W, JOKER_H)
            else:
                # Empty slot — dashed outline.
                pygame.draw.rect(
                    surf, (50, 50, 70),
                    (x, JOKER_ROW_Y, JOKER_W, JOKER_H), 1, border_radius=6,
                )

    def handle_motion(self, mx, my):
        self.hover_pos = None

        if self.state in ("countdown", "game"):
            cell = self._cell_under(mx, my)
            if cell is not None:
                self.hover_pos = cell

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

            self.draw()
            self.clock.tick(60)
            await asyncio.sleep(0)


async def main():
    await GameEngine().run()


if __name__ == "__main__":
    asyncio.run(main())
