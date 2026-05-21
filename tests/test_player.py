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
        assert p.upgrades == {}
        assert p.cells_played == []
        assert p.passive_cards == []
        assert p.blind_shot_marks == []

    def test_player_with_tokens(self):
        p = Player(tokens=10)
        assert p.tokens == 10

    def test_player_upgrades_dict(self):
        p = Player()
        p.upgrades["diagonal_power"] = 1
        assert p.upgrades["diagonal_power"] == 1

    def test_player_can_append_passive_card(self):
        p = Player()
        p.passive_cards.append("Point Multiplier")
        assert p.passive_cards == ["Point Multiplier"]


class TestRunState:
    def test_default_runstate(self):
        rs = RunState()
        assert rs.level == 1
        assert rs.grid_size == 3
        assert rs.games_in_level == 0
        assert rs.games_per_level == 2
        assert rs.total_score == 0
        assert rs.score_this_level == 0
        assert rs.score_targets == [6, 12, 20, 35, 55, 80, 120]
        assert rs.ante_targets == [8, 30, 100, 200, 400, 700, 1100]
        assert rs.current_target == 0
        assert rs.ante_target == 0
        assert rs.is_boss is False
        assert rs.shop_phase is False
        assert rs.run_complete is False
        assert rs.won_run is False
        assert rs.lives == 3
        assert rs.max_lives == 3
        assert rs.joker_cap == 5
        assert rs.max_base_level == 7
        assert rs.endless_mode is False
        assert rs.intro_seen is False
        assert rs.consecutive_wins == 0
        assert rs.draws_this_game == 0
        assert rs.score_this_game == 0
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

    def test_get_target_full_table(self):
        # 7-level base run; level n picks score_targets[n-1].
        targets = [6, 12, 20, 35, 55, 80, 120]
        for i, expected in enumerate(targets, start=1):
            assert RunState(level=i).get_target() == expected

    def test_get_target_endless_formula(self):
        # Past level 7, targets scale 1.3x per level past the base.
        assert RunState(level=8).get_target() == int(120 * 1.3)
        assert RunState(level=10).get_target() == int(120 * 1.3 ** 3)

    def test_get_ante_target_levels(self):
        antes = [8, 30, 100, 200, 400, 700, 1100]
        for i, expected in enumerate(antes, start=1):
            assert RunState(level=i).get_ante_target() == expected

    def test_get_ante_target_endless_formula(self):
        assert RunState(level=8).get_ante_target() == int(1100 * 1.4)

    def test_get_multiplier_equals_level(self):
        # Multiplier scales linearly with level — no clamp.
        for lvl in (1, 2, 3, 4, 5, 6, 7, 8, 10, 20):
            assert RunState(level=lvl).get_multiplier() == lvl

    def test_get_grid_size_full_table(self):
        sizes = [3, 5, 7, 7, 9, 9, 9]
        for i, expected in enumerate(sizes, start=1):
            assert RunState(level=i).get_grid_size() == expected

    def test_get_grid_size_endless_grows(self):
        # Endless grows +1 every 2 levels past the base run.
        assert RunState(level=8).get_grid_size() == 9
        assert RunState(level=9).get_grid_size() == 10
        assert RunState(level=11).get_grid_size() == 11

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

    def test_next_level_from_7_no_score_fails_run(self):
        # Base run is 7 levels — completing level 7 with score < target
        # ends the run as a loss.
        rs = RunState(level=7, score_this_level=0)
        result = rs.next_level()
        assert result is False
        assert rs.run_complete is True
        assert rs.won_run is False

    def test_next_level_from_7_with_score_wins_run(self):
        rs = RunState(level=7, score_this_level=120)
        result = rs.next_level()
        assert result is False
        assert rs.run_complete is True
        assert rs.won_run is True

    def test_next_level_from_intermediate_levels_advances(self):
        # Levels 1-6 always advance regardless of score.
        for start in (1, 2, 3, 4, 5, 6):
            rs = RunState(level=start, score_this_level=0)
            result = rs.next_level()
            assert result is True
            assert rs.level == start + 1
            assert rs.run_complete is False

    def test_next_level_in_endless_never_ends(self):
        # endless_mode = True bypasses the base-run cap.
        rs = RunState(level=7, score_this_level=120, endless_mode=True)
        rs.next_level()
        assert rs.level == 8
        assert rs.run_complete is False
        # Even at level 50 it keeps going.
        rs2 = RunState(level=50, endless_mode=True)
        rs2.next_level()
        assert rs2.level == 51
        assert rs2.run_complete is False

    def test_reset_level_clears_states(self):
        rs = RunState(level=1)
        rs.games_in_level = 2
        rs.is_boss = True
        rs.shop_phase = True
        rs.score_this_level = 10
        rs.player.cells_played = [(0, 0)]

        rs.reset_level()

        assert rs.games_in_level == 0
        assert rs.is_boss is False
        assert rs.shop_phase is False
        assert rs.score_this_level == 0
        assert rs.player.cells_played == []
