from game.player import RunState
from config.bosses import BOSS_LIST


class RogueliteEngine:
    def __init__(self):
        self.state = RunState()
        self.current_boss_mechanic = None
        self.game_result = None  # "win", "lose", "draw"

    def start_new_run(self):
        """Start a fresh run."""
        import random
        self.state = RunState()
        self.state.player.tokens = 5
        self.state.current_target = self.state.get_target()
        # Shuffle a per-run order of boss mechanics so every run sees a
        # varied set instead of always landing on BOSS_LIST[0].
        order = [b.mechanic for b in BOSS_LIST]
        random.shuffle(order)
        self.state.boss_order = order
        self.current_boss_mechanic = None
        self.game_result = None

