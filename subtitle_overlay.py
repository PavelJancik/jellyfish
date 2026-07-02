"""
subtitle_overlay.py
-------------------
Subtitle overlay for video playback in pygame.

Usage:
    subtitles = SubtitleOverlay(screen_w, screen_h)
    subtitles.load([
        SubtitleCue(start=5.0, end=10.0, text="Pavel Jančík presents"),
        SubtitleCue(start=12.0, end=17.0, text="Story based on true events"),
    ])

    # In the game loop:
    subtitles.update(dt)          # every frame
    subtitles.draw(screen)        # after drawing the video
    subtitles.reset()             # before replaying the video
"""

import pygame
from dataclasses import dataclass
from typing import List, Optional
from engine import load_font


@dataclass
class SubtitleCue:
    """One subtitle line with a time range in seconds."""
    start: float          # start time [s]
    end: float            # end time [s]
    text: str             # subtitle text
    # optional per-cue style overrides:
    font_size: Optional[int] = None
    color: Optional[tuple] = None
    y_position: float = 0.5   # vertical position (0.0 = top, 1.0 = bottom)


class SubtitleOverlay:
    """
    Draws subtitles over any pygame surface.

    Subtitles fade in and fade out smoothly.
    """

    # ── default style ─────────────────────────────────────────────────────────
    DEFAULT_FONT_SIZE   = 40
    DEFAULT_COLOR       = (255, 255, 255)   # white
    SHADOW_COLOR        = (0, 0, 0)         # text shadow
    SHADOW_OFFSET       = (4, 6)
    SHADOW_BLUR_PASSES  = 3                 # number of shadow layers (depth)
    BOTTOM_MARGIN       = 80               # distance from the bottom edge
    FADE_DURATION       = 1             # fade-in / fade-out duration [s]
    LETTER_SPACING_FACTOR = 2              # letter spacing (em spaces inserted)
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self, screen_w: int, screen_h: int):
        """
        screen_w, screen_h  – screen resolution
        Font is loaded via load_font() from engine.py (DynaPuff).
        """
        self.screen_w = screen_w
        self.screen_h = screen_h

        self._cues: List[SubtitleCue] = []
        self._elapsed: float = 0.0          # time since the video started
        self._active: Optional[SubtitleCue] = None
        self._alpha: float = 0.0            # 0.0 - 1.0

    def load(self, cues: List[SubtitleCue]) -> None:
        """Loads the cue list and sorts it by start time."""
        self._cues = sorted(cues, key=lambda c: c.start)

    def reset(self) -> None:
        """Resets the timer – call before each new video playback."""
        self._elapsed = 0.0
        self._active = None
        self._alpha = 0.0

    def update(self, dt: float) -> None:
        """
        Advances the internal clock by dt seconds and determines the active cue.
        dt – delta time in seconds (e.g. clock.tick(60) / 1000)
        """
        self._elapsed += dt
        t = self._elapsed

        current: Optional[SubtitleCue] = None
        for cue in self._cues:
            if cue.start <= t <= cue.end:
                current = cue
                break

        self._active = current

        if current is None:
            self._alpha = 0.0
            return

        cue_len = current.end - current.start
        local_t  = t - current.start

        fade = self.FADE_DURATION
        # guard against very short cues
        if cue_len < fade * 2:
            fade = cue_len / 2

        if local_t < fade:
            self._alpha = local_t / fade
        elif local_t > cue_len - fade:
            self._alpha = (current.end - t) / fade
        else:
            self._alpha = 1.0

        self._alpha = max(0.0, min(1.0, self._alpha))

    def draw(self, surface: pygame.Surface) -> None:
        """Draws the current subtitle onto the surface. Call after drawing the video."""
        if self._active is None or self._alpha <= 0:
            return

        cue   = self._active
        alpha = int(self._alpha * 255)

        font  = self._get_font(cue.font_size or self.DEFAULT_FONT_SIZE)
        color = cue.color or self.DEFAULT_COLOR

        # Insert spaces for the letter-spacing effect
        spaced_text = (" " * self.LETTER_SPACING_FACTOR).join(cue.text.upper())

        # Render text to a temp surface (needed for alpha)
        text_surf = font.render(spaced_text, True, color)
        tw, th    = text_surf.get_size()

        # Position – centered horizontally, vertical per cue.y_position
        x = (self.screen_w - tw) // 2
        y = int(self.screen_h * cue.y_position) - th // 2

        # Shadow – multiple layers for a strong drop-shadow effect ────────────
        shadow_surf = font.render(spaced_text, True, self.SHADOW_COLOR)
        for i in range(1, self.SHADOW_BLUR_PASSES + 1):
            layer = shadow_surf.copy()
            layer.set_alpha(alpha // (i + 1))
            surface.blit(layer,
                         (x + self.SHADOW_OFFSET[0] * i,
                          y + self.SHADOW_OFFSET[1] * i))

        # Text ────────────────────────────────────────────────────────────────
        text_surf.set_alpha(alpha)
        surface.blit(text_surf, (x, y))

    # ── internal ─────────────────────────────────────────────────────────────

    def _get_font(self, size: int) -> pygame.font.Font:
        """Loads the font via load_font() from engine.py (DynaPuff)."""
        return load_font(size)