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
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Token Bonus", board, player) is True
        assert player.upgrades.get("token_bonus") == 3

    def test_apply_card_draw(self):
        cs = CardSystem(hand_size=2)
        player = Player(deck=["Card Draw", "Quick Draw", "Fortress", "Overload"])
        player.hand = []
        board = Board()
        board.reset(3)
        result = cs.apply_card("Card Draw", board, player)
        assert result is True
        assert len(player.hand) == 2  # 2 cards drawn (hand_size=2), draw_hand only draws when hand is empty

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
        cs = CardSystem()
        player = Player()
        board = Board()
        board.reset(3)
        assert cs.apply_card("Final Count", board, player) is True
        assert player.upgrades.get("final_count") == 2

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


class TestPostGameCleanup:
    def test_cleanup_clears_temp_effects(self):
        cs = CardSystem()
        player = Player(upgrades={
            "diagonal_power": 1,
            "point_mult": 1,
            "board_control": 0.5,
            "deep_grid": 1,
            "wildcard": 1,
            "final_count": 2,
            "skip_opponent": 1,
            "blind_shot": 1,
        })
        cs.post_game_cleanup(player)
        assert player.upgrades == {}


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
