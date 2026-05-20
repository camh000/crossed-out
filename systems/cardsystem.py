import random
from typing import Callable

from config.cards import get_by_name
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

# Pure scoring-buff jokers: name → upgrade key counted from passive_cards.
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
    def __init__(self):
        pass

    # --- Joker state initialisation --------------------------------------

    def apply_passive_buffs(self, player: Player) -> None:
        """Replay every passive joker in `player.passive_cards` into the
        upgrade counters that the scoring loop reads. Also seeds per-game
        consumable counters (sacrifice charges, AI-skip stacks).
        """
        for key in _PERSISTENT_UPGRADE_KEYS:
            player.upgrades.pop(key, None)
        for name in player.passive_cards:
            key = _CARD_UPGRADE.get(name)
            if key:
                player.upgrades[key] = player.upgrades.get(key, 0) + 1
        # Per-game consumables — re-seeded each start.
        player.upgrades["sacrifice_charges"] = player.passive_cards.count("Sacrifice")
        player.upgrades["overload_charges"] = player.passive_cards.count("Overload")
        player.upgrades["skip_opponent"] = 0  # Quick Draw repopulates on game start.

    def post_game_cleanup(self, player: Player) -> None:
        """Wipe per-game scratch state. Persistent buff stacks survive — they
        get re-applied via `apply_passive_buffs` next game."""
        one_shot_keys = ("skip_opponent", "sacrifice_charges", "overload_charges")
        for key in one_shot_keys:
            player.upgrades.pop(key, None)
        player.blind_shot_marks = []

    # --- Trigger entry points --------------------------------------------
    #
    # Each fire_* returns the list of jokers whose handler produced an
    # observable change. Callers (main.py) use the returned names to drive
    # the joker-glow animation. The "did anything change" detection
    # snapshots cheap board+player signals before and after each handler
    # so we don't have to make every handler return a bool individually.

    def fire_game_start(self, board, player: Player) -> list[str]:
        fired: list[str] = []
        for name, stacks in self._stacks(player):
            handler = _GAME_START_HANDLERS.get(name)
            if handler is None:
                continue
            before = self._snapshot(board, player)
            handler(board, player, stacks)
            if self._snapshot(board, player) != before:
                fired.append(name)
        return fired

    def fire_x_placed(self, board, player: Player, r: int, c: int) -> list[str]:
        fired: list[str] = []
        for name, stacks in self._stacks(player):
            handler = _X_PLACED_HANDLERS.get(name)
            if handler is None:
                continue
            before = self._snapshot(board, player)
            handler(board, player, r, c, stacks)
            if self._snapshot(board, player) != before:
                fired.append(name)
        return fired

    def fire_line_completed(self, board, player: Player, line_cells) -> list[str]:
        fired: list[str] = []
        for name, stacks in self._stacks(player):
            handler = _LINE_COMPLETE_HANDLERS.get(name)
            if handler is None:
                continue
            before = self._snapshot(board, player)
            handler(board, player, line_cells, stacks)
            if self._snapshot(board, player) != before:
                fired.append(name)
        return fired

    def fire_shop_open(self, player: Player) -> list[str]:
        fired: list[str] = []
        for name, stacks in self._stacks(player):
            handler = _SHOP_OPEN_HANDLERS.get(name)
            if handler is None:
                continue
            before = dict(player.upgrades)
            handler(player, stacks)
            if player.upgrades != before:
                fired.append(name)
        return fired

    @staticmethod
    def _snapshot(board, player: Player) -> tuple:
        """Cheap fingerprint of state that on-board triggers might
        change. Covers placements (move_count + grid hash), wall
        additions (wall_cells length), and charge consumption (the
        upgrades values that triggers decrement)."""
        grid_hash = tuple(tuple(row) for row in board.grid)
        upgrade_signal = (
            player.upgrades.get("overload_charges", 0),
            player.upgrades.get("skip_opponent", 0),
        )
        return (board.move_count, grid_hash, len(board.wall_cells), upgrade_signal)

    def try_sacrifice_save(self, board, player: Player) -> bool:
        """If the player owns Sacrifice and has charges left, consume one
        charge and undo the last X placement. Returns True if the loss was
        averted."""
        if player.upgrades.get("sacrifice_charges", 0) <= 0:
            return False
        if not player.cells_played:
            return False
        r, c = player.cells_played.pop()
        board.remove_at(r, c)
        player.upgrades["sacrifice_charges"] -= 1
        return True

    @staticmethod
    def _stacks(player: Player):
        """Yield (card_name, stack_count) once per unique card in the
        passive_cards list. Iteration order matches first-purchase order
        so triggers fire deterministically."""
        seen: set[str] = set()
        for name in player.passive_cards:
            if name in seen:
                continue
            seen.add(name)
            yield name, player.passive_cards.count(name)

    # --- ink × mult scoring ---------------------------------------------

    def score_breakdown(
        self,
        board,
        player: Player,
        level_mult: int,
        *,
        is_boss: bool = False,
        boss_mechanic: str | None = None,
    ) -> tuple[int, float, int]:
        """Compute (ink, mult, total) for the current board state.

        ink: additive component. Each player's completed line contributes
        (sum of cell weights × line length) ink, plus per-card flat bonuses.
        Opponent lines subtract ink at the same base rate — UNLESS the
        Double Cross boss is active, in which case opponent lines add
        ink instead (every line on the board counts toward your score).

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

        double_cross = is_boss and boss_mechanic == "doublecross"
        for cells in o_lines:
            line_ink = self._line_base_ink(board, cells)
            if double_cross:
                ink += line_ink
            else:
                ink -= line_ink

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


# ---------------------------------------------------------------------------
# Trigger handler implementations
# ---------------------------------------------------------------------------

def _is_edge(board, r: int, c: int) -> bool:
    if not board.valid_cells:
        return False
    rows = [rr for (rr, _) in board.valid_cells]
    cols = [cc for (_, cc) in board.valid_cells]
    return r in (min(rows), max(rows)) or c in (min(cols), max(cols))


def _board_centre(board) -> tuple[int, int]:
    rows = [r for (r, _) in board.valid_cells]
    cols = [c for (_, c) in board.valid_cells]
    return (min(rows) + max(rows)) // 2, (min(cols) + max(cols)) // 2


def _random_empty_cells(board, n: int) -> list[tuple[int, int]]:
    empty = [
        pos for pos in board.get_empty_cells()
        if pos not in board.wall_cells
    ]
    if not empty:
        return []
    return random.sample(empty, min(n, len(empty)))


# --- on_game_start ----------------------------------------------------------

def _trigger_cell_lock_start(board, player: Player, stacks: int) -> None:
    """First stack locks the centre cell. Additional stacks lock random
    extra cells. Cells already locked are skipped."""
    if stacks <= 0:
        return
    cr, cc = _board_centre(board)
    target = (cr, cc)
    if target not in board.valid_cells:
        empty = board.get_empty_cells()
        if not empty:
            return
        target = min(empty, key=lambda p: (p[0] - cr) ** 2 + (p[1] - cc) ** 2)
    if target not in board.wall_cells:
        board.wall_cells.append(target)
    extra = stacks - 1
    if extra > 0:
        for pos in _random_empty_cells(board, extra):
            if pos not in board.wall_cells:
                board.wall_cells.append(pos)


def _trigger_fortress_start(board, player: Player, stacks: int) -> None:
    for pos in _random_empty_cells(board, stacks):
        if pos not in board.wall_cells:
            board.wall_cells.append(pos)


def _trigger_ghost_board_start(board, player: Player, stacks: int) -> None:
    for pos in _random_empty_cells(board, 3 * stacks):
        if pos not in board.wall_cells:
            board.wall_cells.append(pos)


def _trigger_blind_shot_start(board, player: Player, stacks: int) -> None:
    """Place stacks X's on random empty edges; track each as a 'blind
    shot' mark so scoring doubles any winning line containing one."""
    for _ in range(stacks):
        edges = [
            (r, c) for (r, c) in board.valid_cells
            if _is_edge(board, r, c)
            and board.grid[r][c] == EMPTY
            and (r, c) not in board.wall_cells
        ]
        if not edges:
            return
        r, c = random.choice(edges)
        if board.place_at(r, c, PLAYER_X):
            player.cells_played.append((r, c))
            player.blind_shot_marks.append((r, c))


