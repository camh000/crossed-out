"""Tests for save/savesetup.py - Meta-progression persistence."""
import sys
import os
json_path = os.path.join(os.path.dirname(__file__), '..', 'crossed_out_save.json')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from save.savesetup import save_progression, load_progression, get_unlocked_cards


class TestSaveProgression:
    def setup_method(self):
        """Clean up save file before each test."""
        if os.path.exists(json_path):
            os.remove(json_path)

    def test_save_won_run(self):
        data = save_progression(won=True, tokens_earned=5, levels_reached=1, cards_unlocked=[])
        assert data["won_run"] is True
        assert data["tokens_banked"] == 5
        assert data["levels_reached"] == 1

    def test_save_lost_run(self):
        data = save_progression(won=False, tokens_earned=3, levels_reached=1, cards_unlocked=[])
        assert data["won_run"] is False
        assert data["tokens_banked"] == 0
        assert data["levels_reached"] == 1

    def test_save_creates_file(self):
        save_progression(won=True, tokens_earned=5, levels_reached=1, cards_unlocked=[])
        assert os.path.exists(json_path)

    def test_save_loads_back(self):
        save_progression(won=True, tokens_earned=5, levels_reached=2, cards_unlocked=["Double Strike"])
        loaded = load_progression()
        assert loaded["won_run"] is True
        assert loaded["levels_reached"] == 2

    def test_save_initial_total_runs_zero(self):
        data = save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        assert data["total_runs"] == 0

    def test_save_consecutive_increments_runs(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        data2 = save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        assert data2["total_runs"] == 1


class TestUnlockCards:
    def setup_method(self):
        if os.path.exists(json_path):
            os.remove(json_path)

    def test_unlock_double_strike_at_3_wins(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        assert "Double Strike" in unlocked

    def test_unlock_double_strike_before_3_wins(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        assert "Double Strike" not in unlocked

    def test_unlock_o_flipper_at_5_wins(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        for _ in range(5):
            save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        assert "O Flipper" in unlocked

    def test_unlock_ghost_board_at_8_wins(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        for _ in range(8):
            save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        assert "Ghost Board" in unlocked

    def test_does_not_unlock_twice(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        for _ in range(6):
            save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        assert unlocked.count("O Flipper") == 1

    def test_preserves_cards_between_wins(self):
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=["Double Strike"])
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        # First run unlocked Double Strike, should be preserved
        assert "Double Strike" in unlocked


class TestLoadProgression:
    def setup_method(self):
        if os.path.exists(json_path):
            os.remove(json_path)

    def test_load_returns_empty_dict_when_no_file(self):
        data = load_progression()
        assert data == {}

    def test_load_returns_valid_data(self):
        save_progression(won=True, tokens_earned=5, levels_reached=1, cards_unlocked=[])
        data = load_progression()
        assert "won_run" in data
        assert "tokens_banked" in data
        assert "levels_reached" in data
        assert "total_runs" in data
        assert "wins" in data
        assert "cards_unlocked" in data

    def test_load_get_unlocked_cards_returns_list(self):
        data = get_unlocked_cards()
        assert isinstance(data, list)

    def test_unlocked_cards_from_saved_data(self):
        save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=["Point Multiplier"])
        data = get_unlocked_cards()
        assert "Point Multiplier" in data
