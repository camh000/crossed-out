"""Tests for save/savesetup.py - Meta-progression persistence."""
import sys
import os
json_path = os.path.join(os.path.dirname(__file__), '..', 'crossed_out_save.json')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from save.savesetup import (
    save_progression, load_progression, get_unlocked_cards,
    is_intro_seen, mark_intro_seen,
)


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

    def test_unlock_sacrifice_at_5_wins(self):
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        for _ in range(5):
            save_progression(won=True, tokens_earned=1, levels_reached=1, cards_unlocked=[])
        unlocked = get_unlocked_cards()
        assert "Sacrifice" in unlocked

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
        assert unlocked.count("Sacrifice") == 1

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


class TestCorruptedSave:
    def setup_method(self):
        if os.path.exists(json_path):
            os.remove(json_path)

    def test_corrupted_json_returns_empty_dict(self):
        """A malformed save file should not crash the game — degrade to {}."""
        from save.savesetup import load_progression
        with open(json_path, "w") as f:
            f.write("{not valid json at all,,,")
        assert load_progression() == {}

    def test_truncated_json_returns_empty_dict(self):
        from save.savesetup import load_progression
        with open(json_path, "w") as f:
            f.write('{"won_run": true,')
        assert load_progression() == {}

    def test_empty_file_returns_empty_dict(self):
        from save.savesetup import load_progression
        open(json_path, "w").close()  # empty
        assert load_progression() == {}

    def test_corrupted_save_can_be_overwritten(self):
        """After a corrupted load, the next save_progression call should produce a clean file."""
        from save.savesetup import save_progression, load_progression
        with open(json_path, "w") as f:
            f.write("garbage")
        save_progression(won=True, tokens_earned=3, levels_reached=1, cards_unlocked=[])
        data = load_progression()
        assert data["won_run"] is True
        assert data["tokens_banked"] == 3


class TestIntroSeenFlag:
    def setup_method(self):
        if os.path.exists(json_path):
            os.remove(json_path)

    def test_default_intro_unseen(self):
        assert is_intro_seen() is False

    def test_mark_intro_seen_persists(self):
        mark_intro_seen()
        assert is_intro_seen() is True

    def test_mark_intro_seen_preserves_other_fields(self):
        save_progression(won=True, tokens_earned=5, levels_reached=3, cards_unlocked=[])
        mark_intro_seen()
        data = load_progression()
        assert data["intro_seen"] is True
        assert data["won_run"] is True
        assert data["tokens_banked"] == 5
        assert data["levels_reached"] == 3


class TestSavePathResolution:
    def test_save_path_is_absolute(self):
        """SAVE_PATH should be an absolute path so the save survives a cwd change."""
        from save.savesetup import SAVE_PATH
        assert os.path.isabs(SAVE_PATH)

    def test_save_path_in_project_root(self):
        """SAVE_PATH should live alongside main.py, not inside save/."""
        from save.savesetup import SAVE_PATH
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assert os.path.dirname(SAVE_PATH) == project_root

    def test_save_works_from_different_cwd(self, tmp_path, monkeypatch):
        """Changing cwd should not change where the save file lives."""
        from save.savesetup import save_progression, SAVE_PATH
        # Clean state
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
        monkeypatch.chdir(tmp_path)
        save_progression(won=False, tokens_earned=0, levels_reached=1, cards_unlocked=[])
        # Save should appear at SAVE_PATH, not in tmp_path
        assert os.path.exists(SAVE_PATH)
        assert not (tmp_path / "crossed_out_save.json").exists()
        # cleanup
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