def _trigger_double_strike_start(board, player: Player, stacks: int) -> None:
    """Place `stacks` free X's, one in each of `stacks` different rows
    where an empty cell exists."""
    placed_rows: set[int] = set()
    remaining = stacks
    for r in sorted({rr for (rr, _) in board.valid_cells}):
        if remaining <= 0:
            return
        empties_in_row = [
            (rr, cc) for (rr, cc) in board.get_empty_cells()
            if rr == r and (rr, cc) not in board.wall_cells
        ]
        if not empties_in_row:
            continue
        rr, cc = random.choice(empties_in_row)
        if board.place_at(rr, cc, PLAYER_X):
            player.cells_played.append((rr, cc))
            placed_rows.add(r)
            remaining -= 1


def _trigger_quick_draw_start(board, player: Player, stacks: int) -> None:
    player.upgrades["skip_opponent"] = player.upgrades.get("skip_opponent", 0) + stacks


# --- on_x_placed ------------------------------------------------------------

def _trigger_ricochet_on_x(board, player: Player, r: int, c: int, stacks: int) -> None:
    if not _is_edge(board, r, c):
        return
    rows = [rr for (rr, _) in board.valid_cells]
    cols = [cc for (_, cc) in board.valid_cells]
    rmin, rmax = min(rows), max(rows)
    cmin, cmax = min(cols), max(cols)
    opp = (rmax - (r - rmin), cmax - (c - cmin))
    if opp == (r, c):
        return
    if opp not in board.valid_cells:
        return
    if board.grid[opp[0]][opp[1]] != EMPTY:
        return
    if opp in board.wall_cells:
        return
    if board.place_at(opp[0], opp[1], PLAYER_X):
        player.cells_played.append(opp)


