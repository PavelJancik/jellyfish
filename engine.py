"""
engine.py — Pygame loading screen with animated progress bar.

Usage:
    from engine import load_frames

    frames = load_frames(screen, "shark")
"""

import os
import pygame
from PIL import Image


# ── internal helpers ──────────────────────────────────────────────────────────

def _count_frames(scene_animal: str) -> int:
    """Return the total number of frame files for the given animal scene."""
    i = 0
    while os.path.exists(f"imgs/water_{scene_animal}/frame_{i}.png"):
        i += 1
    return i

# ── public API ────────────────────────────────────────────────────────────────

def draw_loading_screen(
    screen: pygame.Surface,
    scene_animal: str,
    current: int,
    total: int,
    *,
    bg_color: tuple = (10, 20, 40),
    bar_color: tuple = (80, 160, 255),
    bar_bg_color: tuple = (50, 50, 80),
    bar_border_color: tuple = (100, 120, 200),
    text_color: tuple = (200, 220, 255),
) -> None:
    """Redraw the loading screen for the current frame index."""
    screen_w, screen_h = screen.get_size()

    # ── background ────────────────────────────────────────────────────────────

    screen.fill(bg_color)
    

    # ── layout anchor — everything centred around the middle of the screen ────
    center_x = screen_w // 2
    center_y = screen_h // 2

    # ── title ─────────────────────────────────────────────────────────────────
    font = load_font(30)
    title = font.render(f"loading: {scene_animal}", True, text_color)
    title_y = center_y - 55
    screen.blit(title, (center_x - title.get_width() // 2, title_y))

    # ── progress bar ──────────────────────────────────────────────────────────
    bar_w = int(screen_w * 0.45)
    bar_h = 22
    bar_x = center_x - bar_w // 2
    bar_y = title_y + title.get_height() + 20

    progress = current / total if total > 0 else 0
    filled_w = int(bar_w * progress)

    pygame.draw.rect(screen, bar_bg_color,    (bar_x, bar_y, bar_w, bar_h), border_radius=6)
    if filled_w > 0:
        pygame.draw.rect(screen, bar_color,   (bar_x, bar_y, filled_w, bar_h), border_radius=6)
    pygame.draw.rect(screen, bar_border_color,(bar_x, bar_y, bar_w, bar_h), 2, border_radius=6)

    # ── percentage  (centred under the bar) ───────────────────────────────────
    pct_label = font.render(f"{int(progress * 100)} %", True, text_color)
    pct_y = bar_y + bar_h + 12
    screen.blit(pct_label, (center_x - pct_label.get_width() // 2, pct_y))

    pygame.display.update()

def load_frames(
    screen: pygame.Surface,
    scene_animal: str,
    *,
    base_path: str = "imgs",
) -> list[pygame.Surface]:
    """
    Load all frames for *scene_animal* while displaying a progress bar.

    Parameters
    ----------
    screen       : active pygame display surface
    scene_animal : animal name used to build the image path
                   (e.g. "shark" → imgs/water_shark/frame_N.png)
    base_path    : root folder that contains the water_<animal> directories

    Returns
    -------
    list of scaled pygame.Surface objects, one per frame
    """
    scene_animal = scene_animal.lower()
    screen_w, screen_h = screen.get_size()

    frame_dir = f"{base_path}/water_{scene_animal}"
    total = _count_frames(scene_animal) if base_path == "imgs" else sum(
        1 for i in range(99_999)
        if os.path.exists(f"{frame_dir}/frame_{i}.png")
    )

    # Re-count with the actual base_path
    total = 0
    i = 0
    while os.path.exists(f"{frame_dir}/frame_{i}.png"):
        total += 1
        i += 1

    animal_frames: list[pygame.Surface] = []

    for i in range(total):
        draw_loading_screen(screen, f"{scene_animal} water animation", i, total)

        path = f"{frame_dir}/frame_{i}.png"
        frame = pygame.image.load(path).convert()
        frame = pygame.transform.scale(frame, (screen_w, screen_h))
        animal_frames.append(frame)

    # Draw 100 % before returning
    if total > 0:
        draw_loading_screen(screen, f"{scene_animal} water animation", total, total)

    return animal_frames


class FadeTransition:
    """
    Fade-out -> data switch -> fade-in transition.

    Usage
    -----
        fade = FadeTransition(screen_w, screen_h)

        # on spot selection:
        fade.start(new_spot)

        # in the game loop (after drawing the scene):
        new_spot = fade.update_and_draw(surface, clock.get_time())
        if new_spot:
            map_spot = new_spot
            # switch frames, etc.

    Parameters
    ----------
    speed : alpha per second (default 400 -> ~0.64 s per direction)
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        speed: float = 400.0,
    ) -> None:
        self._surf = pygame.Surface((screen_w, screen_h))
        self._surf.fill((0, 0, 0))
        self._alpha: float = 0.0
        self._dir: int = 0              # 1 = fade-out, -1 = fade-in, 0 = idle
        self._speed: float = speed
        self._pending: str | None = None

    def start(self, spot: str) -> None:
        """Starts a fade-out toward the given spot."""
        self._alpha = 0.0
        self._dir = 1
        self._pending = spot

    def update_and_draw(
        self,
        surface: pygame.Surface,
        dt_ms: float,
    ) -> str | None:
        """
        Updates state and draws the overlay onto the surface.

        Returns the new spot's name at the moment of the switch (exactly
        once), otherwise None.
        """
        if self._dir == 0:
            return None

        self._alpha += self._dir * self._speed * (dt_ms / 1000.0)
        switched_to: str | None = None

        if self._dir == 1 and self._alpha >= 255:
            self._alpha = 255.0
            switched_to = self._pending
            self._pending = None
            self._dir = -1

        elif self._dir == -1 and self._alpha <= 0:
            self._alpha = 0.0
            self._dir = 0

        self._surf.set_alpha(int(self._alpha))
        surface.blit(self._surf, (0, 0))
        return switched_to

    @property
    def active(self) -> bool:
        """True while a transition is in progress."""
        return self._dir != 0


class VideoFade:
    """
    Fade-in at the start of a video and fade-out at the end / on skip.

    Usage
    -----
        vf = VideoFade(screen_w, screen_h, speed=300)

        # every frame (before pygame.display.update):
        done = vf.update_and_draw(screen, dt)
        if done:
            # move to the next state

        # on skip (key / button):
        vf.request_fadeout()

    Parameters
    ----------
    speed       : alpha per second (default 300 -> ~0.85 s per direction)
    fadeout_at  : seconds before the video ends to auto-start the fade-out;
                  None = no automatic fade-out (caller controls it)
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        speed: float = 300.0,
        fadeout_at: float | None = None,
    ) -> None:
        self._surf = pygame.Surface((screen_w, screen_h))
        self._surf.fill((0, 0, 0))
        self._alpha: float = 255.0          # start fully black
        self._dir: int = -1                 # -1 = fade-in right at the start
        self._speed: float = speed
        self._fadeout_at: float | None = fadeout_at
        self._elapsed: float = 0.0
        self._done: bool = False            # True = fade-out finished -> caller can move on
        self._fading_out: bool = False

    # ── public ────────────────────────────────────────────────────────────────

    def request_fadeout(self) -> None:
        """Immediately starts a fade-out (e.g. on skip)."""
        if not self._fading_out and not self._done:
            self._dir = 1
            self._fading_out = True

    def update_and_draw(self, surface: pygame.Surface, dt: float) -> bool:
        """
        Updates alpha and draws the overlay.
        Returns True exactly once — the moment the fade-out finishes.
        """
        if self._done:
            return False

        self._elapsed += dt

        # automatic fade-out based on video length
        if (
            self._fadeout_at is not None
            and not self._fading_out
            and self._elapsed >= self._fadeout_at
        ):
            self.request_fadeout()

        self._alpha += self._dir * self._speed * dt
        self._alpha = max(0.0, min(255.0, self._alpha))

        # fade-in finished -> idle (dir = 0)
        if self._dir == -1 and self._alpha <= 0:
            self._alpha = 0.0
            self._dir = 0

        # fade-out finished -> done
        if self._dir == 1 and self._alpha >= 255:
            self._alpha = 255.0
            self._done = True
            self._surf.set_alpha(255)
            surface.blit(self._surf, (0, 0))
            return True

        if self._alpha > 0:
            self._surf.set_alpha(int(self._alpha))
            surface.blit(self._surf, (0, 0))

        return False

    @property
    def done(self) -> bool:
        return self._done


def load_font(size: int, path: str = 'fonts/DynaPuff/DynaPuff-VariableFont_wdth,wght.ttf') -> pygame.font.Font:
    if path:
        return pygame.font.Font(path, size)
 


class BackgroundMusic:
    """
    Plays background music from the audio/OST/ folder.

    Files are played in random order on a loop.
    Supports smooth fade-in / fade-out when starting and stopping.

    Usage
    -----
        bg_music = BackgroundMusic()

        # in the game loop:
        bg_music.update(dt)

        # start (with fade-in):
        bg_music.play()

        # stop (with fade-out):
        bg_music.stop()

    Parameters
    ----------
    folder      : path to the folder with music files
    volume      : target volume 0.0-1.0
    fade_speed  : fade-in/out speed (volume units per second)
    """

    SUPPORTED_EXTS = {".mp3", ".ogg", ".wav", ".flac"}

    def __init__(
        self,
        folder: str = "audio/OST",
        volume: float = 0.5,
        fade_speed: float = 0.4,
    ) -> None:
        self._folder = folder
        self._target_vol = volume
        self._fade_speed = fade_speed
        self._current_vol: float = 0.0
        self._playing: bool = False        # True = we want to play
        self._active: bool = False         # True = mixer is currently playing
        self._playlist: list[str] = []
        self._index: int = 0
        self._mixer_ok: bool = False
        self._end_event = pygame.USEREVENT + 10

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.set_endevent(self._end_event)
            self._mixer_ok = True
        except Exception:
            pass

        self._build_playlist()

    # ── playlist ──────────────────────────────────────────────────────────────

    def _build_playlist(self) -> None:
        """Loads and shuffles the list of files from the folder."""
        if not os.path.isdir(self._folder):
            return
        files = [
            os.path.join(self._folder, f)
            for f in os.listdir(self._folder)
            if os.path.splitext(f)[1].lower() in self.SUPPORTED_EXTS
        ]
        import random as _random
        _random.shuffle(files)
        self._playlist = files
        self._index = 0

    def _load_next(self) -> bool:
        """Loads the next track from the playlist. Returns False if the playlist is empty."""
        if not self._playlist:
            return False
        path = self._playlist[self._index % len(self._playlist)]
        self._index += 1
        if self._index >= len(self._playlist):
            # Reshuffle for the next pass
            import random as _random
            _random.shuffle(self._playlist)
            self._index = 0
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play()
            self._active = True
            return True
        except Exception:
            return False

    # ── public API ────────────────────────────────────────────────────────────

    def play(self) -> None:
        """Starts playback with fade-in (safe to call repeatedly)."""
        if not self._mixer_ok or not self._playlist:
            return
        self._playing = True
        if not self._active:
            self._load_next()

    def stop(self) -> None:
        """Starts a fade-out then stops the mixer."""
        self._playing = False

    def update(self, dt: float) -> None:
        """Call every frame. Drives fade-in/out and switching to the next track."""
        if not self._mixer_ok:
            return

        # Switch to the next track (mixer finished naturally)
        # Note: we don't rely on the event queue (pygame.mixer.music.set_endevent)
        # because main.py's game loop calls pygame.event.get() with no filter,
        # so it can drain the USEREVENT for track-end before we see it here –
        # that stalled the playlist after the first song. Instead we detect
        # end-of-track directly via get_busy(), which doesn't depend on the
        # event queue.
        if self._active and not pygame.mixer.music.get_busy():
            if self._playing:
                self._load_next()
            else:
                self._active = False

        if self._playing and self._active:
            # Fade-in
            self._current_vol = min(
                self._target_vol,
                self._current_vol + self._fade_speed * dt,
            )
        else:
            # Fade-out
            self._current_vol = max(0.0, self._current_vol - self._fade_speed * dt)
            if self._current_vol <= 0.0 and self._active:
                pygame.mixer.music.stop()
                self._active = False

        if self._active:
            try:
                pygame.mixer.music.set_volume(self._current_vol)
            except Exception:
                pass

    def hand_off(self) -> None:
        """
        Gives up control of the mixer — other code (game_scene) has started
        its own music via pygame.mixer.music. BackgroundMusic stops calling
        stop/set_volume until play() is called again.
        """
        self._playing = False
        self._active = False
        self._current_vol = 0.0

    @property
    def is_playing(self) -> bool:
        return self._playing and self._active

class SkipHoldIndicator:
    """
    Circular indicator in the bottom-right corner of the screen.
    Shows progress of holding the skip-video button.

    Usage
    -----
        skip = SkipHoldIndicator(screen_w, screen_h)

        # in the game loop — pass button state and dt:
        triggered = skip.update(held, dt)
        skip.draw(screen)
        if triggered:
            # perform the skip

        # on transitioning to another state (reset):
        skip.reset()

    Parameters
    ----------
    hold_time   : seconds the button must be held to trigger a skip (default 1.0)
    radius      : circle radius in pixels (default 28)
    margin      : distance from the screen edge (default 30)
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        hold_time: float = 1.0,
        radius: int = 28,
        margin: int = 30,
    ) -> None:
        self._hold_time = hold_time
        self._radius = radius
        self._cx = screen_w - margin - radius
        self._cy = screen_h - margin - radius
        self._progress: float = 0.0   # 0.0 - 1.0
        self._triggered: bool = False

    # ── public ────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Resets both progress and the triggered state."""
        self._progress = 0.0
        self._triggered = False

    def update(self, held: bool, dt: float) -> bool:
        """
        Updates state.

        Parameters
        ----------
        held : True if the button is currently pressed
        dt   : delta time in seconds

        Returns True exactly once, the moment progress reaches 100%.
        """
        if self._triggered:
            return False

        if held:
            self._progress = min(1.0, self._progress + dt / self._hold_time)
            if self._progress >= 1.0:
                self._triggered = True
                return True
        else:
            # Smooth decay when released
            self._progress = max(0.0, self._progress - dt * 2.5 / self._hold_time)

        return False

    def draw(self, surface: pygame.Surface) -> None:
        """Draws the circular indicator, only if progress > 0."""
        if self._progress <= 0.0:
            return

        cx, cy, r = self._cx, self._cy, self._radius
        import math

        # Semi-transparent background ring (thin outline)
        ring_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (255, 255, 255, 80), (r + 2, r + 2), r, 5)
        surface.blit(ring_surf, (cx - r - 2, cy - r - 2))

        # Progress arc as an annulus (wedge with no center)
        arc_color = (255, 255, 255)
        thickness = 5
        angle_start = -math.pi / 2
        angle_end   = angle_start + 2 * math.pi * self._progress
        steps = max(4, int(80 * self._progress))

        arc_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        arc_cx, arc_cy = r + 2, r + 2
        points = [(arc_cx, arc_cy)]
        for s in range(steps + 1):
            a = angle_start + (angle_end - angle_start) * s / steps
            points.append((arc_cx + r * math.cos(a), arc_cy + r * math.sin(a)))
        if len(points) >= 3:
            pygame.draw.polygon(arc_surf, (*arc_color, 200), points)
        # Cut out the center — leaves just the annulus
        pygame.draw.circle(arc_surf, (0, 0, 0, 0), (arc_cx, arc_cy), r - thickness)
        surface.blit(arc_surf, (cx - r - 2, cy - r - 2))

        # "SKIP" text — centered in the circle
        try:
            font = load_font(14)
            label = font.render("SKIP", True, (255, 255, 255))
            surface.blit(label, (cx - label.get_width() // 2, cy - label.get_height() // 2))
        except Exception:
            pass

    @property
    def progress(self) -> float:
        return self._progress


class SpellEffect:
    """
    One-shot spell animation played at a fixed spot on screen.

    Plays imgs/spell.png (5x5 grid = 25 frames) once, then marks itself
    ``done``. Stays visually anchored to where the interaction happened,
    independent of Jelly's movement.

    Usage (in GameScene)
    ----------------------
        # on a successful interaction:
        cx, cy = screen_interaction_center
        self._spell_effects.append(SpellEffect(cx, cy, scale=0.7))

        # in update():
        self._spell_effects = [e for e in self._spell_effects if not e.done]
        for e in self._spell_effects:
            e.update(dt)

        # in draw() – after Jelly, before the HUD:
        for e in self._spell_effects:
            e.draw(surface)

    Parameters
    ----------
    screen_cx, screen_cy : effect center in screen coordinates
    scale                : scale – should match Jelly's scale
    fps                  : playback speed (default 14)
    spritesheet_path     : path to imgs/spell.png
    cols / rows          : grid dimensions (default 5x5)
    """

    SHEET_COLS = 5
    SHEET_ROWS = 5

    # Shared frame cache (same scale = one load)
    _cache: dict[tuple, list] = {}

    @classmethod
    def _load_frames(
        cls,
        path: str,
        cols: int,
        rows: int,
        scale: float,
    ) -> list[pygame.Surface]:
        key = (path, cols, rows, scale)
        if key in cls._cache:
            return cls._cache[key]

        sheet = pygame.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        fw, fh = sw // cols, sh // rows

        frames = []
        for row in range(rows):
            for col in range(cols):
                rect = pygame.Rect(col * fw, row * fh, fw, fh)
                frame = sheet.subsurface(rect).copy()
                if scale != 1.0:
                    nw = max(1, int(fw * scale))
                    nh = max(1, int(fh * scale))
                    frame = pygame.transform.smoothscale(frame, (nw, nh))
                frames.append(frame)

        cls._cache[key] = frames
        return frames

    def __init__(
        self,
        screen_cx: float,
        screen_cy: float,
        scale: float = 1.0,
        fps: float = 14.0,
        spritesheet_path: str = "imgs/spell.png",
        cols: int = SHEET_COLS,
        rows: int = SHEET_ROWS,
    ) -> None:
        self._frames = self._load_frames(spritesheet_path, cols, rows, scale)
        self._fps = fps
        self._frame_idx: int = 0
        self._elapsed: float = 0.0
        self.done: bool = False

        fw = self._frames[0].get_width()
        fh = self._frames[0].get_height()
        # top-left so the center lands on (screen_cx, screen_cy)
        self._x = screen_cx - fw / 2
        self._y = screen_cy - fh / 2

    def scroll(self, dx: float) -> None:
        """Shift the effect by dx pixels – call the same way as fish.x -= delta."""
        self._x -= dx

    def update(self, dt: float) -> None:
        if self.done:
            return
        self._elapsed += dt
        frame_dur = 1.0 / self._fps
        while self._elapsed >= frame_dur:
            self._elapsed -= frame_dur
            self._frame_idx += 1
            if self._frame_idx >= len(self._frames):
                self._frame_idx = len(self._frames) - 1
                self.done = True
                break

    def draw(self, surface: pygame.Surface) -> None:
        if self.done:
            return
        surface.blit(self._frames[self._frame_idx], (int(self._x), int(self._y)))


def gif_to_frames():
    gif = Image.open("imgs/x.GIF")
    for i in range(gif.n_frames):
        gif.seek(i)
        gif.save(f"imgs/water_x/frame_{i}.png")