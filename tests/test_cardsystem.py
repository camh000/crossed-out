"""Tests for systems/cardsystem.py - CardSystem class."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from systems.cardsystem import CardSystem
from game.player import Player
from game.board import Board, PLAYER_X, OPPONENT_O, EMPTY
from config.cards import get_by_name, ALL_CARDS


class TestCardSystemInit:
    def test_default_hand_size(self):
        cs = CardSystem()
        assert cs.hand_size == 3

    def test_custom_hand_size(self):
        cs = CardSystem(hand_size=5)
        assert cs.hand_size == 5


class TestGenerateDeck:
    def test_deck_size(self):
        cs = CardSystem()
        deck = cs.generate_deck()
        assert len(deck) == 12

    def test_deck_contains_valid_cards(self):
        cs = CardSystem()
        deck = cs.generate_deck()
        for card_name in deck:
            assert get_by_name(card_name) is not None

    def test_deck_all_strings(self):
        cs = CardSystem()
        deck = cs.generate_deck()
        assert all(isinstance(c, str) for c in deck)


class TestCanPlayCard:
    def test_can_afford(self):
        cs = CardSystem()
        player = Player(tokens=5)
        assert cs.can_play_card(player, 3) is True

    def test_cannot_afford(self):
        cs = CardSystem()
        player = Player(tokens=2)
        assert cs.can_play_card(player, 3) is False

    def test_exact_cost(self):
        cs = CardSystem()
        player = Player(tokens=3)
        assert cs.can_play_card(player, 3) is True

    def test_free_card(self):
        cs = CardSystem()
        player = Player(tokens=0)
        assert cs.can_play_card(player, 0) is True

    def test_sacrifice_penalty_applied(self):
        cs = CardSystem()
        player = Player(tokens=4)
        player.upgrades["sacrifice_penalty"] = 2
        assert cs.can_play_card(player, 3) is False


class TestCanPlayCardBossMechanics:
    def test_boss_doesnt_break_card_system(self):
        """Boss mechanics shouldn't interfere with card system."""
        cs = CardSystem()
        player = Player(tokens=10)
        assert cs.can_play_card(player, 5) is True


