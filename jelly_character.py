"""
jelly_character.py
==================
A reusable Pygame module for the Jelly jellyfish character.

Sprite sheet layout
-------------------
  • Source file : imgs/Jelly-idle.png
  • Grid        : 5 columns × 5 rows  →  25 frames total
  • Frame size  : 212 × 212 px  (auto-detected at runtime)

Quick-start
-----------
    import pygame
    from jelly_character import JellyCharacter

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock  = pygame.time.Clock()

    jelly = JellyCharacter("imgs/Jelly-idle.png", x=300, y=200)

    running = True
    while running:
        dt = clock.tick(60) / 1000          # seconds since last frame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        jelly.handle_input(keys)
        jelly.update(dt)

        screen.fill((20, 30, 60))
        jelly.draw(screen)
        pygame.display.flip()

    pygame.quit()
"""

from __future__ import annotations

import os
import math
from typing import Optional

import pygame


# ---------------------------------------------------------------------------
# Helper – sprite-sheet slicer
# ---------------------------------------------------------------------------

def load_spritesheet(
    path: str,
    cols: int,
    rows: int,
    scale: float = 1.0,
    make_distant: bool = False,
) -> list[pygame.Surface]:
    """
    Load *path* and slice it into ``cols × rows`` frames.

    Parameters
    ----------
    path         : path to the sprite-sheet image
    cols/rows    : grid dimensions
    scale        : uniform scale factor applied to every frame
    make_distant : if True, applies the same mask to every frame as
                   ``_make_distant`` in ``ambient_fish.py``
                   (darken/desaturate for a more distant layer)

    Returns
    -------
    Ordered list of surfaces, row-major (left→right, top→bottom).
    """
    sheet = pygame.image.load(path).convert_alpha()
    sheet_w, sheet_h = sheet.get_size()
    frame_w = sheet_w // cols
    frame_h = sheet_h // rows

    frames: list[pygame.Surface] = []
    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
            frame = sheet.subsurface(rect).copy()

            if make_distant:
                frame.fill((180, 180, 180, 255), special_flags=pygame.BLEND_RGBA_MULT)

            if scale != 1.0:
                new_w = int(frame_w * scale)
                new_h = int(frame_h * scale)
                frame = pygame.transform.smoothscale(frame, (new_w, new_h))

            frames.append(frame)

    return frames


# ---------------------------------------------------------------------------
# Animation clip descriptor
# ---------------------------------------------------------------------------

class AnimationClip:
    """Describes a looping or one-shot frame range within a frame list."""

    def __init__(
        self,
        name: str,
        frame_indices: list[int],
        fps: float = 10.0,
        loop: bool = True,
    ) -> None:
        self.name = name
        self.frame_indices = frame_indices
        self.fps = fps
        self.loop = loop


# ---------------------------------------------------------------------------
# Animator
# ---------------------------------------------------------------------------

class Animator:
    """Drives frame selection from a clip library."""

    def __init__(self, clips: dict[str, AnimationClip]) -> None:
        self._clips = clips
        self._current: AnimationClip = next(iter(clips.values()))
        self._frame_idx: int = 0          # index into clip.frame_indices
        self._elapsed: float = 0.0
        self.finished: bool = False       # True after a non-looping clip ends

    # ------------------------------------------------------------------
    def play(self, name: str, force_restart: bool = False) -> None:
        """Switch to clip *name* (no-op if already playing unless forced)."""
        if name not in self._clips:
            raise KeyError(f"Animation clip '{name}' not found.")
        if self._current.name == name and not force_restart:
            return
        self._current = self._clips[name]
        self._frame_idx = 0
        self._elapsed = 0.0
        self.finished = False

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        clip = self._current
        if self.finished:
            return

        self._elapsed += dt
        frame_duration = 1.0 / clip.fps

        while self._elapsed >= frame_duration:
            self._elapsed -= frame_duration
            self._frame_idx += 1

            if self._frame_idx >= len(clip.frame_indices):
                if clip.loop:
                    self._frame_idx = 0
                else:
                    self._frame_idx = len(clip.frame_indices) - 1
                    self.finished = True
                    break

    # ------------------------------------------------------------------
    @property
    def current_frame_index(self) -> int:
        """Absolute index into the master frame list."""
        return self._current.frame_indices[self._frame_idx]

    @property
    def current_clip(self) -> str:
        return self._current.name


# ---------------------------------------------------------------------------
# JellyCharacter
# ---------------------------------------------------------------------------

