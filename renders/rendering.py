from game.board import Board, PLAYER_X, OPPONENT_O
from game.opponent import OpponentAI
from config.constants import (
    SCREEN_W, SCREEN_H,
    COLOR_X, COLOR_O, COLOR_PENDING,
    TEXT_COLOR, TEXT_SUB,
    ACCENT_GOLD, ACCENT_GREEN,
    SCORE_MULT_3, SCORE_MULT_5, SCORE_MULT_7,
)
import pygame


# Pre-rendered SRCALPHA surfaces are expensive in WASM. Cache by the
# parameters that uniquely identify them so repeated calls per frame
# (e.g. the gold pulse on every cell in the joker row) hit the cache.
_ALPHA_RECT_CACHE: dict[tuple, pygame.Surface] = {}


def cached_alpha_rect(size: tuple[int, int], color_rgb: tuple[int, int, int],
                      alpha: int, border_radius: int = 0) -> pygame.Surface:
    """Return a cached SRCALPHA rect surface. Cells, panels and glows
    that re-blit the same parameters reuse the same surface."""
    key = (size, color_rgb, int(alpha), border_radius)
    surf = _ALPHA_RECT_CACHE.get(key)
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (*color_rgb, alpha), surf.get_rect(),
                         border_radius=border_radius)
        _ALPHA_RECT_CACHE[key] = surf
    return surf


# --- Static overlays --------------------------------------------------------
#
# Lazy module-level singletons so allocation happens once, not per frame.
# `get_vignette` builds a soft radial darkening; `get_cell_shadow` adds the
# subtle top-highlight / bottom-shadow that makes flat cells read as 3D.

_VIGNETTE: pygame.Surface | None = None
_CELL_SHADOW_CACHE: dict[int, pygame.Surface] = {}


def get_vignette(w: int, h: int) -> pygame.Surface:
    """A 720×1280 SRCALPHA surface darkening the corners. Built once and
    reused; one blit per frame. Approximated with a handful of concentric
    rounded rects to avoid expensive per-pixel work.

    Returns None on any pygame error (e.g. an SRCALPHA / border_radius
    incompatibility on a particular runtime). Callers must tolerate
    `None` from this function."""
    global _VIGNETTE
    if _VIGNETTE is not None and _VIGNETTE.get_size() == (w, h):
        return _VIGNETTE
    try:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        layers = 8
        for i in range(layers):
            inset = int((i / layers) * min(w, h) * 0.35)
            rect = pygame.Rect(inset, inset, w - 2 * inset, h - 2 * inset)
            pygame.draw.rect(surf, (0, 0, 0, 10), rect, border_radius=24)
        _VIGNETTE = surf
    except Exception:
        # If the runtime (e.g. pygame-ce on pygbag/WASM) chokes on either
        # SRCALPHA or border_radius, return None so the renderer skips the
        # blit instead of aborting the whole frame.
        _VIGNETTE = None
    return _VIGNETTE


def get_cell_shadow(cell_size: int) -> pygame.Surface | None:
    """Cell-sized SRCALPHA overlay: 1-px lighter top edge + 1-px darker
    bottom edge. Cached by cell size since grids resize between levels.
    Returns None on pygame error so callers can skip cleanly."""
    if cell_size in _CELL_SHADOW_CACHE:
        return _CELL_SHADOW_CACHE[cell_size]
    try:
        surf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
        pygame.draw.line(surf, (255, 255, 255, 28), (2, 0), (cell_size - 3, 0), 1)
        pygame.draw.line(surf, (0, 0, 0, 70), (2, cell_size - 1),
                         (cell_size - 3, cell_size - 1), 1)
        _CELL_SHADOW_CACHE[cell_size] = surf
    except Exception:
        _CELL_SHADOW_CACHE[cell_size] = None
    return _CELL_SHADOW_CACHE[cell_size]