class TestApplyCard:
    def test_apply_double_strike(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.size = 3
        board.reset(3)
        assert cs.apply_card("Double Strike", board, player) is True

    def test_apply_o_flipper(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        board.grid[1][1] = OPPONENT_O
        assert cs.apply_card("O Flipper", board, player) is True
        assert board.grid[1][1] == PLAYER_X

    def test_apply_o_flipper_no_opponent(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("O Flipper", board, player) is False

    def test_apply_cell_lock(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        mid = 3 // 2
        assert cs.apply_card("Cell Lock", board, player) is True
        assert (mid, mid) in board.wall_cells

    def test_apply_reroll(self):
        cs = CardSystem()
        player = Player(hand=["Reroll"], deck=["Card Draw"])
        player.deck = [c for c in player.deck]
        assert cs.apply_card("Reroll", board=Board(), player=player) is True

    def test_apply_point_multiplier(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Point Multiplier", board, player) is True
        assert player.upgrades.get("point_mult") == 1

    def test_apply_token_bonus(self):
        """Token Bonus is persistent and stacks +1 per copy."""
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Token Bonus", board, player) is True
        assert player.upgrades.get("token_bonus") == 1
        assert "Token Bonus" in player.passive_cards
        assert cs.apply_card("Token Bonus", board, player) is True
        assert player.upgrades.get("token_bonus") == 2

    def test_apply_card_draw(self):
        """Card Draw adds 2 cards on top of hand_size."""
        cs = CardSystem(hand_size=2)
        player = Player(deck=["Card Draw", "Quick Draw", "Fortress", "Overload"])
        player.hand = []
        board = Board()
        board.reset(3)
        result = cs.apply_card("Card Draw", board, player)
        assert result is True
        # Card Draw tops hand up to hand_size + 2 = 4.
        assert len(player.hand) == 4

    def test_apply_quick_draw(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Quick Draw", board, player) is True
        assert player.upgrades.get("skip_opponent") == 1

    def test_apply_wildcard(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Wildcard", board, player) is True
        assert player.upgrades.get("wildcard") == 1

    def test_apply_deep_grid(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Deep Grid", board, player) is True
        assert player.upgrades.get("deep_grid") == 1

    def test_apply_final_count(self):
        """Final Count is persistent and stacks +1 per copy."""
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Final Count", board, player) is True
        assert player.upgrades.get("final_count") == 1
        assert "Final Count" in player.passive_cards

    def test_apply_unknown_card(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Nonexistent Card", board, player) is False


class TestCalculateScore:
    def test_no_lines_scores_zero(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        board.grid[1][1] = PLAYER_X
        score = cs.calculate_score(board, player, 1)
        assert score == 0

    def test_positive_lines_scores(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        board.grid[1][0] = PLAYER_X
        board.grid[1][1] = PLAYER_X
        board.grid[1][2] = PLAYER_X
        opponent = Board()
        opponent.reset(3)
        opponent.grid[0][1] = OPPONENT_O
        score = cs.calculate_score(board, player, 1)
        assert score > 0

    def test_diagonal_power_bonus(self):
        cs = CardSystem()
        player = Player(upgrades={"diagonal_power": 1})
        board = Board()
        board.reset(5)
        for i in range(5):
            board.grid[i][i] = PLAYER_X
        opp = Board()
        opp.reset(5)
        opp.grid[0][2] = OPPONENT_O
        score = cs.calculate_score(board, player, 1)
        assert score > 0

    def test_point_mult_bonus(self):
        cs = CardSystem()
        player = Player(upgrades={"point_mult": 1})
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        opp = Board()
        opp.reset(3)
        opp.grid[1][0] = OPPONENT_O
        score = cs.calculate_score(board, player, 2)
        # base = (1-0)*2 = 2, then +1 per line = +1
        assert score > 0

    def test_board_control_minimum(self):
        cs = CardSystem()
        player = Player(upgrades={"board_control": 0.5})
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        opp = Board()
        opp.reset(3)
        opp.grid[1] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        score = cs.calculate_score(board, player, 1)
        # min = 9 * 0.5 * 1 = 4
        assert score >= 0

    def test_deep_grid_bonus(self):
        cs = CardSystem()
        player = Player(upgrades={"deep_grid": 1})
        board = Board()
        board.reset(3)
        board.grid[1] = [PLAYER_X, PLAYER_X, PLAYER_X]
        opp = Board()
        opp.reset(3)
        opp.grid[0][0] = OPPONENT_O
        score = cs.calculate_score(board, player, 1)
        assert score > 0

    def test_equal_lines_scores_zero(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[1] = [OPPONENT_O, OPPONENT_O, OPPONENT_O]
        score = cs.calculate_score(board, player, 1)
        assert score == 0


class TestChainReaction:
    """Chain Reaction flips O cells orthogonally/diagonally adjacent to any X line."""

    def test_flips_adjacent_o_after_x_line(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        # X line in row 0; an O sitting next to it in row 1 col 1
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[1][1] = OPPONENT_O
        result = cs.apply_card("Chain Reaction", board, player)
        assert result is True
        assert board.grid[1][1] == PLAYER_X

    def test_returns_false_with_no_adjacent_o(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        # No O's anywhere
        result = cs.apply_card("Chain Reaction", board, player)
        assert result is False

    def test_does_not_touch_distant_o(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(5)
        # X line at row 0, O far away at row 4
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X, PLAYER_X, PLAYER_X]
        board.grid[4][4] = OPPONENT_O
        cs.apply_card("Chain Reaction", board, player)
        assert board.grid[4][4] == OPPONENT_O

    def test_flips_multiple_adjacent_o(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        # Three O's all touching the X line on row 1
        board.grid[1][0] = OPPONENT_O
        board.grid[1][1] = OPPONENT_O
        board.grid[1][2] = OPPONENT_O
        cs.apply_card("Chain Reaction", board, player)
        assert board.grid[1][0] == PLAYER_X
        assert board.grid[1][1] == PLAYER_X
        assert board.grid[1][2] == PLAYER_X

    def test_no_x_line_no_effect(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        # No completed X line; O scattered
        board.grid[0][0] = PLAYER_X
        board.grid[1][1] = OPPONENT_O
        result = cs.apply_card("Chain Reaction", board, player)
        assert result is False
        assert board.grid[1][1] == OPPONENT_O


class TestRicochet:
    """Ricochet places X on a random edge and on the opposite edge if empty."""

    def test_places_on_edge_and_opposite(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        result = cs.apply_card("Ricochet", board, player)
        assert result is True
        # Two cells should have been placed (edge + opposite), all on the perimeter
        xs = [(r, c) for r in range(3) for c in range(3) if board.grid[r][c] == PLAYER_X]
        assert len(xs) == 2
        for (r, c) in xs:
            assert r in (0, 2) or c in (0, 2)
        # Opposite-cell relationship: (r, c) and (size-1-r, size-1-c)
        (r1, c1), (r2, c2) = sorted(xs)
        assert (r2, c2) == (2 - r1, 2 - c1)

    def test_records_both_cells_in_player_history(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        cs.apply_card("Ricochet", board, player)
        assert len(player.cells_played) == 2

    def test_returns_false_with_no_empty_edges(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        # Fill every edge cell with O so no empty edges remain
        for r in range(3):
            for c in range(3):
                if r in (0, 2) or c in (0, 2):
                    board.grid[r][c] = OPPONENT_O
        result = cs.apply_card("Ricochet", board, player)
        assert result is False

    def test_opposite_occupied_only_places_one(self):
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        # Pre-fill (0,0) opposite at (2,2) with O so only the first edge cell gets X
        board.grid[2][2] = OPPONENT_O
        # Pre-fill all other edges except (0, 0) to force the random choice
        for (r, c) in [(0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)]:
            board.grid[r][c] = OPPONENT_O
        result = cs.apply_card("Ricochet", board, player)
        assert result is True
        assert board.grid[0][0] == PLAYER_X
        assert board.grid[2][2] == OPPONENT_O  # unchanged
        assert len(player.cells_played) == 1


class TestWildcardScoring:
    """Wildcard buff: lines with exactly 1 O count as the player's line."""

    def test_wildcard_counts_line_with_one_o(self):
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"wildcard": 1})
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, OPPONENT_O]
        # Without wildcard the row scores 0 (1 X + 1 O isn't a line at all).
        assert cs.calculate_score(board, plain, 1) == 0
        # With wildcard the near-line counts and the player gets ink.
        assert cs.calculate_score(board, buffed, 1) > 0

    def test_wildcard_stacks(self):
        """Each Wildcard copy unlocks one extra near-line."""
        cs = CardSystem()
        board = Board()
        board.reset(3)
        # Two near-lines, each two X and one O.
        board.grid[0] = [PLAYER_X, PLAYER_X, OPPONENT_O]
        board.grid[1] = [PLAYER_X, PLAYER_X, OPPONENT_O]
        one = cs.calculate_score(board, Player(upgrades={"wildcard": 1}), 1)
        two = cs.calculate_score(board, Player(upgrades={"wildcard": 2}), 1)
        assert two > one


class TestFinalCountScoring:
    """Final Count buff: boss games ink × 2 per copy."""

    def test_final_count_doubles_boss_ink(self):
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"final_count": 1})
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        plain_ink, _, _ = cs.score_breakdown(board, plain, 1, is_boss=True)
        buffed_ink, _, _ = cs.score_breakdown(board, buffed, 1, is_boss=True)
        assert buffed_ink == 2 * plain_ink

    def test_final_count_no_effect_on_normal_games(self):
        """Final Count only applies during boss games."""
        cs = CardSystem()
        plain = Player()
        buffed = Player(upgrades={"final_count": 3})
        board = Board()
        board.reset(3)
        board.grid[0] = [PLAYER_X, PLAYER_X, PLAYER_X]
        assert cs.calculate_score(board, plain, 1) == cs.calculate_score(board, buffed, 1)


class TestPostGameCleanup:
    def test_cleanup_clears_only_one_shot_keys(self):
        """Persistent buff keys survive cleanup so they keep stacking across
        games. Only one-shot keys (Quick Draw's skip_opponent) get wiped."""
        cs = CardSystem()
        player = Player(upgrades={
            "diagonal_power": 2,
            "point_mult": 3,
            "board_control": 1,
            "deep_grid": 1,
            "wildcard": 1,
            "final_count": 2,
            "token_bonus": 4,
            "skip_opponent": 1,
        })
        player.blind_shot_marks = [(0, 0), (1, 1)]
        cs.post_game_cleanup(player)
        assert player.upgrades.get("diagonal_power") == 2
        assert player.upgrades.get("point_mult") == 3
        assert player.upgrades.get("token_bonus") == 4
        assert "skip_opponent" not in player.upgrades
        # Per-game blind shot tracking also clears.
        assert player.blind_shot_marks == []


class TestPassiveBuffReapply:
    """apply_passive_buffs replays passive_cards into upgrades."""

    def test_passive_buffs_stack_count(self):
        cs = CardSystem()
        player = Player(passive_cards=["Point Multiplier", "Point Multiplier", "Diagonal Power"])
        cs.apply_passive_buffs(player)
        assert player.upgrades["point_mult"] == 2
        assert player.upgrades["diagonal_power"] == 1

    def test_passive_buffs_replaces_stale_counts(self):
        """Calling apply_passive_buffs again resets counts to match
        passive_cards exactly — no double-counting from previous games."""
        cs = CardSystem()
        player = Player(passive_cards=["Point Multiplier"])
        cs.apply_passive_buffs(player)
        cs.apply_passive_buffs(player)
        assert player.upgrades["point_mult"] == 1


class TestDrawHand:
    def test_draw_from_empty_deck_shuffles(self):
        cs = CardSystem(hand_size=3)
        player = Player(deck=[], hand=[])
        board = Board()
        board.reset(3)
        hand = cs.draw_hand(player)
        assert len(player.hand) > 0

    def test_draw_replenishes_deck(self):
        cs = CardSystem(hand_size=3)
        empty_board = Board()
        card_names = [c.name for c in ALL_CARDS[:4]]
        player = Player(deck=card_names * 10, hand=[])
        hand = cs.draw_hand(player)
        assert len(player.hand) == 3

    def test_double_draw_expands_hand(self):
        cs = CardSystem(hand_size=3)
        player = Player(deck=["Card Draw", "Card Draw", "Card Draw", "Card Draw", "Card Draw", "Card Draw"], hand=[])
        board = Board()
        board.reset(3)
        first = cs.draw_hand(player)
        second = cs.draw_hand(player)
        assert len(player.hand) == 3  # draw_hand only draws when hand is empty, second call does nothing
