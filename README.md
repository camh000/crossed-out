# Crossed Out

Balatro-inspired roguelite Tic-Tac-Toe. Complete board lines to meet score targets across progressively larger grids, collect cards with unique mechanics, and fight themed bosses.

## Features

- 3x3 → 5x5 → 7x7 board progression
- Card system with 20+ unique abilities (Double Strike, Ghost Board, Weighted Grid, etc.)
- Boss mechanics: Blind, Mirror, Timer, Poison, Swap, and more
- Meta-progression: unlock new cards by winning runs
- Save / load system for long-term progress
- Full test suite (118 tests, 100% passing)

## Requirements

- Python 3.12+
- Pygame 2.0+

## Installation

```powershell
pip install pygame
```

## Run

```powershell
cd crossed-out
python main.py
```

On RDP/headless systems, validation uses `SDL_VIDEODRIVER=dummy`.

## Test

```powershell
pip install -r requirements-dev.txt
cd crossed-out
python -m pytest tests/
```

## Web build (iPhone / browser)

The game compiles to WebAssembly via [pygbag](https://pygame-web.github.io/)
and runs in any modern browser, including Safari on iOS. Touch maps to
mouse, so no input changes are needed.

```powershell
pip install -r requirements-dev.txt
python -m pygbag --build main.py        # produces build/web/
python -m pygbag main.py                # local dev server on :8000
```

### Deploy to Vercel

`vercel.json` is preconfigured for Vercel's static build. Connect the
repo, accept the defaults, and Vercel runs `pygbag --build` and serves
`build/web/`. The COOP/COEP headers required by WebAssembly threading
are set in `vercel.json`.

## Architecture

```
crossed-out/
  main.py            – Game engine loop, rendering, input
  config/
    constants.py     – Colors, dimensions, targets
    cards.py         – Card definitions (20+ cards)
    bosses.py        – Boss definitions (8 bosses)
  game/
    board.py         – Board state, line detection, win checking
    player.py        – Player state, RunState, deck management
    opponent.py      – Opponent AI
  systems/
    cardsystem.py    – Card application and scoring
    roguelite.py     – Progression, boss selection, meta-game flow
    shop.py          – Shop/merchant mechanics
  save/
    savesetup.py     – JSON save/load progression
  renders/
    rendering.py     – All drawing primitives, cards, boards, UI
  tests/             – Pytest suite (118 tests)
```
