import sys
import os
import threading

# Add the current directory to sys.path to allow imports from game_engine and utils
sys.path.insert(0, os.path.dirname(__file__))

from utils.data.network import load_config, run_discovery_flow, NetworkManager
from utils.master.master import GameMaster, game_thread_func
from utils.scaling.game_settings import PatternMemorySettings
from utils.states import SetupState, CountdownState, PlayState, GameOverState
from utils.ui.cli import prompt_settings, prompt_render

# Align with Matrix project structure: transitions dictionary
transitions = {
    "setup": lambda settings, **kwargs: SetupState(settings, **kwargs),
    "countdown": lambda settings, **kwargs: CountdownState(settings, **kwargs),
    "play": lambda settings, **kwargs: PlayState(settings, **kwargs),
    "end": lambda settings, **kwargs: GameOverState(settings, **kwargs),
}

def main():
    # Load config relative to this file
    cfg_path = os.path.join(os.path.dirname(__file__), "eye_ctrl_config.json")
    cfg = load_config(cfg_path)

    # Manual settings prompt (Phase 4)
    settings = prompt_settings()

    # Initial discovery
    discovered_ip = run_discovery_flow()
    if discovered_ip:
        cfg["device_ip"] = discovered_ip
        print(f"Using discovered device at {discovered_ip}")

    # Instantiate GameMaster with the initial SetupState and transitions
    def make_start():
        return SetupState(settings)

    gm = GameMaster(make_start, settings, transitions)
    
    # Start networking
    net = NetworkManager(gm, config=cfg)
    net.start_bg()

    # Start game thread
    gt = threading.Thread(
        target=game_thread_func, args=(gm,), daemon=True
    )
    gt.start()

    print("Pattern Memory Game (Interactive)")
    print("Commands: 'restart', 'setup', 'quit'")

    try:
        while gm.running:
            prompt_render(gm)
    except KeyboardInterrupt:
        gm.running = False

    net.running = False
    print("Exiting...")

if __name__ == "__main__":
    main()
