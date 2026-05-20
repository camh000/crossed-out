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


class TestPlacedAtAging:
    """Each placement records the move_count at which it landed in
    `board.placed_at[r][c]`. The Blind boss uses this to fade old marks.
    Cleared cells reset to -1; grow/advance keep `placed_at` parallel to
    `grid`."""

    def test_first_placement_records_move_count(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(1, 1, PLAYER_X)
        assert b.placed_at[1][1] == 1  # move_count became 1 on placement
        # Untouched cells stay -1.
        assert b.placed_at[0][0] == -1

    def test_consecutive_placements_increment_stamps(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)   # move 1
        b.place_at(0, 1, OPPONENT_O)  # move 2
        b.place_at(0, 2, PLAYER_X)   # move 3
        assert b.placed_at[0][0] == 1
        assert b.placed_at[0][1] == 2
        assert b.placed_at[0][2] == 3

    def test_age_against_move_count(self):
        """The convention used by the Blind renderer: age = move_count -
        placed_at, where 0 means 'just placed this turn'."""
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0, 0, PLAYER_X)  # move 1; placed_at=1
        # After three more moves, the (0,0) mark is 3 moves old.
        b.place_at(0, 1, PLAYER_X)  # move 2
        b.place_at(1, 0, PLAYER_X)  # move 3
        b.place_at(1, 1, PLAYER_X)  # move 4
        assert b.move_count - b.placed_at[0][0] == 3

    def test_remove_resets_stamp(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(1, 1, PLAYER_X)
        assert b.placed_at[1][1] >= 0
        b.remove_at(1, 1)
        assert b.placed_at[1][1] == -1

    def test_clear_marks_resets_stamps(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.clear_marks()
        assert all(b.placed_at[r][c] == -1 for r in range(3) for c in range(3))

    def test_grow_keeps_placed_at_parallel_to_grid(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.grow_row_and_column()
        # Dimensions match grid.
        assert len(b.placed_at) == b.rows
        for row in b.placed_at:
            assert len(row) == b.cols

    def test_advance_to_size_wipes_stamps_and_resizes(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.advance_to_size(5)
        # placed_at array got expanded and zeroed via clear_marks.
        assert len(b.placed_at) == 5
        for row in b.placed_at:
            assert len(row) == 5
            assert all(v == -1 for v in row)

    def test_poison_clear_resets_stamp(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.poison_cells = [(1, 1)]
        b.place_at(1, 1, PLAYER_X)
        assert b.placed_at[1][1] >= 0
        b.register_poison_hit(1, 1, ttl=1)
        b.tick_poison()  # ttl 1 -> 0, cell cleared
        assert b.placed_at[1][1] == -1


class TestVisibleGridView:
    """Board.visible_grid_view(fade_age) returns a copy of `grid` with
    cells aged past `fade_age` replaced by EMPTY. Used by the Blind boss
    renderer AND the AI so both forget the same way."""

    def test_unfaded_cells_keep_their_value(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.place_at(1, 1, PLAYER_X)  # placed_at=1, move_count=1, age=0
        view = b.visible_grid_view(fade_age=6)
        assert view[1][1] == PLAYER_X

    def test_faded_cells_become_empty(self):
        from game.board import Board, PLAYER_X, EMPTY
        b = Board()
        b.place_at(0, 0, PLAYER_X)  # move 1
        # Pump move_count up by 6 more placements.
        b.place_at(0, 1, PLAYER_X)
        b.place_at(0, 2, PLAYER_X)
        b.place_at(1, 0, PLAYER_X)
        b.place_at(1, 1, PLAYER_X)
        b.place_at(1, 2, PLAYER_X)
        b.place_at(2, 0, PLAYER_X)  # move 7
        # (0,0) was placed at move 1; current move_count=7 → age 6.
        view = b.visible_grid_view(fade_age=6)
        assert view[0][0] == EMPTY
        # The just-placed (2,0) at age 0 stays visible.
        assert view[2][0] == PLAYER_X

    def test_never_placed_cells_unchanged(self):
        from game.board import Board, EMPTY
        b = Board()
        view = b.visible_grid_view(fade_age=1)
        for r in range(3):
            for c in range(3):
                assert view[r][c] == EMPTY

    def test_view_is_an_independent_copy(self):
        from game.board import Board, PLAYER_X, EMPTY
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        view = b.visible_grid_view(fade_age=6)
        view[0][0] = EMPTY
        # Real grid not affected by mutating the view.
        assert b.grid[0][0] == PLAYER_X


class TestPoisonTTL:
    """Poison boss: a player mark on a poison cell is removed after two
    AI ticks via Board.tick_poison()."""

    def test_register_then_tick_clears_mark(self):
        from game.board import Board, PLAYER_X, EMPTY
        b = Board()
        b.poison_cells = [(1, 1)]
        b.place_at(1, 1, PLAYER_X)
        b.register_poison_hit(1, 1, ttl=2)
        # First tick: ttl 2 -> 1. Mark still there.
        cleared = b.tick_poison()
        assert cleared == []
        assert b.grid[1][1] == PLAYER_X
        assert (1, 1) in b.poison_cells
        # Second tick: ttl 1 -> 0. Cell cleared and poison removed.
        cleared = b.tick_poison()
        assert cleared == [(1, 1)]
        assert b.grid[1][1] == EMPTY
        assert (1, 1) not in b.poison_cells

    def test_shift_coords_moves_poisoned_marks(self):
        from game.board import Board
        b = Board()
        b.register_poison_hit(0, 1, ttl=2)
        b.shift_coords(1, 0)
        assert b.poisoned_marks == [(1, 1, 2)]


class TestGrowRowAndColumn:
    """On a draw the board grows by one full new row and one full new
    column on independently-chosen random sides."""

    def test_grow_expands_bounding_box_by_one_in_each_axis(self):
        from game.board import Board
        b = Board()  # 3x3
        b.grow_row_and_column()
        assert b.rows == 4
        assert b.cols == 4
        # Every cell in the new 4x4 bounding box should be playable.
        assert len(b.valid_cells) == 16

    def test_grow_preserves_existing_marks(self):
        from game.board import Board, PLAYER_X, OPPONENT_O
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        b.place_at(2, 2, OPPONENT_O)
        row_shift, col_shift = b.grow_row_and_column()
        # Coordinates may have shifted (if grown at top/left). Either way,
        # the marks should still be present exactly once each.
        flat = [v for row in b.grid for v in row]
        assert flat.count(PLAYER_X) == 1
        assert flat.count(OPPONENT_O) == 1
        # And specifically the shifted positions should hold them.
        assert b.grid[0 + row_shift][0 + col_shift] == PLAYER_X
        assert b.grid[2 + row_shift][2 + col_shift] == OPPONENT_O

    def test_grow_keeps_line_length(self):
        """The size attribute (line-length target) is unaffected by growth."""
        from game.board import Board
        b = Board(size=3)
        for _ in range(4):
            b.grow_row_and_column()
        assert b.size == 3

    def test_grow_returns_shift_amounts(self):
        from game.board import Board
        b = Board()
        row_shift, col_shift = b.grow_row_and_column()
        assert row_shift in (0, 1)
        assert col_shift in (0, 1)

    def test_grow_top_shifts_existing_coords(self):
        """Top growth shifts every existing coord down by 1."""
        from game.board import Board, PLAYER_X
        import random
        b = Board()
        b.place_at(0, 0, PLAYER_X)
        # Seed so the first random.choice picks (True, False) → top, right.
        random.seed(2)
        row_shift, col_shift = b.grow_row_and_column()
        if row_shift == 1:
            # X originally at (0, 0) is now at (1, col_shift)
            assert b.grid[1][col_shift] == PLAYER_X

    def test_grow_shifts_wall_poison_locked(self):
        """Wall, poison and locked cells shift the same as marks."""
        from game.board import Board
        b = Board()
        b.wall_cells = [(0, 1)]
        b.poison_cells = [(2, 2)]
        b.locked_cells = [(1, 0)]
        row_shift, col_shift = b.grow_row_and_column()
        assert (0 + row_shift, 1 + col_shift) in b.wall_cells
        assert (2 + row_shift, 2 + col_shift) in b.poison_cells
        assert (1 + row_shift, 0 + col_shift) in b.locked_cells

    def test_grow_can_grow_in_any_corner(self):
        """Over enough trials the growth should visit all four corner
        combinations (top-left, top-right, bottom-left, bottom-right)."""
        from game.board import Board
        import random
        random.seed(0)
        corners = set()
        for _ in range(64):
            b = Board()
            row_shift, col_shift = b.grow_row_and_column()
            corners.add((row_shift, col_shift))
        assert corners == {(0, 0), (0, 1), (1, 0), (1, 1)}


class TestLineDetectionAfterGrowth:
    """Lines in the newly added row/column count exactly like any other
    row/column line."""

    def test_line_in_added_row(self):
        from game.board import Board, PLAYER_X
        import random
        b = Board()
        # Force a specific growth direction by seeding: we want a new row
        # at the bottom (row_shift=0) and the col side doesn't matter.
        for seed in range(100):
            random.seed(seed)
            b2 = Board()
            row_shift, _ = b2.grow_row_and_column()
            if row_shift == 0:
                b = b2
                break
        # Fill the new bottom row's first three cells with X.
        for c in range(3):
            b.place_at(3, c, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 1

    def test_no_phantom_line_in_partial_fill(self):
        from game.board import Board, PLAYER_X
        b = Board()
        b.grow_row_and_column()
        # Two X's in a row isn't a size-3 line.
        b.place_at(0, 0, PLAYER_X)
        b.place_at(0, 1, PLAYER_X)
        assert b.count_lines_for(PLAYER_X) == 0
