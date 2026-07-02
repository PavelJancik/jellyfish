"""
interactive_object.py
=====================
Interactive-object module for Underwater Adventure.

Object types
------------
  • "trash"  – litter; disappears on interaction (fade-out)
  • "coral"  – dead coral; shown in grayscale; interacting removes
               the grayscale filter (the coral "comes back to life")
  • "trap"   – a trap holding a fish; interacting triggers a fade-out
               and calls the ``on_free`` callback, which spawns an AmbientFish

Position in the game world
---------------------------
Each object has ``world_x`` – its absolute X position within the background.
When drawn, it's converted to screen coordinates using ``bg_x`` (the
background offset passed in from GameScene), same as NPCs.

Usage in game_scene.py
-----------------------
    from interactive_object import InteractiveObject, load_objects

    # Init (once at scene start)
    objects = load_objects("turtle", screen_w, screen_h)   # returns corals
    objects = load_objects("manta",  screen_w, screen_h)   # returns trash
    objects = load_objects("whale",  screen_w, screen_h,   # returns traps
                           on_free=spawn_fish_callback)

    # Callback for spawning a fish (called when freed from a trap)
    # def spawn_fish_callback(world_x: float, y: float) -> None: ...

    # In the game loop
    for obj in objects:
        obj.update(dt, bg_x)

    for obj in objects:
        obj.draw(surface)

    # On space bar / joystick button press
    jelly_rect = pygame.Rect(int(jelly.x), int(jelly.y), fw, fh)
    for obj in objects:
        if obj.try_interact(jelly_rect):
            # Successful interaction (task completed) -> play
            # imgs/jelly_blue_cast.png on Jelly once. On failure (moving away
            # from the object or failing the task) try_interact returns False
            # and nothing plays.
            jelly.play_cast()
"""

from __future__ import annotations

import os
from typing import Callable

import pygame


# ---------------------------------------------------------------------------
# Helper – grayscale filter
# ---------------------------------------------------------------------------

def _to_grayscale(surface: pygame.Surface) -> pygame.Surface:
    """Returns a new Surface with a grayscale filter applied."""
    gray = pygame.Surface(surface.get_size(), flags=pygame.SRCALPHA)
    for x in range(surface.get_width()):
        for y in range(surface.get_height()):
            r, g, b, a = surface.get_at((x, y))
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            gray.set_at((x, y), (lum, lum, lum, a))
    return gray


def _to_grayscale_fast(surface: pygame.Surface) -> pygame.Surface:
    """
    Faster grayscale filter using pygame.surfarray.
    Requires numpy (installed with most pygame distributions).
    Falls back to pixel-by-pixel if numpy is missing.
    """
    try:
        import numpy as np
        arr = pygame.surfarray.array3d(surface)          # shape (W, H, 3)
        alpha = pygame.surfarray.array_alpha(surface)    # shape (W, H)
        lum = (0.299 * arr[:, :, 0] +
               0.587 * arr[:, :, 1] +
               0.114 * arr[:, :, 2]).astype(np.uint8)
        gray_arr = np.stack([lum, lum, lum], axis=2)
        gray = pygame.surfarray.make_surface(gray_arr)
        gray = gray.convert_alpha()
        pygame.surfarray.pixels_alpha(gray)[:] = alpha
        return gray
    except ImportError:
        return _to_grayscale(surface)


# ---------------------------------------------------------------------------
# InteractiveObject
# ---------------------------------------------------------------------------

