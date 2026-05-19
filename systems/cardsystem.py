from config.cards import pick_random, get_by_name
from game.board import PLAYER_X, OPPONENT_O
from game.player import RunState, Player
from copy import deepcopy


class CardSystem:
    def __init__(self, hand_size: int = 3):
        self.hand_size = hand_size

    def generate_deck(self) -> list[str]:
        """Create a shuffled deck of 12 random cards."""
        deck: list[str] = []
        while len(deck) < 12:
            for card in pick_random(20):
                deck.append(card)
                if len(deck) >= 12:
                    break
        return deck

    def draw_hand(self, player: Player) -> list[str]:
        """Draw cards from deck into hand."""
        if not player.hand:
            for _ in range(self.hand_size + player.upgrades.get("extra_card_start", 0)):
                if player.deck:
                    player.hand.append(player.deck.pop(0))
                else:
                    player.deck = self.generate_deck()
                    player.hand.append(player.deck.pop(0))
        return player.hand

    def can_play_card(self, player: Player, cost: int) -> bool:
        """Check if player can afford the card."""
        effective_cost = cost + player.upgrades.get("sacrifice_penalty", 0)
        return player.tokens >= max(effective_cost, cost)

    def apply_card(self, card_name: str, board, player: Player) -> bool:
        """Apply card effect and return True if successful."""
        card = get_by_name(card_name)
        if not card:
            return False

        if card_name == "Double Strike":
            return self._double_strike(board, player)
        elif card_name == "Diagonal Power":
            player.upgrades["diagonal_power"] = 1
            return True
        elif card_name == "O Flipper":
            return self._flip_opponent(board, player)
        elif card_name == "Cell Lock":
            return self._lock_cell(board, player)
        elif card_name == "Reroll":
            return self._reroll(player)
        elif card_name == "Point Multiplier":
            player.upgrades["point_mult"] = 1
            return True
        elif card_name == "Token Bonus":
            player.upgrades["token_bonus"] = 3
            return True
        elif card_name == "Blind Shot":
            return self._blind_shot(board, player)
        elif card_name == "Board Control":
            player.upgrades["board_control"] = 0.5
            return True
        elif card_name == "Card Draw":
            self.draw_hand(player)
            self.draw_hand(player)
            return True
        elif card_name == "Sacrifice":
            return self._sacrifice(board, player)
        elif card_name == "Wildcard":
            player.upgrades["wildcard"] = 1
            return True
        elif card_name == "Overload":
            return self._overload(board, player)
        elif card_name == "Ghost Board":
            return self._ghost_board(board, player)
        elif card_name == "Final Count":
            player.upgrades["final_count"] = 2
            return True
        elif card_name == "Quick Draw":
            player.upgrades["skip_opponent"] = 1
            return True
        elif card_name == "Deep Grid":
            player.upgrades["deep_grid"] = 1
            return True
        elif card_name == "Fortress":
            return self._fortress(board, player)
        return False

    def _double_strike(self, board, player: Player) -> bool:
        # Simplified: marks 2 empty cells
        empty = board.get_empty_cells()
        if len(empty) >= 2:
            # Find row/col with fewest marks
            for r in range(board.size):
                row_empty = [(r, c) for c in range(board.size) if (r, c) in empty]
                if len(row_empty) >= 2:
                    board.place_at(row_empty[0][0], row_empty[0][1], PLAYER_X)
                    board.place_at(row_empty[1][0], row_empty[1][1], PLAYER_X)
                    return True
        return False

    def _flip_opponent(self, board, player: Player) -> bool:
        for r in range(board.size):
            for c in range(board.size):
                if board.grid[r][c] == OPPONENT_O:
                    board.grid[r][c] = PLAYER_X
                    return True
        return False

    def _lock_cell(self, board, player: Player) -> bool:
        # Lock center cell
        mid = board.size // 2
        board.wall_cells.append((mid, mid))
        return True

    def _reroll(self, player: Player) -> bool:
        if player.hand:
            player.deck.append(player.hand.pop())
            self.draw_hand(player)
            return True
        return False

    def _blind_shot(self, board, player: Player) -> bool:
        # Simply place X in random empty cell
        empty = board.get_empty_cells()
        if empty:
            r, c = empty[0]
            player.upgrades["blind_shot"] = 1  # flag for double points if win
            board.place_at(r, c, PLAYER_X)
            player.cells_played.append((r, c))
            return True
        return False

    def _sacrifice(self, board, player: Player) -> bool:
        # Remove last placed X
        if player.cells_played:
            r, c = player.cells_played.pop()
            board.remove_at(r, c)
            return True
        return False

    def _overload(self, board, player: Player) -> bool:
        # Find last X and destroy adjacent O's
        if player.cells_played:
            r, c = player.cells_played[-1]
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < board.size and 0 <= nc < board.size:
                        if board.grid[nr][nc] == OPPONENT_O:
                            board.grid[nr][nc] = PLAYER_X
        return True

    def _ghost_board(self, board, player: Player) -> bool:
        empty = board.get_empty_cells()
        import random
        walls = random.sample(empty, min(3, len(empty)))
        board.wall_cells = walls
        return True

    def _fortress(self, board, player: Player) -> bool:
        empty = board.get_empty_cells()
        if empty:
            r, c = empty[0]
            board.wall_cells.append((r, c))
            return True
        return False

    # Scoring helpers
    def calculate_score(self, board, player: Player, multiplier: int):
        xp_lines = board.count_lines_for(PLAYER_X)
        op_lines = board.count_lines_for(OPPONENT_O)

        if xp_lines == op_lines:
            return 0

        base = xp_lines - op_lines
        if base <= 0:
            return 0

        score = base * multiplier

        # Apply card buffs
        if player.upgrades.get("diagonal_power"):
            # Simplified: 50% bonus
            score = int(score * 1.5)
        if player.upgrades.get("point_mult"):
            score += xp_lines  # +1 per line
        if player.upgrades.get("board_control"):
            min_score = int(board.size * board.size * 0.5 * multiplier)
            score = max(score, min_score)
        if player.upgrades.get("deep_grid"):
            score += xp_lines

        return score

    def post_game_cleanup(self, player: Player):
        """Reset temporary card effects after game."""
        for key in ["diagonal_power", "point_mult", "board_control", "deep_grid", "wildcard",
                     "final_count", "skip_opponent", "blind_shot"]:
            if key in player.upgrades:
                del player.upgrades[key]