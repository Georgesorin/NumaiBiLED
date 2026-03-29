import sys
import os
import threading
import time

# Add the current directory to sys.path to allow imports from game_engine and utils
sys.path.insert(0, os.path.dirname(__file__))

from utils.data.network import load_config, configure_from_discovery, NetworkManager
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

    # Discovery
    cfg, discovered = configure_from_discovery(cfg, cfg_path)
    if discovered:
        print(f"Using discovered device at {cfg['device_ip']}")
    else:
        print("Discovery did not find a device; using config defaults.")

    from utils.ui.colors import RED, GREEN
    from utils.data.audio_manager import get_audio_manager
    audio = get_audio_manager()
    base_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    sfx_start = os.path.join(base_assets, "sfx", "start_pattern_timeout.wav")
    sfx_end = os.path.join(base_assets, "sfx", "end_pattern_timeout.wav")
    
    # Pre-cache sounds (Phase 10 Sync Fix)
    audio.load_sfx(sfx_start)
    audio.load_sfx(sfx_end)

    # Terminal Buffer: Give user time to move to the walls
    print("\nSettings applied. Get ready to move to the walls!")
    for i in range(4, 0, -1):
        if i == 4:
            gm.engine.clear()
            print(f"Starting in {i}...", end="\r")
            time.sleep(1)
        else:
            # LED Animation: flash red, red, green
            if i > 1:
                color = RED
                sfx = sfx_start
            else:
                color = GREEN
                sfx = sfx_end

            # Set LEDs FIRST, then play sound (Phase 10 Fine-tune Sync)
            # 60ms delay compensates for 20ms poll rate + 2 packet delays (8ms each) + network
            gm.engine.set_all(*color)
            audio.play_sfx(sfx, delay_ms=60)
            
            print(f"Starting in {i}...", end="\r")
            time.sleep(0.5)
            gm.engine.clear()
            time.sleep(0.5)
    print("Go!             \n")

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
    from utils.data.audio_manager import get_audio_manager
    get_audio_manager().stop_music()
    print("Exiting...")

if __name__ == "__main__":
    main()
