import random
from config.cards import pick_random, get_by_name
from game.board import PLAYER_X, OPPONENT_O, EMPTY
from game.player import Player


# Upgrade keys that survive the post-game cleanup. These come from
# persistent cards in `player.passive_cards` and are re-applied each game.
_PERSISTENT_UPGRADE_KEYS = {
    "point_mult",
    "diagonal_power",
    "wildcard",
    "deep_grid",
    "token_bonus",
    "final_count",
    "board_control",
}

# Mapping from a persistent card name to the upgrade key it increments.
_CARD_UPGRADE = {
    "Point Multiplier": "point_mult",
    "Diagonal Power": "diagonal_power",
    "Wildcard": "wildcard",
    "Deep Grid": "deep_grid",
    "Token Bonus": "token_bonus",
    "Final Count": "final_count",
    "Board Control": "board_control",
}


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
        """Top up the hand to hand_size (+ any extra_card_start upgrade),
        drawing from the deck and reshuffling a fresh deck if it empties."""
        target = self.hand_size + player.upgrades.get("extra_card_start", 0)
        while len(player.hand) < target:
            if not player.deck:
                player.deck = self.generate_deck()
            player.hand.append(player.deck.pop(0))
        return player.hand

    def can_play_card(self, player: Player, cost: int) -> bool:
        effective_cost = cost + player.upgrades.get("sacrifice_penalty", 0)
        return player.tokens >= max(effective_cost, cost)

    def apply_passive_buffs(self, player: Player) -> None:
        """Re-apply every persistent card in `player.passive_cards` to
        `player.upgrades` as a stacked integer count. Call this at the
        start of each game so the upgrade dict reflects the current build.
        """
        for key in _PERSISTENT_UPGRADE_KEYS:
            player.upgrades.pop(key, None)
        for name in player.passive_cards:
            key = _CARD_UPGRADE.get(name)
            if key:
                player.upgrades[key] = player.upgrades.get(key, 0) + 1

    def apply_card(self, card_name: str, board, player: Player) -> bool:
        """Apply a card's effect. Persistent buffs are appended to
        `passive_cards` and reflected in `upgrades`. One-shot cards run
        their immediate effect and don't persist."""
        card = get_by_name(card_name)
        if not card:
            return False

        if card.persistent:
            player.passive_cards.append(card_name)
            key = _CARD_UPGRADE.get(card_name)
            if key:
                player.upgrades[key] = player.upgrades.get(key, 0) + 1
            return True

        if card_name == "Double Strike":
            return self._double_strike(board, player)
        if card_name == "O Flipper":
            return self._flip_opponent(board, player)
        if card_name == "Cell Lock":
            return self._lock_cell(board, player)
        if card_name == "Reroll":
            return self._reroll(player)
        if card_name == "Blind Shot":
            return self._blind_shot(board, player)
        if card_name == "Card Draw":
            target = self.hand_size + player.upgrades.get("extra_card_start", 0) + 2
            while len(player.hand) < target:
                if not player.deck:
                    player.deck = self.generate_deck()
                player.hand.append(player.deck.pop(0))
            return True
        if card_name == "Sacrifice":
            return self._sacrifice(board, player)
        if card_name == "Overload":
            return self._overload(board, player)
        if card_name == "Ghost Board":
            return self._ghost_board(board, player)
        if card_name == "Quick Draw":
            player.upgrades["skip_opponent"] = player.upgrades.get("skip_opponent", 0) + 1
            return True
        if card_name == "Fortress":
            return self._fortress(board, player)
        if card_name == "Chain Reaction":
            return self._chain_reaction(board, player)
        if card_name == "Ricochet":
            return self._ricochet(board, player)
        return False

    # --- one-shot action implementations --------------------------------

    def _double_strike(self, board, player: Player) -> bool:
        empty = board.get_empty_cells()
        if len(empty) >= 2:
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
        """Place X on a random empty edge cell. If the cell ends up in a
        completed X line, the scoring step doubles that line's ink."""
        edges = [
            (r, c) for r in range(board.size) for c in range(board.size)
            if (r in (0, board.size - 1) or c in (0, board.size - 1)) and board.grid[r][c] == EMPTY
        ]
        if not edges:
            return False
        r, c = random.choice(edges)
        if not board.place_at(r, c, PLAYER_X):
            return False
        player.cells_played.append((r, c))
        player.blind_shot_marks.append((r, c))
        return True

    def _sacrifice(self, board, player: Player) -> bool:
        if player.cells_played:
            r, c = player.cells_played.pop()
            board.remove_at(r, c)
            return True
        return False

    def _overload(self, board, player: Player) -> bool:
        if player.cells_played:
            r, c = player.cells_played[-1]
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < board.size and 0 <= nc < board.size:
                        if board.grid[nr][nc] == OPPONENT_O:
                            board.grid[nr][nc] = PLAYER_X
        return True

    def _ghost_board(self, board, player: Player) -> bool:
        empty = board.get_empty_cells()
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

    def _chain_reaction(self, board, player: Player) -> bool:
        flipped = False
        for val, cells in board.get_lines():
            if val != PLAYER_X:
                continue
            for r, c in cells:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < board.size and 0 <= nc < board.size:
                            if board.grid[nr][nc] == OPPONENT_O:
                                board.grid[nr][nc] = PLAYER_X
                                flipped = True
        return flipped

    def _ricochet(self, board, player: Player) -> bool:
        edges = [
            (r, c) for r in range(board.size) for c in range(board.size)
            if (r in (0, board.size - 1) or c in (0, board.size - 1)) and board.grid[r][c] == 0
        ]
        if not edges:
            return False
        r, c = random.choice(edges)
        if not board.place_at(r, c, PLAYER_X):
            return False
        player.cells_played.append((r, c))
        opp_r, opp_c = board.size - 1 - r, board.size - 1 - c
        if board.grid[opp_r][opp_c] == 0:
            if board.place_at(opp_r, opp_c, PLAYER_X):
                player.cells_played.append((opp_r, opp_c))
        return True

    # --- ink × mult scoring ---------------------------------------------

    def score_breakdown(
        self,
        board,
        player: Player,
        level_mult: int,
        *,
        is_boss: bool = False,
    ) -> tuple[int, float, int]:
        """Compute (ink, mult, total) for the current board state.

        ink: additive component. Each player's completed line contributes
        (sum of cell weights × line length) ink, plus per-card flat bonuses.
        Opponent lines subtract ink at the same base rate.

        mult: multiplicative component. Starts at 1 + level_mult, grows
        with each multiplicative buff card.

        total: int(ink * mult). Falls back to 0 if ink ≤ 0.
        """
        ink = 0
        x_lines = self._collect_lines(board, PLAYER_X)
        o_lines = self._collect_lines(board, OPPONENT_O)

        wildcard_stacks = player.upgrades.get("wildcard", 0)
        if wildcard_stacks > 0:
            x_lines += self._wildcard_lines(board, wildcard_stacks)

        blind_marks = set(player.blind_shot_marks)
        for cells in x_lines:
            line_ink = self._line_base_ink(board, cells)
            if any(cell in blind_marks for cell in cells):
                line_ink *= 2
            ink += line_ink
            ink += player.upgrades.get("point_mult", 0) * 3
            ink += player.upgrades.get("deep_grid", 0)

        for cells in o_lines:
            ink -= self._line_base_ink(board, cells)

        # Board Control floor — each copy adds size*size to a lower bound.
        bc = player.upgrades.get("board_control", 0)
        if bc > 0:
            min_ink = bc * board.size * board.size
            ink = max(ink, min_ink)

        # Final Count doubles ink in boss games, stacking multiplicatively.
        if is_boss:
            final_count_stacks = player.upgrades.get("final_count", 0)
            if final_count_stacks > 0:
                ink *= 2 ** final_count_stacks

        # Multiplicative component.
        mult = 1.0 + max(0, level_mult - 1)
        diag_stacks = player.upgrades.get("diagonal_power", 0)
        if diag_stacks > 0 and any(self._is_diagonal(board, cells) for cells in x_lines):
            mult += 0.5 * diag_stacks

        if ink <= 0:
            return 0, mult, 0
        return int(ink), mult, int(ink * mult)

    def calculate_score(self, board, player: Player, multiplier: int) -> int:
        """Back-compat shim: return just the total. Most callers want this."""
        _ink, _mult, total = self.score_breakdown(board, player, multiplier)
        return total

    def _collect_lines(self, board, val: int) -> list[list[tuple[int, int]]]:
        return [cells for v, cells in board.get_lines() if v == val]

    def _line_base_ink(self, board, cells: list[tuple[int, int]]) -> int:
        # weights default to all-1 unless the Weighted boss rolled values.
        try:
            weight_sum = sum(board.weights[r][c] for (r, c) in cells)
        except (IndexError, AttributeError):
            weight_sum = len(cells)
        return weight_sum * len(cells)

    def _is_diagonal(self, board, cells: list[tuple[int, int]]) -> bool:
        if len(cells) < 2:
            return False
        (r0, c0), (r1, c1) = cells[0], cells[1]
        return r0 != r1 and c0 != c1

    def _wildcard_lines(self, board, stacks: int) -> list[list[tuple[int, int]]]:
        """A 'wildcard' line is `board.size` consecutive cells that are
        all X except for at most one O. Each Wildcard copy unlocks one
        such near-line as scoring."""
        runs: list[list[tuple[int, int]]] = []
        directions = ((0, 1), (1, 0), (1, 1), (1, -1))
        seen: set[tuple] = set()
        for (r, c) in board.valid_cells:
            for dr, dc in directions:
                cells = []
                o_count = 0
                ok = True
                for i in range(board.size):
                    nr, nc = r + i * dr, c + i * dc
                    if (nr, nc) not in board.valid_cells:
                        ok = False
                        break
                    v = board.grid[nr][nc]
                    if v == OPPONENT_O:
                        o_count += 1
                    elif v != PLAYER_X:
                        ok = False
                        break
                    cells.append((nr, nc))
                if ok and len(cells) == board.size and o_count == 1:
                    key = tuple(sorted(cells))
                    if key not in seen:
                        seen.add(key)
                        runs.append(cells)
                        if len(runs) >= stacks:
                            return runs
        return runs

    def post_game_cleanup(self, player: Player):
        """Clear per-game scratch state. Persistent buffs survive — they
        are re-applied at the next game start via apply_passive_buffs.
        Only one-shot upgrade keys are removed here."""
        one_shot_keys = ("skip_opponent",)
        for key in one_shot_keys:
            player.upgrades.pop(key, None)
        player.blind_shot_marks = []
