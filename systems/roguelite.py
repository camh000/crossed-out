from game.board import Board, PLAYER_X
from game.player import RunState
from systems.cardsystem import CardSystem
from config.bosses import BOSS_LIST, BOSS_MAP
from config.constants import SCREEN_W, SCREEN_H


class RogueliteEngine:
    def __init__(self):
        self.state = RunState()
        self.card_system = CardSystem()
        self.boss_choices = BOSS_LIST
        self.current_boss_mechanic = None
        self.game_result = None  # "win", "lose", "draw"

    def start_new_run(self):
        """Start a fresh run."""
        self.state = RunState()
        self.state.player.deck = self.card_system.generate_deck()
        self.state.player.tokens = 5
        self.state.current_target = self.state.get_target()
        self.current_boss_mechanic = None
        self.game_result = None

    def get_next_boss(self):
        """Get the next unchosen boss."""
        available = [b for b in self.boss_choices if b.mechanic != self.current_boss_mechanic]
        import random
        boss = random.choice(available)
        self.current_boss_mechanic = boss.mechanic
        return boss

    def apply_boss_effect(self, board, player):
        """Apply boss-specific effect to the board/player."""
        if self.current_boss_mechanic == "blind":
            player.upgrades["blind_mode"] = True
            return "blind"
        elif self.current_boss_mechanic == "weighted":
            board.weights = board.get_weights()
            return "weighted"
        elif self.current_boss_mechanic == "poison":
            import random
            empty = board.get_empty_cells()
            poison = random.sample(empty, min(3, len(empty)))
            board.poison_cells = poison
            return "poison"
        elif self.current_boss_mechanic == "swap":
            return "swap"
        elif self.current_boss_mechanic == "mirror":
            player.upgrades["mirror_mode"] = True
            return "mirror"
        elif self.current_boss_mechanic == "timed":
            player.upgrades["timed_mode"] = True
            return "timed"
        elif self.current_boss_mechanic == "doublecross":
            return "doublecross"
        elif self.current_boss_mechanic == "ghost_wall":
            import random
            empty = board.get_empty_cells()
            if empty:
                wall = random.choice(empty)
                board.wall_cells = [wall]
            return "ghost_wall"
        return "normal"

    def evaluate_game(self, board, player):
        """Evaluate game outcome and update state."""
        winner = board.has_winner()
        if winner == PLAYER_X:
            result = "win"
        elif winner == None:  # draw
            result = "draw"
        else:
            result = "lose"

        score = self.card_system.calculate_score(board, player, self.state.get_multiplier())
        if result == "win":
            score = max(score, 1)  # At least 1 for winning

        player.score += score
        self.state.score_this_level += score

        self.game_result = result
        return result, score