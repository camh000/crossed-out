# colors
# Portrait 9:16 — matches the dominant mobile aspect ratio so the game
# fills an iPhone in portrait orientation without letterboxing.
_SCREEN_W, _SCREEN_H = 720, 1280
BG_COLOR = (20, 20, 35)
GRID_LINE_COLOR = (30, 30, 50)
BG_ACCENT = (25, 25, 45)

# X / O colors
COLOR_X = (100, 180, 255)
COLOR_O = (255, 100, 100)
COLOR_PENDING = (180, 180, 200)

# text
TEXT_COLOR = (230, 230, 240)
TEXT_SUB = (160, 160, 180)

# accent / highlight
ACCENT_GOLD = (240, 192, 64)
ACCENT_GREEN = (80, 220, 120)
ACCENT_RED = (220, 70, 70)

# card — sized for the 720x1280 portrait canvas so they have real presence
# on a phone instead of being squeezed into a small strip.
CARD_W, CARD_H = 165, 360
CARD_BG = (35, 35, 60)
CARD_BORDER = (70, 70, 120)
CARD_HIGHLIGHT = (100, 100, 180)
CARD_GLYPH_SIZE = 60
CARD_COST_SIZE = 36
CARD_NAME_SIZE = 22
CARD_DESC_SIZE = 16

# scores
SCORE_TARGET_BASE = 6
SCORE_MULT_3 = 1
SCORE_MULT_5 = 2
SCORE_MULT_7 = 3

# shop
SHOP_CARD_COUNT = 4
REROLL_COST = 2

# timing
TIMED_BOSS_DURATION = 5  # seconds per move
GAME_DELAY_AFTER = 1200  # ms pause after game end
# Delay between the player's X landing and the AI's O appearing. Gives
# the placement animation room to play out so the player feels they
# acted before the opponent responds.
AI_MOVE_DELAY_MS = 280

# font
FONT_MAIN = None
FONT_SMALL = None
FONT_BIG = None

# grid rendering
GRID_PX = 90  # approximate cell pixel size for 3x3; scales with grid
GRID_PADDING = 60
GRID_BORDER = 3

# meta
SAVE_PATH = "crossed_out_save.json"

# layout orientation detector — runtime overrides below
SCREEN_W, SCREEN_H = 720, 1280
IS_LANDSCAPE = False  # set at import time if possible, or in GameEngine.__init__


def _detect_layout(w, h):
    """Compute SCREEN_W/H and IS_LANDSCAPE from window dimensions."""
    global IS_LANDSCAPE, SCREEN_W, SCREEN_H
    IS_LANDSCAPE = (w > h)
    if IS_LANDSCAPE and w > h:
        SCREEN_W, SCREEN_H = w, h
    elif not IS_LANDSCAPE and h > w:
        SCREEN_W, SCREEN_H = w, h