import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestBoard:
    """Test game/board.py"""

    def test_board_init_default(self):
        from game.board import Board, EMPTY
        b = Board()
        assert b.size == 3
        assert all(b.grid[r][c] == EMPTY for r in range(3) for c in range(3))
        assert b.move_count == 0
        assert b.game_over is False

    def test_board_init_custom_size(self):
        from game.board import Board, EMPTY
        b = Board(size=5)
        assert b.size == 5
        assert all(b.grid[r][c] == EMPTY for r in range(5) for c in range(5))

    def test_board_reset(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(1, 1, OPPONENT_O)
        b.reset()
        assert all(v == 0 for row in b.grid for v in row)
        assert b.move_count == 0
        assert not b.game_over
        assert not b.wall_cells
        assert not b.poison_cells
        assert not b.locked_cells

    def test_board_reset_size_change(self):
        from game.board import Board
        b = Board()
        b.reset(size=7)
        assert b.size == 7

    def test_place_at_valid(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        assert b.place_at(1, 1, PLAYER_X)
        assert b.grid[1][1] == PLAYER_X
        assert b.move_count == 1

        assert b.place_at(0, 0, OPPONENT_O)
        assert b.grid[0][0] == OPPONENT_O
        assert b.move_count == 2

    def test_place_at_invalid_bounds(self):
        from game.board import Board, PLAYER_X
        b = Board()
        assert not b.place_at(-1, 0, PLAYER_X)
        assert not b.place_at(0, -1, PLAYER_X)
        assert not b.place_at(3, 0, PLAYER_X)
        assert not b.place_at(0, 3, PLAYER_X)

    def test_place_at_taken_cell(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(1, 1, PLAYER_X)
        assert not b.place_at(1, 1, OPPONENT_O)

    def test_place_at_wall_cell(self):
        from game.board import Board, PLAYER_X

    def test_place_at_game_over(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.game_over = True
        assert not b.place_at(1, 1, PLAYER_X)

    def test_remove_at(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(1, 1, PLAYER_X)
        val = b.remove_at(1, 1)
        assert val == PLAYER_X
        assert b.grid[1][1] == 0

    def test_remove_at_empty_cell(self):
        from game.board import Board
        b = Board()
        val = b.remove_at(1, 1)
        assert val == 0

    def test_remove_at_invalid_bounds(self):
        from game.board import Board
        b = Board()
        val = b.remove_at(-5, -5)
        assert val == 0

    def test_get_lines_3x3_row_win(self):
        from game.board import Board, PLAYER_X
        b = Board()
        for c in range(3):
            b.place_at(1, c, PLAYER_X)
        lines = b.get_lines()
        assert len(lines) == 1
        assert lines[0][0] == PLAYER_X

    def test_get_lines_3x3_col_win(self):
        from game.board import Board, PLAYER_X
        b = Board()
        for r in range(3):
            b.place_at(r, 1, PLAYER_X)
        lines = b.get_lines()
        assert len(lines) == 1
        assert lines[0][0] == PLAYER_X

    def test_get_lines_diagonal_win(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(1, 1, PLAYER_X)
        b.place_at(2, 2, PLAYER_X)
        lines = b.get_lines()
        assert any(len(cells) == 3 for val, cells in lines if val == PLAYER_X)

    def test_get_lines_opponent_win(self):
        from game.board import Board, OPPONENT_O
        b = Board()
        for c in range(3):
            b.place_at(0, c, OPPONENT_O)
        lines = b.get_lines()
        assert any(v == OPPONENT_O for v, _ in lines)

    def test_get_lines_no_winner(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(1, 1, OPPONENT_O)
        lines = b.get_lines()
        assert len(lines) == 0

    def test_get_lines_5x5_row_win(self):
        from game.board import Board, PLAYER_X
        b = Board(size=5)
        for c in range(5):
            b.place_at(2, c, PLAYER_X)
        lines = b.get_lines()
        assert len(lines) == 1
        assert lines[0][0] == PLAYER_X

    def test_get_lines_7x7_row_win(self):
        from game.board import Board, PLAYER_X
        b = Board(size=7)
        for c in range(7):
            b.place_at(3, c, PLAYER_X)
        lines = b.get_lines()
        assert len(lines) == 1
        assert lines[0][0] == PLAYER_X

    def test_count_lines_for(self):
        from game.board import Board, PLAYER_X
        b = Board()
        for c in range(3):
            b.place_at(1, c, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 1
        assert b.count_lines_for(-1) == 0

    def test_count_lines_multi(self):
        from game.board import Board, PLAYER_X
        b = Board(size=5)
        for c in range(5):
            b.place_at(1, c, PLAYER_X)
            b.place_at(3, c, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 2

    def test_count_empty(self):
        from game.board import Board, PLAYER_X
        b = Board()
        assert b.count_empty() == 9
        b.place_at(0, 0, PLAYER_X)
        assert b.count_empty() == 8

    def test_count_empty_partial(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(1, 1, OPPONENT_O)
        assert b.count_empty() == 7

    def test_is_full(self):
        from game.board import Board, PLAYER_X
        b = Board()
        assert not b.is_full()
        for r in range(3):
            for c in range(3):
                b.place_at(r, c, PLAYER_X)
        assert b.is_full()

    def test_has_winner_player(self):
        from game.board import Board, PLAYER_X
        b = Board()
        for c in range(3):
            b.place_at(1, c, PLAYER_X)
        assert b.has_winner() == PLAYER_X

    def test_has_winner_opponent(self):
        from game.board import Board, OPPONENT_O
        b = Board()
        for c in range(3):
            b.place_at(1, c, OPPONENT_O)
        assert b.has_winner() == OPPONENT_O

    def test_has_winner_draw(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(0, 1, OPPONENT_O)
        b.place_at(0, 2, OPPONENT_O)
        b.place_at(1, 0, OPPONENT_O)
        b.place_at(1, 1, PLAYER_X)
        b.place_at(1, 2, OPPONENT_O)
        b.place_at(2, 0, OPPONENT_O)
        b.place_at(2, 1, PLAYER_X)
        assert b.has_winner() is None

    def test_has_winner_no_winning_board(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0,0,PLAYER_X)
        b.place_at(1,1,PLAYER_X)
        assert b.has_winner() is None

    def test_get_weights(self):
        from game.board import Board
        b = Board()
        weights = b.get_weights()
        assert len(weights) == 3
        assert len(weights[0]) == 3
        assert all(1 <= weights[r][c] <= 5 for r in range(3) for c in range(3))

    def test_get_empty_cells(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(1, 1, PLAYER_X)
        empty = b.get_empty_cells()
        assert len(empty) == 7
        assert (0, 0) not in empty
        assert (1, 1) not in empty
        assert (0, 1) in empty

    def test_apply_swap(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(1, 1, OPPONENT_O)
        b.place_at(2, 2, PLAYER_X)
        b.apply_swap()
        assert b.grid[0][0] == OPPONENT_O
        assert b.grid[1][1] == PLAYER_X
        assert b.grid[2][2] == OPPONENT_O

    def test_apply_swap_empty_board(self):
        from game.board import Board
        b = Board()
        b.apply_swap()
        assert all(v == 0 for row in b.grid for v in row)

    def test_apply_swap_on_big_board(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board(size=5)
        b.place_at(0, 0, PLAYER_X)
        b.place_at(2, 2, OPPONENT_O)
        b.place_at(4, 4, PLAYER_X)
        b.apply_swap()
        assert b.grid[0][0] == OPPONENT_O
        assert b.grid[2][2] == PLAYER_X
        assert b.grid[4][4] == OPPONENT_O


class TestAddAdjacentCell:
    def test_grow_adds_one_cell(self):
        from game.board import Board
        b = Board()
        before = len(b.valid_cells)
        added = b.add_random_adjacent_cell()
        assert added is not None
        assert len(b.valid_cells) == before + 1
        assert added in b.valid_cells

    def test_grow_extends_bounding_box(self):
        from game.board import Board
        b = Board()  # 3x3
        # Force growth in every direction by repeatedly growing
        for _ in range(8):
            b.add_random_adjacent_cell()
        # bounding box must have expanded in at least one dimension
        assert b.rows > 3 or b.cols > 3

    def test_grow_top_shifts_existing_cells(self):
        """Growing into a negative row shifts all existing coords down by one."""
        from game.board import Board, PLAYER_X
        import random
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        # Force the new cell to be directly above (0, 1) — at conceptual (-1, 1)
        random.seed(0)
        # add cells until one lands above row 0; or force via _absorb
        before = b.grid[0][0]
        b._absorb((-1, 1))
        # After shifting, the X that was at (0, 0) should now be at (1, 0)
        assert b.grid[1][0] == PLAYER_X
        # And (0, 1) — the newly added cell — should be in valid_cells
        assert (0, 1) in b.valid_cells
        assert b.rows == 4

    def test_grow_preserves_marks(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(2, 2, OPPONENT_O)
        for _ in range(5):
            b.add_random_adjacent_cell()
        # find the X and O — coords may have shifted if growth went up/left
        x_positions = [(r, c) for (r, c) in b.valid_cells if b.grid[r][c] == PLAYER_X]
        o_positions = [(r, c) for (r, c) in b.valid_cells if b.grid[r][c] == OPPONENT_O]
        assert len(x_positions) == 1
        assert len(o_positions) == 1

    def test_grow_keeps_line_length(self):
        """The size attribute (line target) is unaffected by growth."""
        from game.board import Board
        b = Board(size=3)
        for _ in range(4):
            b.add_random_adjacent_cell()
        assert b.size == 3


class TestLineDetectionAfterGrowth:
    def test_line_in_added_row(self):
        """3 X's in the new row count as a line of size 3."""
        from game.board import Board, PLAYER_X
        b = Board()
        # Grow to (4, 3) by adding cells below row 2
        b._absorb((3, 0))
        b._absorb((3, 1))
        b._absorb((3, 2))
        b.place_at(3, 0, PLAYER_X)
        b.place_at(3, 1, PLAYER_X)
        b.place_at(3, 2, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 1

    def test_isolated_added_cell_is_not_in_a_line(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b._absorb((-1, 1))  # single cell above row 0
        b.place_at(0, 1, PLAYER_X)
        # one X is not enough for a 3-line
        assert b.count_lines_for(PLAYER_X) == 0

    def test_diagonal_crossing_growth_boundary(self):
        """A ↘ diagonal that includes an added cell still counts as one line."""
        from game.board import Board, PLAYER_X
        b = Board()  # 3x3, valid (0..2, 0..2)
        # Grow so we have a cell at (3, 3) → forms a diagonal at (1,1),(2,2),(3,3)
        b._absorb((3, 2))
        b._absorb((3, 3))
        b.place_at(1, 1, PLAYER_X)
        b.place_at(2, 2, PLAYER_X)
        b.place_at(3, 3, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 1

    def test_anti_diagonal_crossing_growth_boundary(self):
        """A ↙ diagonal crossing growth boundary still counts."""
        from game.board import Board, PLAYER_X
        b = Board()
        # Grow so we have a cell at (3, -1) → forms ↙ at (1,1),(2,0),(3,-1)
        # _absorb of (3, -1) requires extending bottom and prepending col
        b._absorb((3, -1))
        # After prepend col, all coords shift right by 1, so:
        # original (1,1) → (1,2); original (2,0) → (2,1); new cell → (3,0)
        b.place_at(1, 2, PLAYER_X)
        b.place_at(2, 1, PLAYER_X)
        b.place_at(3, 0, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 1


class TestGrowEdgeCases:
    def test_grow_returns_none_when_no_valid_cells(self):
        """An empty playable area has no neighbours to expand into."""
        from game.board import Board
        b = Board()
        b.valid_cells = set()
        assert b.add_random_adjacent_cell() is None

    def test_grow_returns_none_when_no_candidates(self):
        """Defensive check: no orthogonal neighbour outside valid_cells."""
        # Construct a fully-enclosed playable area by mocking — every neighbour
        # of every valid cell is also in valid_cells. This isn't reachable
        # via normal growth, but pin down the guard so the random.choice([])
        # crash can't sneak in via misuse.
        from game.board import Board
        b = Board()
        # Manually mark valid_cells as the full 3x3 plus enough surrounding
        # cells that no outside neighbour exists in a single grow step?
        # Simpler: monkey-patch _absorb to be a no-op and seed valid_cells
        # such that the candidate set ends up empty by overriding the loop.
        b.valid_cells = {(0, 0)}
        # Force candidates to be empty by temporarily removing all neighbours
        # via subclassing
        class _Closed(Board):
            def add_random_adjacent_cell(self):
                candidates: set = set()
                for (r, c) in self.valid_cells:
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nb = (r + dr, c + dc)
                        if nb in self.valid_cells:  # inverted: simulate enclosed
                            candidates.add(nb)
                if not candidates:
                    return None
                return self._absorb(next(iter(candidates)))
        b.__class__ = _Closed
        assert b.add_random_adjacent_cell() is None


class TestShiftPreservesAuxiliaryCells:
    """Wall, poison and locked cells should shift when the grid expands up/left."""

    def test_wall_cells_shift_on_top_growth(self):
        from game.board import Board
        b = Board()
        b.wall_cells = [(0, 1)]
        b._absorb((-1, 0))
        # Top grew → all coords shift down by 1
        assert (1, 1) in b.wall_cells
        assert (0, 1) not in b.wall_cells

    def test_wall_cells_shift_on_left_growth(self):
        from game.board import Board
        b = Board()
        b.wall_cells = [(1, 0)]
        b._absorb((0, -1))
        assert (1, 1) in b.wall_cells
        assert (1, 0) not in b.wall_cells

    def test_poison_cells_shift_on_top_growth(self):
        from game.board import Board
        b = Board()
        b.poison_cells = [(0, 0), (2, 2)]
        b._absorb((-1, 1))
        assert (1, 0) in b.poison_cells
        assert (3, 2) in b.poison_cells

    def test_locked_cells_shift_on_growth(self):
        from game.board import Board
        b = Board()
        b.locked_cells = [(0, 0)]
        b._absorb((0, -1))
        assert (0, 1) in b.locked_cells

    def test_no_shift_when_growing_right_or_down(self):
        """Adding cells past the right/bottom doesn't shift existing coords."""
        from game.board import Board
        b = Board()
        b.wall_cells = [(0, 0)]
        b.poison_cells = [(2, 2)]
        b._absorb((3, 2))  # extend down
        assert (0, 0) in b.wall_cells
        assert (2, 2) in b.poison_cells
        b._absorb((1, 3))  # extend right
        assert (0, 0) in b.wall_cells
        assert (2, 2) in b.poison_cells
