"""Tests for game/player.py - Player and RunState dataclasses."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from game.player import Player, RunState


class TestPlayer:
    def test_default_player(self):
        p = Player()
        assert p.tokens == 0
        assert p.score == 0
        assert p.deck == []
        assert p.hand == []
        assert p.upgrades == {}
        assert p.cells_played == []
        assert p.placed_on_turn == 0
        assert p.can_play_card is True

    def test_player_with_tokens(self):
        p = Player(tokens=10)
        assert p.tokens == 10

    def test_player_adding_hand_card(self):
        p = Player()
        p.hand.append("Double Strike")
        assert p.hand == ["Double Strike"]

    def test_player_upgrades_dict(self):
        p = Player()
        p.upgrades["diagonal_power"] = 1
        assert p.upgrades["diagonal_power"] == 1


class TestRunState:
    def test_default_runstate(self):
        rs = RunState()
        assert rs.level == 1
        assert rs.grid_size == 3
        assert rs.games_in_level == 0
        assert rs.games_per_level == 2
        assert rs.total_score == 0
        assert rs.score_this_level == 0
        assert rs.score_targets == [6, 12, 20]
        assert rs.current_target == 0
        assert rs.is_boss is False
        assert rs.shop_phase is False
        assert rs.run_complete is False
        assert rs.won_run is False
        assert isinstance(rs.player, Player)

    def test_get_grid_size_level_1(self):
        rs = RunState(level=1)
        assert rs.get_grid_size() == 3

    def test_get_grid_size_level_2(self):
        rs = RunState(level=2)
        assert rs.get_grid_size() == 5

    def test_get_grid_size_level_3(self):
        rs = RunState(level=3)
        assert rs.get_grid_size() == 7

    def test_get_grid_size_level_4_clamped(self):
        rs = RunState(level=4)
        assert rs.get_grid_size() == 7

    def test_get_target_level_1(self):
        rs = RunState(level=1)
        assert rs.get_target() == 6

    def test_get_target_level_2(self):
        rs = RunState(level=2)
        assert rs.get_target() == 12

    def test_get_target_level_3(self):
        rs = RunState(level=3)
        assert rs.get_target() == 20

    def test_get_target_level_4_clamped(self):
        rs = RunState(level=4)
        assert rs.get_target() == 20

    def test_get_multiplier_level_1(self):
        rs = RunState(level=1)
        assert rs.get_multiplier() == 1

    def test_get_multiplier_level_2(self):
        rs = RunState(level=2)
        assert rs.get_multiplier() == 2

    def test_get_multiplier_level_3(self):
        rs = RunState(level=3)
        assert rs.get_multiplier() == 3

    def test_get_multiplier_level_4_clamped(self):
        rs = RunState(level=4)
        assert rs.get_multiplier() == 3

    def test_next_level_from_1_advances(self):
        rs = RunState(level=1)
        result = rs.next_level()
        assert result is True
        assert rs.level == 2
        assert rs.games_in_level == 0
        assert rs.is_boss is False
        assert rs.shop_phase is True

    def test_next_level_from_2_advances(self):
        rs = RunState(level=2)
        result = rs.next_level()
        assert result is True
        assert rs.level == 3

    def test_next_level_from_3_no_score_complete(self):
        rs = RunState(level=3, score_this_level=0, current_target=20)
        result = rs.next_level()
        assert result is False
        assert rs.run_complete is True
        assert rs.won_run is False

    def test_next_level_from_3_with_score_complete(self):
        rs = RunState(level=3, score_this_level=20, current_target=20)
        result = rs.next_level()
        assert result is False
        assert rs.run_complete is True
        assert rs.won_run is True

    def test_next_level_from_4_falls_through(self):
        rs = RunState(level=4)
        result = rs.next_level()
        assert result is False

    def test_reset_level_clears_states(self):
        rs = RunState(level=1)
        rs.games_in_level = 2
        rs.is_boss = True
        rs.shop_phase = True
        rs.score_this_level = 10
        rs.player.hand = ["Double Strike"]
        rs.player.cells_played = [(0, 0)]
        rs.player.placed_on_turn = 1
        rs.player.can_play_card = False

        rs.reset_level()

        assert rs.games_in_level == 0
        assert rs.is_boss is False
        assert rs.shop_phase is False
        assert rs.score_this_level == 0
        assert rs.player.hand == []
        assert rs.player.cells_played == []
        assert rs.player.placed_on_turn == 0
        assert rs.player.can_play_card is True
