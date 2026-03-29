import os
import threading
try:
    import pygame
except Exception:
    pygame = None


class AudioManager:
    def __init__(self):
        self._pygame = pygame
        self._lock = threading.Lock()
        self._pending_timer = None
        self._current_path = None
        self._volume = 0.8
        self._sfx_cache = {}

    def init_mixer(self):
        if not self._pygame:
            return False
        try:
            if not self._pygame.mixer or not self._pygame.mixer.get_init():
                self._pygame.init()
                self._pygame.mixer.init()
            return True
        except Exception:
            return False

    def _load_and_play(self, path, loop, fade_ms):
        try:
            if not self.init_mixer():
                return
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.set_volume(self._volume)
            if loop is None:
                loop = -1
            self._pygame.mixer.music.play(loop, fade_ms=fade_ms)
            self._current_path = path
        except Exception:
            pass

    def play_music(self, path, loop=-1, fade_ms=300):
        """Crossfade from current music to `path` over `fade_ms` milliseconds."""
        if not self._pygame:
            return
        with self._lock:
            if self._pending_timer is not None:
                try:
                    self._pending_timer.cancel()
                except Exception:
                    pass
                self._pending_timer = None

            try:
                if self._pygame.mixer.get_init() and self._pygame.mixer.music.get_busy():
                    self._pygame.mixer.music.fadeout(fade_ms)
                t = threading.Timer(fade_ms / 1000.0, self._load_and_play, args=(path, loop, fade_ms))
                t.daemon = True
                t.start()
                self._pending_timer = t
            except Exception:
                self._load_and_play(path, loop, fade_ms)

    def stop_music(self, fade_ms=300):
        if not self._pygame:
            return
        with self._lock:
            if self._pending_timer is not None:
                try:
                    self._pending_timer.cancel()
                except Exception:
                    pass
                self._pending_timer = None
            try:
                if self._pygame.mixer.get_init() and self._pygame.mixer.music.get_busy():
                    self._pygame.mixer.music.fadeout(fade_ms)
                    self._current_path = None
            except Exception:
                pass

    def load_sfx(self, path):
        if not self._pygame:
            return
        try:
            if not self.init_mixer():
                return
            if path not in self._sfx_cache:
                self._sfx_cache[path] = self._pygame.mixer.Sound(path)
        except Exception:
            pass

    def play_sfx(self, path, delay_ms=0):
        if not self._pygame:
            return
        
        def _execute_play():
            try:
                if not self.init_mixer():
                    return
                if path not in self._sfx_cache:
                    self.load_sfx(path)
                if path in self._sfx_cache:
                    self._sfx_cache[path].set_volume(self._volume)
                    self._sfx_cache[path].play()
            except Exception:
                pass

        if delay_ms > 0:
            t = threading.Timer(delay_ms / 1000.0, _execute_play)
            t.daemon = True
            t.start()
        else:
            _execute_play()


_audio_manager = AudioManager()

def get_audio_manager():
    return _audio_manager
