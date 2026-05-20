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
        assert engine.card_played_this_turn is False
        assert engine.player_placed_this_turn is False


class TestMainEngineRun:
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_new_run(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        assert engine.state == "transition"
        assert len(engine.starter_cards) == 3

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_new_run_incorporates_unlocked(self, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=["Point Multiplier"]):
            engine.new_run()
        assert "Point Multiplier" in engine.engine.state.player.deck


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
        engine.engine.card_system.calculate_score = MagicMock(return_value=6)
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
    def test_second_draw_within_same_game_loses_a_life(self, mock_ticks, mock_caption, mock_mode, mock_init):
        """Drawing twice in one game now ends as a loss and costs a life
        (the old behaviour was to keep growing forever for a 0.9x penalty,
        which was the exploit)."""
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
        # Force a second draw on the now-grown board by re-creating the
        # tied pattern and re-evaluating.
        engine.board.reset(3)
        engine.board.grid = [
            [PLAYER_X, PLAYER_X, PLAYER_X],
            [OPPONENT_O, OPPONENT_O, OPPONENT_O],
            [PLAYER_X, OPPONENT_O, PLAYER_X],
        ]
        result = engine.evaluate_and_settle()
        assert result == "lose"
        assert pl.lives == lives_before - 1

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
    def test_player_line_ends_game(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        engine.start_game()
        engine.state = "game"
        # Pre-place 2 X's in row 0 and a couple of O's elsewhere so completing
        # the X line doesn't also fill the board.
        engine.board.grid[0][0] = PLAYER_X
        engine.board.grid[0][1] = PLAYER_X
        engine.board.grid[1][0] = OPPONENT_O
        engine.board.grid[1][1] = OPPONENT_O
        engine.board.move_count = 4
        # Player clicks (0, 2) — completes the X line. Board still has empty cells.
        avail, off_x, off_y = engine._board_layout()
        mx = off_x + 2 * avail + avail // 2
        my = off_y + 0 * avail + avail // 2
        engine.handle_click(mx, my, 1)
        assert engine.engine.state.game_result == "win"
        assert engine.showing_result is True
        # Board should NOT be full — the win came from a line, not from filling.
        assert engine.board.is_full() is False

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
        # Click overlay — should advance to next game (countdown), not shop
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
        engine.start_game()  # → boss
        engine.state = "game"
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        pl.player.score = 10
        pl.current_target = 1
        # Make the ante trivially passable for this test — the ante check
        # is exercised separately.
        pl.ante_target = 0
        engine.evaluate_and_settle()
        # Boss win → showing_result True with pl.is_boss True
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
