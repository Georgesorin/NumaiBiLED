import sys
import os
import threading

# Add the current directory to sys.path to allow imports from game_engine and utils
sys.path.insert(0, os.path.dirname(__file__))

from utils.data.network import load_config, run_discovery_flow, NetworkManager
from utils.master.master import GameMaster, game_thread_func
from utils.states import (
    BossBattleSetupState, BossBattleCountdownState, BossBattleStage1State,
    BossBattleStage2State, BossBattleStage3State, BossBattleGameOverState
)
from utils.ui.cli import prompt_boss_settings, prompt_render

# Transitions specifically for Boss Battle
transitions = {
    "setup": lambda settings, **kwargs: BossBattleSetupState(settings, **kwargs),
    "countdown": lambda settings, **kwargs: BossBattleCountdownState(settings, **kwargs),
    "stage1": lambda settings, **kwargs: BossBattleStage1State(settings, **kwargs),
    "stage2": lambda settings, **kwargs: BossBattleStage2State(settings, **kwargs),
    "stage3": lambda settings, **kwargs: BossBattleStage3State(settings, **kwargs),
    "end": lambda settings, **kwargs: BossBattleGameOverState(settings, **kwargs),
}

def main():
    # Load config relative to this file
    cfg_path = os.path.join(os.path.dirname(__file__), "eye_ctrl_config.json")
    cfg = load_config(cfg_path)

    # Manual settings prompt
    settings = prompt_boss_settings()

    # Initial discovery
    discovered_ip = run_discovery_flow()
    if discovered_ip:
        cfg["device_ip"] = discovered_ip
        print(f"Using discovered device at {discovered_ip}")

    # Instantiate GameMaster with the initial SetupState and transitions
    def make_start():
        return BossBattleSetupState(settings)

    gm = GameMaster(make_start, settings, transitions)
    
    # Start networking
    net = NetworkManager(gm, config=cfg)
    net.start_bg()

    # Start game thread
    gt = threading.Thread(
        target=game_thread_func, args=(gm,), daemon=True
    )
    gt.start()

    print("Boss Battle Game (Evil Eye - Game 3)")
    print("Commands: 'restart', 'setup', 'quit'")

    try:
        while gm.running:
            prompt_render(gm, BossBattleSetupState, prompt_boss_settings)
    except KeyboardInterrupt:
        gm.running = False

    net.running = False
    print("Exiting...")

if __name__ == "__main__":
    main()
