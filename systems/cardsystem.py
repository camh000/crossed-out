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
    # New scoring buffs.
    "edge_lord",
    "centripetal",
    "long_bow",
    "first_strike",
    "rich_vein",
    "quartet",
    "war_machine",
    "last_stand",
    "crescendo",
    "magnitude",
    "lethal",
    "phoenix",
    "shield",
    "patience",
    "pacifist",
    "cursed_coin",
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
    "Edge Lord": "edge_lord",
    "Centripetal": "centripetal",
    "Long Bow": "long_bow",
    "First Strike": "first_strike",
    "Rich Vein": "rich_vein",
    "Quartet": "quartet",
    "War Machine": "war_machine",
    "Last Stand": "last_stand",
    "Crescendo": "crescendo",
    "Magnitude": "magnitude",
    "Lethal": "lethal",
    "Phoenix": "phoenix",
    "Shield": "shield",
    "Patience": "patience",
    "Pacifist": "pacifist",
    "Cursed Coin": "cursed_coin",
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
        player.upgrades["flame_charges"] = player.passive_cards.count("Flame")
        player.upgrades["skip_opponent"] = 0  # Quick Draw repopulates on game start.
        # Per-game counters that drive scoring buffs and end-game bonuses.
        # Cleared by post_game_cleanup so they don't bleed across games.
        player.upgrades["os_destroyed"] = 0
        player.upgrades["lines_scored"] = 0
        player.upgrades["first_x_line_done"] = 0
        player.upgrades["x_placed_count"] = 0
        player.upgrades["ai_placed_count"] = 0
        # Counter-trigger payoff (set when Counter / Vampire fire).
        player.upgrades.pop("counter_bonus_ink", None)
        player.upgrades.pop("vampire_tokens", None)

    def post_game_cleanup(self, player: Player) -> None:
        """Wipe per-game scratch state. Persistent buff stacks survive — they
        get re-applied via `apply_passive_buffs` next game."""
        one_shot_keys = (
            "skip_opponent", "sacrifice_charges", "overload_charges",
            "flame_charges", "os_destroyed", "lines_scored",
            "first_x_line_done", "x_placed_count", "ai_placed_count",
            "counter_bonus_ink", "vampire_tokens",
        )
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

    def fire_ai_placed(self, board, player: Player, r: int, c: int) -> list[str]:
        """Trigger fired right after the AI lands an O. Drives Counter,
        Vampire and Interference."""
        fired: list[str] = []
        for name, stacks in self._stacks(player):
            handler = _AI_PLACED_HANDLERS.get(name)
            if handler is None:
                continue
            before = self._snapshot(board, player)
            handler(board, player, r, c, stacks)
            if self._snapshot(board, player) != before:
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
        spotlight_zone: tuple[int, int] | None = None,
        centre: tuple[int, int] | None = None,
        lives: int = 3,
    ) -> tuple[int, float, int]:
        """Compute (ink, mult, total) for the current board state.

        Per-line ink comes from line_contributions so the same modifiers
        (Edge Lord, Centripetal, First Strike, etc.) are visible to both
        the result panel and the final score. score_breakdown adds the
        aggregate layer on top: Board Control floor, Final Count
        multiplier, and the multiplicative Mult component.
        """
        contribs = self.line_contributions(
            board, player,
            is_boss=is_boss,
            boss_mechanic=boss_mechanic,
            spotlight_zone=spotlight_zone,
            centre=centre,
        )
        ink = sum(c["contribution"] for c in contribs)

        # Quartet — owning ≥4 distinct buff jokers doubles ink.
        quartet = player.upgrades.get("quartet", 0)
        if quartet > 0 and len({n for n in player.passive_cards}) >= 4:
            ink *= 2

        # Last Stand — when down to your final life, +50% ink (per copy).
        last_stand = player.upgrades.get("last_stand", 0)
        if last_stand > 0 and lives <= 1:
            ink = int(ink * (1.0 + 0.5 * last_stand))

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
        x_lines_for_diag = [c["cells"] for c in contribs if c["side"] == "X"]
        diag_stacks = player.upgrades.get("diagonal_power", 0)
        if diag_stacks > 0 and any(self._is_diagonal(board, cells) for cells in x_lines_for_diag):
            mult += 0.5 * diag_stacks
        # Crescendo — Mult +0.2 per X line scored this game (cumulative
        # across the run between cleanups). Read off the upgrade counter
        # that evaluate_and_settle bumps when this game's lines settle.
        crescendo = player.upgrades.get("crescendo", 0)
        if crescendo > 0:
            mult += 0.2 * crescendo * player.upgrades.get("lines_scored", 0)
        # Magnitude — Mult +1 when board has grown past the 5x5 base.
        magnitude = player.upgrades.get("magnitude", 0)
        if magnitude > 0 and max(board.rows, board.cols) > 5:
            mult += magnitude
        # Lethal — Mult +0.5 on boss games.
        lethal = player.upgrades.get("lethal", 0)
        if lethal > 0 and is_boss:
            mult += 0.5 * lethal
        # War Machine — if ≥3 O's destroyed this game, double Mult.
        war_machine = player.upgrades.get("war_machine", 0)
        if war_machine > 0 and player.upgrades.get("os_destroyed", 0) >= 3:
            mult *= 2 * war_machine

        if ink <= 0:
            return 0, mult, 0
        return int(ink), mult, int(ink * mult)

    def calculate_score(self, board, player: Player, multiplier: int) -> int:
        """Back-compat shim: return just the total. Most callers want this."""
        _ink, _mult, total = self.score_breakdown(board, player, multiplier)
        return total

    def line_contributions(
        self,
        board,
        player: Player,
        *,
        is_boss: bool = False,
        boss_mechanic: str | None = None,
        spotlight_zone: tuple[int, int] | None = None,
        centre: tuple[int, int] | None = None,
    ) -> list[dict]:
        """Per-line breakdown of how each completed line contributes to the
        final ink. Used by the result panel to show 'where did the score
        come from'. Returns a list of dicts:

            {
                "cells": [(r, c), ...],   # cells in this line
                "side": "X" | "O",          # whose mark forms it
                "wildcard": bool,           # generated by the Wildcard buff
                "base": int,                # raw line ink (weight_sum × len)
                "modifiers": list[(label, int)],  # per-line additive bonuses
                "contribution": int,        # signed contribution to ink
            }
        """
        contribs: list[dict] = []

        x_lines = self._collect_lines(board, PLAYER_X)
        wildcard_marker: set[tuple] = set()
        wildcard_stacks = player.upgrades.get("wildcard", 0)
        if wildcard_stacks > 0:
            wc = self._wildcard_lines(board, wildcard_stacks)
            for cells in wc:
                wildcard_marker.add(tuple(sorted(cells)))
            x_lines += wc
        o_lines = self._collect_lines(board, OPPONENT_O)
        blind_marks = set(player.blind_shot_marks)
        point_mult_stacks = player.upgrades.get("point_mult", 0)
        deep_grid_stacks = player.upgrades.get("deep_grid", 0)
        double_cross = is_boss and boss_mechanic == "doublecross"

        edge_lord_stacks = player.upgrades.get("edge_lord", 0)
        centripetal_stacks = player.upgrades.get("centripetal", 0)
        long_bow_stacks = player.upgrades.get("long_bow", 0)
        first_x_done = player.upgrades.get("first_x_line_done", 0)
        first_strike_stacks = player.upgrades.get("first_strike", 0)
        rich_vein = player.upgrades.get("rich_vein", 0)
        joker_diversity = len({n for n in player.passive_cards})
        counter_bonus = player.upgrades.get("counter_bonus_ink", 0)

        rmin = min((rr for (rr, _) in board.valid_cells), default=0)
        rmax = max((rr for (rr, _) in board.valid_cells), default=0)
        cmin = min((cc for (_, cc) in board.valid_cells), default=0)
        cmax = max((cc for (_, cc) in board.valid_cells), default=0)
        if centre is None:
            # Centripetal / centre-bonus checks default to the geometric
            # centre of the playable region. The Inverse boss passes its
            # own explicit centre, but otherwise we infer.
            centre = ((rmin + rmax) // 2, (cmin + cmax) // 2)

        def _on_edge(line) -> bool:
            return all(
                r in (rmin, rmax) or c in (cmin, cmax) for (r, c) in line
            )

        def _through_centre(line) -> bool:
            if centre is None:
                return False
            return centre in line

        def _in_spotlight(line) -> bool:
            if spotlight_zone is None:
                return True
            ar, ac = spotlight_zone
            return all(ar <= r <= ar + 2 and ac <= c <= ac + 2 for (r, c) in line)

        for cells in x_lines:
            # Spotlight boss: lines outside the zone score nothing.
            if boss_mechanic == "spotlight" and not _in_spotlight(cells):
                continue
            base = self._line_base_ink(board, cells)
            mods: list[tuple[str, int]] = []
            line_ink = base
            if any(cell in blind_marks for cell in cells):
                mods.append(("Blind Shot x2", base))
                line_ink *= 2
            if point_mult_stacks > 0:
                pm = point_mult_stacks * 3
                mods.append((f"Point Mult x{point_mult_stacks}", pm))
                line_ink += pm
            if deep_grid_stacks > 0:
                mods.append((f"Deep Grid x{deep_grid_stacks}", deep_grid_stacks))
                line_ink += deep_grid_stacks
            if edge_lord_stacks > 0 and _on_edge(cells):
                bonus = (line_ink * edge_lord_stacks) // 2
                mods.append((f"Edge Lord +{50 * edge_lord_stacks}%", bonus))
                line_ink += bonus
            if centripetal_stacks > 0 and _through_centre(cells):
                bonus = 5 * centripetal_stacks
                mods.append((f"Centripetal x{centripetal_stacks}", bonus))
                line_ink += bonus
            if long_bow_stacks > 0 and len(cells) == board.size:
                # On a grown board, lines longer than base size exist too —
                # this rewards staying at the original size.
                if (rmax - rmin + 1) > board.size or (cmax - cmin + 1) > board.size:
                    mods.append((f"Long Bow x{long_bow_stacks}", line_ink * long_bow_stacks))
                    line_ink += line_ink * long_bow_stacks
            if first_strike_stacks > 0 and not first_x_done:
                bonus = 20 * first_strike_stacks
                mods.append((f"First Strike +{bonus}", bonus))
                line_ink += bonus
                first_x_done = 1  # only the very first line gets it
            if rich_vein > 0 and joker_diversity >= 3:
                mods.append((f"Rich Vein +{10 * rich_vein}", 10 * rich_vein))
                line_ink += 10 * rich_vein
            if counter_bonus > 0:
                mods.append((f"Counter +{counter_bonus}", counter_bonus))
                line_ink += counter_bonus
                counter_bonus = 0  # one-shot
            # Inverse boss: lines through the centre cell score negative.
            if boss_mechanic == "inverse" and _through_centre(cells):
                mods.append(("Inverse (centre)", -2 * line_ink))
                line_ink = -line_ink
            contribs.append({
                "cells": list(cells),
                "side": "X",
                "wildcard": tuple(sorted(cells)) in wildcard_marker,
                "base": base,
                "modifiers": mods,
                "contribution": line_ink,
            })

        for cells in o_lines:
            # Spotlight boss zeroes lines outside the zone.
            if boss_mechanic == "spotlight" and not _in_spotlight(cells):
                continue
            base = self._line_base_ink(board, cells)
            sign = 1 if double_cross else -1
            contribs.append({
                "cells": list(cells),
                "side": "O",
                "wildcard": False,
                "base": base,
                "modifiers": [("Double Cross +", base)] if double_cross else [],
                "contribution": sign * base,
            })

        return contribs

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
    destroyed = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if (nr, nc) in board.valid_cells and board.grid[nr][nc] == OPPONENT_O:
                board.grid[nr][nc] = EMPTY
                board.placed_at[nr][nc] = -1
                destroyed += 1
    if destroyed:
        player.upgrades["overload_charges"] = charges - 1
        player.upgrades["os_destroyed"] = player.upgrades.get("os_destroyed", 0) + destroyed


# --- on_line_completed ------------------------------------------------------

def _trigger_chain_reaction_on_line(board, player: Player, line_cells, stacks: int) -> None:
    flipped = 0
    for (r, c) in line_cells:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if (nr, nc) in board.valid_cells and board.grid[nr][nc] == OPPONENT_O:
                    board.grid[nr][nc] = PLAYER_X
                    board.placed_at[nr][nc] = board.move_count
                    flipped += 1
    if flipped:
        player.upgrades["os_destroyed"] = player.upgrades.get("os_destroyed", 0) + flipped


# --- on_shop_open -----------------------------------------------------------

def _trigger_reroll_free(player: Player, stacks: int) -> None:
    player.upgrades["free_rerolls"] = player.upgrades.get("free_rerolls", 0) + stacks


def _trigger_extra_offer(player: Player, stacks: int) -> None:
    player.upgrades["shop_offer_extra"] = player.upgrades.get("shop_offer_extra", 0) + stacks


def _trigger_wholesaler(player: Player, stacks: int) -> None:
    """Shop card costs are reduced by `stacks` (minimum 1). Stored on the
    upgrades dict and read by the shop click handler in main.py."""
    player.upgrades["shop_discount"] = player.upgrades.get("shop_discount", 0) + stacks


def _trigger_banker(player: Player, stacks: int) -> None:
    """+1 token per 3 tokens already held when the shop opens, per copy.
    Compounding savings interest."""
    interest = stacks * (player.tokens // 3)
    if interest:
        player.tokens += interest


# --- on_x_placed (new handlers) --------------------------------------------

def _trigger_flame_on_x(board, player: Player, r: int, c: int, stacks: int) -> None:
    """Destroys orthogonally adjacent O's. Smaller AoE than Overload —
    no diagonals — and uses its own charge pool (also 1/copy/game)."""
    charges = player.upgrades.get("flame_charges", 0)
    if charges <= 0:
        return
    destroyed = 0
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if (nr, nc) in board.valid_cells and board.grid[nr][nc] == OPPONENT_O:
            board.grid[nr][nc] = EMPTY
            board.placed_at[nr][nc] = -1
            destroyed += 1
    if destroyed:
        player.upgrades["flame_charges"] = charges - 1
        player.upgrades["os_destroyed"] = player.upgrades.get("os_destroyed", 0) + destroyed


def _trigger_stutter_on_x(board, player: Player, r: int, c: int, stacks: int) -> None:
    """Every 3rd X placement (cumulative across the game) also mirrors
    to the cell on the opposite edge of the board, if empty."""
    count = player.upgrades.get("x_placed_count", 0) + 1
    player.upgrades["x_placed_count"] = count
    if count % 3 != 0:
        return
    rows = [rr for (rr, _) in board.valid_cells]
    cols = [cc for (_, cc) in board.valid_cells]
    opp = (max(rows) - (r - min(rows)), max(cols) - (c - min(cols)))
    if opp == (r, c) or opp not in board.valid_cells:
        return
    if board.grid[opp[0]][opp[1]] != EMPTY or opp in board.wall_cells:
        return
    if board.place_at(opp[0], opp[1], PLAYER_X):
        player.cells_played.append(opp)


def _trigger_magnet_on_x(board, player: Player, r: int, c: int, stacks: int) -> None:
    """Move the nearest O one cell closer to the just-placed X (Manhattan
    direction). Per copy: pulls one more O."""
    os = [(rr, cc) for (rr, cc) in board.valid_cells if board.grid[rr][cc] == OPPONENT_O]
    if not os:
        return
    # Sort by Manhattan distance to (r, c), pull the nearest `stacks`.
    os.sort(key=lambda p: abs(p[0] - r) + abs(p[1] - c))
    for (or_, oc_) in os[:stacks]:
        # Step the O one cell along whichever axis has the bigger gap.
        dr = (r - or_) and (1 if r > or_ else -1)
        dc = (c - oc_) and (1 if c > oc_ else -1)
        # Prefer the larger axis if both are non-zero.
        if abs(r - or_) >= abs(c - oc_):
            step = (or_ + dr, oc_) if dr else (or_, oc_ + dc)
        else:
            step = (or_, oc_ + dc) if dc else (or_ + dr, oc_)
        if step == (or_, oc_):
            continue
        if step not in board.valid_cells:
            continue
        if board.grid[step[0]][step[1]] != EMPTY or step in board.wall_cells:
            continue
        board.grid[or_][oc_] = EMPTY
        board.placed_at[or_][oc_] = -1
        board.grid[step[0]][step[1]] = OPPONENT_O
        board.placed_at[step[0]][step[1]] = board.move_count


def _trigger_cascade_on_x(board, player: Player, r: int, c: int, stacks: int) -> None:
    """If the just-placed X is collinear with two existing X's, spawn an
    extra X on the line's extension cell (if valid + empty)."""
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        # Walk both ways from (r, c) and count consecutive X's.
        run_forward = 0
        nr, nc = r + dr, c + dc
        while (nr, nc) in board.valid_cells and board.grid[nr][nc] == PLAYER_X:
            run_forward += 1
            nr += dr
            nc += dc
        run_back = 0
        pr, pc = r - dr, c - dc
        while (pr, pc) in board.valid_cells and board.grid[pr][pc] == PLAYER_X:
            run_back += 1
            pr -= dr
            pc -= dc
        if run_forward + run_back >= 2:
            # Find the next empty extension cell on whichever side.
            for ext in ((nr, nc), (pr, pc)):
                if (ext in board.valid_cells and board.grid[ext[0]][ext[1]] == EMPTY
                        and ext not in board.wall_cells):
                    if board.place_at(ext[0], ext[1], PLAYER_X):
                        player.cells_played.append(ext)
                        return


# --- on_ai_placed (new hook) ----------------------------------------------

def _trigger_counter_on_ai(board, player: Player, r: int, c: int, stacks: int) -> None:
    """The next X line you score gets +2 ink per stack. Stored as a
    one-shot bonus the line_contributions calculator reads."""
    player.upgrades["counter_bonus_ink"] = (
        player.upgrades.get("counter_bonus_ink", 0) + 2 * stacks
    )


def _trigger_vampire_on_ai(board, player: Player, r: int, c: int, stacks: int) -> None:
    """Accumulate +1 token per O placed by the AI, paid out at game end."""
    player.upgrades["vampire_tokens"] = (
        player.upgrades.get("vampire_tokens", 0) + stacks
    )


def _trigger_interference_on_ai(board, player: Player, r: int, c: int, stacks: int) -> None:
    """Every 4th AI placement is randomised — overwrite the just-placed
    O onto a random empty cell. Stack count multiplies the frequency
    (1 stack = every 4th, 2 stacks = every 3rd, etc.)."""
    count = player.upgrades.get("ai_placed_count", 0) + 1
    player.upgrades["ai_placed_count"] = count
    every = max(2, 5 - stacks)
    if count % every != 0:
        return
    empty = [
        p for p in board.get_empty_cells() if p not in board.wall_cells
    ]
    if not empty:
        return
    new = random.choice(empty)
    # Move the O from (r, c) to a random empty cell.
    board.grid[r][c] = EMPTY
    board.placed_at[r][c] = -1
    if board.place_at(new[0], new[1], OPPONENT_O):
        pass  # placed_at stamped by place_at


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
    "Flame": _trigger_flame_on_x,
    "Stutter": _trigger_stutter_on_x,
    "Magnet": _trigger_magnet_on_x,
    "Cascade": _trigger_cascade_on_x,
}

_LINE_COMPLETE_HANDLERS: dict[str, Callable] = {
    "Chain Reaction": _trigger_chain_reaction_on_line,
}

_SHOP_OPEN_HANDLERS: dict[str, Callable] = {
    "Reroll": _trigger_reroll_free,
    "Card Draw": _trigger_extra_offer,
    "Wholesaler": _trigger_wholesaler,
    "Banker": _trigger_banker,
}

_AI_PLACED_HANDLERS: dict[str, Callable] = {
    "Counter": _trigger_counter_on_ai,
    "Vampire": _trigger_vampire_on_ai,
    "Interference": _trigger_interference_on_ai,
}
