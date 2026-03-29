from ..scaling.game_settings import PatternMemorySettings, BossBattleSettings, DIFFICULTY
from ..data.pattern_memory_data import PLAYER_CONFIGS

def prompt_settings():
    print("\n=== PATTERN MEMORY - Setup ===\n")

    valid_counts = sorted(PLAYER_CONFIGS.keys())
    while True:
        try:
            n_str = input(f"Number of players ({', '.join(map(str, valid_counts))}): ").strip()
            if not n_str:
                n = 4 # Default
                break
            n = int(n_str)
            if n in valid_counts:
                break
            print(f"  Please enter one of: {', '.join(map(str, valid_counts))}")
        except ValueError:
            print("  Invalid input.")

    diff_names = list(DIFFICULTY.keys())
    print("\nDifficulty:")
    for i, name in enumerate(diff_names, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"Choose difficulty (1-{len(diff_names)}): ").strip()
            if not choice:
                idx = 1 # Default (medium)
                break
            idx = int(choice) - 1
            if 0 <= idx < len(diff_names):
                break
            print(f"  Please enter a number between 1 and {len(diff_names)}.")
        except ValueError:
            print("  Invalid input.")

    diff_name = diff_names[idx]
    settings = PatternMemorySettings(n, diff_name)

    print(f"\n  Players: {settings.player_count}")
    print(f"  Difficulty: {settings.difficulty_name}")
    print(f"  Pattern length: {settings.pattern_length} colours")
    print()
    return settings

def prompt_boss_settings():
    print("\n=== BOSS BATTLE - Setup ===\n")

    valid_counts = sorted(PLAYER_CONFIGS.keys())
    while True:
        try:
            n_str = input(f"Number of players ({', '.join(map(str, valid_counts))}): ").strip()
            if not n_str:
                n = 4 # Default
                break
            n = int(n_str)
            if n in valid_counts:
                break
            print(f"  Please enter one of: {', '.join(map(str, valid_counts))}")
        except ValueError:
            print("  Invalid input.")

    diff_names = ["easy", "medium", "hard"]
    print("\nDifficulty:")
    for i, name in enumerate(diff_names, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"Choose difficulty (1-3): ").strip()
            if not choice:
                idx = 1 # Default (medium)
                break
            idx = int(choice) - 1
            if 0 <= idx < 3:
                break
            print(f"  Please enter a number between 1 and 3.")
        except ValueError:
            print("  Invalid input.")

    diff_name = diff_names[idx]
    settings = BossBattleSettings(n, diff_name)

    print(f"\n  Players: {settings.player_count}")
    print(f"  Difficulty: {settings.difficulty_name}")
    print()
    return settings

def prompt_render(game, setup_state_class=None, prompt_func=None):
    cmd = input("> ").strip().lower()
    if cmd in ('quit', 'exit'):
        game.running = False
    elif cmd == 'restart':
        game.restart()
        print("Restarted.")
    elif cmd == 'setup':
        # Use provided prompt function or default to Game 1
        if prompt_func is None:
            prompt_func = prompt_settings
            
        settings = prompt_func()
        game.settings = settings
        
        # If setup_state_class is provided, use it. 
        # Otherwise, default to Game 1 SetupState.
        if setup_state_class is None:
            from ..states.setup_state import SetupState
            setup_state_class = SetupState
            
        game._initial_state_factory = lambda: setup_state_class(settings)
        game.restart()
        print("Settings applied, game restarted.")
    else:
        print("Unknown command. Try: restart, setup, quit")
