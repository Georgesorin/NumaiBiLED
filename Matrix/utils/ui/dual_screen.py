import pygame
import sys
import os
import threading
import time

class DualScreenManager:
    def __init__(self, main_title="Game Control", timer_title="Timer Display"):
        pygame.init()

        # Get available displays
        self.num_displays = pygame.display.get_num_displays()
        print(f"Found {self.num_displays} displays")

        if self.num_displays < 2:
            print("Warning: Only 1 display detected. Using single window mode.")
            self.single_screen = True
        else:
            self.single_screen = False

        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.GRAY = (128, 128, 128)
        self.BLUE = (0, 0, 255)
        self.GREEN = (0, 255, 0)
        self.RED = (255, 0, 0)
        self.YELLOW = (255, 255, 0)

        # Main screen (touchscreen for controls)
        self.main_width, self.main_height = 800, 600
        if self.single_screen:
            self.main_screen = pygame.display.set_mode((self.main_width, self.main_height))
            pygame.display.set_caption(main_title)
            self.timer_screen = None
        else:
            # Create main window on display 0
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
            self.main_screen = pygame.display.set_mode((self.main_width, self.main_height))
            pygame.display.set_caption(main_title)

            # Create timer window on display 1
            os.environ['SDL_VIDEO_WINDOW_POS'] = '801,0'  # Position next to main
            self.timer_screen = pygame.display.set_mode((400, 200), display=1)
            pygame.display.set_caption(timer_title)

        # Fonts
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)

        # Game state
        self.players_selected = 2
        self.difficulty_selected = 1
        self.game_started = False
        self.timer_running = False
        self.timer_start = 0
        self.current_time = 0

        # UI state
        self.selected_button = None

    def draw_button(self, screen, text, x, y, width, height, color, text_color, selected=False):
        if selected:
            border_color = self.YELLOW
            border_width = 3
        else:
            border_color = self.WHITE
            border_width = 2

        # Draw border
        pygame.draw.rect(screen, border_color, (x-border_width, y-border_width, width+border_width*2, height+border_width*2))
        # Draw button
        pygame.draw.rect(screen, color, (x, y, width, height))

        # Draw text
        text_surf = self.font_medium.render(text, True, text_color)
        text_rect = text_surf.get_rect(center=(x + width//2, y + height//2))
        screen.blit(text_surf, text_rect)

    def draw_main_screen(self):
        self.main_screen.fill(self.BLACK)

        if not self.game_started:
            # Title
            title = self.font_large.render("Game Setup", True, self.WHITE)
            title_rect = title.get_rect(center=(self.main_width//2, 50))
            self.main_screen.blit(title, title_rect)

            # Player selection
            player_title = self.font_medium.render("Number of Players:", True, self.WHITE)
            self.main_screen.blit(player_title, (50, 120))

            player_buttons = []
            for i in range(2, 7):  # 2-6 players
                x = 50 + (i-2) * 100
                y = 160
                selected = (i == self.players_selected)
                color = self.BLUE if selected else self.GRAY
                self.draw_button(self.main_screen, str(i), x, y, 80, 60, color, self.WHITE, selected)
                player_buttons.append((x, y, 80, 60, i))

            # Difficulty selection
            diff_title = self.font_medium.render("Difficulty:", True, self.WHITE)
            self.main_screen.blit(diff_title, (50, 250))

            difficulties = ["Easy", "Medium", "Hard"]
            diff_buttons = []
            for i, diff in enumerate(difficulties):
                x = 50 + i * 150
                y = 290
                selected = (i + 1 == self.difficulty_selected)
                color = self.GREEN if selected else self.GRAY
                self.draw_button(self.main_screen, diff, x, y, 120, 60, color, self.WHITE, selected)
                diff_buttons.append((x, y, 120, 60, i+1))

            # Start button
            start_color = self.RED if self.selected_button == "start" else self.GRAY
            self.draw_button(self.main_screen, "START GAME", 250, 400, 300, 80, start_color, self.WHITE, self.selected_button == "start")

            return player_buttons, diff_buttons
        else:
            # Game running screen
            status = self.font_large.render("Game Running...", True, self.GREEN)
            status_rect = status.get_rect(center=(self.main_width//2, self.main_height//2))
            self.main_screen.blit(status, status_rect)

            # Stop button
            stop_color = self.RED if self.selected_button == "stop" else self.GRAY
            self.draw_button(self.main_screen, "STOP GAME", 250, 450, 300, 80, stop_color, self.WHITE, self.selected_button == "stop")

            return [], []

    def draw_timer_screen(self):
        if self.timer_screen is None:
            return

        self.timer_screen.fill(self.BLACK)

        # Timer display
        if self.timer_running:
            elapsed = time.time() - self.timer_start
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            timer_text = "08d"
        else:
            timer_text = "00:00"

        timer_surf = self.font_large.render(timer_text, True, self.YELLOW)
        timer_rect = timer_surf.get_rect(center=(200, 60))
        self.timer_screen.blit(timer_surf, timer_rect)

        # Status
        if self.game_started:
            status_text = "RUNNING" if self.timer_running else "PAUSED"
            status_color = self.GREEN if self.timer_running else self.RED
        else:
            status_text = "WAITING"
            status_color = self.BLUE

        status_surf = self.font_medium.render(status_text, True, status_color)
        status_rect = status_surf.get_rect(center=(200, 120))
        self.timer_screen.blit(status_surf, status_rect)

        # Players info
        players_surf = self.font_small.render(f"Players: {self.players_selected}", True, self.WHITE)
        self.timer_screen.blit(players_surf, (20, 160))

        diff_names = ["Easy", "Medium", "Hard"]
        diff_surf = self.font_small.render(f"Difficulty: {diff_names[self.difficulty_selected-1]}", True, self.WHITE)
        self.timer_screen.blit(diff_surf, (200, 160))

    def handle_touch(self, pos, player_buttons, diff_buttons):
        x, y = pos

        # Check player buttons
        for bx, by, bw, bh, players in player_buttons:
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.players_selected = players
                return

        # Check difficulty buttons
        for bx, by, bw, bh, diff in diff_buttons:
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.difficulty_selected = diff
                return

        # Check start/stop button
        if not self.game_started:
            if 250 <= x <= 550 and 400 <= y <= 480:
                self.game_started = True
                self.start_timer()
                self.selected_button = "start"
                self.button_select_time = time.time()
        else:
            if 250 <= x <= 550 and 450 <= y <= 530:
                self.game_started = False
                self.stop_timer()
                self.selected_button = "stop"
                self.button_select_time = time.time()

    def start_timer(self):
        self.timer_running = True
        self.timer_start = time.time()

    def stop_timer(self):
        self.timer_running = False

    def get_game_config(self):
        return {
            'players': self.players_selected,
            'difficulty': self.difficulty_selected
        }

    def is_game_started(self):
        return self.game_started

    def update(self):
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Check which window was clicked
                    if self.main_screen.get_rect().collidepoint(event.pos):
                        player_buttons, diff_buttons = self.draw_main_screen()
                        self.handle_touch(event.pos, player_buttons, diff_buttons)

        # Draw screens
        player_buttons, diff_buttons = self.draw_main_screen()
        self.draw_timer_screen()

        # Clear button selection after a short time
        if self.selected_button and time.time() - getattr(self, 'button_select_time', 0) > 0.2:
            self.selected_button = None

        pygame.display.flip()
        return True

    def quit(self):
        pygame.quit()

# Example usage function
def run_dual_screen_setup():
    """Example of how to use the dual screen manager"""
    manager = DualScreenManager()

    running = True
    while running:
        running = manager.update()

        if manager.is_game_started():
            config = manager.get_game_config()
            print(f"Game started with config: {config}")
            # Here you would transition to your actual game

        pygame.time.wait(50)  # ~20 FPS

    manager.quit()

if __name__ == "__main__":
    run_dual_screen_setup()