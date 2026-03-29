import time
import threading
import sys
import os

from ..data.game_engine import GameEngine
from ..data.network import NetworkManager, load_config

class GameMaster:
    """
    Instantiate with `initial_state_factory`, a callable that returns the
    first GameState, and a transitions dictionary.
    """

    def __init__(self, initial_state_factory, settings, transitions):
        self.engine = GameEngine()
        self.running = True
        self.button_states = self.engine.button_states
        self._initial_state_factory = initial_state_factory
        self.settings = settings
        self.transitions = transitions
        
        # Set initial state
        initial_state = initial_state_factory()
        self.engine.change_state(initial_state)

    def tick(self, dt: float):
        state = self.engine.state
        if state is not None:
            # Adopt Matrix pattern: update returns (next_state_name, kwargs)
            next_info = state.update(self.engine, dt)
            if next_info is not None:
                state_name, kwargs = next_info
                if state_name in self.transitions:
                    new_state_factory = self.transitions[state_name]
                    self.engine.change_state(new_state_factory(self.settings, **kwargs))
        
        self.engine.snapshot_input()

    def render(self):
        return self.engine.render()

    def restart(self):
        self.engine.entities.clear()
        self.engine.change_state(self._initial_state_factory())


def game_thread_func(game, tick_interval=0.016):
    last = time.time()
    while game.running:
        now = time.time()
        dt = now - last
        last = now
        game.tick(dt)
        time.sleep(tick_interval)


def run_game(game_master, config=None, title="Evil Eye Game"):
    """Standard main-loop: start networking, game thread, and CLI."""
    # Note: discovery logic removed from master to keep it clean, 
    # as seen in Matrix project (usually handled in entry point or network manager).
    # But EvilEye.game_engine had it in run_game. I'll move it to PatternMemory.py if needed.
    
    net = NetworkManager(game_master, config=config)
    net.start_bg()

    gt = threading.Thread(
        target=game_thread_func, args=(game_master,), daemon=True
    )
    gt.start()

    print(f"{title}")
    print("Commands: 'start', 'restart', 'quit'")

    try:
        while game_master.running:
            cmd = input("> ").strip().lower()
            if cmd in ("quit", "exit"):
                game_master.running = False
                break
            elif cmd.startswith("start"):
                game_master.restart()
                print("Game started.")
            elif cmd == "restart":
                game_master.restart()
                print("Restarted.")
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        game_master.running = False

    net.running = False
    print("Exiting...")
