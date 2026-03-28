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

        # Get display bounds and create windows
        if self.single_screen:
            # For single screen, create one large window and split it
            self.window_width, self.window_height = 1200, 600
            self.screen = pygame.display.set_mode((self.window_width, self.window_height))
            pygame.display.set_caption(f"{main_title} | {timer_title}")
            
            # Split into subsurfaces
            self.main_width, self.main_height = self.window_width // 2, self.window_height
            self.timer_width, self.timer_height = self.window_width // 2, self.window_height
            
            self.main_screen = self.screen.subsurface((0, 0, self.main_width, self.main_height))
            self.timer_screen = self.screen.subsurface((self.main_width, 0, self.timer_width, self.timer_height))
            print(f"Single screen split window: {self.window_width}x{self.window_height}")
        else:
            # Create fullscreen windows on each display
            bounds0 = pygame.display.get_desktop_sizes()[0]
            self.main_width, self.main_height = bounds0[0], bounds0[1]
            self.main_screen = pygame.display.set_mode((self.main_width, self.main_height), pygame.FULLSCREEN)
            pygame.display.set_caption(main_title)
            print(f"Main screen fullscreen: {self.main_width}x{self.main_height} on display 0")

            # Create timer window on display 1
            try:
                bounds1 = pygame.display.get_desktop_sizes()[1]
                self.timer_width, self.timer_height = bounds1[0], bounds1[1]
                self.timer_screen = pygame.display.set_mode((self.timer_width, self.timer_height), pygame.FULLSCREEN, display=1)
                pygame.display.set_caption(timer_title)
                print(f"Timer screen fullscreen: {self.timer_width}x{self.timer_height} on display 1")
            except (IndexError, pygame.error) as e:
                print(f"Could not create fullscreen on display 1: {e}. Falling back to split-screen.")
                self.single_screen = True
                self.window_width, self.window_height = 1200, 600
                self.screen = pygame.display.set_mode((self.window_width, self.window_height))
                self.main_width, self.main_height = self.window_width // 2, self.window_height
                self.timer_width, self.timer_height = self.window_width // 2, self.window_height
                self.main_screen = self.screen.subsurface((0, 0, self.main_width, self.main_height))
                self.timer_screen = self.screen.subsurface((self.main_width, 0, self.timer_width, self.timer_height))

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
            title_rect = title.get_rect(center=(self.main_width//2, int(self.main_height*0.1)))
            self.main_screen.blit(title, title_rect)

            # Player selection
            player_title = self.font_medium.render("Number of Players:", True, self.WHITE)
            player_title_rect = player_title.get_rect(center=(self.main_width//2, int(self.main_height*0.2)))
            self.main_screen.blit(player_title, player_title_rect)

            player_buttons = []
            button_width, button_height = int(self.main_width*0.08), int(self.main_height*0.1)
            button_spacing = int(self.main_width*0.12)
            start_x = self.main_width//2 - (5 * button_spacing)//2
            y = int(self.main_height*0.32)
            
            for i in range(2, 7):  # 2-6 players
                x = start_x + (i-2) * button_spacing
                selected = (i == self.players_selected)
                color = self.BLUE if selected else self.GRAY
                self.draw_button(self.main_screen, str(i), x, y, button_width, button_height, color, self.WHITE, selected)
                player_buttons.append((x, y, button_width, button_height, i))

            # Difficulty selection
            diff_title = self.font_medium.render("Difficulty:", True, self.WHITE)
            diff_title_rect = diff_title.get_rect(center=(self.main_width//2, int(self.main_height*0.48)))
            self.main_screen.blit(diff_title, diff_title_rect)

            difficulties = ["Easy", "Medium", "Hard"]
            diff_buttons = []
            diff_button_width, diff_button_height = int(self.main_width*0.12), int(self.main_height*0.1)
            diff_button_spacing = int(self.main_width*0.16)
            diff_start_x = self.main_width//2 - (3 * diff_button_spacing)//2
            diff_y = int(self.main_height*0.6)
            
            for i, diff in enumerate(difficulties):
                x = diff_start_x + i * diff_button_spacing
                selected = (i + 1 == self.difficulty_selected)
                color = self.GREEN if selected else self.GRAY
                self.draw_button(self.main_screen, diff, x, diff_y, diff_button_width, diff_button_height, color, self.WHITE, selected)
                diff_buttons.append((x, diff_y, diff_button_width, diff_button_height, i+1))

            # Start button
            start_button_width, start_button_height = int(self.main_width*0.3), int(self.main_height*0.12)
            start_x = (self.main_width - start_button_width) // 2
            start_y = int(self.main_height*0.78)
            start_color = self.RED if self.selected_button == "start" else self.GRAY
            self.draw_button(self.main_screen, "START GAME", start_x, start_y, start_button_width, start_button_height, start_color, self.WHITE, self.selected_button == "start")

            return player_buttons, diff_buttons, (start_x, start_y, start_button_width, start_button_height)
        else:
            # Game running screen
            status = self.font_large.render("Game Running...", True, self.GREEN)
            status_rect = status.get_rect(center=(self.main_width//2, self.main_height//2))
            self.main_screen.blit(status, status_rect)

            # Stop button
            stop_button_width, stop_button_height = int(self.main_width*0.3), int(self.main_height*0.12)
            stop_x = (self.main_width - stop_button_width) // 2
            stop_y = int(self.main_height*0.7)
            stop_color = self.RED if self.selected_button == "stop" else self.GRAY
            self.draw_button(self.main_screen, "STOP GAME", stop_x, stop_y, stop_button_width, stop_button_height, stop_color, self.WHITE, self.selected_button == "stop")

            return [], [], (stop_x, stop_y, stop_button_width, stop_button_height)

    def draw_timer_screen(self, settings=None):
        if self.timer_screen is None:
            return

        self.timer_screen.fill(self.BLACK)

        # Timer display
        if settings and settings.time_left > 0:
            minutes = int(settings.time_left // 60)
            seconds = int(settings.time_left % 60)
            timer_text = f"{minutes:02d}:{seconds:02d}"
        elif self.timer_running:
            elapsed = time.time() - self.timer_start
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            timer_text = f"{minutes:02d}:{seconds:02d}"
        else:
            timer_text = "00:00"

        # Use dynamic font size based on screen dimensions
        timer_font_size = int(self.timer_height * 0.3)
        timer_font = pygame.font.Font(None, timer_font_size)
        timer_surf = timer_font.render(timer_text, True, self.YELLOW)
        timer_rect = timer_surf.get_rect(center=(self.timer_width//2, self.timer_height//3))
        self.timer_screen.blit(timer_surf, timer_rect)

        # Status
        if settings and settings.status_text:
            status_text = settings.status_text
            status_color = self.GREEN if settings.time_left > 0 or status_text != "LOBBY" else self.BLUE
        elif self.game_started:
            status_text = "RUNNING" if self.timer_running else "PAUSED"
            status_color = self.GREEN if self.timer_running else self.RED
        else:
            status_text = "WAITING"
            status_color = self.BLUE

        status_font_size = int(self.timer_height * 0.15)
        status_font = pygame.font.Font(None, status_font_size)
        status_surf = status_font.render(status_text, True, status_color)
        status_rect = status_surf.get_rect(center=(self.timer_width//2, self.timer_height//2))
        self.timer_screen.blit(status_surf, status_rect)

        # Players info
        info_font_size = int(self.timer_height * 0.1)
        info_font = pygame.font.Font(None, info_font_size)
        players_surf = info_font.render(f"Players: {self.players_selected}", True, self.WHITE)
        self.timer_screen.blit(players_surf, (int(self.timer_width*0.05), int(self.timer_height*0.75)))

        diff_names = ["Easy", "Medium", "Hard"]
        diff_surf = info_font.render(f"Difficulty: {diff_names[self.difficulty_selected-1]}", True, self.WHITE)
        self.timer_screen.blit(diff_surf, (int(self.timer_width*0.35), int(self.timer_height*0.75)))

    def handle_touch(self, pos, player_buttons, diff_buttons, start_stop_button):
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
        if start_stop_button:
            bx, by, bw, bh = start_stop_button
            if bx <= x <= bx + bw and by <= y <= by + bh:
                if not self.game_started:
                    self.game_started = True
                    self.start_timer()
                    self.selected_button = "start"
                    self.button_select_time = time.time()
                else:
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

    def update(self, settings=None):
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Check which window was clicked
                    pos = event.pos
                    if self.single_screen:
                        # Translate click to main screen if it was on the left half
                        if 0 <= pos[0] <= self.main_width:
                            player_buttons, diff_buttons, start_stop_button = self.draw_main_screen()
                            self.handle_touch(pos, player_buttons, diff_buttons, start_stop_button)
                    else:
                        if self.main_screen.get_rect().collidepoint(pos):
                            player_buttons, diff_buttons, start_stop_button = self.draw_main_screen()
                            self.handle_touch(pos, player_buttons, diff_buttons, start_stop_button)

        # Draw screens
        player_buttons, diff_buttons, start_stop_button = self.draw_main_screen()
        self.draw_timer_screen(settings)

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