def _trigger_overload_on_x(board, player: Player, r: int, c: int, stacks: int) -> None:
    """Wipe adjacent O's, but only if a charge is available — one charge
    per Overload copy per game. Spending a charge requires that at least
    one O was actually destroyed, so the player doesn't waste a charge
    on placements with no nearby opponent marks."""
    charges = player.upgrades.get("overload_charges", 0)
    if charges <= 0:
        return
    destroyed = False
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if (nr, nc) in board.valid_cells and board.grid[nr][nc] == OPPONENT_O:
                board.grid[nr][nc] = EMPTY
                board.placed_at[nr][nc] = -1
                destroyed = True
    if destroyed:
        player.upgrades["overload_charges"] = charges - 1


# --- on_line_completed ------------------------------------------------------

def _trigger_chain_reaction_on_line(board, player: Player, line_cells, stacks: int) -> None:
    for (r, c) in line_cells:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if (nr, nc) in board.valid_cells and board.grid[nr][nc] == OPPONENT_O:
                    board.grid[nr][nc] = PLAYER_X


# --- on_shop_open -----------------------------------------------------------

def _trigger_reroll_free(player: Player, stacks: int) -> None:
    player.upgrades["free_rerolls"] = player.upgrades.get("free_rerolls", 0) + stacks


def _trigger_extra_offer(player: Player, stacks: int) -> None:
    player.upgrades["shop_offer_extra"] = player.upgrades.get("shop_offer_extra", 0) + stacks


# ---------------------------------------------------------------------------
# Dispatch tables — name → handler. Kept at module bottom so handler
# functions are already defined.
# ---------------------------------------------------------------------------

_GAME_START_HANDLERS: dict[str, Callable] = {
    "Cell Lock": _trigger_cell_lock_start,
    "Fortress": _trigger_fortress_start,
    "Ghost Board": _trigger_ghost_board_start,
    "Blind Shot": _trigger_blind_shot_start,
    "Double Strike": _trigger_double_strike_start,
    "Quick Draw": _trigger_quick_draw_start,
}

_X_PLACED_HANDLERS: dict[str, Callable] = {
    "Ricochet": _trigger_ricochet_on_x,
    "Overload": _trigger_overload_on_x,
}

_LINE_COMPLETE_HANDLERS: dict[str, Callable] = {
    "Chain Reaction": _trigger_chain_reaction_on_line,
}

_SHOP_OPEN_HANDLERS: dict[str, Callable] = {
    "Reroll": _trigger_reroll_free,
    "Card Draw": _trigger_extra_offer,
}
