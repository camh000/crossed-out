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
    draw_centered_text, draw_big_centered_text,
)


class GameEngine:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("CROSSED OUT")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("sans-serif", 20)
        self.big_font = pygame.font.SysFont("consolas", 56)

        self.engine = RogueliteEngine()
        self.card_system = CardSystem(hand_size=4)

        self.state = "menu"
        self.board = Board()
        self.hover_pos = None
        self.starter_cards = []
        self.shop_cards = []

        # card slot tracking
        self.card_played_this_turn = False
        self.player_placed_this_turn = False

        # countdown state
        self.countdown_start = None

        # result display
        self.showing_result = False

        # transient "grid grew on draw" overlay
        self.draw_message_until = 0
        self.draw_message_cell = None

    def new_run(self):
        self.engine.start_new_run()
        pl = self.engine.state.player
        pl.deck = self.card_system.generate_deck()
        unlocked = get_unlocked_cards()
        pl.deck.extend([c for c in unlocked if c not in pl.deck])
        pl.deck = list(set(pl.deck))
        self.starter_cards = pick_random(3)
        self.state = "transition"

    def start_game(self):
        pl = self.engine.state
        pl.games_in_level += 1
        gs = pl.get_grid_size()
        self.board.reset(gs)
        pl.current_target = pl.get_target()
        # Per-game score resets so the win check stays per-game; the
        # per-level total lives on score_this_level.
        pl.player.score = 0

        # every 3rd game is a boss
        if pl.games_in_level % 3 == 0:
            pl.boss_index = pl.games_in_level // 3 - 1
            boss = BOSS_LIST[pl.boss_index % len(BOSS_LIST)]
            pl.current_boss = boss
            self.engine.current_boss_mechanic = boss.mechanic

            # apply boss-specific setup
            empty = self.board.get_empty_cells()
            if boss.mechanic == "poison":
                self.board.poison_cells = random.sample(empty, min(3, len(empty)))
            if pl.current_boss.mechanic == "timed":
                self.countdown_start = pygame.time.get_ticks()
            if pl.is_boss:
                pl.current_boss_setup = boss.mechanic
            if pl.current_boss.mechanic == "swap":
                self.board.swap_counter = 0

            pl.is_boss = True
            self.state = "boss_intro"
        else:
            pl.is_boss = False
            pl.shop_phase = False
            self.state = "countdown"
            self.countdown_start = pygame.time.get_ticks()

    def do_shop(self):
        pl = self.engine.state
        pl.shop_phase = True
        self.shop_cards = pick_random(4)
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

    def _should_evaluate(self) -> bool:
        """End the game on the first completed line, or when the board fills.

        Mirror boss is the exception — the player fills the board for both
        sides and the outcome depends on the net X−O line count, so play
        continues even when a line forms mid-game.
        """
        if self.board.is_full():
            return True
        pl = self.engine.state
        if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "mirror":
            return False
        return (
            self.board.count_lines_for(PLAYER_X) > 0
            or self.board.count_lines_for(OPPONENT_O) > 0
        )

    def evaluate_and_settle(self):
        pl = self.engine.state
        base_reward = 2

        if pl.is_boss and pl.current_boss:
            result = self._evaluate_boss()
        else:
            # normal game: compare lines. Outcome is purely tic-tac-toe;
            # the level score target lives on score_this_level and only
            # gates run progression (see RunState.next_level).
            xp_lines = self.board.count_lines_for(PLAYER_X)
            op_lines = self.board.count_lines_for(OPPONENT_O)
            score = self.card_system.calculate_score(self.board, pl.player, pl.get_multiplier())
            pl.total_score += score
            pl.player.score += score
            pl.score_this_level += score

            if xp_lines > op_lines:
                result = "win"
            elif xp_lines < op_lines:
                result = "lose"
            else:
                result = "draw"

        if result == "draw":
            # Grid grows by a full new row and a full new column on random
            # sides, giving both players room to manoeuvre on the next turns.
            # Each draw compounds a 10% penalty on the eventual win reward;
            # a win or loss resets it.
            pl.draw_multiplier *= 0.9
            row_shift, col_shift = self.board.grow_row_and_column()
            if row_shift or col_shift:
                pl.player.cells_played = [
                    (r + row_shift, c + col_shift) for (r, c) in pl.player.cells_played
                ]
            self.board.game_over = False
            self.showing_result = False
            self.player_placed_this_turn = False
            self.card_played_this_turn = False
            pl.game_result = "draw"
            self.draw_message_until = pygame.time.get_ticks() + 1500
            self.draw_message_cell = None
            return result

        if result == "win":
            pl.player.tokens += max(1, round(base_reward * pl.draw_multiplier))
            pl.draw_multiplier = 1.0
        else:
            pl.draw_multiplier = 1.0

        pl.game_result = result
        self.showing_result = True
        self.board.game_over = True
        return result

    def _evaluate_boss(self):
        pl = self.engine.state
        boss = pl.current_boss
        bs = self.board.size

        if boss.mechanic == "doublecross":
            # first to complete a line wins
            xp = self.board.count_lines_for(PLAYER_X)
            op = self.board.count_lines_for(OPPONENT_O)
            if xp >= 1 and op >= 1:
                self.card_system.calculate_score(self.board, pl.player, pl.get_multiplier())
                return "win" if pl.player.score >= pl.current_target else "lose"
            # check if board full
            if self.board.is_full():
                return "draw"
            if xp > op:
                return "win"
            if op > xp:
                return "lose"

        elif boss.mechanic == "mirror":
            xp = self.board.count_lines_for(PLAYER_X)
            op = self.board.count_lines_for(OPPONENT_O)
            win_lines = max(0, xp - op)
            score = win_lines * bs * pl.get_multiplier()
            pl.total_score += score
            pl.player.score += score
            pl.score_this_level += score
            return "win" if win_lines > 0 else "draw"

        elif boss.mechanic == "timed" or boss.mechanic == "swap":
            xp = self.board.count_lines_for(PLAYER_X)
            op = self.board.count_lines_for(OPPONENT_O)
            if xp > op:
                score = self.card_system.calculate_score(self.board, pl.player, pl.get_multiplier())
                pl.total_score += score
                pl.player.score += score
                pl.score_this_level += score
                return "win"
            elif xp == op and self.board.is_full():
                score = self.card_system.calculate_score(self.board, pl.player, pl.get_multiplier())
                pl.total_score += score
                pl.player.score += score
                pl.score_this_level += score
                return "draw"
            else:
                op_lines = self.board.get_lines()
                for v, cells in op_lines:
                    if v == OPPONENT_O and PLAYER_X not in [self.board.grid[r][c] for r, c in cells]:
                        return "lose"

        else:
            # Default / "blind" / "weighted" / "poison" / "ghost_wall": play
            # tic-tac-toe — outcome decided by line counts on the final board.
            xp = self.board.count_lines_for(PLAYER_X)
            op = self.board.count_lines_for(OPPONENT_O)
            score = self.card_system.calculate_score(self.board, pl.player, pl.get_multiplier())
            pl.total_score += score
            pl.player.score += score
            pl.score_this_level += score
            if xp > op:
                return "win"
            if xp < op:
                return "lose"
            return "draw"

        if self.board.is_full():
            if xp > op:
                score = self.card_system.calculate_score(self.board, pl.player, pl.get_multiplier())
                pl.total_score += score
                pl.player.score += score
                pl.score_this_level += score
                return "win"
            elif xp == op:
                return "draw"
        return "lose"

    def _check_boss_continue(self, boss):
        if boss.mechanic == "doublecross":
            xp = self.board.count_lines_for(PLAYER_X)
            op = self.board.count_lines_for(OPPONENT_O)
            return xp < 1 or op < 1
        return not self.board.is_full()

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
            draw_big_centered_text(surf, f"Level {lv}", self.big_font, ACCENT_GOLD, 100)
            draw_centered_text(surf, f"{gs}x{gs} Grid", self.font, TEXT_COLOR, 180)
            pick_text = self.font.render("Choose a starting card:", True, TEXT_SUB)
            surf.blit(pick_text, (SCREEN_W // 2 - pick_text.get_width() // 2, 280))

            sx = SCREEN_W // 2 - (3 * CARD_W) // 2
            for i, name in enumerate(self.starter_cards):
                card = get_by_name(name)
                cx = sx + i * (CARD_W + 12)
                draw_card(
                    surf, name, card.cost if card else 0, card.desc if card else "",
                    cx, 320, CARD_W, CARD_H,
                    is_highlighted=(self.hover_pos == f"starter:{i}"),
                    can_afford=True,
                )

        elif self.state == "boss_intro":
            boss = pl.current_boss
            draw_big_centered_text(surf, "BOSS GAME", self.big_font, ACCENT_RED, 150)
            draw_centered_text(surf, boss.name, pygame.font.SysFont("consolas", 36), ACCENT_GOLD, 260)
            draw_centered_text(surf, boss.desc, self.font, TEXT_SUB, 330)
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

                val = self.board.grid[r][c]
                if val != 0:
                    color = COLOR_X if val == PLAYER_X else COLOR_O
                    if pl.current_boss and pl.current_boss.mechanic == "poison" and (r, c) in self.board.poison_cells:
                        ps = avail // 5
                        pygame.draw.rect(surf, (80, 180, 60), (x + avail//2 - ps//2, y + avail//2 - ps//2, ps, ps), border_radius=3)
                    if val == PLAYER_X:
                        m = avail // 4
                        pygame.draw.line(surf, color, (x + m, y + m), (x + avail - m, y + avail - m), 4)
                        pygame.draw.line(surf, color, (x + m, y + avail - m), (x + avail - m, y + m), 4)
                    else:
                        pygame.draw.circle(surf, color, (x + avail // 2, y + avail // 2), avail // 3, 4)

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
            if pl.current_boss:
                boss_txt = self.font.render(f"BOSS: {pl.current_boss.name}", True, ACCENT_RED)
                surf.blit(boss_txt, (SCREEN_W - 10 - boss_txt.get_width(), 60))

            # timed boss countdown
            if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "timed" and self.countdown_start:
                elapsed = (pygame.time.get_ticks() - self.countdown_start) / 1000
                remaining = 5 - elapsed
                if remaining > 0 and not self.board.game_over:
                    ts = pygame.font.SysFont("consolas", 48).render(f"{remaining:.0f}", True, ACCENT_RED)
                    surf.blit(ts, (SCREEN_W // 2 - ts.get_width() // 2, SCREEN_H // 2 - 100))
                    if remaining <= 0:
                        # auto opponent move
                        ai = OpponentAI(self.board)
                        move = ai.get_best_move()
                        if move:
                            self.board.place_at(move[0], move[1], OPPONENT_O)
                            self.countdown_start = pygame.time.get_ticks()
            if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "timed":
                # restart countdown for timed boss after each move
                pass

            # swap boss tick
            if pl.is_boss and pl.current_boss and pl.current_boss.mechanic == "swap":
                if self.board.move_count > 0 and self.board.move_count % 3 == 0:
                    self.board.apply_swap()

            # hand cards
            hand = pl.player.hand
            if hand:
                sx = (SCREEN_W - len(hand) * CARD_W) // 2
                for i, name in enumerate(hand):
                    card = get_by_name(name)
                    cost_val = card.cost if card else 0
                    cx = sx + i * (CARD_W + 12)
                    cy = SCREEN_H - CARD_H - 40
                    draw_card(
                        surf, name, cost_val, card.desc if card else "",
                        cx, cy, CARD_W, CARD_H,
                        is_highlighted=(self.hover_pos == f"card:{i}"),
                        can_afford=(pl.player.tokens >= cost_val),
                    )

            # transient "DRAW! Grid grows" banner — shows briefly after a draw
            # while play continues on the now-expanded board.
            if self.draw_message_until and pygame.time.get_ticks() < self.draw_message_until:
                penalty_pct = int(round((1 - pl.draw_multiplier) * 100))
                banner = pygame.font.SysFont("consolas", 36).render("DRAW! Grid grows...", True, ACCENT_GOLD)
                surf.blit(banner, (SCREEN_W // 2 - banner.get_width() // 2, 30))
                sub = self.font.render(f"Win reward reduced by {penalty_pct}%", True, TEXT_SUB)
                surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 70))

            # result overlay (win/lose only — draws keep the game going)
            if self.showing_result:
                result = pl.game_result
                txt_map = {"win": ("VICTORY!", ACCENT_GREEN), "lose": ("DEFEAT!", ACCENT_RED)}
                if result in txt_map:
                    txt, col = txt_map[result]
                    ts = pygame.font.SysFont("consolas", 64).render(txt, True, col)
                    surf.blit(ts, (SCREEN_W // 2 - ts.get_width() // 2, SCREEN_H // 2 - 50))
                    ct = self.font.render(f"Score: {pl.player.score}", True, TEXT_COLOR)
                    surf.blit(ct, (SCREEN_W // 2 - ct.get_width() // 2, SCREEN_H // 2 + 20))
                    ct2 = self.font.render("Click to continue", True, TEXT_SUB)
                    surf.blit(ct2, (SCREEN_W // 2 - ct2.get_width() // 2, SCREEN_H // 2 + 55))

        elif self.state == "shop":
            draw_centered_text(surf, "SHOP", pygame.font.SysFont("consolas", 40), ACCENT_GOLD, 50)
            draw_tokens(surf, pl.player.tokens, SCREEN_W - 180, 80)
            if self.shop_cards:
                sx = (SCREEN_W - len(self.shop_cards) * CARD_W) // 2
                for i, name in enumerate(self.shop_cards):
                    card = get_by_name(name)
                    cost_val = card.cost if card else 0
                    cx = sx + i * (CARD_W + 12)
                    cy = SCREEN_H // 2 - CARD_H // 2 - 20
                    draw_card(
                        surf, name, cost_val, card.desc if card else "",
                        cx, cy, CARD_W, CARD_H,
                        is_highlighted=(self.hover_pos == f"shop:{i}"),
                        can_afford=(pl.player.tokens >= cost_val),
                    )

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
            sx = SCREEN_W // 2 - (3 * CARD_W) // 2
            for i in range(len(self.starter_cards)):
                cx = sx + i * (CARD_W + 12)
                if cx <= mx <= cx + CARD_W and 320 <= my <= 320 + CARD_H:
                    card_name = self.starter_cards[i]
                    card = get_by_name(card_name)
                    if card and pl.player.tokens >= card.cost:
                        pl.current_target = pl.get_target()
                        pl.score_targets = [6, 12, 20]
                        pl.player.hand.append(card_name)
                        if card.cost > 0:
                            pl.player.tokens -= card.cost
                    else:
                        pl.player.hand.append(card_name)
                    break
            self.start_game()

        elif self.state == "boss_intro":
            pl.game_result = None
            self.showing_result = False
            pl.is_boss = False
            self.countdown_start = pygame.time.get_ticks()
            if pl.current_boss and pl.current_boss.mechanic == "timed":
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
                self.showing_result = False
                pl.game_result = None
                self.player_placed_this_turn = False
                self.card_played_this_turn = False
                self.card_system.post_game_cleanup(pl.player)
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
                    pl.player.placed_on_turn += 1
                    self.player_placed_this_turn = True

                    if pl.is_boss and pl.current_boss:
                        if pl.current_boss.mechanic == "swap" and self.board.move_count % 3 == 0:
                            self.board.apply_swap()
                        if pl.current_boss.mechanic == "timed":
                            self.countdown_start = pygame.time.get_ticks()

                    # End immediately if the player just completed a line
                    # (or filled the last cell).
                    if self._should_evaluate():
                        self.evaluate_and_settle()
                        return

                    # AI counter-move
                    ai = OpponentAI(self.board)
                    move = ai.get_best_move()
                    if move:
                        self.board.place_at(move[0], move[1], OPPONENT_O)

                    if self._should_evaluate():
                        self.evaluate_and_settle()
                        return

            # check card click
            hand = pl.player.hand
            if hand and not self.showing_result and not self.player_placed_this_turn:
                hx = (SCREEN_W - len(hand) * CARD_W) // 2
                for i, name in enumerate(hand):
                    if hx + i * (CARD_W + 12) <= mx <= hx + i * (CARD_W + 12) + CARD_W and (SCREEN_H - CARD_H - 40) <= my <= (SCREEN_H - 40):
                        card = get_by_name(name)
                        if card and pl.player.tokens >= card.cost:
                            # play the card - consume all tokens
                            pl.player.tokens -= card.cost
                            pl.player.hand.remove(name)
                            self.card_system.apply_card(name, self.board, pl.player)
                            self.player_placed_this_turn = True
                        break

        elif self.state == "shop":
            if self.shop_cards:
                sx = (SCREEN_W - len(self.shop_cards) * CARD_W) // 2
                for i, name in enumerate(self.shop_cards):
                    cx = sx + i * (CARD_W + 12)
                    cy = SCREEN_H // 2 - CARD_H // 2 - 20
                    if cx <= mx <= cx + CARD_W and cy <= my <= cy + CARD_H:
                        card = get_by_name(name)
                        if card and pl.player.tokens >= card.cost:
                            pl.player.tokens -= card.cost
                            pl.player.deck.append(card.name)
                            pl.player.hand.append(card.name)
                            self.shop_cards.pop(i)
                            break

            cont = pygame.Rect(SCREEN_W // 2 - 80, SCREEN_H - 100, 160, 50)
            if cont.collidepoint(mx, my):
                pl.next_level()
                if pl.run_complete:
                    self.state = "gameover"
                else:
                    self.start_game()

        elif self.state == "gameover":
            self.state = "menu"

    def handle_motion(self, mx, my):
        self.hover_pos = None
        pl = self.engine.state

        if self.state in ("countdown", "game"):
            cell = self._cell_under(mx, my)
            if cell is not None:
                self.hover_pos = cell

            # check hand card hover
            hand = pl.player.hand
            if hand:
                hx = (SCREEN_W - len(hand) * CARD_W) // 2
                for i, _ in enumerate(hand):
                    cx = hx + i * (CARD_W + 12)
                    if cx <= mx <= cx + CARD_W and (SCREEN_H - CARD_H - 40) <= my <= (SCREEN_H - 40):
                        self.hover_pos = f"card:{i}"

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
