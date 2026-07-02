"""
ambient_fish.py
===============
Decorative fish for the Underwater Adventure game scene.

Contains:
  - AmbientFish  – a single decorative fish swimming across the screen
  - load_ambient_fishes  – factory function; loads images from a folder and creates instances
"""

from __future__ import annotations

import math
import os
import random

import pygame

from jelly_character import (
    AnimationClip,
    Animator,
    load_spritesheet,
)


# ---------------------------------------------------------------------------
# Helper function – darken/desaturate for a more distant layer
# ---------------------------------------------------------------------------

def _make_distant(surface: pygame.Surface) -> pygame.Surface:
    result = surface.copy()
    result.fill((180, 180, 180, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return result


# ---------------------------------------------------------------------------
# Class – a single decorative fish
# ---------------------------------------------------------------------------

class AmbientFish:
    """
    A simple decorative fish swimming across the screen.

    Parameters
    ---------
    image      : loaded pygame.Surface (original, not copied)
    screen_w   : screen width
    screen_h   : screen height
    scale      : fish size multiplier (0.3 – 1.2)
    speed      : horizontal speed in px/s
    y          : initial Y position of the fish center
    direction  : +1 = left-to-right, -1 = right-to-left
    """

    # Fish size as a fraction of screen height (3-5% of screen_h)
    SIZE_MIN_RATIO = 0.03
    SIZE_MAX_RATIO = 0.04
    # Gentle vertical wobble
    WAVE_AMP_MIN  = 5.0    # px
    WAVE_AMP_MAX  = 10.0
    WAVE_FREQ_MIN = 0.1    # Hz
    WAVE_FREQ_MAX = 0.4

    def __init__(
        self,
        image: pygame.Surface,
        screen_w: int,
        screen_h: int,
        *,
        scale: float | None = None,
        speed: float,
        y: float | None = None,
        direction: int | None = None,
        start_offscreen: bool = True,
        front_layer: bool = False,
        trapped: bool = False,
        free_image: pygame.Surface | None = None,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.speed: float = speed
        self.trapped: bool = trapped
        self._free_image_orig: pygame.Surface | None = free_image
        self._freed: bool = False
        # Direction the _free_surf was last prepared for (to detect if a flip is needed)
        self._free_surf_direction: int = 1  # set below once direction is chosen

        # Random values if not provided
        self.direction: int = direction if direction is not None else random.choice((-1, 1))
        
        # Size: target fish height = 3-5% of screen height * scale
        target_h = random.uniform(
            self.SIZE_MIN_RATIO * screen_h * scale,
            self.SIZE_MAX_RATIO * screen_h * scale,
        )
        orig_w, orig_h = image.get_size()
        scale_val = target_h / orig_h if orig_h > 0 else 1.0

        # Wobble (sinusoidal vertical motion)
        self._wave_amp:   float = random.uniform(self.WAVE_AMP_MIN,  self.WAVE_AMP_MAX)
        self._wave_freq:  float = random.uniform(self.WAVE_FREQ_MIN, self.WAVE_FREQ_MAX)
        self._wave_phase: float = random.uniform(0, 2 * math.pi)   # different phase = unsynced motion
        self._time: float = 0.0

        # Image scaling
        new_w = max(1, int(orig_w * scale_val))
        new_h = max(1, int(orig_h * scale_val))
        scaled = pygame.transform.scale(image, (new_w, new_h))

        # Mirror based on direction:
        # We assume the source image faces right (+1).
        # If the fish swims left, we mirror it.
        if self.direction == -1:
            scaled = pygame.transform.flip(scaled, True, False)

        self._surf: pygame.Surface = scaled
        self.w = new_w
        self.h = new_h

        # Prepare a surface for the freed fish (same size as trapped)
        # _free_surf is always prepared for direction == +1 (head right).
        # The flip is applied later in free() or _respawn() based on the current direction.
        if self._free_image_orig is not None:
            free_scaled = pygame.transform.scale(self._free_image_orig, (new_w, new_h))
            # Store without flip (base = direction +1); flip applied later in free()
            self._free_surf: pygame.Surface = free_scaled
        else:
            # Fallback: same image as trapped, also without flip
            base_scaled = pygame.transform.scale(image, (new_w, new_h))
            self._free_surf = base_scaled
        self._free_surf_direction: int = 1  # _free_surf is always stored for direction +1

        # Initial position
        self.min_y = int(screen_h * 0.5)
        self.max_y = int(screen_h * 0.9)
        self.y_center: float = y if y is not None else random.uniform(self.min_y, self.max_y)
        self.x: float = self._spawn_x(start_offscreen)

    # ------------------------------------------------------------------

    def _spawn_x(self, offscreen: bool = True) -> float:
        """Returns the initial X position based on direction."""
        margin = self.w + 20
        if offscreen:
            if self.direction == 1:
                return float(-margin)               # enters from the left
            else:
                return float(self.screen_w + margin)  # enters from the right
        else:
            # Random position anywhere on screen (for the first spawn)
            return random.uniform(0, self.screen_w * 2)

    def get_rect(self) -> pygame.Rect:
        """Returns the fish's current rect for overlap detection."""
        wave_y = self._wave_amp * math.sin(
            2 * math.pi * self._wave_freq * self._time + self._wave_phase
        )
        draw_y = int(self.y_center + wave_y - self.h / 2)
        return pygame.Rect(int(self.x), draw_y, self.w, self.h)

    def overlaps_jelly(self, jelly_rect: pygame.Rect) -> bool:
        """Returns True if this fish overlaps with Jelly."""
        return self.trapped and not self._freed and self.get_rect().colliderect(jelly_rect)

    @property
    def is_trapped(self) -> bool:
        """True if the fish is still trapped (trapped and not yet freed)."""
        return self.trapped and not self._freed

    def free(self) -> None:
        """Frees the fish – switches its image to free.png and makes sure it swims head-first."""
        if self.trapped and not self._freed:
            self._freed = True
            # _free_surf is stored for direction +1. If the fish is currently going left,
            # we need to flip it so the head faces the direction of travel.
            if self.direction == -1:
                self._surf = pygame.transform.flip(self._free_surf, True, False)
            else:
                self._surf = self._free_surf

    def _respawn(self) -> None:
        """The fish left the screen – respawn it on the opposite side."""
        self.direction   = -self.direction
        self.speed       = self.speed
        self._wave_amp   = random.uniform(self.WAVE_AMP_MIN,  self.WAVE_AMP_MAX)
        self._wave_freq  = random.uniform(self.WAVE_FREQ_MIN, self.WAVE_FREQ_MAX)
        self._wave_phase = random.uniform(0, 2 * math.pi)
        self._time       = 0.0
        self.y_center    = random.uniform(self.max_y, self.min_y)
        self.x           = self._spawn_x(offscreen=True)

        # After changing direction, recompute surf for the new direction.
        # _free_surf is always stored as "head right" (direction +1).
        # Build the correct _surf for the new direction.
        if self._freed:
            # Freed fish: use free_surf, flip if going left
            if self.direction == -1:
                self._surf = pygame.transform.flip(self._free_surf, True, False)
            else:
                self._surf = self._free_surf
        else:
            # Trapped fish: just flip the current surf
            self._surf = pygame.transform.flip(self._surf, True, False)

    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._time += dt
        self.x += self.direction * self.speed * dt

        # Check if it left the screen
        if self.direction == 1 and self.x > self.screen_w + self.w + 20:
            self._respawn()
        elif self.direction == -1 and self.x < -(self.w + 20):
            self._respawn()

    def draw(self, surface: pygame.Surface) -> None:
        wave_y = self._wave_amp * math.sin(
            2 * math.pi * self._wave_freq * self._time + self._wave_phase
        )
        draw_y = int(self.y_center + wave_y - self.h / 2)
        surface.blit(self._surf, (int(self.x), draw_y))


# ---------------------------------------------------------------------------
# Factory function – loads fish from the imgs/fishes folder
# ---------------------------------------------------------------------------

def load_ambient_fishes(
    screen_w: int,
    screen_h: int,
    folder: str = "imgs/fishes",
    count_per_image: int = 3,
    front_layer: bool = False,
    trapped: bool = False,
) -> list[AmbientFish]:
    """
    Scans the `folder`, loads all PNG/JPG images and creates
    `count_per_image` AmbientFish instances per image.

    Returns an empty list if the folder doesn't exist or is empty.
    """
    fishes: list[AmbientFish] = []

    if not os.path.isdir(folder):
        print(f"[AmbientFish] Folder '{folder}' not found – no fish will be shown.")
        return fishes

    extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    image_paths = sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in extensions
    )

    if not image_paths:
        print(f"[AmbientFish] No images in folder '{folder}'.")
        return fishes

    # Folder with the free versions of the fish (same filename, different folder)
    free_folder = "imgs/fishes"

    for path in image_paths:
        try:
            raw = pygame.image.load(path).convert_alpha()
        except pygame.error as exc:
            print(f"[AmbientFish] Failed to load '{path}': {exc}")
            continue

        # For trapped fish, look for a matching file in imgs/fishes
        free_image: pygame.Surface | None = None
        if trapped:
            filename = os.path.basename(path)
            free_path = os.path.join(free_folder, filename)
            if os.path.isfile(free_path):
                try:
                    free_image = pygame.image.load(free_path).convert_alpha()
                except pygame.error as exc:
                    print(f"[AmbientFish] Failed to load '{free_path}': {exc}")
            else:
                print(f"[AmbientFish] Free version '{free_path}' not found – fish image stays unchanged.")

        for _ in range(count_per_image):
            size = 1
            if "small" in path.lower(): size *= 0.9
            if "mid"   in path.lower(): size *= 1.5
            if "big"   in path.lower(): size *= 2.8
            if front_layer: size *= 1.2
            else:           size *= 0.8

            fishes.append(
                AmbientFish(
                    raw if front_layer else _make_distant(raw),
                    screen_w,
                    screen_h,
                    start_offscreen=False,   # first spawn anywhere on screen
                    scale=size,
                    speed=random.uniform(30, 60) if front_layer else random.uniform(20, 40),
                    trapped=trapped,
                    free_image=free_image,
                )
            )

    return fishes


# ---------------------------------------------------------------------------
# Factory function – spawn a single freed fish at a specific position
# ---------------------------------------------------------------------------

def make_freed_fish(
    screen_w: int,
    screen_h: int,
    world_x: float,
    y: float,
    free_folder: str = "imgs/fishes",
    bg_x: float = 0.0,
    trap_img_path: str | None = None
) -> "AmbientFish | None":
    """
    Creates a single ``AmbientFish`` at the position of a freed trap.

    Intended for use as the ``on_free`` callback in ``load_objects``::

        freed: list[AmbientFish] = []

        def spawn_freed(wx: float, wy: float) -> None:
            fish = make_freed_fish(screen_w, screen_h, wx, wy, bg_x=bg_x)
            if fish:
                freed.append(fish)

        objects = load_objects("whale", screen_w, screen_h, on_free=spawn_freed)

        # In the game loop, same as the other fish:
        for fish in freed:
            fish.update(dt)
            fish.draw(surface)

    The fish spawns directly at the trap's screen coordinate and swims
    toward the direction closer to the screen center (so it doesn't vanish immediately).

    Parameters
    ----------
    screen_w   : screen width
    screen_h   : screen height
    world_x    : absolute X position of the trap in the game world
    y          : Y position of the trap on screen
    free_folder: folder with the free versions of the fish (``imgs/fishes``)
    bg_x       : current background offset (to convert world_x -> screen_x)
    trap_img_path: path to the trap image being freed (used to find the matching free-fish image)
    Returns
    -------
    AmbientFish, or None if no image could be loaded.
    """
    # Look for the free version of the fish in imgs/fishes (same filename, different folder)
    filename = os.path.basename(trap_img_path)
    free_path = os.path.join(free_folder, filename)

    raw: pygame.Surface | None = None
    if os.path.isfile(free_path):
        try:
            raw = pygame.image.load(free_path).convert_alpha()
        except pygame.error as exc:
            print(f"[AmbientFish] make_freed_fish: cannot load '{free_path}': {exc}")
    else:
        print(f"[AmbientFish] make_freed_fish: free version '{free_path}' not found.")

    if raw is None:
        return None

    # Convert to screen X to pick a direction
    screen_x = world_x + bg_x

    size = 1.2
    if "small" in free_path.lower(): size *= 1.2
    if "mid"   in free_path.lower(): size *= 1.7
    if "big"   in free_path.lower(): size *= 2.0

    fish = AmbientFish(
        raw,
        screen_w,
        screen_h,
        scale=size,
        speed=random.uniform(90, 120),
        y=y,                    # y is the trap center (passed from the on_free callback)
        direction=random.choice([-1, 1]),
        start_offscreen=False,
        trapped=True,           # allows calling free() and switching to free_image
        free_image=raw,         # raw is already the free fish – free() switches to the same image
        front_layer=True,
    )

    # Set X to the trap center, subtract half the fish width
    fish.x = screen_x - fish.w / 2

    # Immediately switch to the "free" image
    fish.free()

    return fish

# ---------------------------------------------------------------------------
# Animated decorative fish (5x5 sprite sheet)
# ---------------------------------------------------------------------------

class AnimatedAmbientFish(AmbientFish):
    """
    A decorative fish with sprite-sheet animation (same format as
    ``NPCCharacter`` – 5x5 frames, e.g. 212x212 px).

    Unlike ``AmbientFish``, which draws a single static image, this
    class plays a looping "swim" animation – the fish is always
    shown in motion (no "idle"/"trapped"/"free" state).

    Parameters
    ---------
    spritesheet_path : path to the PNG spritesheet (SHEET_COLS x SHEET_ROWS frames)
    screen_w, screen_h, scale, speed, y, direction, start_offscreen,
    fps : "swim" animation playback speed (frames per second)
    """

    SHEET_COLS = 5
    SHEET_ROWS = 5

    def __init__(
        self,
        spritesheet_path: str,
        screen_w: int,
        screen_h: int,
        *,
        scale: float | None = None,
        speed: float,
        y: float | None = None,
        direction: int | None = None,
        start_offscreen: bool = True,
        fps: float = 8.0,
    ) -> None:
        if not os.path.isfile(spritesheet_path):
            raise FileNotFoundError(f"Sprite sheet nenalezen: {spritesheet_path}")

        # Load all sprite-sheet frames unscaled (scale=1.0) –
        # final size is resolved the same way as AmbientFish, based
        # screen_h a parametru `scale`.
        raw_frames = load_spritesheet(
            spritesheet_path, self.SHEET_COLS, self.SHEET_ROWS, scale=1.0, make_distant=True if "whale_shark" in spritesheet_path else False
    )

        # Init via AmbientFish – only the first frame is used
        # to compute size (self.w/self.h), position, wobble, etc.
        super().__init__(
            raw_frames[0],
            screen_w,
            screen_h,
            scale=scale,
            speed=speed,
            y=y,
            direction=direction,
            start_offscreen=start_offscreen,
            front_layer=True,
            trapped=False,
            free_image=None,
        )

        # Scale all animation frames to the final size (self.w x self.h).
        # Stored as the "base" set for direction +1 (head right).
        self._frames_base: list[pygame.Surface] = [
            pygame.transform.scale(frame, (self.w, self.h)) for frame in raw_frames
        ]

        # Animator with a single, looping "swim" clip over all frames.
        self._animator = Animator({
            "swim": AnimationClip(
                "swim",
                list(range(len(self._frames_base))),
                fps=fps,
                loop=True,
            ),
        })
        self._animator.play("swim")

        # Frames for the current direction (mirrored if the fish swims left).
        self._frames: list[pygame.Surface] = self._build_frames_for_direction(self.direction)
        self._surf = self._frames[0]

    # ------------------------------------------------------------------

    def _build_frames_for_direction(self, direction: int) -> list[pygame.Surface]:
        """Returns the frame set mirrored per ``direction`` (+1 = head right)."""
        if direction == -1:
            return [pygame.transform.flip(frame, True, False) for frame in self._frames_base]
        return list(self._frames_base)

    def _respawn(self) -> None:
        """Respawn on the opposite side – frame mirroring must be recomputed too."""
        super()._respawn()
        self._frames = self._build_frames_for_direction(self.direction)

    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        super().update(dt)
        self._animator.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        wave_y = self._wave_amp * math.sin(
            2 * math.pi * self._wave_freq * self._time + self._wave_phase
        )
        draw_y = int(self.y_center + wave_y - self.h / 2)
        frame = self._frames[self._animator.current_frame_index]
        surface.blit(frame, (int(self.x), draw_y))


# ---------------------------------------------------------------------------
# Factory function – loads animated fish from sprite-sheet folders
# ---------------------------------------------------------------------------

def load_animated_ambient_fishes(
    screen_w: int,
    screen_h: int,
    folder: str = "imgs/fishes_animated",
    count_per_image: int = 3,
    fps: float = 12.0,
    size: float = 3.0,
) -> list[AnimatedAmbientFish]:
    """
    Scans the `folder`, loads all PNG sprite sheets (5x5 frames)
    and creates `count_per_image` ``AnimatedAmbientFish`` instances per
    sprite sheet.

    Returns an empty list if the folder doesn't exist or is empty.
    """
    fishes: list[AnimatedAmbientFish] = []

    if not os.path.isdir(folder):
        print(f"[AnimatedAmbientFish] Folder '{folder}' not found – no fish will be shown.")
        return fishes

    sheet_paths = sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() == ".png"
    )

    if not sheet_paths:
        print(f"[AnimatedAmbientFish] No sprite sheets in folder '{folder}'.")
        return fishes

    for path in sheet_paths:     
        for _ in range(count_per_image):
            try:
                fishes.append(
                    AnimatedAmbientFish(
                        path,
                        screen_w,
                        screen_h,
                        start_offscreen=False,   # first spawn anywhere on screen
                        scale=size,
                        speed=30 if 'whale_shark' in path else random.uniform(70, 120),
                        fps=fps,
                    )
                )
            except FileNotFoundError as exc:
                print(f"[AnimatedAmbientFish] {exc}")

    return fishes