"""
npc_character.py
================
Standing NPC character module for Underwater Adventure.

The NPC plays an idle animation with a gentle vertical bob and is
anchored to the world – it scrolls along with the background.

Usage in game_scene.py
-----------------------
    from npc_character import NPCCharacter

    npc = NPCCharacter("imgs/whale.png", scale=0.2, flip_x=True)

    # after loading the background – place at scene end, center vertically:
    npc.place_at_scene_end(self.bg_w)
    npc.center_on_screen(screen_h)

    # in GameScene.update:
    self.npc.sync_with_background(self.bg_x)
    self.npc.update(dt)

    # in GameScene.draw:
    self.npc.draw(surface)
"""

from __future__ import annotations

import os
import math

import pygame

from jelly_character import (
    AnimationClip,
    Animator,
    load_spritesheet,
)

# "turtle": "Rising ocean temperatures are killing the coral reefs. Locate the dying corals and save them, before it's too late!",
# "manta":  "The ocean is flooded with trash. Help us get rid of it!",
# "whale": "Overfishing is devastating these waters. Save the fish and set them free!",
# "final": "Oh, look at that. What a horrible view. Let's clean the ocean!"

class NPCCharacter:
    """
    Standing NPC character using the same spritesheet format as Jelly.

    The NPC isn't driven by its own key input – it only moves passively
    along with the scrolling background (via ``sync_with_background``).

    Parameters
    ----------
    spritesheet_path : path to the PNG spritesheet (5 x 5 frames, 212 x 212 px)
    world_x          : X position in the background's coordinate system
    y                : top-left Y position on screen
    scale            : frame scaling (1.0 = native 212 px)
    idle_fps         : idle animation playback speed
    bob_amplitude    : vertical bob amplitude in pixels
    bob_frequency    : bob frequency in cycles per second
    flip_x           : mirror the character horizontally
    debug            : draw a bounding rect (for debugging)
    """

    SHEET_COLS = 5
    SHEET_ROWS = 5

    # Default margin from the scene's right edge (pixels, after scaling)
    DEFAULT_END_MARGIN: int = 40

    def __init__(
        self,
        spritesheet_path: str,
        world_x: float = 0.0,
        y: float = 0.6,
        scale: float = 1.0,
        idle_fps: float = 8.0,
        bob_amplitude: float = 5.0,
        bob_frequency: float = 0.9,
        flip_x: bool = False,
        debug: bool = False,
    ) -> None:
        if not os.path.isfile(spritesheet_path):
            raise FileNotFoundError(f"Sprite sheet not found: {spritesheet_path}")

        # --- Frames ---
        self._frames = load_spritesheet(
            spritesheet_path, self.SHEET_COLS, self.SHEET_ROWS, scale=scale
        )
        self._frame_w, self._frame_h = self._frames[0].get_size()

        # --- Idle animation (single clip) ---
        self._animator = Animator({
            "idle": AnimationClip(
                "idle",
                list(range(25)),
                fps=idle_fps,
                loop=True,
            ),
        })
        self._animator.play("idle")

        # --- Position ---
        self.world_x: float = world_x
        self.y: float = y
        self._screen_x: float = world_x

        # --- Bob effect ---
        self.bob_amplitude = bob_amplitude
        self.bob_frequency = bob_frequency
        self._bob_timer: float = 0.0
        self._bob_offset: float = 0.0

        # --- Visual ---
        self.flip_x = flip_x
        self.debug = debug

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    def place_at_scene_end(self, bg_w: int, margin: int | None = None) -> None:
        """
        Places the NPC at the end of the scene (right edge of the background).

        world_x is set so the sprite's right edge sits ``margin`` pixels
        from the background's right edge. Works correctly at any scale –
        a larger sprite shifts further left but always stays fully visible.

        Parameters
        ----------
        bg_w   : background width in pixels (GameScene.bg_w)
        margin : gap from the right edge; None -> DEFAULT_END_MARGIN
        """
        if margin is None:
            margin = self.DEFAULT_END_MARGIN
        self.world_x = float(max(0.0, bg_w - self._frame_w - margin))

    def center_on_screen(self, screen_h: int, percent: float) -> None:
        """
        Centers the NPC vertically on the screen.

        Sets ``y`` so the sprite's center matches the target screen
        position, independent of frame height (scale).

        Parameters
        ----------
        screen_h : screen height in pixels
        percent  : screen-height fraction to center the NPC on (0.0 = top, 0.5 = middle, 1.0 = bottom)
        """
        self.y = float(screen_h * percent - self._frame_h / 2)

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------

    def sync_with_background(self, bg_x: float) -> None:
        """
        Updates screen_x based on the current background scroll offset.

        Call every frame in GameScene.update() before update().

        Parameters
        ----------
        bg_x : current self.bg_x from GameScene (negative = scrolled left)
        """
        self._screen_x = self.world_x + bg_x

    def update(self, dt: float) -> None:
        """Advances the animation and the bob effect."""
        self._bob_timer += dt
        self._bob_offset = self.bob_amplitude * math.sin(
            2 * math.pi * self.bob_frequency * self._bob_timer
        )
        self._animator.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Draws the NPC onto the surface."""
        frame = self._frames[self._animator.current_frame_index]

        if self.flip_x:
            frame = pygame.transform.flip(frame, True, False)

        draw_x = int(self._screen_x)
        draw_y = int(self.y + self._bob_offset)

        surface.blit(frame, (draw_x, draw_y))

        if self.debug:
            pygame.draw.rect(
                surface,
                (255, 80, 80),
                pygame.Rect(draw_x, draw_y, self._frame_w, self._frame_h),
                2,
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def screen_rect(self) -> pygame.Rect:
        """Current NPC rect in screen coordinates."""
        return pygame.Rect(
            int(self._screen_x),
            int(self.y + self._bob_offset),
            self._frame_w,
            self._frame_h,
        )

    @property
    def frame_size(self) -> tuple[int, int]:
        return self._frame_w, self._frame_h

    def __repr__(self) -> str:
        return (
            f"NPCCharacter(world_x={self.world_x:.0f}, y={self.y:.0f})"
        )