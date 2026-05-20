from game.board import Board, PLAYER_X, OPPONENT_O
import random


class OpponentAI:
    def __init__(self, board: Board):
        self.board = board
        self.difficulty = 0.7  # 70% optimal play

    def get_best_move(self) -> tuple[int, int] | None:
        """Return best empty cell for opponent O."""
        if not self.board.game_over:
            move = self._try_block()
            if move:
                return move
            move = self._try_win()
            if move:
                return move
            if random.random() < self.difficulty:
                move = self._center_or_corner()
                if move:
                    return move
            if move is None:
                return self._random()
        return None

    def _try_win(self) -> tuple[int, int] | None:
        for (r, c) in self.board.valid_cells:
            if self.board.grid[r][c] == 0:
                self.board.grid[r][c] = OPPONENT_O
                lines = self.board.count_lines_for(OPPONENT_O)
                self.board.grid[r][c] = 0
                if lines > 0:
                    return (r, c)
        return None

    def _try_block(self) -> tuple[int, int] | None:
        for (r, c) in self.board.valid_cells:
            if self.board.grid[r][c] == 0:
                self.board.grid[r][c] = PLAYER_X
                lines = self.board.count_lines_for(PLAYER_X)
                self.board.grid[r][c] = 0
                if lines > 0:
                    return (r, c)
        return None

    def _center_or_corner(self) -> tuple[int, int] | None:
        empties = [pos for pos in self.board.valid_cells if self.board.grid[pos[0]][pos[1]] == 0]
        if not empties:
            return None
        # Prefer the cell closest to the centroid of the playable area
        cells = list(self.board.valid_cells)
        cx = sum(c for _, c in cells) / len(cells)
        cy = sum(r for r, _ in cells) / len(cells)
        empties.sort(key=lambda p: (p[0] - cy) ** 2 + (p[1] - cx) ** 2)
        return empties[0]

    def _random(self) -> tuple[int, int] | None:
        empty = self.board.get_empty_cells()
        if empty:
            return random.choice(empty)
        return None