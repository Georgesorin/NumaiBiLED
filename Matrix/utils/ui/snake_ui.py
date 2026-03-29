from ..data.snake_data import SnakeSettings, SNAKE_DIFFICULTIES

def prompt_snake_settings():
    print("\n=== SNAKE - Setup ===\n")

    while True:
        try:
            n = int(input("Number of players (2-6): ").strip())
            if 2 <= n <= 6:
                break
            print("  Please enter a number between 2 and 6.")
        except ValueError:
            print("  Invalid input.")

    diff_names = list(SNAKE_DIFFICULTIES.keys())
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

    settings = SnakeSettings(n, diff_names[idx])
    print(f"\n  Players: {settings.player_count}")
    print(f"  Difficulty: {settings.difficulty_name}")
    print(f"  Snake length: {settings.initial_length}")
    print(f"  Speed: base={settings.base_interval:.2f}s  min={settings.min_interval:.2f}s")
    print(f"  Fruits: min={settings.min_fruits}  spawn every {settings.spawn_interval:.1f}s\n")
    return settings
