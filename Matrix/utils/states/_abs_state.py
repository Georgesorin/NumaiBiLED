from abc import ABC, abstractmethod

class GameState(ABC):
    @abstractmethod
    def enter(self, engine):
        pass

    @abstractmethod
    def update(self, engine, dt: float):
        pass

    @abstractmethod
    def exit(self, engine):
        pass