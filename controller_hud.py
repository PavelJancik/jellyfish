import pygame
import math
import random


# ====================================================================== #
#  RumbleEffect - 3 short controller shakes on failure                  #
# ====================================================================== #

class RumbleEffect:
    """
    Fires 3 short vibration pulses on the joystick.

    Parameters
    ---------
    joystick      : pygame.joystick.Joystick | None
    pulses        : number of pulses (default 3)
    pulse_on      : vibration duration in seconds (default 0.10)
    pulse_off     : pause between pulses in seconds (default 0.10)
    low_freq      : low-frequency intensity 0.0-1.0
    high_freq     : high-frequency intensity 0.0-1.0
    """

    def __init__(
        self,
        joystick=None,
        pulses: int = 3,
        pulse_on: float = 0.10,
        pulse_off: float = 0.10,
        low_freq: float = 0.8,
        high_freq: float = 0.4,
    ):
        self.joystick  = joystick
        self.pulses    = pulses
        self.pulse_on  = pulse_on
        self.pulse_off = pulse_off
        self.low_freq  = low_freq
        self.high_freq = high_freq

        self._active       = False
        self._pulse_done   = 0          # number of completed pulses
        self._phase_on     = False      # True = vibrace, False = pauza
        self._timer        = 0.0

    def start(self):
        """Starts the rumble sequence."""
        self._active     = True
        self._pulse_done = 0
        self._phase_on   = True
        self._timer      = self.pulse_on
        self._rumble_on()

    def stop(self):
        """Immediately stops the rumble."""
        self._active = False
        self._rumble_off()

    @property
    def active(self) -> bool:
        return self._active

    def update(self, dt: float):
        if not self._active:
            return
        self._timer -= dt
        if self._timer > 0:
            return

        if self._phase_on:
            # Pulse finished -> pause
            self._rumble_off()
            self._pulse_done += 1
            if self._pulse_done >= self.pulses:
                # All pulses done
                self._active = False
                return
            self._phase_on = False
            self._timer    = self.pulse_off
        else:
            # Pause finished -> next pulse
            self._phase_on = True
            self._timer    = self.pulse_on
            self._rumble_on()

    # ------------------------------------------------------------------ #
    #  Internal vibration control                                        #
    # ------------------------------------------------------------------ #

    def _rumble_on(self):
        if self.joystick is None:
            return
        try:
            self.joystick.rumble(self.low_freq, self.high_freq, 0)
        except Exception:
            pass  # Controller doesn't support rumble -> ignore

    def _rumble_off(self):
        if self.joystick is None:
            return
        try:
            self.joystick.rumble(0, 0, 0)
        except Exception:
            pass


class ControllerHUD:
    """
    HUD module showing controller state in the bottom-left corner.

    The joystick challenge runs directly in the HUD panel:
      - Yellow circle = play area
      - Green dot = stick position (returns to center on release)
      - Red dot = target (random position inside the circle)
      - Success: the green dot is fully inside the red one + player presses button 0
    """

    # Joystick dead zone
    DEADZONE = 0.12

    # Speed at which the green dot returns to center when the stick is released (fraction/s)
    RETURN_SPEED = 4.5

    def __init__(self, screen_w, screen_h, joystick=None):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.joystick = joystick

        # Colors
        self.COL_YELLOW  = (247, 202, 24)
        self.COL_RED     = (220, 60,  50)
        self.COL_GREEN   = (46,  204, 64)
        self.COL_WHITE   = (255, 255, 255)
        self.COL_GRAY    = (120, 120, 140)
        self.COL_DARK    = (10,  10,  20)

        # HUD panel – screen center, 1/3 down from the top
        self.joy_r       = 88           # circle radius (2x the original 44)
        self.stick_r     = 14           # moving dot radius
        self.target_r       = int(14 * 1.5)  # red target radius = stick_r * 1.5

        # Circle center – horizontally centered, 1/3 down vertically
        self.joy_cx = screen_w // 2
        self.joy_cy = screen_h // 3

        # Green dot position (normalized, -1..1 within joy_r)
        self._gx: float = 0.0   # normalized X position (-1..1)
        self._gy: float = 0.0   # normalized Y position (-1..1)

        # Joystick axes (-1..1)
        self.joy_axis_x: float = 0.0
        self.joy_axis_y: float = 0.0

        # Trigger (kept for possible future use)
        self.trigger_val: float = 0.0

        # Challenge state
        self.joy_game: _JoyChallenge | None = None

        # Rumble effect on failure
        self.rumble = RumbleEffect(joystick=joystick)

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    def start_joystick_game(self, on_complete=None):
        """
        Starts the joystick challenge directly in the HUD.

        Parameters
        ----------
        on_complete : callable | None
            Called after the success is confirmed (button 0 / K_0 on success).
        """
        self.joy_game = _JoyChallenge(
            joy_r=self.joy_r,
            stick_r=self.stick_r,
            target_r=self.target_r,
            on_complete=on_complete,
            keyboard_only=(self.joystick is None),
        )
        # Reset the green dot to the center
        self._gx = 0.0
        self._gy = 0.0

    def start_mash_game(self, on_complete=None, required_clicks: int = 15, time_limit: float = 3.0, on_fail=None):
        """
        Starts the mash challenge – rapidly repeated presses of button A (0).

        Parameters
        ----------
        on_complete     : callable | None – called on completion (enough clicks)
        required_clicks : how many clicks are required
        time_limit      : time in seconds to complete it
        on_fail         : callable | None – called when time runs out without completing;
                          the challenge auto-ends and no interaction occurs
        """
        def _mash_on_fail():
            self.rumble.start()
            if on_fail is not None:
                on_fail()

        self.joy_game = _MashChallenge(
            required_clicks=required_clicks,
            time_limit=time_limit,
            on_complete=on_complete,
            on_fail=_mash_on_fail,
        )

    def start_dpad_game(self, on_complete=None, steps: int = 10, step_time: float = 0.5, on_fail=None):
        """
        Starts the D-pad challenge – a series of random directions to press.

        Parameters
        ----------
        on_complete : callable | None – called once all steps are done
        steps       : number of steps (default 10)
        step_time   : time per step in seconds (default 0.5)
        on_fail     : callable | None – called when a step times out;
                      the challenge auto-ends and no interaction occurs
        """
        def _dpad_on_fail():
            self.rumble.start()
            if on_fail is not None:
                on_fail()

        self.joy_game = _DpadChallenge(
            steps=steps,
            step_time=step_time,
            on_complete=on_complete,
            on_fail=_dpad_on_fail,
        )

    def stop_games(self):
        """Stops the active challenge."""
        self.joy_game = None

    def handle_button_press(self, button: int):
        """
        Called on any joystick button press during a challenge.
        Forwards the press to the active challenge (mash / dpad).
        """
        if self.joy_game and hasattr(self.joy_game, 'handle_button'):
            self.joy_game.handle_button(button)

    def handle_confirm(self):
        """
        Called on pressing button 4 (△ / Y) or L1.
        If a challenge is running and green is FULLY inside red -> success.
        Ignored for MashChallenge and DpadChallenge, which have no confirm().
        """
        if isinstance(self.joy_game, _JoyChallenge):
            self.joy_game.confirm()

    def handle_key(self, event):
        """
        Keyboard input for all challenge types.

        Mash challenge  : SPACE = one click (button 0)
        DPad challenge  : W/A/S/D  = up/left/down/right
        Joy challenge   : WASD     = stick movement (via joy_axis_x/y)
                          SPACE = confirm (like joystick button 0 / L1)
        Fallback        : K_4      = confirm (original behavior)
        """
        if event.type != pygame.KEYDOWN:
            return

        # Original confirm key (kept)
        if event.key == pygame.K_4:
            self.handle_confirm()

        # --- Mash challenge ---
        if isinstance(self.joy_game, _MashChallenge):
            if event.key == pygame.K_SPACE:
                self.joy_game.handle_button(0)   # space = button A

        # --- DPad challenge ---
        elif isinstance(self.joy_game, _DpadChallenge):
            key_to_hat = {
                pygame.K_w: (0,  1),   # W = up
                pygame.K_s: (0, -1),   # S = down
                pygame.K_a: (-1, 0),   # A = left
                pygame.K_d: (1,  0),   # D = right
            }
            hat = key_to_hat.get(event.key)
            if hat is not None:
                self.joy_game.handle_hat(hat)

        # --- Joy challenge ---
        else:
            if event.key == pygame.K_SPACE:
                self.handle_confirm()

    def update(self, dt, joystick=None):
        js = joystick or self.joystick

        # Update the joystick reference in the rumble effect
        if js is not None:
            self.rumble.joystick = js

        # Update the rumble effect
        self.rumble.update(dt)
        if js:
            raw_x = js.get_axis(3)
            raw_y = js.get_axis(4)
            axis_x = raw_x if abs(raw_x) >= self.DEADZONE else 0.0
            axis_y = raw_y if abs(raw_y) >= self.DEADZONE else 0.0
            raw_t = js.get_axis(5)
            self.trigger_val = (raw_t + 1) / 2
            # Joystick takes priority; keyboard only fills in when the stick is idle
            if axis_x != 0.0 or axis_y != 0.0:
                self.joy_axis_x = axis_x
                self.joy_axis_y = axis_y
            # else: keep joy_axis_x/y as set by the keyboard (from the main loop / handle_key)

        # Green dot movement – maps directly to the stick position
        if self.joy_axis_x != 0.0 or self.joy_axis_y != 0.0:
            # Stick is pushed -> direct position from the axis
            self._gx = self.joy_axis_x
            self._gy = self.joy_axis_y
        else:
            # Stick released -> return to center
            dist = math.hypot(self._gx, self._gy)
            if dist > 0.001:
                step = self.RETURN_SPEED * dt
                if step >= dist:
                    self._gx = 0.0
                    self._gy = 0.0
                else:
                    self._gx -= (self._gx / dist) * step
                    self._gy -= (self._gy / dist) * step
            else:
                self._gx = 0.0
                self._gy = 0.0

        # Clamp the green dot inside the circle (in case a diagonal exceeds 1.0)
        dist = math.hypot(self._gx, self._gy)
        max_norm = 1.0 - self.stick_r / self.joy_r
        if dist > max_norm:
            self._gx = self._gx / dist * max_norm
            self._gy = self._gy / dist * max_norm

        # Update the challenge
        if self.joy_game:
            if isinstance(self.joy_game, (_MashChallenge, _DpadChallenge)):
                self.joy_game.update(dt)
                # On failure (time ran out) auto-end the challenge
                if self.joy_game._failed:
                    self.joy_game = None
                    return
            else:
                # Green dot pixel position relative to the circle center
                gpx = self._gx * (self.joy_r - self.stick_r)
                gpy = self._gy * (self.joy_r - self.stick_r)
                self.joy_game.update(gpx, gpy)

    def draw(self, surface):
        """Draws the HUD panel for the active challenge type."""
        if isinstance(self.joy_game, _MashChallenge):
            self._draw_mash_panel(surface)
        elif isinstance(self.joy_game, _DpadChallenge):
            self._draw_dpad_panel(surface)
        else:
            self._draw_hud_panel(surface)

    # ------------------------------------------------------------------ #
    #  Internal drawing                                                   #
    # ------------------------------------------------------------------ #

    def _draw_hud_panel(self, surface):
        cx, cy, r = self.joy_cx, self.joy_cy, self.joy_r

        # Circle – semi-transparent dark background
        circle_surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(circle_surf, (0, 0, 0, 50), (r + 1, r + 1), r)
        surface.blit(circle_surf, (cx - r - 1, cy - r - 1))

        # White circle border
        pygame.draw.circle(surface, self.COL_WHITE, (cx, cy), r, 2)

        # Red target (only while a challenge is active)
        if self.joy_game:
            tx = cx + int(self.joy_game.target_x)
            ty = cy + int(self.joy_game.target_y)
            col_red = (255, 130, 110) if self.joy_game.in_target else self.COL_RED
            pygame.draw.circle(surface, col_red, (tx, ty), self.target_r)
            pygame.draw.circle(surface, self.COL_WHITE, (tx, ty), self.target_r, 1)


        # Circle center
        mid_surf = pygame.Surface((self.stick_r * 2 + 2, self.stick_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(mid_surf, (0, 0, 0, 50), (self.stick_r + 1, self.stick_r + 1), self.stick_r)
        surface.blit(mid_surf, (cx - self.stick_r - 1, cy - self.stick_r - 1))


        # Moving dot (stick position)
        gpx = int(cx + self._gx * (r - self.stick_r))
        gpy = int(cy + self._gy * (r - self.stick_r))

        in_tgt = self.joy_game and self.joy_game.in_target

        # Semi-transparent background for the moving dot
        stick_surf = pygame.Surface((self.stick_r * 2 + 2, self.stick_r * 2 + 2), pygame.SRCALPHA)
        fill_color = (100, 220, 100, 160) if in_tgt else (200, 200, 220, 130)
        pygame.draw.circle(stick_surf, fill_color, (self.stick_r + 1, self.stick_r + 1), self.stick_r)
        surface.blit(stick_surf, (gpx - self.stick_r - 1, gpy - self.stick_r - 1))

        pygame.draw.circle(surface, self.COL_WHITE, (gpx, gpy), self.stick_r, 1)

        # Label below the circle
        font = pygame.font.SysFont("monospace", 18)

        if self.joy_game and self.joy_game.in_target:
            confirm_txt = "Press L1!" if self.joystick else "Press Space!"
            lbl = font.render(confirm_txt, True, (180, 255, 180))
        else:
            stick_txt = "R-STICK" if self.joystick else "WASD"
            lbl = font.render(stick_txt, True, self.COL_WHITE)

        surface.blit(lbl, (cx - lbl.get_width() // 2, cy + r + 8))


    # ------------------------------------------------------------------ #
    #  Drawing the Mash challenge                                        #
    # ------------------------------------------------------------------ #

    def _draw_mash_panel(self, surface):
        """Draws the mash challenge – progress bar + prompt."""
        if not isinstance(self.joy_game, _MashChallenge):
            return
        game = self.joy_game

        cx, cy = self.joy_cx, self.joy_cy
        bar_w, bar_h = 260, 28
        bx = cx - bar_w // 2
        by = cy - bar_h // 2

        # Background
        bg = pygame.Surface((bar_w + 24, bar_h + 80), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 120), bg.get_rect(), border_radius=14)
        surface.blit(bg, (bx - 12, by - 36))

        # Nadpis
        font_big = pygame.font.SysFont("monospace", 22, bold=True)
        mash_txt = "Mash  A !" if self.joystick else "Mash Space!"
        lbl = font_big.render(mash_txt, True, (255, 220, 60))
        surface.blit(lbl, (cx - lbl.get_width() // 2, by - 30))

        # Track
        pygame.draw.rect(surface, (60, 60, 90), (bx, by, bar_w, bar_h), border_radius=10)

        # Fill
        progress = min(game.clicks / game.required_clicks, 1.0)
        fill = int(bar_w * progress)
        if fill > 0:
            col = (80, 220, 120) if not game._completed else (255, 215, 0)
            pygame.draw.rect(surface, col, (bx, by, fill, bar_h), border_radius=10)

        # Border
        pygame.draw.rect(surface, (255, 255, 255, 80), (bx, by, bar_w, bar_h), 2, border_radius=10)

        # Click counter
        font_sm = pygame.font.SysFont("monospace", 18)
        cnt = font_sm.render(f"{game.clicks} / {game.required_clicks}", True, (230, 230, 255))
        surface.blit(cnt, (cx - cnt.get_width() // 2, by + bar_h + 8))

        # Timer – thin bar below the progress bar
        t_w = int(bar_w * max(0.0, game.time_left / game.time_limit))
        pygame.draw.rect(surface, (200, 80, 60), (bx, by + bar_h + 34, bar_w, 6), border_radius=3)
        if t_w > 0:
            pygame.draw.rect(surface, (255, 140, 40), (bx, by + bar_h + 34, t_w, 6), border_radius=3)

    # ------------------------------------------------------------------ #
    #  Drawing the D-pad challenge                                       #
    # ------------------------------------------------------------------ #

    def _draw_dpad_panel(self, surface):
        """Draws the d-pad challenge – shows the current required direction as an arrow."""
        if not isinstance(self.joy_game, _DpadChallenge):
            return
        game = self.joy_game

        cx, cy = self.joy_cx, self.joy_cy
        r = self.joy_r

        # Semi-transparent background
        panel_w, panel_h = r * 2 + 60, r * 2 + 80
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 120), bg.get_rect(), border_radius=16)
        surface.blit(bg, (cx - panel_w // 2, cy - panel_h // 2))

        # Nadpis
        font_big = pygame.font.SysFont("monospace", 20, bold=True)
        step_txt = f"Step  {game.current_step + 1} / {game.steps}"
        lbl = font_big.render(step_txt, True, (180, 220, 255))
        surface.blit(lbl, (cx - lbl.get_width() // 2, cy - r - 28))

        if game.current_step >= game.steps:
            # Hotovo
            done_lbl = font_big.render("Done!", True, (80, 220, 120))
            surface.blit(done_lbl, (cx - done_lbl.get_width() // 2, cy - 14))
            return

        # Large arrow for the current direction
        dx, dy = game.current_direction()
        arrow_size = 54
        self._draw_arrow(surface, cx, cy, dx, dy, arrow_size,
                         color=(255, 220, 60) if not game._flash else (120, 220, 120))

        # Timer – arc or bar
        t_ratio = max(0.0, game.step_time_left / game.step_time)
        timer_col = (80, 200, 255) if t_ratio > 0.35 else (255, 100, 60)
        timer_w = int((r * 2 - 4) * t_ratio)
        bx = cx - r + 2
        bby = cy + r + 10
        pygame.draw.rect(surface, (60, 60, 90), (bx, bby, r * 2 - 4, 8), border_radius=4)
        if timer_w > 0:
            pygame.draw.rect(surface, timer_col, (bx, bby, timer_w, 8), border_radius=4)

        # Indicate previous steps as small dots
        dot_y = cy + r + 26
        total = game.steps
        dot_spacing = min(18, (r * 2) // max(total, 1))
        start_x = cx - (total - 1) * dot_spacing // 2
        for i in range(total):
            col = (80, 220, 120) if i < game.current_step else (60, 60, 90)
            pygame.draw.circle(surface, col, (start_x + i * dot_spacing, dot_y), 5)

        # Control label
        font_ctrl = pygame.font.SysFont("monospace", 16)
        ctrl_txt = "D-pad" if self.joystick else "WASD"
        ctrl_lbl = font_ctrl.render(ctrl_txt, True, (160, 200, 255))
        surface.blit(ctrl_lbl, (cx - ctrl_lbl.get_width() // 2, dot_y + 14))

    def _draw_arrow(self, surface, cx, cy, dx, dy, size, color=(255, 220, 60)):
        """Draws a simple arrow at (cx, cy) pointing in direction (dx, dy)."""
        import math
        angle = math.atan2(dy, dx)
        tip_x = cx + int(math.cos(angle) * size * 0.5)
        tip_y = cy + int(math.sin(angle) * size * 0.5)
        tail_x = cx - int(math.cos(angle) * size * 0.5)
        tail_y = cy - int(math.sin(angle) * size * 0.5)

        # Tip – triangle
        perp_angle = angle + math.pi / 2
        hw = size * 0.28
        head_len = size * 0.38
        base_x = tip_x - int(math.cos(angle) * head_len)
        base_y = tip_y - int(math.sin(angle) * head_len)
        p1 = (tip_x, tip_y)
        p2 = (base_x + int(math.cos(perp_angle) * hw),
              base_y + int(math.sin(perp_angle) * hw))
        p3 = (base_x - int(math.cos(perp_angle) * hw),
              base_y - int(math.sin(perp_angle) * hw))

        # Arrow body – ends at the tip's base (not its apex), so the flat
        # end of the thick line doesn't cut into the triangle tip and
        # make it look "blunt".
        pygame.draw.line(surface, color, (tail_x, tail_y), (base_x, base_y), 8)

        pygame.draw.polygon(surface, color, [p1, p2, p3])


# ====================================================================== #
#  Internal helper class – joystick challenge state                       #
# ====================================================================== #

class _JoyChallenge:
    """
    Holds joystick-challenge state (target, overlap detection, callback).
    All drawing is handled by ControllerHUD._draw_hud_panel.

    target_x, target_y : target position in pixels relative to the circle center
    in_target          : True = green is close enough to red
    """

    # 8 directions (normalized vectors): 4 cardinal + 4 diagonal
    _KB_DIRECTIONS = [
        ( 0.0, -1.0),                                              # up
        ( 0.0,  1.0),                                              # down
        (-1.0,  0.0),                                              # left
        ( 1.0,  0.0),                                              # right
        (-1.0 / math.sqrt(2), -1.0 / math.sqrt(2)),               # up-left
        ( 1.0 / math.sqrt(2), -1.0 / math.sqrt(2)),               # up-right
        (-1.0 / math.sqrt(2),  1.0 / math.sqrt(2)),               # down-left
        ( 1.0 / math.sqrt(2),  1.0 / math.sqrt(2)),               # down-right
    ]

    def __init__(self, joy_r: int, stick_r: int, target_r: int, on_complete=None, keyboard_only: bool = False):
        self.joy_r          = joy_r
        self.stick_r        = stick_r
        self.target_r       = target_r
        self._on_complete   = on_complete
        self._completed     = False
        self.in_target      = False
        self._keyboard_only = keyboard_only

        self._spawn_target()

    def _spawn_target(self):
        """
        Random target position inside the circle (with a margin).

        With keyboard-only control, the target is placed at one of 8 fixed positions
        (up, down, left, right and 4 diagonals). The spawn distance is
        chosen so the target is always reachable regardless of direction:
          - the green dot reaches at most pixel_reach = (1 - stick_r/joy_r) * (joy_r - stick_r)
          - success condition: dist(green, target) + stick_r <= target_r
            -> the target must be at most (pixel_reach + target_r - stick_r) from the center
            and fully inside the circle: target_d <= joy_r - target_r
        """
        if self._keyboard_only:
            max_norm   = 1.0 - self.stick_r / self.joy_r
            pixel_reach = max_norm * (self.joy_r - self.stick_r)
            overlap    = self.target_r - self.stick_r          # how many px of overlap is enough
            d_min = max(pixel_reach - overlap, 4)              # closest reachable position
            d_max = float(self.joy_r - self.target_r)          # target must be fully inside the circle
            d = random.uniform(d_min, d_max)
            dx, dy = random.choice(self._KB_DIRECTIONS)
            self.target_x = dx * d
            self.target_y = dy * d
        else:
            max_d = self.joy_r - self.target_r - self.stick_r - 6
            max_d = max(max_d, 4)
            angle = random.uniform(0, math.tau)
            d = random.uniform(max_d * 0.3, max_d)
            self.target_x = math.cos(angle) * d
            self.target_y = math.sin(angle) * d

    def update(self, stick_px: float, stick_py: float):
        """
        Updates overlap detection.

        stick_px, stick_py : green dot pixel position relative to the center

        Success condition: the green dot must be FULLY inside the red one,
        i.e. distance between centers + stick_r <= target_r.
        """
        dist = math.hypot(stick_px - self.target_x, stick_py - self.target_y)
        self.in_target = dist + self.stick_r <= self.target_r

    def confirm(self):
        """Called on pressing button 4 (△) if in_target == True."""
        if self.in_target and not self._completed:
            self._completed = True
            if self._on_complete is not None:
                self._on_complete()




# ====================================================================== #
#  _MashChallenge - rapid button-A mashing                                #
# ====================================================================== #

class _MashChallenge:
    """
    The player must click button A (button 0) as fast as possible.
    The challenge completes once required_clicks is reached within time_limit.

    Attributes
    ----------
    clicks          : current click count
    required_clicks : clicks needed to complete
    time_left       : remaining time
    time_limit      : total challenge time
    """

    def __init__(self, required_clicks: int = 15, time_limit: float = 3.0, on_complete=None, on_fail=None):
        self.required_clicks = required_clicks
        self.time_limit = time_limit
        self.time_left = time_limit
        self.clicks = 0
        self._on_complete = on_complete
        self._on_fail = on_fail
        self._completed = False
        self._failed = False

    def handle_button(self, button: int):
        """Called on a joystick button press; button 0 = A."""
        if self._completed:
            return
        if button == 0:
            self.clicks += 1
            if self.clicks >= self.required_clicks:
                self._completed = True
                if self._on_complete is not None:
                    self._on_complete()

    def update(self, dt: float):
        if self._completed or self._failed:
            return
        self.time_left -= dt
        if self.time_left <= 0.0:
            self.time_left = 0.0
            self._failed = True
            if self._on_fail is not None:
                self._on_fail()

    # Compatibility with update(gpx, gpy) called from ControllerHUD.update –
    # the mash challenge doesn't need the stick position, so ignore it.
    def __call__(self, *args):
        pass


# ====================================================================== #
#  _DpadChallenge - a series of D-pad directions                          #
# ====================================================================== #

class _DpadChallenge:
    """
    The player must press a series of randomly generated D-pad directions
    (or the matching joystick buttons) within a set time.

    Available directions (dx, dy):
        ( 0, -1) up       -> button index 11 (DpadUp)    / K_UP
        ( 0,  1) down     -> button index 12 (DpadDown)  / K_DOWN
        (-1,  0) left     -> button index 13 (DpadLeft)  / K_LEFT
        ( 1,  0) right    -> button index 14 (DpadRight) / K_RIGHT

    D-pad button mapping depends on the controller.
    Support for SDL hat events is in ControllerHUD.handle_hat (added below).
    """

    DIRECTIONS = [
        ( 0, -1),   # up
        ( 0,  1),   # down
        (-1,  0),   # left
        ( 1,  0),   # right
    ]

    # SDL hat → (dx, dy) mapa
    HAT_MAP = {
        ( 0,  1): ( 0, -1),   # hat up   -> direction up
        ( 0, -1): ( 0,  1),   # hat down   -> direction down
        (-1,  0): (-1,  0),   # hat left  -> direction left
        ( 1,  0): ( 1,  0),   # hat right -> direction right
    }

    def __init__(self, steps: int = 10, step_time: float = 0.5, on_complete=None, on_fail=None):
        self.steps = steps
        self.step_time = step_time
        self.step_time_left = step_time
        self._sequence = [random.choice(self.DIRECTIONS) for _ in range(steps)]
        self.current_step = 0
        self._on_complete = on_complete
        self._on_fail = on_fail
        self._completed = False
        self._failed = False
        self._flash = False          # brief flash on a correct press
        self._flash_timer = 0.0

    def current_direction(self):
        """Returns (dx, dy) of the currently required direction."""
        if self.current_step >= self.steps:
            return (0, 0)
        return self._sequence[self.current_step]

    def handle_button(self, button: int):
        """
        Called on a joystick button press.
        D-pad buttons: 11=up, 12=down, 13=left, 14=right (Xbox/PS standard).
        """
        if self._completed or self._failed or self.current_step >= self.steps:
            return
        btn_to_dir = {
            11: ( 0, -1),
            12: ( 0,  1),
            13: (-1,  0),
            14: ( 1,  0),
        }
        direction = btn_to_dir.get(button)
        if direction is not None:
            self._check_direction(direction)

    def handle_hat(self, hat_value):
        """
        Called on D-pad movement (JOYHATMOTION).
        hat_value = (x, y) from SDL: up=(0,1), down=(0,-1), left=(-1,0), right=(1,0).
        """
        if self._completed or self._failed or self.current_step >= self.steps:
            return
        if hat_value == (0, 0):
            return   # released
        direction = self.HAT_MAP.get(hat_value)
        if direction is not None:
            self._check_direction(direction)

    def _check_direction(self, direction):
        """Checks whether the pressed direction matches the required one."""
        if direction == self.current_direction():
            self._flash = True
            self._flash_timer = 0.15
            self.current_step += 1
            self.step_time_left = self.step_time   # reset the timer for the next step
            if self.current_step >= self.steps:
                self._completed = True
                if self._on_complete is not None:
                    self._on_complete()
        else:
            # Wrong direction -> immediate fail
            self._failed = True
            if self._on_fail is not None:
                self._on_fail()

    def update(self, dt: float):
        if self._completed or self._failed:
            return
        # Flash timer
        if self._flash:
            self._flash_timer -= dt
            if self._flash_timer <= 0.0:
                self._flash = False
        # Step timer – expiry = fail
        if self.current_step < self.steps:
            self.step_time_left -= dt
            if self.step_time_left <= 0.0:
                self.step_time_left = 0.0
                self._failed = True
                if self._on_fail is not None:
                    self._on_fail()

    # Compatibility with update(gpx, gpy) calls from ControllerHUD.update
    def __call__(self, *args):
        pass
