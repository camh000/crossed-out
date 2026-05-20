import random
from dataclasses import dataclass, field
from typing import Optional

EMPTY = 0
PLAYER_X = 1
OPPONENT_O = -1


@dataclass
class Board:
    """A tic-tac-toe board that can grow into an irregular polyomino.

    `grid` is a rectangular bounding-box backing store; the actual playable
    area is described by `valid_cells`. The board grows by adding adjacent
    cells via `add_random_adjacent_cell`, which extends the bounding box if
    the new cell falls outside the current grid.

    `size` is the line-length target (3, 5, 7) and never changes after
    reset(); growth does not change it. A "line" is `size` consecutive
    same-mark cells in any of the four directions (row, col, two diagonals).
    """
    grid: list[list[int]] = field(default_factory=list)
    size: int = 3
    valid_cells: set[tuple[int, int]] = field(default_factory=set)
    wall_cells: list[tuple[int, int]] = field(default_factory=list)
    poison_cells: list[tuple[int, int]] = field(default_factory=list)
    locked_cells: list[tuple[int, int]] = field(default_factory=list)
    # Poison boss: when a player places on a poison cell, the cell + a
    # ttl is pushed here. Each AI move ticks the ttls down; at 0 the
    # mark is removed and the poison cell cleared.
    poisoned_marks: list[tuple[int, int, int]] = field(default_factory=list)
    # Per-cell ink weights. Weighted boss replaces this with 1-5 random
    # values; other modes leave it at all-1.
    weights: list[list[int]] = field(default_factory=list)
    move_count: int = 0
    game_over: bool = False

    def __post_init__(self):
        if not self.grid:
            self.reset(self.size)
        elif not self.valid_cells:
            self.valid_cells = {
                (r, c) for r in range(len(self.grid)) for c in range(len(self.grid[0]))
            }
        if not self.weights:
            self.weights = [[1] * self.cols for _ in range(self.rows)]

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    def reset(self, size: int | None = None):
        if size is not None:
            self.size = size
        self.grid = [[EMPTY] * self.size for _ in range(self.size)]
        self.valid_cells = {(r, c) for r in range(self.size) for c in range(self.size)}
        self.wall_cells = []
        self.poison_cells = []
        self.poisoned_marks = []
        self.locked_cells = []
        self.move_count = 0
        self.game_over = False
        self.weights = [[1] * self.size for _ in range(self.size)]
        self.swap_counter = 0

    def clear_marks(self):
        """Wipe placed marks and per-game state but preserve the current
        bounding box and valid-cells set, so growth gained from a draw in
        a prior game carries into the next game within the same level."""
        self.grid = [[EMPTY] * self.cols for _ in range(self.rows)]
        self.wall_cells = []
        self.poison_cells = []
        self.poisoned_marks = []
        self.locked_cells = []
        self.move_count = 0
        self.game_over = False
        self.weights = [[1] * self.cols for _ in range(self.rows)]
        self.swap_counter = 0

    def place_at(self, r: int, c: int, val: int) -> bool:
        if self.game_over:
            return False
        if (r, c) not in self.valid_cells:
            return False
        if self.grid[r][c] != EMPTY:
            return False
        if (r, c) in self.wall_cells:
            return False
        if val == PLAYER_X or val == OPPONENT_O:
            self.grid[r][c] = val
            self.move_count += 1
            return True
        return False

    def remove_at(self, r: int, c: int) -> int:
        """Remove cell and return its value."""
        if (r, c) in self.valid_cells:
            val = self.grid[r][c]
            self.grid[r][c] = EMPTY
            return val
        return EMPTY

    def _value(self, pos: tuple[int, int]) -> int:
        if pos in self.valid_cells:
            return self.grid[pos[0]][pos[1]]
        return EMPTY

    def get_lines(self) -> list[tuple[int, list[tuple[int, int]]]]:
        """Return all runs of exactly `size` consecutive same-mark cells.

        Iterates over the four directions (→, ↓, ↘, ↙) starting from any
        valid cell whose "previous" cell in that direction is not the same
        mark — this prevents counting overlapping sub-runs of a longer run
        more than once for the starting position, while still emitting one
        line per overlapping `size`-window when a longer run exists.
        """
        lines: list[tuple[int, list[tuple[int, int]]]] = []
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for val in (PLAYER_X, OPPONENT_O):
            for (r, c) in self.valid_cells:
                if self.grid[r][c] != val:
                    continue
                for dr, dc in directions:
                    prev = (r - dr, c - dc)
                    if prev in self.valid_cells and self.grid[prev[0]][prev[1]] == val:
                        continue
                    cells = []
                    for i in range(self.size):
                        nr, nc = r + i * dr, c + i * dc
                        if (nr, nc) not in self.valid_cells:
                            break
                        if self.grid[nr][nc] != val:
                            break
                        cells.append((nr, nc))
                    if len(cells) == self.size:
                        lines.append((val, cells))
        return lines

    def count_lines_for(self, val: int) -> int:
        return sum(1 for v, _ in self.get_lines() if v == val)

    def count_empty(self) -> int:
        return sum(1 for (r, c) in self.valid_cells if self.grid[r][c] == EMPTY)

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
        return [[int(random.uniform(1.0, 5.0)) for _ in range(self.cols)] for _ in range(self.rows)]

    def get_empty_cells(self) -> list[tuple[int, int]]:
        return [(r, c) for (r, c) in sorted(self.valid_cells) if self.grid[r][c] == EMPTY]

    def apply_swap(self):
        """Swap all X and O marks for Swap boss."""
        for (r, c) in self.valid_cells:
            if self.grid[r][c] == PLAYER_X:
                self.grid[r][c] = OPPONENT_O
            elif self.grid[r][c] == OPPONENT_O:
                self.grid[r][c] = PLAYER_X

    def register_poison_hit(self, r: int, c: int, ttl: int = 2) -> None:
        """Mark a player-placed cell as poisoned. tick_poison() will
        remove it once the ttl reaches 0."""
        self.poisoned_marks.append((r, c, ttl))

    def tick_poison(self) -> list[tuple[int, int]]:
        """Decrement every poison mark's ttl; clear the cells whose ttl
        has reached zero. Returns the list of cleared cell coords."""
        cleared: list[tuple[int, int]] = []
        next_marks: list[tuple[int, int, int]] = []
        for (r, c, ttl) in self.poisoned_marks:
            new_ttl = ttl - 1
            if new_ttl <= 0:
                if (r, c) in self.valid_cells:
                    self.grid[r][c] = EMPTY
                if (r, c) in self.poison_cells:
                    self.poison_cells.remove((r, c))
                cleared.append((r, c))
            else:
                next_marks.append((r, c, new_ttl))
        self.poisoned_marks = next_marks
        return cleared

    def shift_coords(self, row_shift: int, col_shift: int) -> None:
        """Shift every coordinate-bearing list by (row_shift, col_shift).
        Used by grow_row_and_column when it adds rows/cols on top/left."""
        if not (row_shift or col_shift):
            return
        self.valid_cells = {(r + row_shift, c + col_shift) for (r, c) in self.valid_cells}
        self.wall_cells = [(r + row_shift, c + col_shift) for (r, c) in self.wall_cells]
        self.poison_cells = [(r + row_shift, c + col_shift) for (r, c) in self.poison_cells]
        self.locked_cells = [(r + row_shift, c + col_shift) for (r, c) in self.locked_cells]
        self.poisoned_marks = [
            (r + row_shift, c + col_shift, ttl) for (r, c, ttl) in self.poisoned_marks
        ]

    def grow_row_and_column(self) -> tuple[int, int]:
        """Add one new row and one new column on independently-chosen random
        sides (top/bottom for the row, left/right for the column).

        Returns (row_shift, col_shift) — 1 if the corresponding axis grew at
        the top/left (which shifts every existing coordinate by that
        amount), 0 if it grew at the bottom/right. Callers holding board
        coordinates outside the Board (e.g. `player.cells_played`) should
        apply the same shift.
        """
        add_top = random.choice((True, False))
        add_left = random.choice((True, False))
        row_shift = 1 if add_top else 0
        col_shift = 1 if add_left else 0

        # Grow columns first so the new row's width matches the new col count.
        if add_left:
            for row in self.grid:
                row.insert(0, EMPTY)
            for row in self.weights:
                row.insert(0, 1)
        else:
            for row in self.grid:
                row.append(EMPTY)
            for row in self.weights:
                row.append(1)

        new_width = self.cols
        if add_top:
            self.grid.insert(0, [EMPTY] * new_width)
            self.weights.insert(0, [1] * new_width)
        else:
            self.grid.append([EMPTY] * new_width)
            self.weights.append([1] * new_width)

        self.shift_coords(row_shift, col_shift)

        new_row_idx = 0 if add_top else self.rows - 1
        new_col_idx = 0 if add_left else self.cols - 1
        for c in range(self.cols):
            self.valid_cells.add((new_row_idx, c))
        for r in range(self.rows):
            self.valid_cells.add((r, new_col_idx))

        return (row_shift, col_shift)