class JellyCharacter:
    """
    A fully-animated jellyfish character for a 2-D Pygame game.

    Attributes
    ----------
    x, y        : world position (top-left of the sprite)
    speed       : pixels per second for keyboard movement
    flip_x      : mirror horizontally when moving left
    bob_amplitude / bob_frequency : idle floating effect

    Public methods
    --------------
    handle_input(keys, joystick=None) – read pygame key state + optional joystick each frame
    update(dt)          – advance physics + animation
    draw(surface)       – blit current frame (+ optional debug rect)
    play(clip_name)     – manually trigger an animation clip

    Signals / callbacks
    -------------------
    Set ``on_animation_end`` to a callable; it receives the clip name
    when a non-looping clip completes.
    """

    # Sprite-sheet constants
    SHEET_COLS = 5
    SHEET_ROWS = 5
    TOTAL_FRAMES = SHEET_COLS * SHEET_ROWS  # 25

    def __init__(
        self,
        spritesheet_path: str,
        x: float = 0.0,
        y: float = 0.0,
        scale: float = 1.0,
        idle_fps: float = 8.0,
        speed: float = 800.0,
        bob_amplitude: float = 6.0,
        bob_frequency: float = 1.2,
        debug: bool = False,
        move_spritesheet_path: str = "imgs/jelly_blue_move.png",
    ) -> None:
        """
        Parameters
        ----------
        spritesheet_path : path to Jelly-idle.png
        x, y             : initial screen position
        scale            : resize factor (1.0 = native 212 px frames)
        idle_fps         : playback speed for the idle animation
        speed            : movement speed in px/s
        bob_amplitude    : vertical bob in pixels
        bob_frequency    : bob cycles per second
        debug                 : draw collision rect outline
        move_spritesheet_path : path to jelly_blue_move.png (used while moving)
        """
        if not os.path.isfile(spritesheet_path):
            raise FileNotFoundError(f"Sprite sheet not found: {spritesheet_path}")

        self._frames = load_spritesheet(
            spritesheet_path, self.SHEET_COLS, self.SHEET_ROWS, scale=scale
        )

        # Move sprite sheet – all 25 frames from jelly_blue_move.png
        if os.path.isfile(move_spritesheet_path):
            self._move_frames = load_spritesheet(
                move_spritesheet_path, self.SHEET_COLS, self.SHEET_ROWS, scale=scale
            )
        else:
            self._move_frames = self._frames  # fallback

        # Dedicated animator for the move sheet (all 25 frames, loops)
        self._move_animator = Animator({
            "move": AnimationClip(
                "move",
                list(range(self.TOTAL_FRAMES)),
                fps=idle_fps * 1.4,
                loop=True,
            )
        })
        self._move_animator.play("move")

        # Build animation clips
        # ── Idle  : all 25 frames  (rows 0–4, left→right)
        clips = {
            "idle": AnimationClip(
                "idle",
                list(range(self.TOTAL_FRAMES)),
                fps=idle_fps,
                loop=True,
            ),
        }
        self._animator = Animator(clips)
        self._animator.play("idle")

        # Position & movement
        self.x: float = x
        self.y: float = y
        self.speed: float = speed
        self._vel_x: float = 0.0
        self._vel_y: float = 0.0
        self.flip_x: bool = False
        self._is_moving: bool = False

        # Idle bob
        self.bob_amplitude: float = bob_amplitude
        self.bob_frequency: float = bob_frequency
        self._bob_timer: float = 0.0
        self._bob_offset: float = 0.0

        # Frame size (after scaling)
        self._frame_w = self._frames[0].get_width()
        self._frame_h = self._frames[0].get_height()

        # Collision rect (80 % of frame, centred)
        self._hitbox_margin_x = int(self._frame_w * 0.10)
        self._hitbox_margin_y = int(self._frame_h * 0.05)

        # Optional callback
        self.on_animation_end: Optional[callable] = None

        self.debug: bool = debug

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def rect(self) -> pygame.Rect:
        """Bounding rect in world space (top-left = self.x, self.y)."""
        return pygame.Rect(int(self.x), int(self.y), self._frame_w, self._frame_h)

    @property
    def hitbox(self) -> pygame.Rect:
        """Smaller collision rect, centred on the sprite."""
        mx, my = self._hitbox_margin_x, self._hitbox_margin_y
        return pygame.Rect(
            int(self.x) + mx,
            int(self.y) + my,
            self._frame_w - 2 * mx,
            self._frame_h - 2 * my,
        )

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self._frame_w / 2, self.y + self._frame_h / 2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, clip_name: str, force_restart: bool = False) -> None:
        """Manually switch to an animation clip by name."""
        self._animator.play(clip_name, force_restart)

    # Joystick dead zone – values near zero are ignored
    JOYSTICK_DEADZONE: float = 0.15

    def handle_input(
        self,
        keys: pygame.key.ScancodeWrapper,
        joystick: Optional[pygame.joystick.JoystickType] = None,
    ) -> None:
        """
        Map arrow keys / WASD to velocity, plus optional joystick support.

        Parameters
        ----------
        keys     : pygame key state (pygame.key.get_pressed())
        joystick : optional pygame.joystick.Joystick instance.
                   Left stick – axis 0 (horizontal) and axis 1 (vertical).
                   Ignored if None.

        Call once per frame *before* ``update()``.
        """
        vx, vy = 0.0, 0.0

        # --- keyboard ---
        if keys[pygame.K_LEFT]:
            vx -= self.speed
        if keys[pygame.K_RIGHT]:
            vx += self.speed
        if keys[pygame.K_UP]:
            vy -= self.speed
        if keys[pygame.K_DOWN]:
            vy += self.speed

        # Normalise diagonal movement (keyboard)
        if vx != 0 and vy != 0:
            factor = 1.0 / math.sqrt(2)
            vx *= factor
            vy *= factor

        # --- joystick (left stick, axis 0 = X, axis 1 = Y) ---
        if joystick is not None:
            raw_x = joystick.get_axis(0)
            raw_y = joystick.get_axis(1)

            # Dead zone – eliminates physical joystick drift
            if abs(raw_x) < self.JOYSTICK_DEADZONE:
                raw_x = 0.0
            if abs(raw_y) < self.JOYSTICK_DEADZONE:
                raw_y = 0.0

            # Joystick overrides keyboard only when deflected
            if raw_x != 0.0 or raw_y != 0.0:
                # Normalize: diagonals can push the stick past magnitude 1.0
                magnitude = math.sqrt(raw_x ** 2 + raw_y ** 2)
                if magnitude > 1.0:
                    raw_x /= magnitude
                    raw_y /= magnitude
                vx = raw_x * self.speed
                vy = raw_y * self.speed

        self._vel_x = vx
        self._vel_y = vy

        # Move spritesheet only kicks in once the joystick passes 0.5.
        # Keyboard movement always activates the move sheet.
        if joystick is not None:
            joy_x = joystick.get_axis(0)
            joy_y = joystick.get_axis(1)
            joy_magnitude = math.sqrt(joy_x ** 2 + joy_y ** 2)
            self._is_moving = abs(joy_x) > 0.5
        else:
            self._is_moving = vx != 0 or vy != 0

        # Flip sprite when moving left
        if vx < 0:
            self.flip_x = True
        elif vx > 0:
            self.flip_x = False

        # _animator (idle) always ticks in the background; draw() picks the
        # visible frame set based on _is_moving.

    def update(self, dt: float) -> None:
        """
        Advance position, bob, and animation.

        Parameters
        ----------
        dt : seconds elapsed since last frame (use ``clock.tick(fps)/1000``)
        """
        # Movement
        self.x += self._vel_x * dt
        self.y += self._vel_y * dt

        # Vertical bob (only while not actively moving vertically)
        self._bob_timer += dt
        self._bob_offset = self.bob_amplitude * math.sin(
            2 * math.pi * self.bob_frequency * self._bob_timer
        )

        # Animation
        self._move_animator.update(dt)  # always ticking so move anim is continuous

        prev_finished = self._animator.finished
        self._animator.update(dt)
        if self._animator.finished and not prev_finished:
            if self.on_animation_end:
                self.on_animation_end(self._animator.current_clip)

    def draw(
        self,
        surface: pygame.Surface,
        camera_offset: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """
        Blit the current frame onto *surface*.

        Parameters
        ----------
        surface       : render target
        camera_offset : (ox, oy) subtracted from world position – useful
                        for scrolling cameras.
        """
        if self._is_moving:
            frame = self._move_frames[self._move_animator.current_frame_index]
        else:
            frame = self._frames[self._animator.current_frame_index]

        if self.flip_x:
            frame = pygame.transform.flip(frame, True, False)

        draw_x = int(self.x - camera_offset[0])
        draw_y = int(self.y - camera_offset[1] + self._bob_offset)

        surface.blit(frame, (draw_x, draw_y))

        if self.debug:
            # Draw bounding rect (cyan) and hitbox (yellow)
            r = self.rect.move(-camera_offset[0], -camera_offset[1] + self._bob_offset)
            h = self.hitbox.move(-camera_offset[0], -camera_offset[1] + self._bob_offset)
            pygame.draw.rect(surface, (0, 255, 255), r, 1)
            pygame.draw.rect(surface, (255, 255, 0), h, 1)

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def clamp_to_screen(self, screen_w: int, screen_h: int) -> None:
        """Keep the character fully inside the screen rectangle."""
        self.x = max(0.0, min(self.x, screen_w - self._frame_w))
        self.y = max(0.0, min(self.y, screen_h - self._frame_h))

    def set_position(self, x: float, y: float) -> None:
        self.x, self.y = x, y

    def move_to_center(self, cx: float, cy: float) -> None:
        """Position so that the sprite centre lands at (cx, cy)."""
        self.x = cx - self._frame_w / 2
        self.y = cy - self._frame_h / 2

    def collides_with_rect(self, other: pygame.Rect) -> bool:
        """Pixel-friendly collision using the hitbox."""
        return self.hitbox.colliderect(other)

    @property
    def frame_size(self) -> tuple[int, int]:
        """(width, height) of a single scaled frame."""
        return self._frame_w, self._frame_h

    @property
    def available_clips(self) -> list[str]:
        return list(self._animator._clips.keys())

    def __repr__(self) -> str:
        return (
            f"JellyCharacter(pos=({self.x:.1f},{self.y:.1f}), "
            f"clip={self._animator.current_clip!r}, "
            f"frame={self._animator.current_frame_index})"
        )