def draw_board(surface: pygame.Surface, board: Board, cell_size: int, offset_x: int, offset_y: int):
    """Draw the game board."""
    for r in range(board.size):
        for c in range(board.size):
            x = offset_x + c * cell_size
            y = offset_y + r * cell_size
            cx = x + cell_size / 2
            cy = y + cell_size / 2

            # cell background
            pygame.draw.rect(surface, (28, 28, 48), (x, y, cell_size, cell_size), border_radius=4)

            # mark
            val = board.grid[r][c]
            if val != 0:
                color = COLOR_X if val == PLAYER_X else COLOR_O
                if board.poison_cells and (r, c) in board.poison_cells:
                    # draw poison indicator on poisoned cells
                    s = cell_size // 4
                    sx = int(x + cell_size / 2 - s / 2)
                    sy = int(y + cell_size / 2 - s / 2)
                    pygame.draw.rect(surface, (80, 180, 60), (sx, sy, s, s), border_radius=3)
                # draw X or O
                if val == PLAYER_X:
                    margin = cell_size // 4
                    pygame.draw.line(surface, color,
                                     (x + margin, y + margin),
                                     (x + cell_size - margin, y + cell_size - margin),
                                     4)
                    pygame.draw.line(surface, color,
                                     (x + margin, y + cell_size - margin),
                                     (x + cell_size - margin, y + margin),
                                     4)
                else:
                    pygame.draw.circle(surface, color,
                                       (int(cx), int(cy)), cell_size // 3, 4)
            else:
                # empty cell highlight
                hover_rect = (x + 2, y + 2, cell_size - 4, cell_size - 4)
                pygame.draw.rect(surface, (40, 40, 60), hover_rect, border_radius=4)


def draw_lines(surface: pygame.Surface, lines: list[tuple[int, list[tuple[int, int]]]], cell_size: int, offset_x: int, offset_y: int, color: tuple[int, int, int] | None = None):
    """Draw highlighting lines."""
    if not lines:
        return
    for val, cells in lines:
        c = color if color else (ACCENT_GOLD if val == PLAYER_X else ACCENT_RED)
        first_r, first_c = cells[0]
        px = offset_x + first_c * cell_size + cell_size / 2
        py = offset_y + first_r * cell_size + cell_size / 2
        last_r, last_c = cells[-1]
        ex = offset_x + last_c * cell_size + cell_size / 2
        ey = offset_y + last_r * cell_size + cell_size / 2
        pygame.draw.line(surface, c, (px, py), (ex, ey), 6)


def _wrap_lines(text: str, font, max_width: int) -> list[str]:
    """Wrap text into lines that fit max_width using font.size for measurement."""
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    space_w = font.size(" ")[0]
    lines: list[str] = []
    current: list[str] = []
    current_w = 0
    for word in words:
        word_w = font.size(word)[0]
        if not current:
            current = [word]
            current_w = word_w
            continue
        # account for space + word
        if current_w + space_w + word_w > max_width:
            lines.append(" ".join(current))
            current = [word]
            current_w = word_w
        else:
            current.append(word)
            current_w += space_w + word_w
    if current:
        lines.append(" ".join(current))
    return lines


def draw_card(surface: pygame.Surface, card_name: str, card_cost: int, card_desc: str,
              x: int, y: int, w: int, h: int,
              is_highlighted: bool = False, can_afford: bool = True):
    """Draw a single card with wrapped name and description."""
    from config.constants import CARD_BG, CARD_BORDER, CARD_HIGHLIGHT

    bg = CARD_HIGHLIGHT if is_highlighted else CARD_BG
    if is_highlighted:
        border = ACCENT_GOLD
    elif can_afford:
        border = ACCENT_GREEN
    else:
        border = CARD_BORDER

    pygame.draw.rect(surface, bg, (x, y, w, h), border_radius=8)
    pygame.draw.rect(surface, border, (x, y, w, h), 2, border_radius=8)

    # cost circle (top-left)
    cost_cx, cost_cy, cost_r = x + 24, y + 24, 18
    pygame.draw.circle(surface, ACCENT_GOLD, (cost_cx, cost_cy), cost_r)
    cost_font = pygame.font.SysFont("consolas", 28)
    cost_surf = cost_font.render(str(card_cost), True, (0, 0, 0))
    surface.blit(cost_surf,
                 (cost_cx - cost_surf.get_width() // 2,
                  cost_cy - cost_surf.get_height() // 2))

    pad = 10
    # name — wraps to up to 2 lines, first line clears the cost circle
    name_font = pygame.font.SysFont("sans-serif", 22, bold=True)
    name_line_h = name_font.get_linesize()
    first_line_x = cost_cx + cost_r + 6  # right of the cost circle
    name_first_width = (x + w - pad) - first_line_x
    name_full_width = w - 2 * pad

    name_lines: list[str] = []
    if card_name:
        words = card_name.split()
        first: list[str] = []
        first_w = 0
        space_w = name_font.size(" ")[0]
        idx = 0
        for i, word in enumerate(words):
            ww = name_font.size(word)[0]
            extra = (space_w if first else 0) + ww
            if first and first_w + extra > name_first_width:
                idx = i
                break
            first.append(word)
            first_w += extra
            idx = i + 1
        if first:
            name_lines.append(" ".join(first))
        if idx < len(words):
            rest_text = " ".join(words[idx:])
            wrapped_rest = _wrap_lines(rest_text, name_font, name_full_width)
            for line in wrapped_rest[:1]:
                name_lines.append(line)

    if name_lines:
        surface.blit(name_font.render(name_lines[0], True, TEXT_COLOR),
                     (first_line_x, cost_cy - name_line_h // 2))
    name_bottom = cost_cy + cost_r
    if len(name_lines) > 1:
        surface.blit(name_font.render(name_lines[1], True, TEXT_COLOR),
                     (x + pad, name_bottom + 2))
        name_bottom += 2 + name_line_h

    # description, fills remaining vertical space
    desc_font = pygame.font.SysFont("sans-serif", 16)
    desc_line_h = desc_font.get_linesize()
    desc_y = name_bottom + 8
    available_h = (y + h - pad) - desc_y
    max_lines = max(1, available_h // desc_line_h)
    desc_lines = _wrap_lines(card_desc or "", desc_font, name_full_width)
    for i, line in enumerate(desc_lines[:max_lines]):
        surface.blit(desc_font.render(line, True, TEXT_SUB),
                     (x + pad, desc_y + i * desc_line_h))


def draw_score(surface: pygame.Surface, score: int, target: int, x: int, y: int):
    score_surf = pygame.font.SysFont("consolas", 60).render(str(score), True, ACCENT_GOLD)
    surface.blit(score_surf, (x, y))
    tgt_surf = pygame.font.SysFont("sans-serif", 14).render(
        f"Level Goal: {target} ink", True, TEXT_SUB,
    )
    surface.blit(tgt_surf, (x, y + score_surf.get_height() + 4))


def draw_tokens(surface: pygame.Surface, tokens: int, x: int, y: int):
    txt = pygame.font.SysFont("consolas", 32).render(f"Tokens: {tokens}", True, ACCENT_GOLD)
    surface.blit(txt, (x, y))


def draw_level_info(surface: pygame.Surface, level: int, grid_size: int, boss_name: str, x: int, y: int):
    lvl_surf = pygame.font.SysFont("consolas", 18).render(f"Level {level} — {grid_size}x{grid_size}", True, TEXT_SUB)
    surface.blit(lvl_surf, (x, y))
    if boss_name:
        bsurf = pygame.font.SysFont("sans-serif", 14).render(f"Boss: {boss_name}", True, ACCENT_RED)
        surface.blit(bsurf, (x, y + lvl_surf.get_height() + 4))


def draw_start_card(surface, card_name, card_cost, card_desc, x, y):
    font = pygame.font.SysFont("consolas", 24)
    cost_surf = pygame.font.SysFont("consolas", 14).render(str(card_cost), True, ACCENT_GOLD)
    surface.blit(cost_surf, (x + 20, y + 20))


def draw_centered_text(surface, text, font, color, y):
    rect = font.render(text, True, color).get_rect()
    rect.centerx = surface.get_width() // 2
    rect.y = y
    surface.blit(font.render(text, True, color), rect)


def draw_big_centered_text(surface, text, font, color, y):
    rect = font.render(text, True, color).get_rect()
    rect.centerx = surface.get_width() // 2
    rect.y = y
    surface.blit(font.render(text, True, color), rect)


def draw_joker_chip(surface: pygame.Surface, name: str, count: int,
                    x: int, y: int, w: int, h: int,
                    glow: float = 0.0) -> None:
    """Compact card view used in the joker row. Shows the joker name (auto-
    wrapped to 2 lines) and an `xN` stack badge in the top-right when more
    than one copy is owned. `glow` 0..1 brightens the border when the
    joker's trigger just fired."""
    from config.constants import CARD_BG, CARD_BORDER

    pygame.draw.rect(surface, CARD_BG, (x, y, w, h), border_radius=6)
    # Border colour modulates toward bright white when glow > 0.
    border_col = (
        int(ACCENT_GOLD[0] + (255 - ACCENT_GOLD[0]) * glow),
        int(ACCENT_GOLD[1] + (255 - ACCENT_GOLD[1]) * glow),
        int(ACCENT_GOLD[2] + (200 - ACCENT_GOLD[2]) * glow),
    )
    border_w = 2 + int(glow * 2)
    pygame.draw.rect(surface, border_col, (x, y, w, h), border_w, border_radius=6)

    pad = 6
    name_font = pygame.font.SysFont("sans-serif", 14, bold=True)
    lines = _wrap_lines(name or "", name_font, w - 2 * pad)
    for i, line in enumerate(lines[:3]):
        s = name_font.render(line, True, TEXT_COLOR)
        surface.blit(s, (x + pad, y + pad + i * name_font.get_linesize()))

    if count > 1:
        badge_font = pygame.font.SysFont("consolas", 14, bold=True)
        bs = badge_font.render(f"x{count}", True, (0, 0, 0))
        bw, bh = bs.get_width() + 8, bs.get_height() + 2
        bx, by = x + w - bw - 4, y + h - bh - 4
        pygame.draw.rect(surface, ACCENT_GOLD, (bx, by, bw, bh), border_radius=4)
        surface.blit(bs, (bx + 4, by + 1))


def draw_multiline_text(surface, text, font, color, x, y, max_width, max_lines=4):
    """Wrapped text rendering within a max_width box."""
    lines = _wrap_lines(text or "", font, max_width)
    line_h = font.get_linesize()
    for i, line_text in enumerate(lines[:max_lines]):
        ls = font.render(line_text, True, color)
        surface.blit(ls, (x, y + i * line_h))


def draw_centered_multiline_text(surface, text, font, color, y, max_width, max_lines=8):
    """Wrap `text` to fit `max_width` and render each line centred at `y`,
    `y + line_h`, etc. Returns the y-coordinate immediately below the
    last rendered line so the caller can stack additional content."""
    lines = _wrap_lines(text or "", font, max_width)
    line_h = font.get_linesize()
    screen_mid = surface.get_width() // 2
    for i, line_text in enumerate(lines[:max_lines]):
        ls = font.render(line_text, True, color)
        surface.blit(ls, (screen_mid - ls.get_width() // 2, y + i * line_h))
    return y + min(len(lines), max_lines) * line_h