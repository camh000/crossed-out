import random
from dataclasses import dataclass, field
from typing import Optional

from config.constants import COLOR_X, COLOR_O

EMPTY = 0
PLAYER_X = 1
OPPONENT_O = -1


@dataclass
class Board:
    grid: list[list[int]] = field(default_factory=list)
    size: int = 3
    wall_cells: list[tuple[int, int]] = field(default_factory=list)
    poison_cells: list[tuple[int, int]] = field(default_factory=list)
    locked_cells: list[tuple[int, int]] = field(default_factory=list)
    move_count: int = 0
    game_over: bool = False

    def __post_init__(self):
        if not self.grid:
            self.grid = [[EMPTY] * self.size for _ in range(self.size)]

    def reset(self, size: int | None = None):
        if size is not None:
            self.size = size
        self.grid = [[EMPTY] * self.size for _ in range(self.size)]
        self.wall_cells = []
        self.poison_cells = []
        self.locked_cells = []
        self.move_count = 0
        self.game_over = False
        self.weights = [[1] * self.size for _ in range(self.size)]
        self.swap_counter = 0

    def place_at(self, r: int, c: int, val: int) -> bool:
        if self.game_over:
            return False
        if not (0 <= r < self.size and 0 <= c < self.size):
            return False
        if self.grid[r][c] != EMPTY:
            return False
        if (r, c) in self.wall_cells:
            return False
        if val == PLAYER_X:
            self.grid[r][c] = PLAYER_X
            self.move_count += 1
            return True
        elif val == OPPONENT_O:
            self.grid[r][c] = OPPONENT_O
            self.move_count += 1
            return True
        return False

    def remove_at(self, r: int, c: int) -> int:
        """Remove cell and return its value."""
        if 0 <= r < self.size and 0 <= c < self.size:
            val = self.grid[r][c]
            self.grid[r][c] = EMPTY
            return val
        return EMPTY

    def get_lines(self) -> list[tuple[int, list[tuple[int, int]]]]:
        """Return all completed lines of same mark."""
        lines = []
        for val in [PLAYER_X, OPPONENT_O]:
            # rows
            for r in range(self.size):
                if all(self.grid[r][c] == val for c in range(self.size)):
                    lines.append((val, [(r, c) for c in range(self.size)]))
            # cols
            for c in range(self.size):
                if all(self.grid[r][c] == val for r in range(self.size)):
                    lines.append((val, [(r, c) for r in range(self.size)]))
        # diagonals
        for val in [PLAYER_X, OPPONENT_O]:
            if all(self.grid[i][i] == val for i in range(self.size)):
                lines.append((val, [(i, i) for i in range(self.size)]))
            if all(self.grid[i][self.size - 1 - i] == val for i in range(self.size)):
                lines.append((val, [(i, self.size - 1 - i) for i in range(self.size)]))
        return lines

    def count_lines_for(self, val: int) -> int:
        return sum(1 for v, _ in self.get_lines() if v == val)

    def count_empty(self) -> int:
        return sum(1 for r in range(self.size) for c in range(self.size) if self.grid[r][c] == EMPTY)

    def is_full(self) -> bool:
        return self.count_empty() == 0

    def has_winner(self) -> Optional[int]:
        """Return PLAYER_X, OPPONENT_O, or None for draw."""
        lines = self.get_lines()
        if lines:
            return lines[-1][0]
        if self.is_full():
            xp = self.count_lines_for(PLAYER_X)
            op = self.count_lines_for(OPPONENT_O)
            if xp > op:
                return PLAYER_X
            elif op > xp:
                return OPPONENT_O
            return None
        return None

    def get_weights(self) -> list[list[float]]:
        """Generate cell weights (1-5) for weighted boss."""
        return [[int(random.uniform(1.0, 5.0)) for _ in range(self.size)] for _ in range(self.size)]

    def get_empty_cells(self) -> list[tuple[int, int]]:
        return [(r, c) for r in range(self.size) for c in range(self.size) if self.grid[r][c] == EMPTY]

    def apply_swap(self):
        """Swap all X and O marks for Swap boss."""
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] == PLAYER_X:
                    self.grid[r][c] = OPPONENT_O
                elif self.grid[r][c] == OPPONENT_O:
                    self.grid[r][c] = PLAYER_X