class InteractiveObject:
    """
    Interactive object – trash, dead coral, or a trap holding a fish.

    Parameters
    ----------
    kind      : "trash", "coral", or "trap"
    image     : loaded Surface (original color)
    world_x   : X position in background coordinates (same logic as NPC)
    y         : Y position on screen (fixed)
    scale     : image scale
    on_free   : callback called when the fish is freed from the trap;
                signature: ``(world_x: float, y: float) -> None``
                (only used for kind="trap", ignored otherwise)
    """

    # Fade-out animation speed (alpha per second)
    FADE_SPEED: float = 300.0

    def __init__(
        self,
        kind: str,
        image: pygame.Surface,
        world_x: float,
        y: float,
        scale: float = 1.0,
        on_free: Callable[[float, float], None] | None = None,
    ) -> None:
        if kind not in ("trash", "coral", "trap"):
            raise ValueError(f"Unknown object type: {kind!r}. Use 'trash', 'coral' or 'trap'.")

        self.kind = kind
        self.world_x = world_x
        self.y = y

        # Callback for a trap – called on interaction, passes world_x/y for the fish spawn
        self._on_free: Callable[[float, float], None] | None = on_free

        # Scaling
        if scale != 1.0:
            w, h = image.get_size()
            image = pygame.transform.smoothscale(image, (int(w * scale), int(h * scale)))

        self._image_color: pygame.Surface = image.convert_alpha()

        # Grayscale version for corals
        self._image_gray: pygame.Surface = _to_grayscale_fast(self._image_color)

        # State
        self.active: bool = True          # False = gone (trash/trap) or animation finished
        self.faded: bool = (kind == "coral")  # coral starts in grayscale

        # Fade-out (trash and trap after interaction)
        self._fading: bool = False
        self._alpha: float = 255.0

        # Dimensions for collision
        self._w, self._h = self._image_color.get_size()

    # ------------------------------------------------------------------
    # Helper properties
    # ------------------------------------------------------------------

    @property
    def screen_rect(self) -> pygame.Rect:
        """Current on-screen rect (must be set before calling)."""
        return pygame.Rect(int(self._screen_x), int(self.y), self._w, self._h)

    @property
    def is_done(self) -> bool:
        """
        True if the object has been successfully handled.

        • trash  -> gone (active == False)
        • coral  -> revived, grayscale filter removed (faded == False)
        • trap   -> gone after the fish was freed (active == False)
        """
        if self.kind == "trash":
            return not self.active
        elif self.kind == "coral":
            return not self.faded
        elif self.kind == "trap":
            return not self.active
        return False

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def try_interact(self, jelly_rect: pygame.Rect) -> bool:
        """
        If Jelly overlaps this object, performs the interaction.

        • trash  -> starts a fade-out
        • coral  -> removes the grayscale filter (coral "comes back to life")
        • trap   -> starts a fade-out and calls the on_free callback to spawn a fish

        Returns True if the interaction was performed.
        """
        if not self.active:
            return False
        if not jelly_rect.colliderect(self.screen_rect):
            return False

        if self.kind == "trash":
            if not self._fading:
                self._fading = True
                return True

        elif self.kind == "coral":
            if self.faded:
                self.faded = False
                return True

        elif self.kind == "trap":
            if not self._fading:
                self._fading = True
                # Call the callback immediately – the fish spawns right when
                # freed, before the trap has fully faded, which feels natural.
                if self._on_free is not None:
                    cx = self.world_x + self._w / 2
                    cy = self.y + self._h / 2
                    self._on_free(cx, cy)
                return True

        return False

    # ------------------------------------------------------------------
    # Update & Draw
    # ------------------------------------------------------------------

    def update(self, dt: float, bg_x: float) -> None:
        """
        Updates the object's state.

        Parameters
        ----------
        dt    : delta time in seconds
        bg_x  : current background X offset from GameScene (negative = scrolled left)
        """
        # Convert to screen coordinates (same logic as NPC.sync_with_background)
        self._screen_x = self.world_x + bg_x

        # Fade-out animation (trash and trap)
        if self._fading:
            self._alpha -= self.FADE_SPEED * dt
            if self._alpha <= 0.0:
                self._alpha = 0.0
                self.active = False

    def draw(self, surface: pygame.Surface) -> None:
        """Draws the object onto the surface."""
        if not self.active:
            return

        # Pick the right texture
        img = self._image_gray if self.faded else self._image_color

        # Fade-out alpha
        if self._fading:
            img = img.copy()
            img.set_alpha(int(self._alpha))

        surface.blit(img, (int(self._screen_x), int(self.y)))

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"InteractiveObject(kind={self.kind!r}, "
            f"world_x={self.world_x:.0f}, active={self.active}, "
            f"faded={self.faded})"
        )


# ---------------------------------------------------------------------------
# Factory function – loads all images from a folder and places them in the scene
# ---------------------------------------------------------------------------

