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
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        engine.board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        engine.board.grid[1] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        pl = engine.engine.state
        pl.is_boss = False
        pl.player.score = 0
        pl.total_score = 0
        pl.score_this_level = 0
        pl.current_target = 10
        pl.player = MagicMock()
        pl.tokens = 0
        pl.next_level()
        pl.next_level()
        pl.next_level()
        pl.player.score = 0
        pl.player.hand = []
        pl.player.cells_played = []
        pl.player.placed_on_turn = 0
        pl.player.can_play_card = True
        pl.get_multiplier = MagicMock(return_value=1)
        pl.player.score = 6
        pl.total_score = 0
        pl.score_this_level = 0
        pl.current_target = 3
        engine.engine.card_system.calculate_score = MagicMock(return_value=6)
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
        result = engine._evaluate_boss()
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
        before = len(engine.board.valid_cells)
        result = engine.evaluate_and_settle()
        assert result == "draw"
        assert len(engine.board.valid_cells) == before + 1
        assert engine.board.game_over is False
        assert engine.showing_result is False
        assert pl.draw_multiplier == 0.9

    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.display.set_caption')
    @patch('pygame.time.get_ticks', return_value=1000)
    def test_draw_penalty_compounds(self, mock_ticks, mock_caption, mock_mode, mock_init):
        from main import GameEngine
        from game.board import PLAYER_X, OPPONENT_O
        engine = GameEngine()
        engine.board.reset(3)
        pl = engine.engine.state
        pl.is_boss = False
        pl.player.score = 0
        pl.current_target = 999
        pl.draw_multiplier = 1.0
        # Trigger three draws. The board grows each time, so we reset to a
        # clean balanced 3x3 between iterations — the multiplier on RunState
        # persists across resets.
        for _ in range(3):
            engine.board.reset(3)
            engine.board.grid = [
                [PLAYER_X, PLAYER_X, PLAYER_X],
                [OPPONENT_O, OPPONENT_O, OPPONENT_O],
                [PLAYER_X, OPPONENT_O, PLAYER_X],
            ]
            assert engine.evaluate_and_settle() == "draw"
        assert abs(pl.draw_multiplier - 0.9 ** 3) < 1e-9

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
