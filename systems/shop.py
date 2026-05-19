import pygame
from game.player import RunState, Player
from config.constants import SCREEN_W, SCREEN_H, BG_COLOR, TEXT_COLOR, TEXT_SUB, CARD_W, CARD_H, ACCENT_GOLD, ACCENT_GREEN
from config.cards import pick_random
from renders.rendering import draw_score, draw_tokens


class ShopScreen:
    def __init__(self):
        self.running = True
        self.selected_card = -1

    def update(self, events: list, state: RunState) -> tuple[str | None, list[str]]:
        """Return (action, cards_bought)."""
        bought = []
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = e.pos
                # buy cards
                buy_cards = state.player.deck  # cards in shop
                for i, card_name in enumerate(buy_cards):
                    cx = SCREEN_W // 2 - (len(buy_cards) * (CARD_W + 20)) // 2 + i * (CARD_W + 20)
                    cy = SCREEN_H // 2 + 50
                    if cx <= mx <= cx + CARD_W and cy <= my <= cy + CARD_H:
                        if state.player.tokens >= 3:  # simplified cost
                            state.player.tokens -= 3
                            state.player.deck.append(card_name)
                            bought.append(card_name)
                # reroll
                rr_x = SCREEN_W // 2 - 60
                rr_y = SCREEN_H // 2 + CARD_H + 100
                if rr_x <= mx <= rr_x + 120 and rr_y <= my <= rr_y + 40:
                    if state.player.tokens >= 2:
                        state.player.tokens -= 2
                        buy_cards[:] = pick_random(4)
                # continue
                cont_x = SCREEN_W // 2 - 60
                cont_y = SCREEN_H // 2 + CARD_H + 150
                if cont_x <= mx <= cont_x + 120 and cont_y <= my <= cont_y + 40:
                    self.running = False
                    return ("next_level", bought)
        return (None, bought)

    def draw(self, surface: pygame.Surface, state: RunState):
        surface.fill(BG_COLOR)

        title = pygame.font.SysFont("sans-serif", 36).render("SHOP", True, TEXT_COLOR)
        surface.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 100))

        # shop cards
        buy_cards = state.player.deck  # simplified: deck = cards on offer
        if not buy_cards:
            buy_cards[:] = pick_random(4)

        start_x = SCREEN_W // 2 - (len(buy_cards) * (CARD_W + 20)) // 2
        for i, card_name in enumerate(buy_cards):
            cx = start_x + i * (CARD_W + 20)
            cy = SCREEN_H // 2 + 50
            # simplified draw
            from config.cards import get_by_name
            card = get_by_name(card_name)
            if card:
                from renders.rendering import draw_card
                draw_card(surface, card.name, card.cost, card.desc,
                          cx, cy, CARD_W, CARD_H,
                          can_afford=state.player.tokens >= card.cost)

        # reroll
        rr_x = SCREEN_W // 2 - 60
        rr_y = SCREEN_H // 2 + CARD_H + 100
        rr_btn = pygame.draw.rect(surface, (50, 50, 80), (rr_x, rr_y, 120, 40), border_radius=6)
        rr_text = pygame.font.SysFont("sans-serif", 16).render("Reroll (2)", True, TEXT_SUB)
        surface.blit(rr_text, (rr_x + 60 - rr_text.get_width() // 2, rr_y + 15))

        # continue
        continue_btn = pygame.draw.rect(surface, ACCENT_GREEN, (rr_x, rr_y + 50, 120, 40), border_radius=6)
        cont_text = pygame.font.SysFont("sans-serif", 16).render("Continue", True, (0, 0, 0))
        surface.blit(cont_text, (rr_x + 60 - cont_text.get_width() // 2, rr_y + 65))

        # tokens
        draw_tokens(surface, state.player.tokens, SCREEN_W - 200, 120)