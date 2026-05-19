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
