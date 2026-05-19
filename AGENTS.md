# AGENTS.md — Crossed Out

## Environment
- Windows PowerShell. Use `;` for command chaining (not `&&`).
- Python 3.13. Pygame 2.0+ required for runtime; excluded for tests via conftest.

## Commands
```powershell
python -m pytest tests/            # 118 tests, all passing
SDL_VIDEODRIVER=dummy python main.py  # headless validation (RDP-compatible)
```

## Test Gotcha: State Machine Access
- `pl = engine.engine.state` — RunState, not Player. Player is `pl.player`.
- Call mutations: `pl.next_level()`, not `pl()`.
- Always set `pl.tokens = 0` in tests that invoke `next_level` chains.
- Test evaluation: `engine.engine.card_system.calculate_score(board, pl.player, pl.get_multiplier())`.
- conftest.py fully stubs pygame (`sys.modules['pygame']`). Never remove or bypass it.

## Architecture Notes
- `main.py:22` — `GameEngine` is the top-level class. Entry point calls `GameEngine().run()`.
- `game/player.py:21` — `RunState` holds grid size, score targets, level progression. Not a Player instance.
- `game/player.py:8` — `Player` is `RunState.player`. Dataclass with `tokens`, `score`, `deck`, `hand`, `upgrades`.
- `systems/roguelite.py:8` — `RogueliteEngine` is nested inside `GameEngine` (`self.engine`). Boss logic: `pl.current_boss.mechanic` strings are `"blind"`, `"weighted"`, `"poison"`, `"swap"`, `"mirror"`, `"timed"`, `"doublecross"`, `"ghost_wall"`.
- `config/bosses.py:12` — `BOSS_LIST` and `BOSS_MAP` are the source of truth for boss mechanics.
- Line scoring: use `pl.get_multiplier()` which returns `[1, 2, 3]` for levels 1-3.
- LSP false positives on `RunState` fields are known and benign — ignore them.

## Save System
- Progression data in `crossed_out_save.json` (same directory as main.py).
- Load/unlock via `save.savesetup.load_progression()` and `get_unlocked_cards()`.
- Cards unlock at 3/5/8 wins: Double Strike / O Flipper / Ghost Board.

## File Structure (core)
```
main.py             – GameEngine, rendering loop, input
game/
  board.py          – Board, line detection (rows/cols/diagonals), has_winner()
  player.py         – Player + RunState dataclasses
  opponent.py       – OpponentAI
systems/
  cardsystem.py     – Card application, score calculation
  roguelite.py      – RogueliteEngine, boss selection, game evaluation
  shop.py           – Shop/merchant flow
save/
  savesetup.py      – JSON save/load progression
config/
  cards.py          – ALL_CARDS (20+ defs), pick_random()
  bosses.py         – BOSS_LIST (8 bosses), BOSS_MAP
  constants.py      – Colors, dimensions, targets
renders/
  rendering.py      – All draw primitives
tests/
  conftest.py       – Full pygame stubbing (headless)
  test_board.py     – 3x3/5x5/7x7 line detection
  test_main_engine.py – GameEngine state machine
```
