"""
audio.py — Vault Zero Audio Manager
Language : Python (pygame)
Handles  : BGM playback, sound effects, volume control, mute toggle
All audio files live in  assets/audio/
  bgm/   — background music tracks (.ogg / .mp3)
  sfx/   — sound effects (.wav / .ogg)

If audio files are missing or pygame fails, everything silently falls back
to no-ops so the game always runs regardless of audio setup.
"""
import os, threading, time

BASE       = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR  = os.path.join(BASE, "assets", "audio")
BGM_DIR    = os.path.join(AUDIO_DIR, "bgm")
SFX_DIR    = os.path.join(AUDIO_DIR, "sfx")

_READY     = False   # pygame mixer initialised successfully
_MUTED     = False
_BGM_VOL   = 0.35    # 0.0 – 1.0
_SFX_VOL   = 0.65
_current_bgm: str | None = None


# ── Init ──────────────────────────────────────────────────────────────────────
def init() -> bool:
    global _READY
    if _READY:
        return True
    try:
        import pygame
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        _READY = True
        _ensure_dirs()
        _generate_placeholder_sounds()
        return True
    except Exception as e:
        print(f"[audio] pygame mixer unavailable: {e}")
        return False


def _ensure_dirs():
    for d in [AUDIO_DIR, BGM_DIR, SFX_DIR]:
        os.makedirs(d, exist_ok=True)


# ── Placeholder sound generator ───────────────────────────────────────────────
def _generate_placeholder_sounds():
    """
    Generate simple synthesised placeholder sounds using pygame.sndarray
    so the game has audio immediately without any external files.
    Players can replace these .wav files with their own assets.
    """
    try:
        import pygame
        import pygame.sndarray
        import numpy as np
    except ImportError:
        return

    def _sine_wave(freq, duration_ms, volume=0.3, sample_rate=44100):
        n  = int(sample_rate * duration_ms / 1000)
        t  = np.linspace(0, duration_ms/1000, n, False)
        wave = np.sin(2 * np.pi * freq * t) * volume * 32767
        stereo = np.column_stack([wave, wave]).astype(np.int16)
        return pygame.sndarray.make_sound(stereo)

    def _chord(freqs, duration_ms, volume=0.2, sample_rate=44100):
        n   = int(sample_rate * duration_ms / 1000)
        t   = np.linspace(0, duration_ms/1000, n, False)
        mix = sum(np.sin(2*np.pi*f*t) for f in freqs)
        mix = mix / len(freqs) * volume * 32767
        stereo = np.column_stack([mix, mix]).astype(np.int16)
        return pygame.sndarray.make_sound(stereo)

    def _save(sound, path):
        if not os.path.exists(path):
            try:
                pygame.sndarray  # already imported
                import wave, struct
                arr = pygame.sndarray.array(sound)
                with wave.open(path, 'w') as wf:
                    wf.setnchannels(2)
                    wf.setsampwidth(2)
                    wf.setframerate(44100)
                    wf.writeframes(arr.tobytes())
            except Exception:
                pass

    try:
        sfx_defs = {
            "correct.wav":  (_chord([523, 659, 784], 300, 0.25),),   # C-E-G chord
            "wrong.wav":    (_chord([220, 233], 200, 0.3),),          # dissonant
            "click.wav":    (_sine_wave(800, 60, 0.2),),              # short click
            "unlock.wav":   (_chord([392, 523, 659, 784], 400, 0.2),),# triumphant
            "item.wav":     (_sine_wave(1047, 120, 0.2),),            # high ping
            "alarm.wav":    (_chord([110, 116], 500, 0.4),),          # low alarm
            "proceed.wav":  (_chord([523, 784, 1047], 500, 0.2),),    # ascending
            "button.wav":   (_sine_wave(600, 40, 0.15),),             # soft click
            "clue.wav":     (_chord([659, 784], 200, 0.2),),          # two-note
            "escape.wav":   (_chord([523, 659, 784, 1047], 800, 0.25),),# full chord
        }
        for fname, (sound,) in sfx_defs.items():
            path = os.path.join(SFX_DIR, fname)
            _save(sound, path)
        print("[audio] placeholder SFX generated in assets/audio/sfx/")
    except Exception as e:
        print(f"[audio] placeholder generation skipped: {e}")


