"""
map_screen.py
=============
Standalone Map screen module for the Pygame game.

Usage
-----
    from map_screen import MapScreen

    map_screen = MapScreen(screen_w, screen_h)

    # in the main loop:
    for event in pygame.event.get():
        result = map_screen.handle_event(event)
        if result:
            print(result)   # e.g. {"action": "select", "spot": {"name": "Turtle", ...}}

    map_screen.update(dt)
    map_screen.draw(screen)
"""

from __future__ import annotations
import pygame
from engine import load_font


class MapScreen:
    """
    Map screen with a rotating target marker and spot selection.

    Parameters
    ----------
    screen_w / screen_h : screen dimensions
    map_img_path        : path to the map image
    target_img_path     : path to the target marker image
    spots               : list of dicts {"name": str, "pos": (rel_x, rel_y)}
                          pos are relative coordinates 0.0-1.0
    target_size_ratio   : target width as a fraction of screen_w (default 0.22)
    rotate_speed        : degrees per second (default 90)

    handle_event() returns
    -----------------------
    None                          – no action
    {"action": "select",
     "spot": dict}                – player pressed ENTER on a spot
    {"action": "back"}            – player pressed ESC/BACKSPACE
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        map_img_path: str = "imgs/map.jpg",
        target_img_path: str = "imgs/target.png",
        spots: list[dict] | None = None,
        target_size_ratio: float = 0.22,
        rotate_speed: float = 90.0,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.rotate_speed = rotate_speed

        # Images
        raw_map = pygame.image.load(map_img_path).convert()
        self._map_img = pygame.transform.scale(raw_map, (screen_w, screen_h))

        raw_target = pygame.image.load(target_img_path).convert_alpha()
        target_size = int(screen_w * target_size_ratio)
        self._target_img = pygame.transform.scale(raw_target, (target_size, target_size))

        # Spots
        self.spots: list[dict] = spots or [
            {"name": "Turtle", "pos": (0.2,  0.25)},
            {"name": "Manta",  "pos": (0.32, 0.68)},
            {"name": "Whale",  "pos": (0.72, 0.5 )},
        ]
        self.selected_index: int = 0

        # State
        self._angle: float = 0.0
        self._axis_moved: bool = False  # joystick axis debounce

        # Optional font for spot labels
        self._font = load_font(int(screen_h * 0.024))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> dict | None:
        """
        Handle one pygame event.
        Returns an action dict or None.
        """
        if event.type != pygame.KEYDOWN:
            return None

        if event.key in (pygame.K_m, pygame.K_ESCAPE):
            return {"action": "back"}

        if event.key == pygame.K_LEFT:
            self.selected_index = max(0, self.selected_index - 1)

        if event.key == pygame.K_RIGHT:
            self.selected_index = min(len(self.spots) - 1, self.selected_index + 1)

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return {"action": "select", "spot": self.spots[self.selected_index]}

        return None

    def handle_select(self) -> dict:
        """Returns the action dict for the currently selected spot (joystick button 0)."""
        return {"action": "select", "spot": self.spots[self.selected_index]}

    def handle_axis(self, value: float, deadzone: float = 0.5) -> None:
        """
        Handle left-stick X-axis movement for spot selection.
        Switches spot only past the deadzone; repeats are gated by _axis_moved.
        """
        if value > deadzone:
            if not self._axis_moved:
                self.selected_index = min(len(self.spots) - 1, self.selected_index + 1)
                self._axis_moved = True
        elif value < -deadzone:
            if not self._axis_moved:
                self.selected_index = max(0, self.selected_index - 1)
                self._axis_moved = True
        else:
            self._axis_moved = False  # stick back to center -> reset

    def update(self, dt: float) -> None:
        """Update animations (call every frame)."""
        self._angle = (self._angle + self.rotate_speed * dt) % 360

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the whole map screen onto the surface."""
        surface.blit(self._map_img, (0, 0))
        self._draw_spots(surface)
        self._draw_hud(surface)

    # ------------------------------------------------------------------
    # Private drawing
    # ------------------------------------------------------------------

    def _draw_spots(self, surface: pygame.Surface) -> None:
        for i, spot in enumerate(self.spots):
            rx, ry = spot["pos"]
            cx = int(rx * self.screen_w)
            cy = int(ry * self.screen_h)
            if i == self.selected_index:
                # Rotating target marker on the selected spot
                rotated = pygame.transform.rotozoom(self._target_img, self._angle, 1.0)
                rect = rotated.get_rect(center=(cx, cy))
                surface.blit(rotated, rect)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        spot_name = self.spots[self.selected_index]["name"]
        surf = self._font.render(spot_name, True, (220, 240, 255))
        shadow = self._font.render(spot_name, True, (0, 0, 0))
        x, y = self.screen_w / 2, self.screen_h - 100
        surface.blit(shadow, (x + 2, y + 2))
        surface.blit(surf,   (x,     y    ))

    # ------------------------------------------------------------------

    @property
    def selected_spot(self) -> dict:
        return self.spots[self.selected_index]

    def __repr__(self) -> str:
        return (
            f"MapScreen(selected={self.selected_index}, "
            f"spot={self.spots[self.selected_index]['name']!r})"
        )