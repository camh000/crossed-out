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


def draw_card(surface: pygame.Surface, card_name: str, card_cost: int, card_desc: str,
              x: int, y: int, w: int, h: int,
              is_highlighted: bool = False, can_afford: bool = False):
    """Draw a single card."""
    from config.constants import CARD_BG, CARD_BORDER, CARD_HIGHLIGHT

    bg = CARD_HIGHLIGHT if is_highlighted else CARD_BG
    border = CARD_HIGHLIGHT if is_highlighted else CARD_BORDER
    if can_afford:
        border = ACCENT_GREEN

    pygame.draw.rect(surface, bg, (x, y, w, h), border_radius=8)
    pygame.draw.rect(surface, border, (x, y, w, h), 2, border_radius=8)

    # cost circle
    pygame.draw.circle(surface, ACCENT_GOLD, (x + 20, y + 20), 14)
    cost_surf = pygame.font.SysFont("consolas", CARD_COST_SIZE).render(str(card_cost), True, (0, 0, 0))
    surface.blit(cost_surf, (x + 20 - cost_surf.get_width() // 2, y + 20 - cost_surf.get_height() // 2))

    # name
    name_surf = pygame.font.SysFont("sans-serif", CARD_NAME_SIZE).render(card_name, True, TEXT_COLOR)
    surface.blit(name_surf, (x + 10, y + 45))

    # desc
    lines = _wrap_text(card_desc, w - 20, CARD_DESC_SIZE)
    for i, line in enumerate(lines[:4]):
        desc_surf = pygame.font.SysFont("sans-serif", CARD_DESC_SIZE // 3, bold=True).render(line, True, TEXT_SUB)
        surface.blit(desc_surf, (x + 10, y + 80 + i * 14))


def _wrap_text(text: str, max_w: int, font_size: int) -> list[str]:
    font = pygame.font.SysFont("sans-serif", font_size)
    words = text.split()
    lines = []
    current_line = []
    current_w = 0
    for word in words:
        w = font.size(f"{word} ")[0]
        if current_w + w > max_w:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_w = font.size(f"{word} ")[0]
        else:
            current_line.append(word)
            current_w += w
    if current_line:
        lines.append(" ".join(current_line))
    return lines


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