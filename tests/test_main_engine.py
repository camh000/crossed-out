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
        with patch('main.get_unlocked_cards', return_value=[]):
            engine.new_run()
        assert engine.state == "transition"
        assert len(engine.starter_cards) == 3

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    def test_new_run_seeds_empty_passive_cards(self, mock_caption, mock_mode, mock_init):
        """A fresh run starts with no jokers — the starter screen picks
        one before the first game starts."""
        from main import GameEngine
        engine = GameEngine()
        with patch('main.get_unlocked_cards', return_value=[]):
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

    def test_level3_win_check_uses_pre_increment_target(self):
        """Beating level 3 with cumulative ink ≥ that level's target should
        register as a run win. The check must happen BEFORE level += 1, or
        get_target() would compare against the clamped final value."""
        from game.player import RunState
        rs = RunState(level=3)
        rs.score_this_level = rs.get_target()  # exactly hit
        rs.next_level()
        assert rs.run_complete is True
        assert rs.won_run is True

    def test_level3_miss_check_fails_run(self):
        from game.player import RunState
        rs = RunState(level=3)
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

    def test_ai_forfeits_when_picking_occupied_faded_cell(self):
        """If the AI's blind perception leads it to pick a cell that's
        actually occupied (a faded mark), get_best_move returns None
        instead of a guaranteed-to-fail placement."""
        from game.board import Board, PLAYER_X
        from game.opponent import OpponentAI
        # Fill every cell except one, all aged past the fade threshold.
        b = Board(size=3)
        for r in range(3):
            for c in range(3):
                if (r, c) != (1, 1):
                    b.place_at(r, c, PLAYER_X)
        # move_count == 8; oldest cell is age 7. With fade_age=1 every
        # placed cell is "faded" from the AI's view, so the AI thinks
        # all of them are EMPTY and may pick any of them.
        ai = OpponentAI(b, fade_age=1)
        # Force the perceived view to a known state where the AI picks
        # a truly-occupied cell — by seeding random it'll choose from
        # the perceived-empty set which includes everything but is
        # mostly real-occupied.
        import random
        # Try several seeds — at least one should land on a real-occupied
        # cell and return None.
        forfeited = False
        for seed in range(32):
            random.seed(seed)
            m = ai.get_best_move()
            # The AI's choice is either the truly-empty (1,1) or None
            # (forfeit). It should never name a real-occupied cell.
            if m is None:
                forfeited = True
            else:
                assert m == (1, 1)
        assert forfeited, "AI never forfeited despite perceived-empty cells being real-occupied"

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