# ── BGM ───────────────────────────────────────────────────────────────────────
# Track list per context — add your own .ogg/.mp3 files to assets/audio/bgm/
BGM_TRACKS = {
    "menu":    ["menu_theme.ogg",    "menu_ambient.ogg"],
    "storage": ["storage_amb.ogg",   "dungeon_low.ogg"],
    "lab":     ["lab_hum.ogg",       "tech_ambient.ogg"],
    "server":  ["server_drone.ogg",  "tech_ambient.ogg"],
    "vault":   ["vault_tension.ogg", "dungeon_low.ogg"],
    "reactor": ["reactor_alarm.ogg", "tension_high.ogg"],
    "victory": ["victory.ogg"],
    "gameover":["gameover.ogg"],
}


def play_bgm(context: str, loop: bool = True):
    """Play background music for the given context (fades between tracks)."""
    global _current_bgm
    if not _READY or _MUTED:
        return
    try:
        import pygame
        tracks = BGM_TRACKS.get(context, [])
        for track in tracks:
            path = os.path.join(BGM_DIR, track)
            if os.path.exists(path):
                if _current_bgm == path:
                    return   # already playing
                pygame.mixer.music.fadeout(600)
                time.sleep(0.05)
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(_BGM_VOL)
                pygame.mixer.music.play(-1 if loop else 0)
                _current_bgm = path
                return
        # No file found — stop current music silently
        pygame.mixer.music.fadeout(400)
        _current_bgm = None
    except Exception:
        pass


def stop_bgm(fade_ms: int = 500):
    global _current_bgm
    if not _READY: return
    try:
        import pygame
        pygame.mixer.music.fadeout(fade_ms)
        _current_bgm = None
    except Exception:
        pass


# ── SFX ───────────────────────────────────────────────────────────────────────
_sfx_cache: dict = {}


def _load_sfx(name: str):
    if name in _sfx_cache:
        return _sfx_cache[name]
    if not _READY:
        return None
    try:
        import pygame
        path = os.path.join(SFX_DIR, name)
        if os.path.exists(path):
            snd = pygame.mixer.Sound(path)
            snd.set_volume(_SFX_VOL)
            _sfx_cache[name] = snd
            return snd
    except Exception:
        pass
    return None


def play_sfx(name: str):
    """Play a named sound effect. name = filename without path, e.g. 'correct.wav'"""
    if _MUTED: return
    snd = _load_sfx(name)
    if snd:
        try:
            snd.play()
        except Exception:
            pass


# ── Named events (called from game logic) ─────────────────────────────────────
def on_puzzle_correct():   play_sfx("correct.wav")
def on_puzzle_wrong():     play_sfx("wrong.wav")
def on_item_obtained():    play_sfx("item.wav")
def on_puzzle_open():      play_sfx("click.wav")
def on_room_unlock():      play_sfx("unlock.wav")
def on_proceed():          play_sfx("proceed.wav")
def on_button_click():     play_sfx("button.wav")
def on_clue_found():       play_sfx("clue.wav")
def on_escape():           play_sfx("escape.wav")
def on_alarm():            play_sfx("alarm.wav")


# ── Volume / mute ─────────────────────────────────────────────────────────────
def set_bgm_volume(v: float):
    global _BGM_VOL
    _BGM_VOL = max(0.0, min(1.0, v))
    if _READY:
        try:
            import pygame
            pygame.mixer.music.set_volume(_BGM_VOL if not _MUTED else 0.0)
        except Exception:
            pass


def set_sfx_volume(v: float):
    global _SFX_VOL
    _SFX_VOL = max(0.0, min(1.0, v))
    for snd in _sfx_cache.values():
        try: snd.set_volume(_SFX_VOL)
        except Exception: pass


def toggle_mute() -> bool:
    global _MUTED
    _MUTED = not _MUTED
    if _READY:
        try:
            import pygame
            pygame.mixer.music.set_volume(0.0 if _MUTED else _BGM_VOL)
        except Exception:
            pass
    return _MUTED


def is_muted() -> bool:
    return _MUTED


def is_ready() -> bool:
    return _READY


# ── Shutdown ──────────────────────────────────────────────────────────────────
def shutdown():
    if _READY:
        try:
            import pygame
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass
