"""
home_screen.py
==============
Modul pro Home screen v Underwater Adventure.

Contains three buttons: Play, Controls, Exit.
Navigate with left/right arrows or the left stick (axis 0).
Confirm: Enter or joystick button 0.

Usage
-------
    from home_screen import HomeScreen

    home_screen = HomeScreen(screen_w, screen_h)

    # in the main loop:
    for event in pygame.event.get():
        result = home_screen.handle_event(event)
        if result:
            # result: {"action": "play"} | {"action": "controls"} | {"action": "exit"}
            ...

    home_screen.handle_axis(joystick.get_axis(0))   # optional, outside the event loop
    home_screen.update(dt)
    home_screen.draw(screen)

handle_event() returns
--------------------
None                      – no action
{"action": "play"}        – spustit hru
{"action": "controls"}    – zobrazit controls screen
{"action": "exit"}        – quit the game
"""

from __future__ import annotations
import math
import pygame
from engine import load_font
 
# ---------------------------------------------------------------------------
# ControlsScreen
# ---------------------------------------------------------------------------

class ControlsScreen:
    # (action, keyboard, joystick)
    CONTROLS = [
        ("Move",       "Arrows",           "Left Stick"),
        ("Map",        "M",                "Y"),
        ("Home",       "ESC",              "Home"),        
        ("Confirm",    "Enter",            "A"),
        ("Quests",     "WASD + Space",      "D-Pad + R. Joy + L1 + A"),
    ]

    # Column colors
    _COL_ACTION  = (200, 230, 255)   # light blue
    _COL_KB      = (200, 200, 240)   # blue
    _COL_JOY     = (230, 230,  230)  # white

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h

        self._title_font  = load_font(int(screen_h * 0.065))
        self._head_font   = load_font(int(screen_h * 0.030))
        self._row_font    = load_font(int(screen_h * 0.030))
        self._hint_font   = load_font(int(screen_h * 0.024))

        # Semi-transparent background
        self._overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        self._overlay.fill((8, 20, 45, 215))

        # Frame
        pad_x = int(screen_w * 0.08)
        pad_y = int(screen_h * 0.08)
        self._box_rect = pygame.Rect(pad_x, pad_y,
                                     screen_w - 2 * pad_x,
                                     screen_h - 2 * pad_y)

        # Column widths (relative to the box width)
        inner_w = self._box_rect.width - 80   # 40px padding on each side
        self._col_w = [
            int(inner_w * 0.50),   # Action
            int(inner_w * 0.25),   # Keyboard
            int(inner_w * 0.25),   # Joystick
        ]
        # X coordinate of each column start
        x0 = self._box_rect.left + 40
        self._col_x = [
            x0,
            x0 + self._col_w[0] + 20,
            x0 + self._col_w[0] + self._col_w[1] + 40,
        ]

    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if the screen should be closed."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE,
                             pygame.K_RETURN, pygame.K_KP_ENTER,
                             pygame.K_c):
                return True
        if event.type == pygame.JOYBUTTONDOWN:
            if event.button in (1, 2, 3, 8):
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._overlay, (0, 0))

        # Frame
        pygame.draw.rect(surface, (20, 55, 115), self._box_rect, border_radius=18)
        pygame.draw.rect(surface, (80, 180, 255), self._box_rect, width=2, border_radius=18)

        # Title
        title_surf = self._title_font.render("CONTROLS", True, (140, 220, 255))
        title_rect = title_surf.get_rect(centerx=self.screen_w // 2,
                                          top=self._box_rect.top + 22)
        surface.blit(title_surf, title_rect)

        sep_y = title_rect.bottom + 14
        pygame.draw.line(surface, (80, 180, 255),
                         (self._box_rect.left + 30, sep_y),
                         (self._box_rect.right - 30, sep_y), 1)

        # Column headers
        headers    = ["ACTION", "KEYBOARD", "JOYSTICK"]
        header_col = [self._COL_ACTION, self._COL_KB, self._COL_JOY]
        head_y = sep_y + 12
        for col_i, (hdr, col) in enumerate(zip(headers, header_col)):             
            h_surf = self._head_font.render(hdr, True, col)
            surface.blit(h_surf, (self._col_x[col_i], head_y))

        head_bottom = head_y + self._head_font.size("A")[1] + 10
        pygame.draw.line(surface, (60, 130, 200),
                         (self._box_rect.left + 30, head_bottom),
                         (self._box_rect.right - 30, head_bottom), 1)

        # Data rows
        row_h = int((self._box_rect.bottom - head_bottom - 60) / len(self.CONTROLS))
        for i, (action, kb, joy) in enumerate(self.CONTROLS):
            y = head_bottom + 10 + i * row_h

            # Alternating background for readability
            if i % 2 == 0:
                row_bg = pygame.Surface(
                    (self._box_rect.width - 20, row_h - 4), pygame.SRCALPHA)
                row_bg.fill((255, 255, 255, 12))
                surface.blit(row_bg, (self._box_rect.left + 10, y - 2))

            cells = [action, kb, joy]
            cols  = [self._COL_ACTION, self._COL_KB, self._COL_JOY]
            for col_i, (text, col) in enumerate(zip(cells, cols)):
                txt = self._row_font.render(text, True, col)
                # Center vertically within the row
                ty = y + (row_h - txt.get_height()) // 2
                surface.blit(txt, (self._col_x[col_i], ty))

            # Thin separator
            if i < len(self.CONTROLS) - 1:
                line_y = y + row_h - 2
                pygame.draw.line(surface, (40, 80, 140),
                                 (self._box_rect.left + 30, line_y),
                                 (self._box_rect.right - 30, line_y), 1)

        # Hint
        hint = self._hint_font.render("Press Esc / B to close", True, (70, 130, 190))
        hint_rect = hint.get_rect(centerx=self.screen_w // 2,
                                   bottom=self._box_rect.bottom - 16)
        surface.blit(hint, hint_rect)


# ---------------------------------------------------------------------------
# HomeScreen
# ---------------------------------------------------------------------------

class HomeScreen:
    """
    Home screen with an animated background and three buttons.

    Parameters
    ---------
    screen_w / screen_h  : screen dimensions
    bg_frames            : list of pygame.Surface (animated background), optional
    joystick_deadzone    : deadzone for the left stick (default 0.4)
    """

    _BUTTONS = [
        {"label": "PLAY",     "action": "play"},
        {"label": "CONTROLS", "action": "controls"},        
        {"label": "EXIT",     "action": "exit"},
    ]

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        bg_frames: list[pygame.Surface] | None = None,
        joystick_deadzone: float = 0.4,
        joystick=None,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.joystick_deadzone = joystick_deadzone
        self.joystick = joystick

        # Animated background (optional)
        self._bg_frames = bg_frames or []
        self._bg_frame_idx: int = 0
        self._bg_frame_counter: int = 0
        self._bg_frame_delay: int = 5

        # Fonty
        self._title_font  = load_font(int(screen_h * 0.13))
        self._sub_font    = load_font(int(screen_h * 0.032))
        self._btn_font    = load_font(int(screen_h * 0.052))
        self._hint_font   = load_font(int(screen_h * 0.026))
        self._ctrl_font   = load_font(int(screen_h * 0.028))

        # Button state
        self.selected_index: int = 0

        # Joystick debounce
        self._axis_moved: bool = False

        # Animation – time in seconds
        self._time: float = 0.0

        # Controls screen
        self._controls_screen = ControlsScreen(screen_w, screen_h)
        self._show_controls: bool = False

        # Precomputed button dimensions
        self._btn_w = int(screen_w * 0.22)
        self._btn_h = int(screen_h * 0.10)
        self._btn_gap = int(screen_w * 0.04)
        total_w = len(self._BUTTONS) * self._btn_w + (len(self._BUTTONS) - 1) * self._btn_gap
        self._btn_start_x = (screen_w - total_w) // 2
        self._btn_y = int(screen_h * 0.68)

        # Semi-transparent gradient under the buttons
        self._gradient = self._make_gradient(screen_w, int(screen_h * 0.55))

        # Controller image
        self._ctrl_img: pygame.Surface | None = None
        try:
            raw = pygame.image.load("imgs/controller.png").convert_alpha()
            ctrl_h = int(screen_h * 0.07)
            ctrl_w = int(raw.get_width() * ctrl_h / raw.get_height())
            self._ctrl_img = pygame.transform.scale(raw, (ctrl_w, ctrl_h))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _make_gradient(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            alpha = int(180 * (y / h))
            pygame.draw.line(surf, (4, 12, 35, alpha), (0, y), (w, y))
        return surf

    def _btn_rect(self, index: int) -> pygame.Rect:
        x = self._btn_start_x + index * (self._btn_w + self._btn_gap)
        return pygame.Rect(x, self._btn_y, self._btn_w, self._btn_h)

    def _perform_action(self, action: str) -> dict | None:
        if action == "controls":
            self._show_controls = True
            return None          # HomeScreen handles it internally
        return {"action": action}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> dict | None:
        """
        Handle a pygame event.
        Returns an action dict or None.
        """
        # Controls overlay takes precedence
        if self._show_controls:
            if self._controls_screen.handle_event(event):
                self._show_controls = False
            return None

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected_index = max(0, self.selected_index - 1)

            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected_index = min(len(self._BUTTONS) - 1,
                                          self.selected_index + 1)

            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                action = self._BUTTONS[self.selected_index]["action"]
                return self._perform_action(action)

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:
                action = self._BUTTONS[self.selected_index]["action"]
                return self._perform_action(action)
            if event.button == 2:
                return {"action": "exit"}

        return None

    def handle_axis(self, value: float) -> None:
        """Handle the left joystick (axis 0) – call every frame."""
        if self._show_controls:
            return
        if value > self.joystick_deadzone:
            if not self._axis_moved:
                self.selected_index = min(len(self._BUTTONS) - 1,
                                          self.selected_index + 1)
                self._axis_moved = True
        elif value < -self.joystick_deadzone:
            if not self._axis_moved:
                self.selected_index = max(0, self.selected_index - 1)
                self._axis_moved = True
        else:
            self._axis_moved = False

    def set_bg_frames(self, frames: list[pygame.Surface]) -> None:
        """Set the animated background (can also be called after init)."""
        self._bg_frames = frames
        self._bg_frame_idx = 0

    def update(self, dt: float) -> None:
        """Update animations – call every frame."""
        self._time += dt

        # Advance background frame
        if self._bg_frames:
            self._bg_frame_counter += 1
            if self._bg_frame_counter >= self._bg_frame_delay:
                self._bg_frame_counter = 0
                self._bg_frame_idx = (self._bg_frame_idx + 1) % len(self._bg_frames)

    def draw(self, surface: pygame.Surface) -> None:
        """Draws the home screen onto the surface."""
        # --- Background ---
        if self._bg_frames:
            surface.blit(self._bg_frames[self._bg_frame_idx], (0, 0))
        else:
            surface.fill((10, 25, 60))

        # --- Gradient panel ---
        surface.blit(self._gradient, (0, self.screen_h - self._gradient.get_height()))

        # --- Game title ---
        self._draw_title(surface)

        # --- Buttons ---
        self._draw_buttons(surface)

        # --- Hint ---
        self._draw_hint(surface)

        # --- Controller status ---
        self._draw_controller_status(surface)

        # --- Controls overlay ---
        if self._show_controls:
            self._controls_screen.draw(surface)

    # ------------------------------------------------------------------
    # Private drawing
    # ------------------------------------------------------------------

    def _draw_title(self, surface: pygame.Surface) -> None:
        t = self._time

        # Main title with a slight float
        bob = math.sin(t * 1.2) * 6
        title_y = int(self.screen_h * 0.38 + bob)

        # Shadow (blue tint)
        shadow = self._title_font.render("A Jelly’s Odyssey", True, (0, 40, 120))
        shadow_rect = shadow.get_rect(centerx=self.screen_w // 2,
                                       top=title_y + 5)
        surface.blit(shadow, shadow_rect)

        # Main text (light cyan)
        title = self._title_font.render("A Jelly’s Odyssey", True, (120, 220, 255))
        title_rect = title.get_rect(centerx=self.screen_w // 2, top=title_y)
        surface.blit(title, title_rect)

        # Podtitul
        bob2 = math.sin(t * 1.2 + 0.5) * 4
        sub_y = title_rect.bottom + int(self.screen_h * 0.01) + bob2
        sub = self._sub_font.render("T h e  L a s t  H o p e", True, (80, 180, 255))
        sub_rect = sub.get_rect(centerx=self.screen_w // 2, top=sub_y)

        # Decorative lines beside the subtitle
        line_margin = 24
        line_y = sub_rect.centery
        pygame.draw.line(surface, (80, 180, 255),
                         (sub_rect.left - line_margin - 80, line_y),
                         (sub_rect.left - line_margin, line_y), 2)
        pygame.draw.line(surface, (80, 180, 255),
                         (sub_rect.right + line_margin, line_y),
                         (sub_rect.right + line_margin + 80, line_y), 2)

        surface.blit(sub, sub_rect)

    def _draw_buttons(self, surface: pygame.Surface) -> None:
        t = self._time

        for i, btn in enumerate(self._BUTTONS):
            rect = self._btn_rect(i)
            is_selected = (i == self.selected_index)

            # Slight float for the selected button
            if is_selected:
                bob = math.sin(t * 2.5) * 4
                rect = rect.move(0, int(bob))

            # Barvy
            if is_selected:
                bg_color   = (20, 80, 160)
                border_col = (120, 220, 255)
                text_col   = (220, 245, 255)
                glow_alpha = int(60 + 40 * math.sin(t * 3))
            else:
                bg_color   = (10, 30, 70)
                border_col = (40, 100, 180)
                text_col   = (80, 160, 220)
                glow_alpha = 0

            # Glow effect (selected only)
            if is_selected and glow_alpha > 0:
                glow_rect = rect.inflate(20, 14)
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (80, 180, 255, glow_alpha),
                                 glow_surf.get_rect(), border_radius=16)
                surface.blit(glow_surf, glow_rect)

            # Button fill
            btn_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            alpha = 230 if is_selected else 200
            pygame.draw.rect(btn_surf, (*bg_color, alpha),
                             btn_surf.get_rect(), border_radius=12)
            surface.blit(btn_surf, rect)

        # Frame
            pygame.draw.rect(surface, border_col, rect, width=2, border_radius=12)

            # Top highlight
            if is_selected:
                shine_rect = pygame.Rect(rect.left + 8, rect.top + 4,
                                         rect.width - 16, rect.height // 3)
                shine_surf = pygame.Surface(shine_rect.size, pygame.SRCALPHA)
                shine_surf.fill((255, 255, 255, 18))
                surface.blit(shine_surf, shine_rect)

            # Popisek
            label = self._btn_font.render(btn["label"], True, text_col)
            label_rect = label.get_rect(center=rect.center)
            surface.blit(label, label_rect)

    def _draw_hint(self, surface: pygame.Surface) -> None:
        if self.joystick is not None and pygame.joystick.get_count() > 0:
            hint_text = "Press A to confirm"
        else:
            hint_text = "Press Enter to confirm"

        hint_y = self.screen_h - int(self.screen_h * 0.06)
        surf = self._hint_font.render(hint_text, True, (60, 120, 180))
        rect = surf.get_rect(centerx=self.screen_w // 2, top=hint_y)
        surface.blit(surf, rect)

    def _draw_controller_status(self, surface: pygame.Surface) -> None:
        """Draw the controller icon and connection status in the bottom-right corner."""
        connected = self.joystick is not None and pygame.joystick.get_count() > 0
        color_dot  = (60, 220, 100) if connected else (220, 70, 60)
        label      = self.joystick.get_name() if connected else "Controller not connected"
        # Truncate long names
        if len(label) > 28:
            label = label[:26] + "…"

        margin = int(self.screen_w * 0.02)
        bottom = self.screen_h - int(self.screen_h * 0.025)

        # Controller image
        img_w = 0
        if self._ctrl_img:
            img_rect = self._ctrl_img.get_rect(
                right=self.screen_w - margin,
                bottom=bottom,
            )
            # Dim/brighten based on connection status
            alpha_img = 255 if connected else 90
            tmp = self._ctrl_img.copy()
            tmp.set_alpha(alpha_img)
            surface.blit(tmp, img_rect)
            img_w = img_rect.width + 8

        # Colored dot
        dot_r = int(self.screen_h * 0.012)
        dot_x = self.screen_w - margin - img_w - dot_r - 6
        dot_y = bottom - dot_r - 2
        pygame.draw.circle(surface, color_dot, (dot_x, dot_y), dot_r)
        # Thin dot outline
        pygame.draw.circle(surface, (255, 255, 255, 80), (dot_x, dot_y), dot_r, 1)

        # Text
        txt_surf = self._ctrl_font.render(label, True,
                                          (180, 255, 180) if connected else (255, 140, 120))
        txt_rect = txt_surf.get_rect(
            right=dot_x - dot_r - 8,
            centery=dot_y,
        )
        surface.blit(txt_surf, txt_rect)

    # ------------------------------------------------------------------

    @property
    def showing_controls(self) -> bool:
        return self._show_controls

    def __repr__(self) -> str:
        return (f"HomeScreen(selected={self.selected_index}, "
                f"btn={self._BUTTONS[self.selected_index]['label']!r})")