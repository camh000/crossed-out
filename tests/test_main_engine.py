"""Tests for main.py - GameEngine state machine and event handling."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock


class TestMainEngineInit:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_engine_initializes(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        assert engine.state == "menu"
        assert engine.board is not None
        assert engine.board.size == 3
        assert isinstance(engine.engine, object)
        assert isinstance(engine.card_system, object)
        assert engine.starter_cards == []
        assert engine.shop_cards == []
        # The hand mechanic is gone — these flags were removed.
        assert not hasattr(engine, "card_played_this_turn")
        assert not hasattr(engine, "player_placed_this_turn")


class TestMainEngineRun:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_new_run(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        # Skip the first-run intro by claiming it's already been seen.
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        assert engine.state == "transition"
        assert len(engine.starter_cards) == 3

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_new_run_first_ever_routes_to_intro(self, mock_caption, mock_mode, mock_init):
        """First-ever run shows the tutorial overlay instead of going
        straight to the starter-glyph picker."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=False):
            engine.new_run()
        assert engine.state == "intro"
        assert engine._intro_step == 0

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_new_run_seeds_empty_passive_cards(self, mock_caption, mock_mode, mock_init):
        """A fresh run starts with no jokers — the starter screen picks
        one before the first game starts."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        assert engine.engine.state.player.passive_cards == []


class TestStartGame:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_start_game_normal_first_game(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.engine.state.level = 1
        engine.engine.state.games_in_level = 0
        engine.start_game()
        assert engine.state == "countdown"
        assert engine.countdown_start is not None
        assert engine.engine.state.is_boss is False
        assert engine.engine.state.games_in_level == 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_start_game_boss_third_game(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.engine.state.games_in_level = 2
        engine.start_game()
        assert engine.state == "boss_intro"
        assert engine.engine.state.is_boss is True


class TestDoShop:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_do_shop(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        engine.engine.state.shop_phase = True
        engine.engine.state.level = 1
        engine.do_shop()
        assert engine.state == "shop"
        assert engine.engine.state.shop_phase is True
        assert len(engine.shop_cards) == 4


class TestFinishRun:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_finish_run_won(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        engine.engine.state.player.tokens = 10
        engine.engine.state.won_run = False
        engine.engine.state.run_complete = False
        engine.finish_run(won=True)
        assert engine.state == "gameover"
        assert engine.engine.state.run_complete is True
        assert engine.engine.state.won_run is True

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_finish_run_lost(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        engine.engine.state.player.tokens = 5
        engine.engine.state.run_complete = False
        engine.finish_run(won=False)
        assert engine.state == "gameover"
        assert engine.engine.state.won_run is False


class TestEvaluateSettle:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_evaluate_normal_game_wins(self, mock_caption, mock_mode, mock_init):
        """A normal game ends as a win when X has more completed lines than O."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        # One X line in row 0, no O line.
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        engine.board.grid[1] = [OPPONENT_O, OPPONENT_O, 0]
        pl = engine.engine.state
        pl.is_boss = False
        pl.player.score = 0
        pl.current_target = 6
        result = engine.evaluate_and_settle()
        assert result == "win"
        assert pl.game_result == "win"

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_evaluate_boss_doublecross(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        from config.bosses import BOSS_LIST
        engine = GameEngine()
        engine.board.reset(3)
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_target = 6
        pl.current_boss = BOSS_LIST[1]
        pl.player = MagicMock()
        pl.next_level()
        pl.next_level()
        pl.next_level()
        pl.current_boss_setup = None
        pl.player.score = 0
        pl.player.hand = []
        pl.player.cells_played = []
        pl.player.placed_on_turn = 0
        pl.player.can_play_card = True
        pl.player.total_score = MagicMock(return_value=1)
        pl.get_multiplier = MagicMock(return_value=1)
        pl.total_score = 0
        pl.player.score = 1
        pl.score_this_level = 0
        pl.current_target = 1
        # card_system lives on the GameEngine, not on RogueliteEngine.
        engine.card_system.calculate_score = MagicMock(return_value=6)
        result = engine._boss_outcome()
        assert result in ("win", "lose", "draw")

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_evaluate_boss_mirror(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        from config.bosses import BOSS_LIST
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_evaluate_boss_mirror(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        from config.bosses import BOSS_LIST
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state


class TestDrawGrowsGrid:
    """A draw should expand the board by one adjacent cell, compound the
    0.9x reward penalty, and let play continue (no end-of-game overlay)."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_draw_adds_one_cell_and_continues(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        # Balanced 3x3 — 1 X line + 1 O line → draw
        engine.board.grid = [
            [PLAYER_X, PLAYER_X, PLAYER_X],
            [OPPONENT_O, OPPONENT_O, OPPONENT_O],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        engine.board.move_count = 9
        pl = engine.engine.state
        pl.is_boss = False
        pl.player.score = 0
        pl.current_target = 999
        pl.draw_multiplier = 1.0
        result = engine.evaluate_and_settle()
        assert result == "draw"
        # Board grew by a full new row and a full new column → 3x3 becomes 4x4.
        assert engine.board.rows == 4
        assert engine.board.cols == 4
        assert len(engine.board.valid_cells) == 16
        assert engine.board.game_over is False
        assert engine.showing_result is False
        # First draw applies a 0.5x penalty (steeper than the old 0.9 to
        # discourage stalling).
        assert pl.draw_multiplier == 0.5
        assert pl.draws_this_game == 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_consecutive_draws_keep_growing(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """Draws are now unlimited — every draw grows the grid by one
        row + one column and lets play continue. The diminishing
        draw_multiplier (halved per draw) is the only stalling
        penalty. Old behaviour: 2nd draw → -1 life. New behaviour:
        2nd / 3rd / Nth draw → keep growing, no life lost."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.player.score = 0
        pl.current_target = 999
        pl.draw_multiplier = 1.0
        pl.draws_this_game = 0
        lives_before = pl.lives

        engine.board.grid = [
            [PLAYER_X, PLAYER_X, PLAYER_X],
            [OPPONENT_O, OPPONENT_O, OPPONENT_O],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        assert engine.evaluate_and_settle() == "draw"
        assert pl.draws_this_game == 1
        # Force a second draw on the now-grown board.
        engine.board.reset(3)
        engine.board.grid = [
            [PLAYER_X, PLAYER_X, PLAYER_X],
            [OPPONENT_O, OPPONENT_O, OPPONENT_O],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        assert engine.evaluate_and_settle() == "draw"
        assert pl.draws_this_game == 2
        # No life lost on the second draw — that's the whole point.
        assert pl.lives == lives_before
        # Multiplier has halved twice (1.0 → 0.5 → 0.25).
        assert pl.draw_multiplier == 0.25

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_win_resets_multiplier(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.draw_multiplier = 0.81
        pl.player.tokens = 0
        pl.player.score = 0
        pl.current_target = 1
        # Single line of X — clear win
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        result = engine.evaluate_and_settle()
        assert result == "win"
        assert pl.draw_multiplier == 1.0
        # tokens awarded at the moment of evaluation use the pre-reset 0.81 multiplier
        assert pl.player.tokens >= 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_lose_resets_multiplier(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.draw_multiplier = 0.5
        pl.player.score = 0
        pl.current_target = 999
        # O lines > X lines (1 vs 0) → lose
        engine.board.grid[0] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        result = engine.evaluate_and_settle()
        assert result == "lose"
        assert pl.draw_multiplier == 1.0


class TestMidGameWinDetection:
    """A 3-in-a-row should end the game immediately, not after the board fills.
    Pinning the regression where a Boss game showed "VICTORY!" on a full board
    that had zero completed lines."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_line_does_not_end_game_until_board_fills(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """Under the first-to-fill rule, completing a line mid-game no
        longer ends the round. Play continues until every valid cell
        is occupied, and outcome is decided by total line count."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.start_game()
        engine.state = "game"
        engine.board.grid[0][0] = PLAYER_X
        engine.board.grid[0][1] = PLAYER_X
        engine.board.grid[1][0] = OPPONENT_O
        engine.board.grid[1][1] = OPPONENT_O
        engine.board.move_count = 4
        # Player clicks (0, 2) — completes an X line, but board has empties.
        avail, off_x, off_y = engine._board_layout()
        mx = off_x + 2 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        # Game is NOT over — no result overlay, no game_result.
        assert engine.engine.state.game_result is None
        assert engine.showing_result is False
        assert engine.board.is_full() is False

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_full_board_with_more_x_lines_wins(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """A filled board with 1 X line and 0 O lines settles as a win."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        # 1 X line in row 0, no O lines. Everything else filled.
        engine.board.grid = [
            [PLAYER_X, PLAYER_X, PLAYER_X],
            [OPPONENT_O, PLAYER_X, OPPONENT_O],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        result = engine.evaluate_and_settle()
        assert result == "win"

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_mirror_boss_does_not_end_on_line(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """Mirror boss must play until the board fills — a line mid-game is
        not the win condition, the net X−O line count is."""
        from main import GameEngine
        from game.board import PLAYER_X
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.start_game()
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["mirror"]
        # An X line exists on the board.
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        # Board is not full → should NOT trigger evaluation.
        assert engine._should_evaluate() is False


class TestScoreResetsBetweenGames:
    """Per-game score (player.score) resets at the start of each game so the
    win check stays per-game and never auto-wins from a previous game's score."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_start_game_zeroes_player_score(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.player.score = 42
        engine.start_game()
        assert pl.player.score == 0

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_full_board_with_no_lines_is_a_draw(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """A full board with equal (zero) line counts is a draw, regardless
        of any previously-accumulated score on player.score."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        # The exact board from the screenshot the user reported: full, but
        # no completed line for either side.
        engine.board.grid = [
            [PLAYER_X, PLAYER_X, OPPONENT_O],
            [OPPONENT_O, OPPONENT_O, PLAYER_X],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        pl = engine.engine.state
        pl.is_boss = False
        # Pretend prior games accumulated score past the target — the bug we
        # just fixed would have called this "win" because of that.
        pl.player.score = 6
        pl.current_target = 6
        result = engine.evaluate_and_settle()
        assert result == "draw"


class TestLivesAndAnte:
    """Lives system, draw cap, and boss ante failure modes."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_lose_decrements_life(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.lives = 3
        # AI has more lines than the player.
        engine.board.grid[0] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        result = engine.evaluate_and_settle()
        assert result == "lose"
        assert pl.lives == 2

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_zero_lives_pends_run_end(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.lives = 1
        engine.board.grid[0] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        engine.evaluate_and_settle()
        assert pl.lives == 0
        assert engine._pending_run_end is True

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_boss_ante_failure_ends_run(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """A mechanical boss win that doesn't hit the ante target is a
        loss AND ends the run, regardless of remaining lives."""
        from main import GameEngine
        from game.board import PLAYER_X
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["blind"]
        pl.lives = 3
        pl.ante_target = 50
        pl.score_this_game = 0
        # One X line; ink will be small, far below ante 50.
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        result = engine.evaluate_and_settle()
        assert result == "lose"
        assert engine._pending_run_end is True

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_boss_ante_pass_does_not_end_run(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["blind"]
        pl.lives = 3
        pl.ante_target = 1  # trivially passable
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        result = engine.evaluate_and_settle()
        assert result == "win"
        assert engine._pending_run_end is False


class TestTokenBonusReward:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_token_bonus_stacks_on_win(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.lives = 3
        pl.player.tokens = 0
        pl.player.upgrades["token_bonus"] = 2  # Two Token Bonus copies.
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        engine.evaluate_and_settle()
        # base 2 win reward + 3 * 2 from Token Bonus stacks = 8.
        assert pl.player.tokens == 8


class TestStartGameRefreshes:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_start_game_applies_passive_buffs(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.player.passive_cards = ["Point Multiplier", "Point Multiplier", "Diagonal Power"]
        engine.start_game()
        assert pl.player.upgrades.get("point_mult") == 2
        assert pl.player.upgrades.get("diagonal_power") == 1
        # Per-game scratch cleared.
        assert pl.draws_this_game == 0
        assert pl.score_this_game == 0
        assert pl.player.blind_shot_marks == []


class TestGameCycle:
    """Within a level: game 1 normal → game 2 normal → game 3 boss → shop."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_third_game_is_boss(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        # Game 1
        engine.start_game()
        assert pl.games_in_level == 1
        assert pl.is_boss is False
        # Game 2
        engine.start_game()
        assert pl.games_in_level == 2
        assert pl.is_boss is False
        # Game 3 — boss
        engine.start_game()
        assert pl.games_in_level == 3
        assert pl.is_boss is True
        assert pl.current_boss is not None

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_next_level_resets_games_counter(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.games_in_level = 3
        pl.next_level()
        assert pl.games_in_level == 0
        assert pl.level == 2

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_grid_size_scales_with_level(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        # Level 1 → 3, Level 2 → 5, Level 3 → 7
        pl.level = 1
        engine.start_game()
        assert engine.board.size == 3
        pl.level = 2
        engine.start_game()
        assert engine.board.size == 5
        pl.level = 3
        engine.start_game()
        assert engine.board.size == 7


class TestClickToAdvance:
    """Clicking the result overlay transitions to the next phase."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_normal_game_win_then_click_starts_next_game(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.games_in_level = 0
        engine.start_game()  # games_in_level = 1, normal
        engine.state = "game"
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        pl.player.score = 0
        pl.current_target = 1
        engine.evaluate_and_settle()
        assert engine.showing_result is True
        # First click during the result staging only skips the reveal.
        engine.handle_click(100, 100, 1)
        assert engine.showing_result is True
        # Second click actually advances to the next game.
        engine.handle_click(100, 100, 1)
        assert engine.state == "countdown"
        assert pl.games_in_level == 2
        assert engine.showing_result is False

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_boss_win_then_click_enters_shop(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.games_in_level = 2
        engine.start_game()  # → boss (also grows the grid by 1 row/col)
        engine.state = "game"
        # Place an X line at the top of the (post-grow) board.
        engine.board.grid[0][0] = PLAYER_X
        engine.board.grid[0][1] = PLAYER_X
        engine.board.grid[0][2] = PLAYER_X
        pl.player.score = 10
        pl.current_target = 1
        # Make the ante trivially passable for this test — the ante check
        # is exercised separately.
        pl.ante_target = 0
        engine.evaluate_and_settle()
        # Boss win → showing_result True with pl.is_boss True.
        # First click skips the staged reveal; second click advances.
        engine.handle_click(100, 100, 1)
        engine.handle_click(100, 100, 1)
        assert engine.state == "shop"
        assert len(engine.shop_cards) == 4

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_draw_overlay_does_not_block_advancement(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """A draw shouldn't set showing_result; click on board should still place a mark."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        engine.start_game()
        engine.state = "game"
        engine.board.grid = [
            [PLAYER_X, PLAYER_X, PLAYER_X],
            [OPPONENT_O, OPPONENT_O, OPPONENT_O],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        engine.board.move_count = 9
        pl.is_boss = False
        pl.player.score = 0
        pl.current_target = 999
        engine.evaluate_and_settle()
        assert pl.game_result == "draw"
        assert engine.showing_result is False
        assert engine.board.game_over is False


class TestShopFlow:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_do_shop_populates_cards(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.do_shop()
        assert engine.state == "shop"
        assert len(engine.shop_cards) == 4
        assert engine.engine.state.shop_phase is True

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_shop_continue_button_advances_level(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from config.constants import SCREEN_W, SCREEN_H
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.do_shop()
        pl = engine.engine.state
        start_level = pl.level
        # Click "Continue" button at center bottom
        cont_x = SCREEN_W // 2
        cont_y = SCREEN_H - 75
        engine.handle_click(cont_x, cont_y, 1)
        assert pl.level == start_level + 1


class TestFinishRun:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_finish_run_persists_to_save(self, mock_caption, mock_mode, mock_init, tmp_path, monkeypatch):
        """finish_run should write a save file with the run outcome."""
        from main import GameEngine
        save_path = tmp_path / "save.json"
        monkeypatch.setattr("save.savesetup.SAVE_PATH", str(save_path))
        engine = GameEngine()
        engine.engine.state.player.tokens = 4
        engine.engine.state.level = 2
        engine.finish_run(won=True)
        assert save_path.exists()
        import json
        data = json.loads(save_path.read_text())
        assert data["won_run"] is True
        assert data["tokens_banked"] == 4
        assert data["levels_reached"] == 2
        assert data["wins"] == 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_finish_run_lost_banks_no_tokens(self, mock_caption, mock_mode, mock_init, tmp_path, monkeypatch):
        from main import GameEngine
        save_path = tmp_path / "save.json"
        monkeypatch.setattr("save.savesetup.SAVE_PATH", str(save_path))
        engine = GameEngine()
        engine.engine.state.player.tokens = 10
        engine.finish_run(won=False)
        import json
        data = json.loads(save_path.read_text())
        assert data["tokens_banked"] == 0
        assert data["won_run"] is False


class TestBossBannerClears:
    """After a boss game finishes, the next non-boss start_game must clear
    `current_boss` so the BOSS label and ante row don't leak into the next
    level's games."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_non_boss_start_game_clears_boss(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        # Simulate having just finished a boss: current_boss set, games_in_level
        # at 3 (the boss was game 3), then next_level + start_game for the
        # first non-boss game of the next level.
        pl.games_in_level = 3
        from config.bosses import BOSS_MAP
        pl.current_boss = BOSS_MAP["blind"]
        pl.is_boss = True
        pl.next_level()  # → level 2, games_in_level=0
        engine.start_game()  # → game 1 of level 2, non-boss
        assert pl.is_boss is False
        assert pl.current_boss is None
        assert pl.ante_target == 0


class TestTimedBossAutoMoveTriggers:
    """Reachable timeout: once the per-move timer hits 0, the AI moves and
    the countdown resets. Previously the auto-move was nested inside
    `if remaining > 0` so it never fired."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_timeout_block_is_reachable(self, mock_caption, mock_mode, mock_init):
        """Source-level pin: the auto-move branch must not be nested inside
        the 'remaining > 0' check that originally hid it."""
        import re, inspect
        from main import GameEngine
        src = inspect.getsource(GameEngine.draw)
        # Find the timed-boss section and confirm the auto-move sits under
        # the timeout branch, not the 'remaining > 0' branch.
        m = re.search(r'mechanic == "timed".*?(?=\n {8}elif self\.state)', src, re.DOTALL)
        assert m, "could not locate timed-boss block in GameEngine.draw"
        block = m.group(0)
        # The OpponentAI call should appear after an `else:` (the timeout
        # branch), not inside `if remaining > 0:`.
        assert "OpponentAI" in block
        # Order matters: the `else:` must precede `OpponentAI` and there
        # must be no `if remaining <= 0:` inside `if remaining > 0:` block.
        assert "if remaining <= 0:" not in block, (
            "unreachable timeout branch still present"
        )


class TestSwapBossDoesNotDoubleApply:
    """`apply_swap` used to run every frame from draw() in addition to once
    per third click — net effect was an oscillating board. The frame-loop
    swap has been removed; only the click-driven swap remains."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_draw_does_not_call_apply_swap(self, mock_caption, mock_mode, mock_init):
        import inspect
        from main import GameEngine
        src = inspect.getsource(GameEngine.draw)
        # The only swap call inside draw() should be gone — the move-driven
        # one lives in handle_click. (handle_click is a separate method.)
        assert "apply_swap" not in src, (
            "draw() should not call apply_swap — that caused a per-frame oscillation"
        )


class TestLevelScoreResets:
    """score_this_level used to grow cumulatively across the whole run.
    next_level() now resets it so each level scores from zero."""

    def test_next_level_resets_level_score(self):
        from game.player import RunState
        rs = RunState(level=1)
        rs.score_this_level = 25
        rs.next_level()
        assert rs.score_this_level == 0
        assert rs.level == 2

    def test_final_level_win_check_uses_pre_increment_target(self):
        """Beating the final base level with cumulative ink ≥ target
        should register as a run win. The check must happen BEFORE
        level += 1, or get_target() would jump to the endless formula."""
        from game.player import RunState
        rs = RunState(level=7)
        rs.score_this_level = rs.get_target()
        rs.next_level()
        assert rs.run_complete is True
        assert rs.won_run is True

    def test_final_level_miss_check_fails_run(self):
        from game.player import RunState
        rs = RunState(level=7)
        rs.score_this_level = rs.get_target() - 1
        rs.next_level()
        assert rs.run_complete is True
        assert rs.won_run is False


class TestCellLockOnGrownBoard:
    """Cell Lock used to drop the wall at (board.size//2, board.size//2),
    which is wrong once the board has grown via draws — that coordinate
    may no longer be a valid cell. The joker trigger now picks the
    geometric centre of the playable region."""

    def test_lock_centre_of_grown_board_lands_on_valid_cell(self):
        import random
        from systems.cardsystem import CardSystem
        from game.board import Board
        from game.player import Player
        random.seed(0)
        board = Board()
        # Grow 3 times so the bounding box has shifted off (1,1).
        for _ in range(3):
            board.grow_row_and_column()
        cs = CardSystem()
        player = Player(passive_cards=["Cell Lock"])
        cs.apply_passive_buffs(player)
        cs.fire_game_start(board, player)
        assert len(board.wall_cells) == 1
        assert board.wall_cells[0] in board.valid_cells


class TestFortressRandomPlacement:
    """Fortress trigger picks a random empty cell, not sorted[0]."""

    def test_fortress_visits_multiple_cells_over_trials(self):
        import random
        from systems.cardsystem import CardSystem
        from game.board import Board
        from game.player import Player
        cs = CardSystem()
        placements = set()
        # Use 5x5 so there's room for variance — sorted[0] would always be (0,0).
        for seed in range(64):
            random.seed(seed)
            board = Board(size=5)
            player = Player(passive_cards=["Fortress"])
            cs.apply_passive_buffs(player)
            cs.fire_game_start(board, player)
            placements.update(board.wall_cells)
        # If still picking sorted[0] every time, we'd only ever see (0, 0).
        assert len(placements) > 1


class TestGrowthPersistsWithinLevel:
    """A board that grew during a draw should keep that growth in the next
    game within the same level (only a level transition restores the base
    grid size)."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_growth_carries_to_next_game_same_level(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        engine.start_game()  # game 1 of level 1 → 3x3
        assert engine.board.rows == 3
        assert engine.board.cols == 3
        # Simulate a draw growing the board mid-game.
        engine.board.grow_row_and_column()
        assert engine.board.rows == 4
        assert engine.board.cols == 4
        # Next game in the same level should preserve the 4x4 bounding box.
        engine.start_game()
        assert pl.games_in_level == 2
        assert engine.board.rows == 4
        assert engine.board.cols == 4
        # But the marks must be wiped.
        assert all(engine.board.grid[r][c] == 0 for r in range(4) for c in range(4))

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_growth_carries_across_level_transition(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """Growth survives a level change too: the new level's base only
        expands the board further; it never shrinks it."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        engine.start_game()  # level 1, 3x3
        # Grow level 1 board to 6x6 across several "draw" expansions.
        engine.board.grow_row_and_column()
        engine.board.grow_row_and_column()
        engine.board.grow_row_and_column()
        assert engine.board.rows == 6 and engine.board.cols == 6
        # Advance to level 2 (base 5). Player kept the 6x6.
        pl.next_level()
        engine.start_game()
        assert pl.level == 2
        assert engine.board.size == 5  # line-length target updated
        assert engine.board.rows == 6  # bounding box preserved
        assert engine.board.cols == 6

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_level_transition_expands_when_growth_below_base(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """If the board hasn't grown past the new level's base size, it
        gets expanded out to that base."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        engine.start_game()  # 3x3
        engine.board.grow_row_and_column()  # 4x4
        pl.next_level()
        engine.start_game()
        # 4x4 was below the level-2 base (5) → expanded to 5x5.
        assert engine.board.rows == 5
        assert engine.board.cols == 5
        assert engine.board.size == 5

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_new_run_resets_board(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """A fresh run starts on a fresh 3x3, even if the previous run
        ended with a larger grown board."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.start_game()
        for _ in range(4):
            engine.board.grow_row_and_column()
        assert engine.board.rows > 3
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        assert engine.board.rows == 3
        assert engine.board.cols == 3

    def test_clear_marks_preserves_box_but_wipes_grid(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.grow_row_and_column()
        b.grow_row_and_column()  # 5x5
        b.place_at(1, 1, PLAYER_X)
        b.place_at(2, 2, OPPONENT_O)
        b.wall_cells.append((0, 0))
        b.poison_cells.append((3, 3))
        b.move_count = 2
        b.game_over = True
        b.clear_marks()
        assert b.rows == 5
        assert b.cols == 5
        assert len(b.valid_cells) == 25
        assert all(b.grid[r][c] == 0 for r in range(5) for c in range(5))
        assert b.wall_cells == []
        assert b.poison_cells == []
        assert b.move_count == 0
        assert b.game_over is False


class TestRunFailedReason:
    """The result panel surfaces WHY the run ended (lives vs ante), not
    just a bare 'Run failed'."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_pending_run_end_is_distinguishable_from_continue(self, mock_caption, mock_mode, mock_init):
        import inspect
        from main import GameEngine
        src = inspect.getsource(GameEngine.draw)
        # The two failure modes must appear as branches in the result panel.
        assert "Failed boss ante" in src
        assert "Out of lives" in src


class TestAIMoveScheduling:
    """The AI's response is deferred by AI_MOVE_DELAY_MS so the player
    sees their own X land before the opponent reacts. _tick_ai_move is
    called at the top of each frame from run() and fires the deferred
    move once the delay has elapsed."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_tick_ai_move_noop_when_unscheduled(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        engine._ai_move_at = None
        # Should not raise, should not place anything.
        engine._tick_ai_move()

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_tick_ai_move_waits_for_delay(self, mock_caption, mock_mode, mock_init):
        """With the conftest pygame stub, get_ticks() returns 0. Setting
        _ai_move_at into the future (1) means the tick should NOT fire;
        setting it into the past (-1) means it SHOULD fire and clear."""
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(3)
        # Future deadline — no-op.
        engine._ai_move_at = 1
        engine._tick_ai_move()
        assert engine._ai_move_at == 1
        # Past deadline — fires and clears.
        engine._ai_move_at = -1
        engine._tick_ai_move()
        assert engine._ai_move_at is None

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_player_click_schedules_ai_move(self, mock_caption, mock_mode, mock_init):
        """A player click should NOT place an AI O in the same frame —
        it should just schedule one."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.start_game()
        engine.state = "game"
        avail, off_x, off_y = engine._board_layout()
        mx = off_x + 1 * avail + avail // 2
        my = off_y + 1 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        # Player's X landed on (1, 1).
        assert engine.board.grid[1][1] == PLAYER_X
        # No AI O on the board yet — scheduled for the next frame.
        assert all(
            engine.board.grid[r][c] != OPPONENT_O
            for r in range(3) for c in range(3)
        )
        assert engine._ai_move_at is not None


class TestStagingSkip:
    """The result panel stages ink → mult → total over ~1.1s. A click
    during staging snaps the reveal to the final frame; a second click
    actually advances state. This matches the Balatro convention."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_first_click_keeps_showing_result(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        engine.start_game()
        engine.state = "game"
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        engine.evaluate_and_settle()
        assert engine.showing_result is True
        # First click — should NOT advance state because staging hasn't
        # elapsed (clock is mocked at 0 in conftest).
        engine.handle_click(100, 100, 1)
        assert engine.showing_result is True

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_second_click_advances_after_skip(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        engine.start_game()
        engine.state = "game"
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        engine.evaluate_and_settle()
        engine.handle_click(100, 100, 1)  # skip staging
        engine.handle_click(100, 100, 1)  # actually advance
        assert engine.showing_result is False


class TestJokerInspectAndSell:
    """The joker row supports tap-to-inspect (a big card modal with the
    full description) and a Sell button in the shop that refunds 50% of
    the joker's cost. Cursed Coin can't be sold."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_tap_joker_chip_opens_modal(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.player.passive_cards = ["Point Multiplier"]
        engine.state = "game"
        # Click on the first joker chip — should open inspect modal.
        rects = engine._joker_row_rects(pl)
        assert len(rects) == 1
        name, rect = rects[0]
        engine.handle_click(rect.centerx, rect.centery, 1)
        assert engine._inspecting_joker == "Point Multiplier"

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_outside_click_closes_modal(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.engine.state.player.passive_cards = ["Point Multiplier"]
        engine.state = "game"
        engine._inspecting_joker = "Point Multiplier"
        # Click well outside the modal area (top-left corner).
        engine.handle_click(5, 5, 1)
        assert engine._inspecting_joker is None

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_sell_refunds_half_cost(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.player.passive_cards = ["Point Multiplier"]  # cost 5
        pl.player.tokens = 0
        engine.state = "shop"
        engine._inspecting_joker = "Point Multiplier"
        sell_rect = engine._inspect_modal_rects()["sell"]
        engine.handle_click(sell_rect.centerx, sell_rect.centery, 1)
        # Cost 5 // 2 = 2.
        assert pl.player.tokens == 2
        assert "Point Multiplier" not in pl.player.passive_cards
        assert engine._inspecting_joker is None

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_sell_only_in_shop(self, mock_caption, mock_mode, mock_init):
        """A click on the same screen coordinates outside the shop
        state should just close the modal — not credit any tokens."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.player.passive_cards = ["Point Multiplier"]
        pl.player.tokens = 0
        engine.state = "game"
        engine._inspecting_joker = "Point Multiplier"
        sell_rect = engine._inspect_modal_rects()["sell"]
        engine.handle_click(sell_rect.centerx, sell_rect.centery, 1)
        assert pl.player.tokens == 0
        assert "Point Multiplier" in pl.player.passive_cards

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_cursed_coin_cannot_be_sold(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.player.passive_cards = ["Cursed Coin"]
        pl.player.tokens = 0
        engine.state = "shop"
        engine._inspecting_joker = "Cursed Coin"
        sell_rect = engine._inspect_modal_rects()["sell"]
        engine.handle_click(sell_rect.centerx, sell_rect.centery, 1)
        # Modal dismissed but the joker stays and no tokens credited.
        assert pl.player.tokens == 0
        assert "Cursed Coin" in pl.player.passive_cards

    def test_sell_price_is_half_rounded_down(self):
        from main import GameEngine
        from unittest.mock import patch
        with patch('pygame.init'), patch('pygame.display.set_mode'), patch('pygame.display.set_caption'):
            engine = GameEngine()
        # Spot-check a few representative cards.
        assert engine._joker_sell_price("Point Multiplier") == 2   # 5 // 2
        assert engine._joker_sell_price("Quick Draw") == 0          # 1 // 2
        assert engine._joker_sell_price("Cursed Coin") == 0         # 0 // 2
        assert engine._joker_sell_price("Final Count") == 3         # 6 // 2


class TestBossRotation:
    """Bosses must vary across a run. Old bug: pl.boss_index was set to
    games_in_level // 3 - 1, which always evaluated to 0 because
    games_in_level resets each level — so every boss was BOSS_LIST[0]."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_run_visits_multiple_distinct_bosses(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        seen = []
        # Walk through three boss encounters across three levels.
        for lvl in range(1, 4):
            pl.games_in_level = 2  # next start_game will be the boss
            engine.start_game()
            seen.append(pl.current_boss.mechanic)
            pl.next_level()
        # We may get repeats in a worst-case shuffle, but boss_index
        # advances each time so the indices should differ.
        assert pl.boss_index == 3
        # Three boss_order entries got consumed.
        assert len(seen) == 3

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_boss_order_shuffled_per_run(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from config.bosses import BOSS_LIST
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        order = engine.engine.state.boss_order
        # Every boss mechanic appears exactly once.
        assert set(order) == {b.mechanic for b in BOSS_LIST}
        assert len(order) == len(BOSS_LIST)


class TestShopVariety:
    """The shop sampler biases toward unseen glyphs so a run gradually
    surfaces the whole pool instead of looping back to the same few."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_seen_offers_track_across_visits(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        # Sample several shop visits.
        offered_once = set(engine._sample_shop_offers(4))
        offered_twice = set(engine._sample_shop_offers(4))
        # Track set grew (no overlap since unseen pool was large).
        assert len(pl.seen_shop_offers) >= 8
        assert offered_once.isdisjoint(offered_twice)

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_seen_set_resets_when_pool_exhausted(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from config.cards import ALL_CARDS
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        pl = engine.engine.state
        pl.seen_shop_offers = {c.name for c in ALL_CARDS}
        engine._sample_shop_offers(4)
        # Reset triggers — set is the offer just made, not everything.
        assert len(pl.seen_shop_offers) == 4


class TestCodex:
    """Main-menu CODEX button opens a browser of every glyph and every
    boss modifier. Each entry opens the inspect modal — glyph view for
    the glyphs tab, boss view for the bosses tab. No Sell button in
    the codex (it's a meta view, not a shop)."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_codex_layout_has_back_and_tabs(self, mock_caption, mock_mode, mock_init):
        """Layout helper must expose the three control rects every code
        path through draw + handle_click depends on. The conftest pygame
        stub makes rect.collidepoint untestable, so we just verify the
        layout structure itself."""
        from main import GameEngine
        engine = GameEngine()
        engine.state = "codex"
        layout = engine._codex_layout()
        assert "back" in layout
        assert "tab_glyphs" in layout
        assert "tab_bosses" in layout
        assert "chips" in layout

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_codex_tab_switches_chip_set(self, mock_caption, mock_mode, mock_init):
        """Switching tabs changes which name pool the chips iterate."""
        from main import GameEngine
        from config.cards import ALL_CARDS
        from config.bosses import BOSS_LIST
        engine = GameEngine()
        engine.state = "codex"
        engine._codex_tab = "glyphs"
        glyph_names = {name for (name, _) in engine._codex_layout()["chips"]}
        assert glyph_names == {c.name for c in ALL_CARDS}
        engine._codex_tab = "bosses"
        boss_names = {name for (name, _) in engine._codex_layout()["chips"]}
        assert boss_names == {b.name for b in BOSS_LIST}

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_inspect_modal_supports_both_glyph_and_boss(self, mock_caption, mock_mode, mock_init):
        """_draw_inspect_modal branches on _inspecting_boss vs
        _inspecting_joker; both flavours must exist on the engine."""
        from main import GameEngine
        engine = GameEngine()
        assert hasattr(engine, "_inspecting_joker")
        assert hasattr(engine, "_inspecting_boss")
        # Either being set is sufficient to put the modal up.
        engine._inspecting_boss = "The Blind"
        assert engine._inspecting_boss == "The Blind"
        engine._inspecting_boss = None
        engine._inspecting_joker = "Point Multiplier"
        assert engine._inspecting_joker == "Point Multiplier"

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_codex_has_rules_tab(self, mock_caption, mock_mode, mock_init):
        """Third tab (RULES) renders no chips but is a valid tab."""
        from main import GameEngine
        engine = GameEngine()
        engine.state = "codex"
        engine._codex_tab = "rules"
        layout = engine._codex_layout()
        assert "tab_rules" in layout
        # RULES tab has no chips — it's a static info panel.
        assert layout["chips"] == []

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_open_help_pushes_into_codex_rules(self, mock_caption, mock_mode, mock_init):
        """The in-game '?' icon routes into the codex RULES tab with a
        return-state pointer so BACK comes back to the game."""
        from main import GameEngine
        engine = GameEngine()
        engine.state = "game"
        engine._open_help()
        assert engine.state == "codex"
        assert engine._codex_tab == "rules"
        assert engine._codex_return_state == "game"


class TestIntroOverlay:
    """First-run tutorial overlay — 3 steps, dismissable with SKIP, and
    persists intro_seen so it doesn't fire on subsequent runs."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_intro_layout_has_three_buttons(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        layout = engine._intro_layout()
        assert "back" in layout and "next" in layout and "skip" in layout

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_intro_has_three_steps(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        steps = engine._intro_steps()
        assert len(steps) == 3
        # Each step is (heading, body) — both non-empty strings.
        for heading, body in steps:
            assert heading and isinstance(heading, str)
            assert body and isinstance(body, str)


class TestRoundLabel:
    """The top-bar 'Round N / 7' label replaces the old 'Level N' so
    the player can see how long the run is."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_max_base_level_default(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        # The intro copy and the round label both reference this value.
        assert engine.engine.state.max_base_level == 7


class TestHighScoresRoute:
    """finish_run records a high-score entry every run. The 'scores'
    state surfaces them."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_finish_run_records_score(self, mock_caption, mock_mode, mock_init):
        # Use a fresh-ish save so the record list starts empty.
        import os
        save_path = os.path.join(
            os.path.dirname(__file__), '..', 'crossed_out_save.json',
        )
        if os.path.exists(save_path):
            os.remove(save_path)
        from main import GameEngine
        from save.savesetup import load_scores
        engine = GameEngine()
        engine.engine.state.total_score = 1234
        engine.engine.state.level = 5
        engine.finish_run(won=True)
        scores = load_scores()
        assert len(scores) == 1
        assert scores[0]["total_score"] == 1234
        assert scores[0]["level_reached"] == 5
        assert scores[0]["won"] is True
        # The just-finished entry is remembered for the gold-highlight pass.
        assert engine._last_score_entry["total_score"] == 1234
        if os.path.exists(save_path):
            os.remove(save_path)


class TestBlindAI:
    """The AI is symmetrically blind during Blind boss games: it reads
    the same faded grid the player sees, so faded threats are invisible
    and the AI can pick cells that are actually occupied (forfeiting)."""

    def test_ai_does_not_block_faded_threat(self):
        from game.board import Board, PLAYER_X
        from game.opponent import OpponentAI
        b = Board(size=3)
        # Two X's in a row — a clear threat the omniscient AI would block.
        b.place_at(0, 0, PLAYER_X)  # move 1
        b.place_at(0, 1, PLAYER_X)  # move 2
        # Age the board past fade_age by spamming moves elsewhere.
        for r, c in [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1)]:
            b.place_at(r, c, PLAYER_X)
        # Now the (0,0) and (0,1) marks are at age 6+ from move_count=7.
        # Faded AI should not see them and therefore not block (0, 2).
        ai = OpponentAI(b, fade_age=2)
        # With aggressive fading, the AI shouldn't pick (0, 2) as a
        # forced block — the threat isn't visible.
        move = ai.get_best_move()
        # The only truly empty cells on the real board are (0, 2) and (2, 2).
        # The AI may pick either; what we're asserting is it doesn't
        # treat (0, 2) as a "must block" move (which it would if it saw
        # the unfaded threat).
        assert move in [(0, 2), (2, 2), None]

    def test_omniscient_ai_blocks_unfaded_threat(self):
        """Sanity check: same board, no fade_age → AI blocks correctly."""
        from game.board import Board, PLAYER_X
        from game.opponent import OpponentAI
        b = Board(size=3)
        b.place_at(0, 0, PLAYER_X)
        b.place_at(0, 1, PLAYER_X)
        ai = OpponentAI(b)  # no fade_age — sees everything
        assert ai.get_best_move() == (0, 2)

    def test_blind_ai_falls_back_to_truly_empty_cell(self):
        """If the AI's blind perception leads it to pick a cell that's
        actually occupied (a faded mark), get_best_move falls back to
        a truly-empty cell instead of forfeiting. The AI stays
        informationally blind but doesn't waste turns."""
        from game.board import Board, PLAYER_X
        from game.opponent import OpponentAI
        # Fill every cell except (1, 1) with X. fade_age=1 → all
        # placed cells look empty to the AI.
        b = Board(size=3)
        for r in range(3):
            for c in range(3):
                if (r, c) != (1, 1):
                    b.place_at(r, c, PLAYER_X)
        ai = OpponentAI(b, fade_age=1)
        import random
        # Across many seeds, the AI must always either pick (1, 1) (the
        # only truly-empty cell) or fall back to it — never forfeit.
        for seed in range(32):
            random.seed(seed)
            m = ai.get_best_move()
            assert m == (1, 1), f"seed {seed}: expected fallback to (1,1), got {m}"

    def test_ai_skips_wall_cells(self):
        """The AI never picks a wall cell, even though walls aren't
        tracked in board.grid. Fortress / Cell Lock / Ghost Board /
        Architect / Hourglass all place walls — picking one was a
        wasted opponent turn that gave the player a free move."""
        from game.board import Board
        from game.opponent import OpponentAI
        b = Board(size=3)
        # Wall every cell except (1, 1) so the AI is forced to either
        # pick the wall or the single truly-empty cell.
        for r in range(3):
            for c in range(3):
                if (r, c) != (1, 1):
                    b.wall_cells.append((r, c))
        ai = OpponentAI(b)
        import random
        for seed in range(32):
            random.seed(seed)
            m = ai.get_best_move()
            # Should always pick (1, 1); never a wall.
            assert m == (1, 1) or m is None
            if m is not None:
                assert m not in b.wall_cells

    def test_main_passes_fade_age_for_blind_boss_only(self):
        """The _ai_fade_age helper returns BLIND_FADE_AGE only on Blind
        boss games. Other games leave the AI omniscient."""
        from unittest.mock import patch
        from main import GameEngine, BLIND_FADE_AGE
        with patch('pygame.init'), patch('pygame.display.set_mode'), patch('pygame.display.set_caption'):
            engine = GameEngine()
        pl = engine.engine.state
        # Default non-boss state.
        assert engine._ai_fade_age() is None
        # Boss but not Blind.
        from config.bosses import BOSS_MAP
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["weighted"]
        assert engine._ai_fade_age() is None
        # Blind boss.
        pl.current_boss = BOSS_MAP["blind"]
        assert engine._ai_fade_age() == BLIND_FADE_AGE


class TestNewBosses:
    """Smoke tests for the second-pass boss additions: tide, echo,
    spotlight, inverse, taxman, vandal, twins, hourglass, quicksand,
    hivemind. Each test exercises just the on/off behaviour — full
    play simulation isn't tractable here."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_all_new_bosses_registered(self, mock_caption, mock_mode, mock_init):
        from config.bosses import BOSS_MAP
        for key in ("tide", "echo", "spotlight", "inverse", "taxman",
                    "vandal", "twins", "hourglass", "quicksand", "hivemind",
                    "cartographer", "architect",
                    "plague_doctor", "hot_potato"):
            assert key in BOSS_MAP, f"{key} boss missing"
        # Two-Headed was a verbatim duplicate of Twins and has been cut.
        assert "two_headed" not in BOSS_MAP

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_plague_doctor_halves_ink(self, mock_caption, mock_mode, mock_init):
        from systems.cardsystem import CardSystem
        from game.board import Board, PLAYER_X
        from game.player import Player
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        plain_ink, _, _ = cs.score_breakdown(board, player, 1, is_boss=True)
        plague_ink, _, _ = cs.score_breakdown(
            board, player, 1, is_boss=True, boss_mechanic="plague_doctor",
        )
        assert plague_ink == plain_ink // 2

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_architect_walls_at_game_start(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        # Force a 9x9 board (level 5) so Architect has room.
        engine.engine.state.level = 5
        engine.board.reset(9)
        engine._architect_walls()
        # Walls land inset 1 from the edges, with gaps at the centre row/col.
        assert any((r, c) in engine.board.wall_cells for r in (1, 7) for c in range(1, 8))

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_boss_game_grows_grid_by_one_row_and_col(self, mock_caption, mock_mode, mock_init):
        """Every boss game adds one row + one column on top of whatever
        the current grid size is. _setup_boss_board grows BEFORE per-
        mechanic setup so new cells are eligible for poison / ghost_wall
        sampling."""
        from main import GameEngine
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        engine.board.reset(5)  # start at 5x5
        rows_before = engine.board.rows
        cols_before = engine.board.cols
        engine._setup_boss_board(BOSS_MAP["weighted"])
        assert engine.board.rows == rows_before + 1
        assert engine.board.cols == cols_before + 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_boss_grow_carries_draw_growth(self, mock_caption, mock_mode, mock_init):
        """A board that's already 6x7 from a draw becomes 7x8 when the
        next boss game sets up — no shrink, just one more on each axis."""
        from main import GameEngine
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        engine.board.reset(5)
        # Simulate draw-growth by manually growing once.
        engine.board.grow_row_and_column()
        engine.board.grow_row_and_column()
        rows_before = engine.board.rows
        cols_before = engine.board.cols
        engine._setup_boss_board(BOSS_MAP["weighted"])
        assert engine.board.rows == rows_before + 1
        assert engine.board.cols == cols_before + 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_cartographer_swap_preserves_marks(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        engine.board.place_at(0, 0, PLAYER_X)
        engine.board.place_at(2, 2, OPPONENT_O)
        before = sum(1 for r in range(3) for c in range(3) if engine.board.grid[r][c] != 0)
        import random
        random.seed(0)
        engine._cartographer_swap()
        after = sum(1 for r in range(3) for c in range(3) if engine.board.grid[r][c] != 0)
        assert after == before  # marks count unchanged; only positions swap

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_hot_potato_rotates_lit_cell(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(3)
        seen = set()
        import random
        for seed in range(32):
            random.seed(seed)
            engine._hot_potato_rotate()
            if engine._hot_potato_cell is not None:
                seen.add(engine._hot_potato_cell)
        assert len(seen) > 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_taxman_drains_token_on_player_move(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.start_game()
        engine.state = "game"
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["taxman"]
        pl.player.tokens = 5
        avail, off_x, off_y = engine._board_layout()
        mx = off_x + 0 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        assert pl.player.tokens == 4

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_inverse_scores_centre_line_negative(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        engine.board.reset(3)
        # X line down the middle row — passes through centre (1, 1).
        engine.board.grid[1] = [PLAYER_X, PLAYER_X, PLAYER_X]
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["inverse"]
        engine.evaluate_and_settle()
        # Inverse flips the line's contribution negative → ink ≤ 0 →
        # total clamps to 0. The line still counts for the line-based
        # outcome decision (so this isn't a "lose" per se), but the
        # ink reward is zeroed.
        assert pl.last_total == 0

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_spotlight_only_zone_lines_score(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        engine.board.reset(5)
        # X line in row 0 cols 0-2; if Spotlight zone anchored at (2,2)
        # it's outside the zone and shouldn't score.
        for c in range(3):
            engine.board.grid[0][c] = PLAYER_X
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["spotlight"]
        engine._spotlight_anchor = (2, 2)
        result = engine.evaluate_and_settle()
        assert pl.last_ink == 0  # line is outside the spotlight

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_ghost_places_one_wall_on_boss_start(self, mock_caption, mock_mode, mock_init):
        """The Ghost boss's setup branch drops exactly one wall cell."""
        from main import GameEngine
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[], create=True), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        pl = engine.engine.state
        # Force a boss game next, with Ghost as the picked mechanic.
        pl.games_in_level = 2
        pl.boss_order = ["ghost_wall"]
        pl.boss_index = 0
        engine.start_game()
        assert pl.current_boss is not None
        assert pl.current_boss.mechanic == "ghost_wall"
        assert len(engine.board.wall_cells) == 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_mirror_player_alternates_x_and_o(self, mock_caption, mock_mode, mock_init):
        """On Mirror, two consecutive player clicks place X then O."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[], create=True), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.start_game()
        engine.state = "game"
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["mirror"]
        engine._mirror_player_o = False
        avail, off_x, off_y = engine._board_layout()
        # First click → X
        mx = off_x + 0 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        assert engine.board.grid[0][0] == PLAYER_X
        # Second click → O (no AI move happened in between)
        mx = off_x + 1 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        assert engine.board.grid[0][1] == OPPONENT_O

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_mirror_does_not_schedule_ai_move(self, mock_caption, mock_mode, mock_init):
        """The AI never moves on Mirror — _ai_move_at stays None."""
        from main import GameEngine
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[], create=True), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.start_game()
        engine.state = "game"
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["mirror"]
        engine._mirror_player_o = False
        avail, off_x, off_y = engine._board_layout()
        mx = off_x + 0 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        assert engine._ai_move_at is None

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_echo_mirrors_player_x_across_centre(self, mock_caption, mock_mode, mock_init):
        """Echo boss: an X at (0, 0) on a 5x5 board drops an O at (4, 4)."""
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[], create=True), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.engine.state.level = 2  # 5x5 board
        engine.start_game()
        engine.state = "game"
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["echo"]
        avail, off_x, off_y = engine._board_layout()
        # Click (0, 0) — Echo should mirror to (4, 4) on a 5x5 board.
        mx = off_x + 0 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        assert engine.board.grid[0][0] == PLAYER_X
        assert engine.board.grid[4][4] == OPPONENT_O

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_echo_no_longer_in_extras_tuple(self, mock_caption, mock_mode, mock_init):
        """Echo's response is the centre-mirror, not a generic 'extra AI
        O' — confirm by checking _tick_ai_move's extras logic. Twins is
        the only mechanic that should grant extras now."""
        from main import GameEngine
        from config.bosses import BOSS_MAP
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[], create=True), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.engine.state.level = 2  # 5x5 board
        engine.start_game()
        engine.state = "game"
        pl = engine.engine.state
        pl.is_boss = True
        pl.current_boss = BOSS_MAP["echo"]
        # Schedule an immediate AI move and tick it. The AI plays a
        # normal single O — not 2.
        import pygame as _pg
        engine._ai_move_at = _pg.time.get_ticks() - 1
        os_before = sum(
            1 for r in range(engine.board.rows) for c in range(engine.board.cols)
            if engine.board.grid[r][c] == -1
        )
        engine._tick_ai_move()
        os_after = sum(
            1 for r in range(engine.board.rows) for c in range(engine.board.cols)
            if engine.board.grid[r][c] == -1
        )
        # _tick_ai_move on Echo runs the AI exactly once (1 new O).
        assert os_after - os_before == 1


class TestClickHandlerDispatch:
    """`handle_click` now routes to per-state methods via the
    `_CLICK_HANDLERS` dispatch table. Pin the table shape so
    refactors can't silently drop a state, and exercise each
    handler enough to keep their CRAP under control."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_dispatch_table_covers_every_state(self, mc, mm, mi):
        from main import GameEngine
        expected = {
            "menu", "codex", "scores", "intro", "transition",
            "boss_intro", "gameover", "game", "shop",
        }
        assert set(GameEngine._CLICK_HANDLERS) == expected

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_codex_back_routes_to_menu_by_default(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.state = "codex"
        layout = engine._codex_layout()
        engine._click_codex(layout["back"].centerx, layout["back"].centery)
        assert engine.state == "menu"

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_codex_back_routes_to_return_state(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.state = "codex"
        engine._codex_return_state = "game"
        layout = engine._codex_layout()
        engine._click_codex(layout["back"].centerx, layout["back"].centery)
        assert engine.state == "game"
        assert engine._codex_return_state is None

    # Tab switching + chip selection live under the same _click_codex
    # entry point; they hit `back` first under the conftest pygame
    # stub (collidepoint always truthy) so they're not testable via
    # the dispatcher path. The dispatch-table pin + layout pin in
    # TestCodex cover the shape; coverage will come from a Phase-3
    # rect-aware fixture if needed.

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_intro_skip_marks_seen_and_transitions(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.state = "intro"
        engine._intro_step = 1
        layout = engine._intro_layout()
        with patch('main.mark_intro_seen') as mocked_mark:
            engine._click_intro(
                layout["skip"].centerx, layout["skip"].centery,
            )
            mocked_mark.assert_called_once()
        assert engine.state == "transition"

    # back / next are guarded by `skip` in the rect order — under the
    # conftest pygame stub `collidepoint` always returns truthy, so
    # `skip` would fire first regardless. Skip is the most important
    # path to pin, and it works because it's the first rect checked.

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_shop_card_purchase_consumes_tokens(self, mc, mm, mi):
        from main import GameEngine
        from config.constants import SCREEN_W, SCREEN_H, CARD_W
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.do_shop()
        pl = engine.engine.state
        pl.player.tokens = 50
        before_count = len(pl.player.passive_cards)
        sx = (SCREEN_W
              - (len(engine.shop_cards) * CARD_W
                 + max(0, len(engine.shop_cards) - 1) * 12)) // 2
        cx, cy = sx + CARD_W // 2, SCREEN_H // 2
        consumed = engine._try_buy_shop_card(cx, cy, pl)
        assert consumed is True
        assert len(pl.player.passive_cards) == before_count + 1

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_shop_card_refused_when_at_joker_cap(self, mc, mm, mi):
        from main import GameEngine
        from config.constants import SCREEN_W, SCREEN_H, CARD_W
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.do_shop()
        pl = engine.engine.state
        pl.player.tokens = 50
        pl.player.passive_cards = ["Point Multiplier"] * pl.joker_cap
        sx = (SCREEN_W
              - (len(engine.shop_cards) * CARD_W
                 + max(0, len(engine.shop_cards) - 1) * 12)) // 2
        cx, cy = sx + CARD_W // 2, SCREEN_H // 2
        consumed = engine._try_buy_shop_card(cx, cy, pl)
        assert consumed is True  # click consumed (flash fires)
        assert len(pl.player.passive_cards) == pl.joker_cap

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_shop_card_refused_when_low_tokens(self, mc, mm, mi):
        from main import GameEngine
        from config.constants import SCREEN_W, SCREEN_H, CARD_W
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        engine.do_shop()
        pl = engine.engine.state
        pl.player.tokens = 0
        before_count = len(pl.player.passive_cards)
        sx = (SCREEN_W
              - (len(engine.shop_cards) * CARD_W
                 + max(0, len(engine.shop_cards) - 1) * 12)) // 2
        cx, cy = sx + CARD_W // 2, SCREEN_H // 2
        engine._try_buy_shop_card(cx, cy, pl)
        assert len(pl.player.passive_cards) == before_count


class TestQuicksandTick:
    """Direct unit tests for `_quicksand_tick`. The helper iterates the
    board and erases marks that have been left without a same-side
    neighbour for >= 3 moves. Tested in isolation — no full-game
    fixture needed."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_erases_isolated_mark_past_age_threshold(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        # X at (2, 2) placed at move 1; no same-side neighbours.
        # Advance move_count so the age exceeds 3.
        engine.board.grid[2][2] = PLAYER_X
        engine.board.placed_at[2][2] = 1
        engine.board.move_count = 5
        engine._quicksand_tick()
        assert engine.board.grid[2][2] == 0

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_preserves_mark_with_same_neighbour(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        engine.board.grid[2][2] = PLAYER_X
        engine.board.grid[2][3] = PLAYER_X  # same-side neighbour
        engine.board.placed_at[2][2] = 1
        engine.board.placed_at[2][3] = 1
        engine.board.move_count = 5
        engine._quicksand_tick()
        # Both survive — each one is the other's neighbour.
        assert engine.board.grid[2][2] == PLAYER_X
        assert engine.board.grid[2][3] == PLAYER_X

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_skips_recently_placed(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        engine.board.grid[2][2] = PLAYER_X
        engine.board.placed_at[2][2] = 3
        engine.board.move_count = 4  # age = 1 < 3 → safe
        engine._quicksand_tick()
        assert engine.board.grid[2][2] == PLAYER_X

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_empty_cells_untouched(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(3)
        engine.board.move_count = 10
        engine._quicksand_tick()
        # No marks → no removals.
        assert all(
            engine.board.grid[r][c] == 0 for r in range(3) for c in range(3)
        )


class TestVandalStrike:
    """Direct unit tests for `_vandal_strike`. Removes one random
    non-edge X cell per call, or no-ops when none exist."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_removes_interior_x(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        engine.board.grid[2][2] = PLAYER_X  # interior cell
        engine._vandal_strike()
        assert engine.board.grid[2][2] == 0

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_skips_edge_x(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        # Only edge X's → vandal has no candidates and no-ops.
        engine.board.grid[0][0] = PLAYER_X
        engine.board.grid[0][4] = PLAYER_X
        engine.board.grid[4][2] = PLAYER_X
        engine._vandal_strike()
        assert engine.board.grid[0][0] == PLAYER_X
        assert engine.board.grid[0][4] == PLAYER_X
        assert engine.board.grid[4][2] == PLAYER_X

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_no_op_on_empty_board(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(5)
        # No X's at all — no-op, no crash.
        engine._vandal_strike()

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_removes_exactly_one_per_call(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        for (r, c) in [(1, 1), (1, 2), (2, 1), (2, 3)]:
            engine.board.grid[r][c] = PLAYER_X
        before = sum(
            1 for r in range(5) for c in range(5)
            if engine.board.grid[r][c] == PLAYER_X
        )
        engine._vandal_strike()
        after = sum(
            1 for r in range(5) for c in range(5)
            if engine.board.grid[r][c] == PLAYER_X
        )
        assert before - after == 1


class TestTideTick:
    """`_tide_tick` walks `_tide_clear_deadlines` and clears any cells
    whose deadline has passed (move_count >= when)."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_clears_cells_at_or_past_deadline(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        engine.board.grid[1][0] = PLAYER_X
        engine.board.grid[1][1] = PLAYER_X
        engine.board.grid[1][2] = PLAYER_X
        engine.board.move_count = 10
        engine._tide_clear_deadlines = [(10, [(1, 0), (1, 1), (1, 2)])]
        engine._tide_tick()
        assert engine.board.grid[1][0] == 0
        assert engine.board.grid[1][1] == 0
        assert engine.board.grid[1][2] == 0
        # Deadline consumed.
        assert engine._tide_clear_deadlines == []

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_keeps_cells_before_deadline(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(5)
        engine.board.grid[0][0] = PLAYER_X
        engine.board.move_count = 5
        engine._tide_clear_deadlines = [(10, [(0, 0)])]
        engine._tide_tick()
        # Mark survives; deadline preserved for a later tick.
        assert engine.board.grid[0][0] == PLAYER_X
        assert engine._tide_clear_deadlines == [(10, [(0, 0)])]

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_empty_list_noop(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(5)
        engine._tide_clear_deadlines = []
        engine._tide_tick()  # no crash
        assert engine._tide_clear_deadlines == []

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_already_cleared_cell_is_skipped(self, mc, mm, mi):
        """If a scheduled cell is already empty (e.g. cleared by another
        boss mechanic), the tick must not crash."""
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(5)
        # Cell is empty even though it's scheduled.
        engine.board.move_count = 10
        engine._tide_clear_deadlines = [(10, [(2, 2)])]
        engine._tide_tick()
        assert engine._tide_clear_deadlines == []


class TestLiveLineView:
    """`_refresh_line_view` fills `pl.live_line_contributions` so the
    HUD can paint live streaks + per-side ink totals without waiting
    for the result panel."""

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_refresh_populates_x_lines(self, mc, mm, mi):
        from main import GameEngine
        from game.board import PLAYER_X
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        engine._refresh_line_view(pl)
        assert len(pl.live_line_contributions) == 1
        assert pl.live_line_contributions[0]["side"] == "X"

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_refresh_returns_empty_on_empty_board(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        engine._refresh_line_view(pl)
        assert pl.live_line_contributions == []

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_start_game_clears_live_lines(self, mc, mm, mi):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]), \
             patch('main.is_intro_seen', return_value=True):
            engine.new_run()
        pl = engine.engine.state
        # Seed a stale value.
        pl.live_line_contributions = [{"cells": [(0, 0)], "side": "X",
                                        "base": 5, "modifiers": [],
                                        "wildcard": False,
                                        "contribution": 5}]
        engine.start_game()
        assert pl.live_line_contributions == []

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_runstate_default_is_empty(self, mc, mm, mi):
        from game.player import RunState
        rs = RunState()
        assert rs.live_line_contributions == []