def load_objects(
    map_spot: str,
    screen_w: int,
    screen_h: int,
    bg_width: int | None = None,
    count: int | None = None,
    on_free: Callable[[str, float, float], None] | None = None,
    final_scene: bool = False,
) -> list[InteractiveObject]:
    """
    Loads interactive objects for the given ``map_spot``.

    • "turtle" → corals from imgs/corals/
    • "manta"  → trash from imgs/trash/
    • "whale"  → traps from imgs/traps/

    Parameters
    ----------
    map_spot  : "turtle", "manta" or "whale"
    screen_w  : screen width
    screen_h  : screen height
    bg_width  : background width in pixels (for placing objects);
                if None, screen_w * 2 is used
    count     : number of objects (None = one per image)
    on_free   : callback called when a fish is freed from a trap;
                signature: ``(trap_img_path: str, world_x: float, y: float) -> None``
                Passed to every object of type "trap".
                Ignored for other map_spots.
    """
    if map_spot == "turtle":
        folder = "imgs/corals"
        kind = "coral"
        scale = 0.10
    elif map_spot == "manta":
        folder = "imgs/trash"
        kind = "trash"
        scale = 0.4
    elif map_spot == "whale":
        folder = "imgs/traps"
        kind = "trap"
        scale = 0.15
    elif map_spot == "final":
        final_objects: list[InteractiveObject] = []
        final_objects.extend(load_objects('whale', screen_w, screen_h, bg_width=bg_width, on_free=on_free, final_scene=True))
        final_objects.extend(load_objects('manta', screen_w, screen_h, bg_width=bg_width, on_free=on_free, final_scene=True))
        final_objects.extend(load_objects('turtle', screen_w, screen_h, bg_width=bg_width, on_free=on_free, final_scene=True))
        return final_objects
    else:
        return []   # other spots have no objects yet

    if not os.path.isdir(folder):
        print(f"[InteractiveObject] Folder '{folder}' does not exist – no objects.")
        return []

    # Load images
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    image_paths = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in extensions
    ])

    if not image_paths:
        print(f"[InteractiveObject] No images in '{folder}'.")
        return []

    bg_w = bg_width if bg_width is not None else screen_w * 2

    objects: list[InteractiveObject] = []

    # Total number of objects
    total = count if count is not None else len(image_paths)

    corals_coords = [(0.07, 0.85), (0.14, 0.83), (0.20, 0.85), (0.34, 0.856), (0.41, 0.61), (0.5, 0.88), (0.624, 0.92), (0.688, 0.778), (0.739, 0.848), (0.802, 0.81)]
    trash_coords = [(0.075, 0.85), (0.22, 0.9), (0.235, 0.7), (0.38, 0.88), (0.5, 0.85), (0.6, 0.85), (0.63, 0.75), (0.83, 0.9), (0.89, 0.88)]
    trap_coords = [(0.05, 0.875), (0.29, 0.875), (0.4, 0.875), (0.6, 0.875), (0.72, 0.875)]
    final_corals_coords = [(0.027, 0.87), (0.14, 0.85), (0.20, 0.9), (0.21, 0.84), 
    (0.375, 0.81), (0.395, 0.75),
    (0.6, 0.84), (0.69, 0.57), (0.74, 0.77), (0.798, 0.75)]
    final_trash_coords = [(0.88, 0.88), (0.38, 0.88), (0.7, 0.85), (0.075, 0.85), (0.22, 0.9), (0.3, 0.85), (0.5, 0.85), (0.63, 0.8), (0.68, 0.82)]
    final_trap_coords = [(0.03, 0.78), (0.22, 0.71), (0.34, 0.87), (0.65, 0.875), (0.85, 0.78)]
    for i in range(total):
        img_path = image_paths[i % len(image_paths)]
        try:
            img = pygame.image.load(img_path).convert_alpha()
        except pygame.error as e:
            print(f"[InteractiveObject] Cannot load '{img_path}': {e}")
            continue

        def _make_darker(surface: pygame.Surface) -> pygame.Surface:
            result = surface.copy()
            result.fill((160, 160, 160, 255), special_flags=pygame.BLEND_RGBA_MULT)
            return result

        x, y = (0, 0)
        if kind == "coral":
            x, y = corals_coords[i] if not final_scene else final_corals_coords[i]
        elif kind == "trash":
            x, y = trash_coords[i] if not final_scene else final_trash_coords[i]
        elif kind == "trap":
            x, y = trap_coords[i]if not final_scene else final_trap_coords[i]
            img = _make_darker(img) if not final_scene else img

        obj = InteractiveObject(
            kind=kind,
            image=img,
            world_x=bg_w * x,
            y=screen_h * y,
            scale=scale,
            on_free=(lambda wx, wy, path=img_path: on_free(path, wx, wy)) if kind == "trap" else None,
        )
        objects.append(obj)

    return objects