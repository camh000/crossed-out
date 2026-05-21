from game.board import Board, PLAYER_X, OPPONENT_O
import random


class OpponentAI:
    def __init__(self, board: Board, fade_age: int | None = None):
        """The AI plays for OPPONENT_O.

        `fade_age` enables Blind-boss symmetry: when set, the AI sees
        the same faded board the player does. Cells aged past `fade_age`
        are treated as EMPTY during line-counting, threat detection,
        and win-search. If the AI's blind pick collides with a
        real-occupied cell (a faded mark it couldn't see), it falls
        back to a random truly-empty cell — that way the AI stays
        informationally blind without wasting its turn entirely.
        """
        self.board = board
        self.difficulty = 0.7  # 70% optimal play
        self.fade_age = fade_age

    def get_best_move(self) -> tuple[int, int] | None:
        """Return best empty cell for opponent O."""
        if self.board.game_over:
            return None
        if self.fade_age is None:
            return self._compute_move()
        # Swap grid for a faded view while the AI deliberates. Mutations
        # made by _try_win / _try_block during scoring land on the
        # perceived copy and never touch the real grid.
        real_grid = self.board.grid
        self.board.grid = self.board.visible_grid_view(self.fade_age)
        try:
            move = self._compute_move()
        finally:
            self.board.grid = real_grid
        # If the chosen cell is actually occupied (a faded mark the AI
        # couldn't see) OR a wall, fall back to a truly-empty cell
        # instead of forfeiting. Stays informationally blind without
        # giving the player a free turn every time the AI guesses wrong.
        if move is not None and (
            real_grid[move[0]][move[1]] != 0
            or move in self.board.wall_cells
        ):
            empty = self.board.get_empty_cells()
            return random.choice(empty) if empty else None
        return move

    def _compute_move(self) -> tuple[int, int] | None:
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
        return self._random()

    def _placeable(self, r: int, c: int) -> bool:
        """A cell is placeable iff it's empty in the (possibly swapped)
        perceived grid AND not a wall on the real board. Walls are stored
        on the Board directly, not in `grid`, so even the swapped grid
        needs the wall guard."""
        return (
            self.board.grid[r][c] == 0
            and (r, c) not in self.board.wall_cells
        )

    def _try_win(self) -> tuple[int, int] | None:
        for (r, c) in self.board.valid_cells:
            if self._placeable(r, c):
                self.board.grid[r][c] = OPPONENT_O
                lines = self.board.count_lines_for(OPPONENT_O)
                self.board.grid[r][c] = 0
                if lines > 0:
                    return (r, c)
        return None

    def _try_block(self) -> tuple[int, int] | None:
        for (r, c) in self.board.valid_cells:
            if self._placeable(r, c):
                self.board.grid[r][c] = PLAYER_X
                lines = self.board.count_lines_for(PLAYER_X)
                self.board.grid[r][c] = 0
                if lines > 0:
                    return (r, c)
        return None

    def _center_or_corner(self) -> tuple[int, int] | None:
        empties = [pos for pos in self.board.valid_cells if self._placeable(*pos)]
        if not empties:
            return None
        # Prefer the cell closest to the centroid of the playable area
        cells = list(self.board.valid_cells)
        cx = sum(c for _, c in cells) / len(cells)
        cy = sum(r for r, _ in cells) / len(cells)
        empties.sort(key=lambda p: (p[0] - cy) ** 2 + (p[1] - cx) ** 2)
        return empties[0]

    def _random(self) -> tuple[int, int] | None:
        empty = [(r, c) for (r, c) in sorted(self.board.valid_cells)
                 if self._placeable(r, c)]
        if empty:
            return random.choice(empty)
        return None
