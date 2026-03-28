from ._abs_state import GameState
from ..ui.colors import *

class SBReviewState(GameState):
    def __init__(self, settings, spawn_rules, players, target_drawing, **kwargs):
        self.settings, self.players, self.target_drawing = settings, players, target_drawing
        self.timer, self.winner, self.is_tie, self.tied_players = 0.0, None, False, []

    def enter(self, engine):
        for p in self.players:
            p.score = sum(1 for y in range(6) for x in range(6) if p.board[y][x] == self.target_drawing[y][x])
        
        sorted_p = sorted(self.players, key=lambda p: (p.score, -(p.completion_time if p.completion_time else 9999)), reverse=True)
        best = sorted_p[0]
        if best.score == 36 and best.completion_time is not None:
            self.winner = best
        else:
            tied = [p for p in self.players if p.score == best.score]
            if len(tied) > 1: self.is_tie, self.tied_players = True, tied
            else: self.winner = best

    def update(self, engine, dt: float):
        self.timer += dt
        engine.clear()
        show_target, flash_on = (int(self.timer) % 4 >= 2), (int(self.timer * 2) % 2 == 0)
        flash_y = {self.winner} if (not self.is_tie and flash_on) else set()
        flash_r = set(self.tied_players) if (self.is_tie and flash_on) else set()

        for p in self.players:
            if p in flash_y:
                # Draw score instead of board content (flickering winner)
                score_color = YELLOW
                score_text = str(p.score)
                engine.draw_rect((p.base_x, p.base_y), (8, 8), BLACK)
                text_width = len(score_text) * 4 - 1
                center_x = p.base_x + 1 + (6 - text_width) // 2
                center_y = p.base_y + 3
                # Draw larger black background around score
                engine.draw_rect((center_x - 2, center_y - 2), (text_width + 4, 9), BLACK)
                engine.draw_text_small(score_text, center_x, center_y, score_color)
            elif p in flash_r:
                # Draw score instead of board content (flickering ties)
                score_color = WHITE
                score_text = str(p.score)
                engine.draw_rect((p.base_x, p.base_y), (8, 8), BLACK)
                text_width = len(score_text) * 4 - 1
                center_x = p.base_x + 1 + (6 - text_width) // 2
                center_y = p.base_y + 3
                # Draw larger black background around score
                engine.draw_rect((center_x - 2, center_y - 2), (text_width + 4, 9), BLACK)
                engine.draw_text_small(score_text, center_x, center_y, score_color)
            else:
                engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, WHITE)
                for y in range(6):
                    for x in range(6):
                        c = self.target_drawing[y][x] if show_target else p.board[y][x]
                        engine.set_pixel(p.base_x + 1 + x, p.base_y + 1 + y, *c)

                # Display player score inside the player box, centered. Winner gets yellow text.
                score_color = YELLOW if (self.winner == p and not self.is_tie) else WHITE
                score_text = str(p.score)
                text_width = len(score_text) * 4 - 1
                center_x = p.base_x + 1 + (6 - text_width) // 2
                center_y = p.base_y + 2
                # Draw larger black background for score text to cover top border
                engine.draw_rect((center_x - 2, center_y - 3), (text_width + 4, 9), BLACK)
                engine.draw_text_small(score_text, center_x, center_y, score_color)

        if self.timer > 5.0 and engine.any_pressed():
            return ("show", {"tied_players": self.tied_players}) if self.is_tie else ("init", {})
        if self.timer > 15.0:
            return ("show", {"tied_players": self.tied_players}) if self.is_tie else ("init", {})

    def exit(self, engine): pass
