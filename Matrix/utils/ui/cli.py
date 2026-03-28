from ..scaling import DIFFICULTIES
from ..scaling import GameSettings
from ..scaling import SpawnRules
from ..states import GameStartState

def prompt_settings():
    print("\n=== KEEP ALIVE - Setup ===\n")

    while True:
        try:
            n = int(input("Number of players (2-6): ").strip())
            if 2 <= n <= 6:
                break
            print("  Please enter a number between 2 and 6.")
        except ValueError:
            print("  Invalid input.")

    diff_names = list(DIFFICULTIES.keys())
    print("\nDifficulty:")
    for i, name in enumerate(diff_names, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"Choose difficulty (1-{len(diff_names)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(diff_names):
                break
            print(f"  Please enter a number between 1 and {len(diff_names)}.")
        except ValueError:
            print("  Invalid input.")

    diff_name = diff_names[idx]
    settings = GameSettings(n, diff_name)

    print(f"\n  Players: {settings.player_count}")
    print(f"  Difficulty: {settings.difficulty}")
    print(f"  Initial platforms: {settings.tile_spawn_initial}")
    print(f"  Platforms per round: {settings.tile_spawn_per_round}")
    print()
    return settings

def prompt_render(game, area):
    cmd = input("> ").strip().lower()
    if cmd in ('quit', 'exit'):
        game.running = False
    elif cmd == 'restart':
        spawn_rules.reset()
        game.restart()
        print("Restarted.")
    elif cmd == 'setup':
        settings = prompt_settings()
        spawn_rules = SpawnRules(settings, area)
        def make_start_new(s=settings, sr=spawn_rules):
            return GameStartState(s, sr)
        game._initial_state_factory = make_start_new
        game.restart()
        print("Settings applied, game restarted.")
    else:
        print("Unknown command. Try: restart, setup, quit")