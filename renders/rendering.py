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
    tgt_surf = pygame.font.SysFont("sans-serif", 14).render(f"Target: {target}", True, TEXT_SUB)
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


def draw_multiline_text(surface, text, font, color, x, y, max_width, max_lines=4):
    """Wrapped text rendering within a max_width box."""
    lines = _wrap_lines(text or "", font, max_width)
    line_h = font.get_linesize()
    for i, line_text in enumerate(lines[:max_lines]):
        ls = font.render(line_text, True, color)
        surface.blit(ls, (x, y + i * line_h))