from ..game_engine import GameEngine

class GameMaster:
    def __init__(self, initial_state_factory, settings, spawn_rules, transitions):
        self.engine = GameEngine()
        self.running = True
        self.button_states = self.engine.button_states
        self._initial_state_factory = initial_state_factory
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.transitions = transitions
        self.engine.change_state(initial_state_factory())

    def tick(self, dt: float):
        state = self.engine.state
        if state is not None:
            next_info = state.update(self.engine, dt)
            if next_info is not None:
                state_name, kwargs = next_info
                self.engine.change_state(self.transitions[state_name](self.settings, self.spawn_rules, **kwargs))
        self.engine.snapshot_input()

    def render(self):
        return self.engine.render()

    def restart(self):
        self.engine.entities.clear()
        self.engine.change_state(self._initial_state_factory())
