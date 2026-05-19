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
        for r in range(self.board.size):
            for c in range(self.board.size):
                if self.board.grid[r][c] == 0:
                    self.board.grid[r][c] = OPPONENT_O
                    lines = self.board.count_lines_for(OPPONENT_O)
                    self.board.grid[r][c] = 0
                    if lines > 0:
                        return (r, c)
        return None

    def _try_block(self) -> tuple[int, int] | None:
        for r in range(self.board.size):
            for c in range(self.board.size):
                if self.board.grid[r][c] == 0:
                    self.board.grid[r][c] = PLAYER_X
                    lines = self.board.count_lines_for(PLAYER_X)
                    self.board.grid[r][c] = 0
                    if lines > 0:
                        return (r, c)
        return None

    def _center_or_corner(self) -> tuple[int, int] | None:
        if self.board.size >= 3:
            mid = self.board.size // 2
            if self.board.grid[mid][mid] == 0:
                return (mid, mid)
        corners = [(0, 0), (0, self.board.size - 1), (self.board.size - 1, 0), (self.board.size - 1, self.board.size - 1)]
        random.shuffle(corners)
        for r, c in corners:
            if self.board.grid[r][c] == 0:
                return (r, c)
        return None

    def _random(self) -> tuple[int, int] | None:
        empty = self.board.get_empty_cells()
        if empty:
            return random.choice(empty)
        return None