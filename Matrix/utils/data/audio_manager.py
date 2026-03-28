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

    def init_mixer(self):
        if not self._pygame:
            return False
        try:
            if not self._pygame.mixer.get_init():
                self._pygame.mixer.init()
            return True
        except Exception:
            return False

    def _load_and_play(self, path, loop, fade_ms):
        try:
            if not self.init_mixer():
                return
            # load and play with fade-in
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.set_volume(self._volume)
            if loop is None:
                loop = -1
            # play with fade-in
            self._pygame.mixer.music.play(loop, fade_ms=fade_ms)
            self._current_path = path
        except Exception:
            pass

    def play_music(self, path, loop=-1, fade_ms=300):
        """Crossfade from current music to `path` over `fade_ms` milliseconds."""
        if not self._pygame:
            return
        with self._lock:
            # cancel pending timer
            if self._pending_timer is not None:
                try:
                    self._pending_timer.cancel()
                except Exception:
                    pass
                self._pending_timer = None

            try:
                if self._pygame.mixer.get_init() and self._pygame.mixer.music.get_busy():
                    # fade out current music
                    self._pygame.mixer.music.fadeout(fade_ms)
                # schedule new music to start after fade_ms
                t = threading.Timer(fade_ms / 1000.0, self._load_and_play, args=(path, loop, fade_ms))
                t.daemon = True
                t.start()
                self._pending_timer = t
            except Exception:
                # fallback: immediate load
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


_audio_manager = AudioManager()

def get_audio_manager():
    return _audio_manager
