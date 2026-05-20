"""Tests for systems/cardsystem.py — joker dispatch and ink × mult scoring."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import random
import pytest
from systems.cardsystem import CardSystem
from game.player import Player
from game.board import Board, PLAYER_X, OPPONENT_O, EMPTY
from config.cards import get_by_name, ALL_CARDS


# ----------------------------------------------------------------------
# apply_passive_buffs / post_game_cleanup
# ----------------------------------------------------------------------


class TestApplyPassiveBuffs:
    def test_buff_stacks_set_from_passive_cards(self):
        cs = CardSystem()
        player = Player(passive_cards=["Point Multiplier", "Point Multiplier", "Diagonal Power"])
        cs.apply_passive_buffs(player)
        assert player.upgrades["point_mult"] == 2
        assert player.upgrades["diagonal_power"] == 1

    def test_replay_resets_stale_counts(self):
        cs = CardSystem()
        player = Player(passive_cards=["Point Multiplier"])
        cs.apply_passive_buffs(player)
        cs.apply_passive_buffs(player)
        assert player.upgrades["point_mult"] == 1

    def test_sacrifice_charges_seeded_per_copy(self):
        cs = CardSystem()
        player = Player(passive_cards=["Sacrifice", "Sacrifice"])
        cs.apply_passive_buffs(player)
        assert player.upgrades["sacrifice_charges"] == 2

    def test_skip_opponent_zeroed_then_filled_by_trigger(self):
        """Quick Draw fills `skip_opponent` via its on_game_start handler,
        not via apply_passive_buffs directly. So immediately after
        apply_passive_buffs the stack is 0 even when Quick Draw is owned."""
        cs = CardSystem()
        player = Player(passive_cards=["Quick Draw", "Quick Draw"])
        player.upgrades["skip_opponent"] = 99  # stale
        cs.apply_passive_buffs(player)
        assert player.upgrades["skip_opponent"] == 0


class TestLineContributions:
    """Per-line breakdown used by the result panel to colour-code each
    completed line on the board with a +N / -N label."""

    def test_x_line_positive_contribution(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        contribs = cs.line_contributions(board, player)
        assert len(contribs) == 1
        c = contribs[0]
        assert c["side"] == "X"
        assert c["contribution"] > 0
        assert tuple(c["cells"]) == ((0, 0), (0, 1), (0, 2))

    def test_o_line_subtracts_by_default(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[2] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        contribs = cs.line_contributions(board, player)
        assert len(contribs) == 1
        c = contribs[0]
        assert c["side"] == "O"
        assert c["contribution"] < 0

    def test_doublecross_o_line_becomes_positive(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[2] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        contribs = cs.line_contributions(
            board, player, is_boss=True, boss_mechanic="doublecross",
        )
        assert contribs[0]["contribution"] > 0

    def test_point_mult_appears_in_modifiers(self):
        cs = CardSystem()
        player = Player(upgrades={"point_mult": 2})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        contribs = cs.line_contributions(board, player)
        labels = [m[0] for m in contribs[0]["modifiers"]]
        assert any("Point Mult" in label for label in labels)

    def test_blind_shot_doubles_line_when_intersecting(self):
        cs = CardSystem()
        player = Player()
        player.blind_shot_marks = [(0, 0)]
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        contribs = cs.line_contributions(board, player)
        labels = [m[0] for m in contribs[0]["modifiers"]]
        assert any("Blind Shot" in label for label in labels)
        # Base ink for a 3-cell line is weight_sum × length = 3 × 3 = 9.
        # Blind Shot doubles it → 18.
        assert contribs[0]["contribution"] == 18


class TestNewBuffCards:
    """The second-pass buffs that fold into line_contributions /
    score_breakdown — Edge Lord, Centripetal, First Strike, Counter,
    Rich Vein, Quartet, Last Stand, Magnitude, Lethal."""

    def test_edge_lord_boosts_edge_line(self):
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"edge_lord": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]  # top edge row
        plain_ink, _, _ = cs.score_breakdown(board, plain, 1)
        buff_ink, _, _ = cs.score_breakdown(board, buffed, 1)
        assert buff_ink > plain_ink

    def test_centripetal_adds_to_centre_line(self):
        cs = CardSystem()
        buffed = Player(upgrades={"centripetal": 2})
        board = Board()
        board.grid[1] = [PLAYER_X, PLAYER_X, PLAYER_X]  # passes (1,1)
        ink, _, _ = cs.score_breakdown(board, buffed, 1)
        plain, _, _ = cs.score_breakdown(board, Player(), 1)
        assert ink - plain == 10  # +5 per copy × 2

    def test_first_strike_only_on_first_line(self):
        cs = CardSystem()
        player = Player(upgrades={"first_strike": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        # Before any line scored — bonus applies.
        ink_first, _, _ = cs.score_breakdown(board, player, 1)
        # Mark the first line as scored. Subsequent contributions skip it.
        player.upgrades["first_x_line_done"] = 1
        ink_after, _, _ = cs.score_breakdown(board, player, 1)
        assert ink_first - ink_after == 20

    def test_counter_one_shot_consumed(self):
        cs = CardSystem()
        player = Player(upgrades={"counter_bonus_ink": 4})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        contribs = cs.line_contributions(board, player)
        # Counter folds 4 ink into the line modifiers.
        labels = [m[0] for m in contribs[0]["modifiers"]]
        assert any("Counter" in l for l in labels)

    def test_quartet_doubles_ink_with_four_distinct_jokers(self):
        cs = CardSystem()
        player = Player(
            upgrades={"quartet": 1},
            passive_cards=["Quartet", "Edge Lord", "Centripetal", "Deep Grid"],
        )
        # Manually re-seed (don't call apply_passive_buffs — that
        # overwrites quartet which we set directly).
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        single = Player(passive_cards=["Quartet"], upgrades={"quartet": 1})
        ink_solo, _, _ = cs.score_breakdown(board, single, 1)
        ink_quartet, _, _ = cs.score_breakdown(board, player, 1)
        assert ink_quartet >= 2 * ink_solo

    def test_last_stand_boosts_ink_when_one_life(self):
        cs = CardSystem()
        player = Player(upgrades={"last_stand": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        normal, _, _ = cs.score_breakdown(board, player, 1, lives=3)
        clutch, _, _ = cs.score_breakdown(board, player, 1, lives=1)
        assert clutch > normal

    def test_magnitude_only_when_board_grown(self):
        cs = CardSystem()
        player = Player(upgrades={"magnitude": 1})
        small = Board(size=3)
        small.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        big = Board(size=7)
        big.grid[0] = [PLAYER_X] * 7
        _, m_small, _ = cs.score_breakdown(small, player, 1)
        _, m_big, _ = cs.score_breakdown(big, player, 1)
        assert m_big > m_small

    def test_lethal_only_on_boss_games(self):
        cs = CardSystem()
        player = Player(upgrades={"lethal": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        _, m_normal, _ = cs.score_breakdown(board, player, 1, is_boss=False)
        _, m_boss, _ = cs.score_breakdown(board, player, 1, is_boss=True)
        assert m_boss > m_normal


class TestPostGameCleanup:
    def test_persistent_buffs_survive(self):
        cs = CardSystem()
        player = Player(passive_cards=["Point Multiplier", "Token Bonus"])
        cs.apply_passive_buffs(player)
        cs.post_game_cleanup(player)
        # apply_passive_buffs in the NEXT game will re-seed these — we
        # check they got cleaned out here so post_game_cleanup only kills
        # per-game scratch.
        assert "skip_opponent" not in player.upgrades
        assert "sacrifice_charges" not in player.upgrades
        # blind_shot_marks always clears.
        assert player.blind_shot_marks == []


# ----------------------------------------------------------------------
# on_game_start triggers
# ----------------------------------------------------------------------


class TestGameStartTriggers:
    def test_cell_lock_locks_centre(self):
        cs = CardSystem()
        player = Player(passive_cards=["Cell Lock"])
        cs.apply_passive_buffs(player)
        board = Board()
        cs.fire_game_start(board, player)
        # 3x3 → centre is (1, 1).
        assert (1, 1) in board.wall_cells

    def test_cell_lock_stacks_add_random_walls(self):
        cs = CardSystem()
        player = Player(passive_cards=["Cell Lock", "Cell Lock", "Cell Lock"])
        cs.apply_passive_buffs(player)
        random.seed(0)
        board = Board(size=5)
        cs.fire_game_start(board, player)
        # Centre plus (stacks-1)=2 more random walls = 3 total.
        assert len(board.wall_cells) == 3

    def test_fortress_adds_random_walls_per_copy(self):
        cs = CardSystem()
        player = Player(passive_cards=["Fortress", "Fortress"])
        cs.apply_passive_buffs(player)
        random.seed(0)
        board = Board(size=5)
        cs.fire_game_start(board, player)
        assert len(board.wall_cells) == 2

    def test_ghost_board_adds_three_walls_per_copy(self):
        cs = CardSystem()
        player = Player(passive_cards=["Ghost Board"])
        cs.apply_passive_buffs(player)
        random.seed(0)
        board = Board(size=5)
        cs.fire_game_start(board, player)
        assert len(board.wall_cells) == 3

    def test_blind_shot_places_x_on_edge(self):
        cs = CardSystem()
        player = Player(passive_cards=["Blind Shot"])
        cs.apply_passive_buffs(player)
        random.seed(0)
        board = Board()
        cs.fire_game_start(board, player)
        # One X on an edge, recorded as both a cell-played and a blind-shot mark.
        xs = [(r, c) for r in range(3) for c in range(3) if board.grid[r][c] == PLAYER_X]
        assert len(xs) == 1
        r, c = xs[0]
        assert r in (0, 2) or c in (0, 2)
        assert player.blind_shot_marks == [(r, c)]

    def test_double_strike_places_one_x_per_copy(self):
        cs = CardSystem()
        player = Player(passive_cards=["Double Strike", "Double Strike"])
        cs.apply_passive_buffs(player)
        random.seed(0)
        board = Board(size=5)
        cs.fire_game_start(board, player)
        xs = [(r, c) for r in range(5) for c in range(5) if board.grid[r][c] == PLAYER_X]
        assert len(xs) == 2
        # Each X in a different row.
        assert len({r for (r, _) in xs}) == 2

    def test_quick_draw_seeds_skip_opponent(self):
        cs = CardSystem()
        player = Player(passive_cards=["Quick Draw", "Quick Draw", "Quick Draw"])
        cs.apply_passive_buffs(player)
        board = Board()
        cs.fire_game_start(board, player)
        assert player.upgrades["skip_opponent"] == 3


# ----------------------------------------------------------------------
# on_x_placed triggers
# ----------------------------------------------------------------------


class TestXPlacedTriggers:
    def test_ricochet_mirrors_to_opposite_edge(self):
        cs = CardSystem()
        player = Player(passive_cards=["Ricochet"])
        cs.apply_passive_buffs(player)
        board = Board()
        # Place X at top-left corner, then fire the trigger.
        board.place_at(0, 0, PLAYER_X)
        cs.fire_x_placed(board, player, 0, 0)
        # Opposite of (0,0) on a 3x3 is (2,2).
        assert board.grid[2][2] == PLAYER_X
        assert (2, 2) in player.cells_played

    def test_ricochet_does_nothing_for_non_edge(self):
        cs = CardSystem()
        player = Player(passive_cards=["Ricochet"])
        cs.apply_passive_buffs(player)
        board = Board(size=5)
        board.place_at(2, 2, PLAYER_X)  # centre — not an edge
        cs.fire_x_placed(board, player, 2, 2)
        # Only the original placement; no mirror because (2,2) isn't an edge.
        xs = [(r, c) for r in range(5) for c in range(5) if board.grid[r][c] == PLAYER_X]
        assert xs == [(2, 2)]

    def test_overload_destroys_adjacent_o(self):
        cs = CardSystem()
        player = Player(passive_cards=["Overload"])
        cs.apply_passive_buffs(player)
        board = Board()
        board.grid[0][0] = OPPONENT_O
        board.grid[0][2] = OPPONENT_O
        board.place_at(1, 1, PLAYER_X)
        cs.fire_x_placed(board, player, 1, 1)
        # Both O's are adjacent → both wiped.
        assert board.grid[0][0] == EMPTY
        assert board.grid[0][2] == EMPTY

    def test_overload_consumes_one_charge_per_use(self):
        """One copy = one use per game. Second X placement next to an O
        no longer fires."""
        cs = CardSystem()
        player = Player(passive_cards=["Overload"])
        cs.apply_passive_buffs(player)
        board = Board()
        # First X next to an O → wipes it, consumes the charge.
        board.grid[0][0] = OPPONENT_O
        board.place_at(1, 1, PLAYER_X)
        cs.fire_x_placed(board, player, 1, 1)
        assert board.grid[0][0] == EMPTY
        assert player.upgrades["overload_charges"] == 0
        # Second X next to another O → charge is gone, O survives.
        board.grid[2][2] = OPPONENT_O
        board.place_at(2, 1, PLAYER_X)
        cs.fire_x_placed(board, player, 2, 1)
        assert board.grid[2][2] == OPPONENT_O

    def test_overload_charge_not_consumed_without_targets(self):
        """If no adjacent O exists, the charge isn't spent — the player
        keeps it for a turn where it actually matters."""
        cs = CardSystem()
        player = Player(passive_cards=["Overload"])
        cs.apply_passive_buffs(player)
        board = Board()
        # Place X with no nearby O's.
        board.place_at(1, 1, PLAYER_X)
        cs.fire_x_placed(board, player, 1, 1)
        assert player.upgrades["overload_charges"] == 1

    def test_overload_stacks_grant_charges_per_copy(self):
        cs = CardSystem()
        player = Player(passive_cards=["Overload", "Overload", "Overload"])
        cs.apply_passive_buffs(player)
        assert player.upgrades["overload_charges"] == 3


# ----------------------------------------------------------------------
# on_line_completed triggers
# ----------------------------------------------------------------------


class TestLineCompletedTriggers:
    def test_chain_reaction_flips_adjacent_o(self):
        cs = CardSystem()
        player = Player(passive_cards=["Chain Reaction"])
        cs.apply_passive_buffs(player)
        board = Board()
        # X line in row 0; O at (1,1) is adjacent to it.
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[1][1] = OPPONENT_O
        cs.fire_line_completed(board, player, [(0, 0), (0, 1), (0, 2)])
        assert board.grid[1][1] == PLAYER_X

    def test_chain_reaction_does_not_touch_distant_o(self):
        cs = CardSystem()
        player = Player(passive_cards=["Chain Reaction"])
        cs.apply_passive_buffs(player)
        board = Board(size=5)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[4][4] = OPPONENT_O
        cs.fire_line_completed(board, player, [(0, c) for c in range(5)])
        assert board.grid[4][4] == OPPONENT_O


# ----------------------------------------------------------------------
# on_shop_open triggers
# ----------------------------------------------------------------------


class TestShopOpenTriggers:
    def test_reroll_grants_free_rerolls(self):
        cs = CardSystem()
        player = Player(passive_cards=["Reroll", "Reroll"])
        cs.fire_shop_open(player)
        assert player.upgrades.get("free_rerolls") == 2

    def test_card_draw_grants_extra_offer(self):
        cs = CardSystem()
        player = Player(passive_cards=["Card Draw"])
        cs.fire_shop_open(player)
        assert player.upgrades.get("shop_offer_extra") == 1


# ----------------------------------------------------------------------
# Sacrifice save
# ----------------------------------------------------------------------


class TestSacrificeSave:
    def test_consumes_charge_and_removes_last_x(self):
        cs = CardSystem()
        player = Player(passive_cards=["Sacrifice"])
        cs.apply_passive_buffs(player)
        board = Board()
        board.place_at(1, 1, PLAYER_X)
        player.cells_played.append((1, 1))
        saved = cs.try_sacrifice_save(board, player)
        assert saved is True
        assert board.grid[1][1] == EMPTY
        assert (1, 1) not in player.cells_played
        assert player.upgrades["sacrifice_charges"] == 0

    def test_no_save_without_charges(self):
        cs = CardSystem()
        player = Player(passive_cards=[])
        cs.apply_passive_buffs(player)
        board = Board()
        assert cs.try_sacrifice_save(board, player) is False

    def test_no_save_without_played_cells(self):
        cs = CardSystem()
        player = Player(passive_cards=["Sacrifice"])
        cs.apply_passive_buffs(player)
        board = Board()
        # Player hasn't placed anything yet — nothing to undo.
        assert cs.try_sacrifice_save(board, player) is False
        # Charge should NOT be spent.
        assert player.upgrades["sacrifice_charges"] == 1


# ----------------------------------------------------------------------
# Scoring (unchanged from previous overhaul — sanity-check the math)
# ----------------------------------------------------------------------


class TestCalculateScore:
    def test_no_lines_scores_zero(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[1][1] = PLAYER_X
        assert cs.calculate_score(board, player, 1) == 0

    def test_positive_lines_scores(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[1] = [PLAYER_X, PLAYER_X, PLAYER_X]
        assert cs.calculate_score(board, player, 1) > 0

    def test_point_mult_bonus(self):
        cs = CardSystem()
        player = Player(upgrades={"point_mult": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        assert cs.calculate_score(board, player, 1) > 0

    def test_deep_grid_bonus(self):
        cs = CardSystem()
        player = Player(upgrades={"deep_grid": 1})
        board = Board()
        board.grid[1] = [PLAYER_X, PLAYER_X, PLAYER_X]
        assert cs.calculate_score(board, player, 1) > 0

    def test_equal_lines_scores_zero(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[1] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        assert cs.calculate_score(board, player, 1) == 0


class TestWildcardScoring:
    def test_wildcard_counts_line_with_one_o(self):
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"wildcard": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, OPPONENT_O]
        assert cs.calculate_score(board, plain, 1) == 0
        assert cs.calculate_score(board, buffed, 1) > 0


class TestDoubleCrossScoring:
    """The Double Cross boss flips opponent lines from negative to
    positive ink — every line on the board counts toward your score."""

    def test_o_lines_add_ink_under_doublecross(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        # 1 X line and 1 O line on the same 3x3.
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[2] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        plain_ink, _, _ = cs.score_breakdown(board, player, 1, is_boss=True)
        dc_ink, _, _ = cs.score_breakdown(
            board, player, 1, is_boss=True, boss_mechanic="doublecross",
        )
        # Plain boss: O lines subtract → net 0 (equal counts).
        # Double Cross: O lines add → 2× the per-line ink.
        assert plain_ink == 0
        assert dc_ink > 0

    def test_doublecross_only_in_boss_games(self):
        """boss_mechanic is ignored when is_boss is False."""
        cs = CardSystem()
        player = Player()
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[2] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        normal_ink, _, _ = cs.score_breakdown(
            board, player, 1, is_boss=False, boss_mechanic="doublecross",
        )
        # is_boss=False so the doublecross flag has no effect — O lines
        # still subtract.
        assert normal_ink == 0


class TestFinalCountScoring:
    def test_final_count_doubles_boss_ink(self):
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"final_count": 1})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        plain_ink, _, _ = cs.score_breakdown(board, plain, 1, is_boss=True)
        buffed_ink, _, _ = cs.score_breakdown(board, buffed, 1, is_boss=True)
        assert buffed_ink == 2 * plain_ink

    def test_final_count_no_effect_on_normal_games(self):
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"final_count": 3})
        board = Board()
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        assert cs.calculate_score(board, plain, 1) == cs.calculate_score(board, buffed, 1)
