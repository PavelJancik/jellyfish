"""
game_scene.py
=============
Game scene module for Underwater Adventure.

Movement logic
---------------
The background is wider than the screen.
Jelly stays centered on screen and the BACKGROUND MOVES around it.

Phase 1 – background scrolling:
  While the left/right edge of the background hasn't reached the screen edge,
  the background scrolls and Jelly stays centered (horizontally).
  Vertically, Jelly always moves freely (clamped to the screen height).

Phase 2 – Jelly moves:
  Once the background hits its end, Jelly starts moving
  across the screen and is clamped to its edge.
  Once Jelly returns to the screen center, the background starts
  scrolling again (phase 1).

Usage in main.py
-----------------
    from game_scene import GameScene

    game_scene = GameScene(screen_w, screen_h, jelly)

    # in the game loop:
    elif state == 'game':
        keys = pygame.key.get_pressed()
        game_scene.update(dt, keys)
        game_scene.draw(screen)
"""

from __future__ import annotations

import random
import os
import pygame
from jelly_character import JellyCharacter
from npc_character import NPCCharacter
from ambient_fish import AmbientFish, make_freed_fish
from interactive_object import load_objects
from engine import load_font, VideoFade, SpellEffect


class FallingTrash:
    """
    A piece of trash falling from top to bottom.
    Spawns at y=0.1*screen_h, falls to y=0.9*screen_h where it stops.
    The image is picked randomly from imgs/trash/.
    """
    FALL_SPEED = 80.0   # px/s

    _images: list[pygame.Surface] = []   # shared across instances (loaded once)

    @classmethod
    def preload(cls, screen_h: int) -> None:
        """Loads images from imgs/trash/ (call once before the first spawn)."""
        if cls._images:
            return
        folder = "imgs/trash"
        if not os.path.isdir(folder):
            return
        exts = {".png", ".jpg", ".jpeg", ".webp"}
        for fname in sorted(os.listdir(folder)):
            if os.path.splitext(fname)[1].lower() in exts:
                try:
                    raw = pygame.image.load(os.path.join(folder, fname)).convert_alpha()
                    # Scale to ~4% of screen height (same as manta trash)
                    scale = (screen_h * 0.10) / raw.get_height()
                    w = max(1, int(raw.get_width()  * scale))
                    h = max(1, int(raw.get_height() * scale))
                    cls._images.append(pygame.transform.smoothscale(raw, (w, h)))
                except Exception:
                    pass

    def __init__(self, screen_w: int, screen_h: int, bg_w: int, bg_x: float, world_x: float | None = None) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._surf = random.choice(self._images) if self._images else None
        self.w = self._surf.get_width()  if self._surf else 40
        self.h = self._surf.get_height() if self._surf else 40
        # world_x random across the full background width, x = current screen position
        self.world_x = float(random.randint(0, max(0, bg_w - self.w))) if world_x is None else world_x
        self.x = self.world_x + bg_x
        self.y = float(screen_h * 0.1)
        self._floor_y = screen_h * random.uniform(0.8, 0.9)
        self._landed  = False
        self._fading   = False
        self._fade_in  = True
        self._alpha    = 0.0
        self.active    = True
        self._angle      = random.uniform(-60.0, 60.0)  # static rotation set at spawn

    # screen_rect for collision with Jelly (compatible with the InteractiveObject API)
    @property
    def screen_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def is_done(self) -> bool:
        return not self.active

    def try_interact(self, jelly_rect: pygame.Rect) -> bool:
        """If Jelly collides with the trash, starts a fade-out."""
        if not self.active or self._fading:
            return False
        if jelly_rect.colliderect(self.screen_rect):
            self._fading = True
            return True
        return False

    def update(self, dt: float, scroll_delta: float = 0.0) -> None:
        if not self.active:
            return
        # Track background scrolling
        self.x -= scroll_delta
        if self._fade_in:
            self._alpha += 255.0 * dt   # fade in za ~1 s
            if self._alpha >= 255.0:
                self._alpha = 255.0
                self._fade_in = False
        if self._fading:
            self._alpha -= 300.0 * dt
            if self._alpha <= 0.0:
                self._alpha = 0.0
                self.active = False
            return
        if not self._landed:
            self.y += self.FALL_SPEED * dt
            if self.y >= self._floor_y:
                self.y = self._floor_y
                self._landed = True

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active or self._surf is None:
            return
        rotated = pygame.transform.rotate(self._surf, self._angle)
        rw, rh = rotated.get_size()
        cx = int(self.x) + self.w // 2 - rw // 2
        cy = int(self.y) + self.h // 2 - rh // 2
        if self._fading or self._fade_in:
            rotated = rotated.copy()
            rotated.set_alpha(int(self._alpha))
        surface.blit(rotated, (cx, cy))


class GameScene:
    """
    Game scene with a scrolling background and the Jelly character.

    Shared audio cache (loaded once for all instances):
    ----------------------------------------------------------
    _bubble_sounds  : list of preloaded pygame.mixer.Sound for audio/bubbles/
    _speech_cache   : dict {mission_type: pygame.mixer.Sound} for NPC speech
    

    # Shared cache – filled by calling GameScene.preload_audio() from main.py
    _bubble_sounds: list = []
    _speech_cache:  dict = {}

    Parameters
    ----------
    screen_w, screen_h : screen dimensions
    jelly              : instance JellyCharacter
    animal             : animal name (used to load the background and NPC)

    Missions
    --------
    A mission starts the moment Jelly overlaps the NPC.
    Only one mission can run at a time across all GameScene
    instances – main.py enforces this via the ``mission_active`` property.

    - turtle : interact with all interactive_object instances (faded corals)
    - manta  : interact with all interactive_object instances (trash)
                + free all trapped fish
    - whale  : no mission
    """

    @classmethod
    def preload_audio(cls) -> None:
        """
        Preloads all game audio into RAM.
        Call once from main.py during the loading screen (before the game loop starts).

        Loads:
          • audio/bubbles/   – bubble sounds on interaction (channel 6)
          • audio/speech/turtle.mp3, manta.mp3, whale.mp3, final.mp3 – NPC speech (channel 7)
        """
        # --- Bubble sounds ---
        folder = "audio/bubbles"
        exts = {".mp3", ".wav", ".ogg", ".flac"}
        cls._bubble_sounds = []
        if os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                if os.path.splitext(fname)[1].lower() in exts:
                    try:
                        snd = pygame.mixer.Sound(os.path.join(folder, fname))
                        snd.set_volume(0.3)
                        cls._bubble_sounds.append(snd)
                    except Exception:
                        pass

        # --- NPC speech ---
        cls._speech_cache = {}
        for mission in ("turtle", "manta", "whale", "final"):
            path = f"audio/speech/{mission}.mp3"
            if os.path.isfile(path):
                try:
                    snd = pygame.mixer.Sound(path)
                    snd.set_volume(0.6)
                    cls._speech_cache[mission] = snd
                except Exception:
                    pass

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        jelly: JellyCharacter,
        animal: str,
        back_fishes: list[AmbientFish],
        front_fishes: list[AmbientFish],
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.jelly = jelly
        self.npc = NPCCharacter(
            f"imgs/{animal}.png",
            world_x=0,          # recomputed below via place_at_scene_end
            scale=0.7 if animal == "whale" else 1.1,
            flip_x=False if animal == "manta" else True,
            idle_fps=8 if animal == "whale" else 16,
        )

        # --- Background ---
        bg_path = f"imgs/water_{animal}_front.png"
        raw_bg = pygame.image.load(bg_path).convert_alpha()
        orig_w, orig_h = raw_bg.get_size()
        scaled_w = int(orig_w * screen_h / orig_h)
        self.bg = pygame.transform.scale(raw_bg, (scaled_w, screen_h))
        self.bg_w = scaled_w
        # Place the NPC at the scene end – the whole sprite fits regardless of scale
        self.npc.place_at_scene_end(self.bg_w)
        # Center the NPC vertically – independent of frame height

        self.npc.center_on_screen(screen_h, percent=0.75 if animal in ("turtle", "manta") else 0.65)

        # Background's left-edge position on screen (negative = scrolled left)
        self.bg_x: float = 0.0
    
        # --- Mid layer (optional) ---
        self.mid_layer: pygame.Surface | None = None
        mid_layer_path = f"imgs/water_{animal}_mid.png"
        raw_mid = pygame.image.load(mid_layer_path).convert_alpha()
        orig_mid_w, orig_mid_h = raw_mid.get_size()
        scaled_mid_w = int(orig_mid_w * screen_h / orig_mid_h)
        self.mid_layer = pygame.transform.scale(raw_mid, (scaled_mid_w, screen_h))
        self.mid_layer_w = int(orig_mid_w * screen_h / orig_mid_h)
        self.mid_layer_x: float = 0.0
        if animal == 'manta':
             self.mid_layer.fill((200, 200, 200, 255), special_flags=pygame.BLEND_RGBA_MULT)
    
        # --- Jelly at screen center ---
        fw, fh = jelly.frame_size
        self._home_x = screen_w / 2 - fw / 2
        self._home_y = screen_h / 2 - fh / 2
        jelly.set_position(self._home_x, self._home_y)

        # True = Jelly is moving (phase 2), False = background is scrolling (phase 1)
        self._jelly_free: bool = False

        # --- Decorative fish from the imgs/fishes folder ---
        self._fishes_back: list[AmbientFish] = back_fishes
        self._fishes_front: list[AmbientFish] = front_fishes

        self._freed_fishes: list[AmbientFish] = []

        # Interactive objects
        self._objects = load_objects(animal, screen_w, screen_h, bg_width=self.bg_w, on_free=self._spawn_freed)

        # --- Missions ---
        # "turtle"  → interact with all interactive_object instances
        # "manta"   → interact with all interactive_object instances + free trapped fish
        # "whale"   → free trapped fish
        # None      → no mission
        self._mission_type: str | None = animal if animal in ("turtle", "manta", "whale", "final") else None
        self._mission_active: bool = False   # mission is currently running
        self._mission_complete: bool = False  # mission has been completed
        self._game_over: bool = False          # final: object limit exceeded
        # Spell effects – world-space animation at the interaction spot
        self._spell_effects: list[SpellEffect] = []
        # Ikonka "lze interagovat" – zobrazuje se za objektem
        _ci_path = "imgs/can_interact.png"
        if os.path.isfile(_ci_path):
            _ci_raw = pygame.image.load(_ci_path).convert_alpha()
            _ci_h = int(screen_h * 0.12)   # 12% of screen height
            _ci_w = max(1, int(_ci_raw.get_width() * _ci_h / _ci_raw.get_height()))
            self._can_interact_img: pygame.Surface | None = pygame.transform.smoothscale(_ci_raw, (_ci_w, _ci_h))
        else:
            self._can_interact_img = None
        self._interact_angle: float = 0.0   # current icon rotation angle (degrees)
        # Final mission – timers
        self._music_timer:  float = 0.0   # time since music started
        self._trash_timer:  float = 0.0   # countdown to the next trash spawn
        self._falling_trash: list = []    # falling trash items
        self._outro_triggered: bool = False   # True = video already started
        self._outro_video = None               # pyvidplayer2.Video or None
        self._outro_video_done: bool = False   # True = video ended naturally
        self._outro_playing: bool = False      # True = video is playing (game scene isn't drawn)
        self._outro_fade: VideoFade | None = None   # fade-out before the outro video starts
        self._outro_fade_done: bool = False         # True = fade-out finished, video can start
        self._music_fade_start_vol: float = 1.0    # music volume at the start of the fade-out
        # Preloaded music for the final mission (avoids a lag spike on start)
        self._final_music_channel: pygame.mixer.Channel | None = None
        if self._mission_type == "final":
            try:
                self._final_music_sound = pygame.mixer.Sound("audio/final_bg_audio.mp3")
            except Exception:
                self._final_music_sound = None
        else:
            self._final_music_sound = None

    def start_interact_challenge(self, controller_hud, joystick=None) -> bool:
        """
        Checks if Jelly overlaps an interactive object (or a trapped fish
        for the manta mission). If so, starts the matching challenge in controller_hud:
          - "manta"  → joystick challenge (stick + L1)
          - "whale"  → mash challenge (rapid A presses)
          - "turtle" → d-pad challenge (direction sequence)

        Called instead of button 0 from main.py.

        Returns True if a challenge was started (Jelly is near an object).
        """
        if not self._mission_active:
            return False
        if controller_hud.joy_game is not None:
            # A challenge is already running – don't start another
            return False

        fw, fh = self.jelly.frame_size
        jelly_rect = pygame.Rect(int(self.jelly.x), int(self.jelly.y), fw, fh)

        # Find the first object Jelly collides with
        target_obj = None
        for obj in self._objects:
            if obj.active and not obj.is_done and jelly_rect.colliderect(obj.screen_rect):
                target_obj = obj
                break

        # For manta/final missions also look for a trapped fish or falling trash
        target_fish = None
        if self._mission_type in ("manta", "final") and target_obj is None:
            for fish in self._fishes_front + self._fishes_back:
                if fish.overlaps_jelly(jelly_rect):
                    target_fish = fish
                    break

        # Look for falling trash (final mission only)
        target_trash = None
        if self._mission_type == "final" and target_obj is None and target_fish is None:
            fw2, fh2 = self.jelly.frame_size
            jelly_rect2 = pygame.Rect(int(self.jelly.x), int(self.jelly.y), fw2, fh2)
            for trash in self._falling_trash:
                if trash.active and not trash._fading and jelly_rect2.colliderect(trash.screen_rect):
                    target_trash = trash
                    break

        if target_obj is None and target_fish is None and target_trash is None:
            return False

        # Snapshot of the current rect (for the callback)
        snap_rect = pygame.Rect(jelly_rect)

        def _on_success():
            # Called once the challenge is completed
            if target_obj is not None:
                target_obj.try_interact(snap_rect)
            if target_fish is not None:
                target_fish.free()
            if target_trash is not None:
                target_trash._fading = True
            # Spell effect at the interacted object's center (stays visually in place)
            if target_obj is not None:
                sr = target_obj.screen_rect
                self._spawn_spell_effect(sr.centerx, sr.centery)
            elif target_fish is not None:
                self._spawn_spell_effect(target_fish.get_rect().centerx, target_fish.get_rect().centery)
            elif target_trash is not None:
                tr = target_trash.screen_rect
                self._spawn_spell_effect(tr.centerx, tr.centery)
            if joystick is not None:
                try:
                    joystick.rumble(0.3, 0.7, 200)
                except Exception:
                    pass

        if self._mission_type == "manta":
            controller_hud.start_joystick_game(on_complete=_on_success)
        elif self._mission_type == "whale":
            controller_hud.start_mash_game(on_complete=_on_success, required_clicks=10, time_limit=2.5)
        elif self._mission_type == "turtle":
            controller_hud.start_dpad_game(on_complete=_on_success, steps=5, step_time=1.25)
        elif self._mission_type == "final":
            random_choice = random.choice(["joystick", "mash", "dpad"])
            if random_choice == "joystick":
                controller_hud.start_joystick_game(on_complete=_on_success)
            elif random_choice == "mash":
                controller_hud.start_mash_game(on_complete=_on_success, required_clicks=5, time_limit=2.0)
            elif random_choice == "dpad":
                controller_hud.start_dpad_game(on_complete=_on_success, steps=3, step_time=2.0)
        else:
            controller_hud.start_joystick_game(on_complete=_on_success)

        # Store references to the challenge target and HUD for auto-cancel on walk-away
        self._challenge_hud = controller_hud
        self._challenge_target_obj = target_obj
        self._challenge_target_fish = target_fish
        self._challenge_target_trash = target_trash
        self._challenge_joystick = joystick   # for _draw_interact_prompt
        return True

    # ------------------------------------------------------------------
    # Mission – public API
    # ------------------------------------------------------------------

    @property
    def mission_active(self) -> bool:
        """True if a mission is currently running in this scene."""
        return self._mission_active

    @property
    def mission_complete(self) -> bool:
        """True if the mission has been completed (all goals done)."""
        return self._mission_complete

    @property
    def game_over(self) -> bool:
        """True if the final mission ended in game-over (too many objects)."""
        return self._game_over

    @property
    def outro_video_done(self) -> bool:
        """True if the final outro video finished playing naturally."""
        return self._outro_video_done

    @property
    def outro_playing(self) -> bool:
        """True = the outro video has started and should take over the screen (game scene isn't drawn)."""
        return self._outro_playing

    def start_mission(self) -> None:
        """Starts the mission (called by main.py once no other mission is running)."""
        if self._mission_type is None or self._mission_complete:
            return
        self._mission_active = True

        # --- Music and setup for the final mission ---
        if self._mission_type == "final":
            FallingTrash.preload(self.screen_h)
            self._music_timer    = 0.0
            self._trash_timer    = 0.0   # first trash right after reaching 35 s
            self._falling_trash  = []
            self._outro_triggered  = False
            self._outro_video      = None
            self._outro_video_done = False
            self._outro_playing    = False
            self._outro_fade       = None
            self._outro_fade_done  = False
            self._music_fade_start_vol = 0.85
            # Final music was preloaded in __init__ – just start playback here
            # Channel 5 = final music, 6 = bubbles, 7 = NPC voice.
            try:
                if self._final_music_sound is not None:
                    self._final_music_sound.set_volume(self._music_fade_start_vol)
                    self._final_music_channel = pygame.mixer.Channel(5)
                    self._final_music_channel.play(self._final_music_sound)  # no looping
            except Exception:
                self._final_music_channel = None

        # --- NPC speech – played on its own channel (Sound) so it doesn't interrupt
        #     other active audio tracks (music, ambience...).
        #     pygame.mixer.Sound runs independently of pygame.mixer.music. ---
        # NPC speech from the preloaded cache (preload_audio) – no I/O at runtime
        speech = self._speech_cache.get(self._mission_type)
        if speech is not None:
            try:
                speech_channel = pygame.mixer.Channel(7)
                speech_channel.stop()          # stop any previous speech (edge case)
                speech_channel.play(speech)    # plays once, doesn't interrupt the music
            except Exception:
                pass  # mixer not initialized

    def _try_trigger_mission(self, can_start: bool) -> None:
        """
        Checks if Jelly overlaps the NPC.
        If so, and the mission hasn't started or completed yet,
        and no other mission is running (can_start), starts the mission.
        """
        if self._mission_type is None:
            return
        if self._mission_active or self._mission_complete:
            return
        if not can_start:
            return
        fw, fh = self.jelly.frame_size
        jelly_rect = pygame.Rect(int(self.jelly.x), int(self.jelly.y), fw, fh)
        if jelly_rect.colliderect(self.npc.screen_rect):
            self.start_mission()

    def _check_mission_complete(self) -> None:
        """Checks whether all mission goals have been completed."""
        if not self._mission_active:
            return

        if self._mission_type == "turtle":
            done = all(obj.is_done for obj in self._objects)

        elif self._mission_type == "manta":
            objects_done = all(obj.is_done for obj in self._objects)
            fishes_done = all(
                not fish.is_trapped
                for fish in self._fishes_front + self._fishes_back
            )
            done = objects_done and fishes_done

        elif self._mission_type == "whale":
            done = all(obj.is_done for obj in self._objects)

        elif self._mission_type == "final":
            done = False   # the final mission has no standard end (time/video driven)

        else:
            done = False

        if done:
            self._mission_active = False
            self._mission_complete = True

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @property
    def _bg_max_scroll(self) -> float:
        """Maximum leftward background scroll (a negative number)."""
        return -(self.bg_w - self.screen_w)

    def _bg_at_left_end(self) -> bool:
        return self.bg_x >= 0.0

    def _bg_at_right_end(self) -> bool:
        return self.bg_x <= self._bg_max_scroll

    def _bg_can_scroll(self, direction_x: float) -> bool:
        """
        Returns True if the background can scroll in the player's movement direction.
        Player moves right (vx > 0) -> bg moves left (bg_x decreases) -> limited by the right end.
        Player moves left  (vx < 0) -> bg moves right (bg_x increases) -> limited by the left end.
        """
        if direction_x > 0:
            return not self._bg_at_right_end()
        if direction_x < 0:
            return not self._bg_at_left_end()
        return False

    def _jelly_at_center(self) -> bool:
        """Jelly has reached the screen center (within a 2px tolerance)."""
        return abs(self.jelly.x - self._home_x) < 2.0

    def _jelly_passed_center(self, vx: float) -> bool:
        """
        Returns True if Jelly has passed the center in the direction of movement.
        vx > 0 = moving right -> center passed once jelly.x >= home_x
        vx < 0 = moving left  -> center passed once jelly.x <= home_x
        """
        if vx > 0:
            return self.jelly.x >= self._home_x
        if vx < 0:
            return self.jelly.x <= self._home_x
        return False

    def _spawn_freed(self, trap_img_path: str, world_x: float, y: float) -> None:
        fish = make_freed_fish(self.screen_w, self.screen_h, world_x, y, bg_x=self.bg_x, trap_img_path=trap_img_path)
        if fish:
            self._freed_fishes.append(fish)

    def _spawn_spell_effect(self, screen_cx: float, screen_cy: float) -> None:
        """
        Creates a SpellEffect at the given screen coordinates.
        The effect visually stays at the interaction spot (independent of Jelly's movement).
        Also plays a random sound from audio/bubbles/ on channel 6,
        so it doesn't interrupt the music (pygame.mixer.music) or NPC voice (channel 7).
        """
        self._spell_effects.append(SpellEffect(screen_cx, screen_cy, scale=0.2))
        self._play_bubble_sound()

    def _play_bubble_sound(self) -> None:
        """
        Plays a random sound from the preloaded cache (GameScene._bubble_sounds).

        Channel 6 is reserved for interaction bubble sounds only.
        Channel 7 is reserved for NPC voice (see start_mission).
        pygame.mixer.music runs independently (background music / final_bg_audio).
        So none of these sounds interrupt each other.
        """
        if not self._bubble_sounds:
            return
        try:
            sound = random.choice(self._bubble_sounds)
            bubble_channel = pygame.mixer.Channel(6)
            # Only play if the channel isn't already busy (sounds don't overlap)
            if not bubble_channel.get_busy():
                bubble_channel.play(sound)
        except Exception:
            pass  # mixer not initialized

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper, joystick=None, can_start_mission: bool = True) -> None:
        """
        Updates the scene.

        Parameters
        ----------
        dt                : delta time in seconds
        keys              : output of pygame.key.get_pressed()
        joystick          : pygame.joystick.Joystick or None
        can_start_mission : True if no other scene currently has
                            an active mission – passed in by main.py
        """

        self.npc.sync_with_background(self.bg_x)
        self.npc.update(dt)

        # Interactive objects
        for obj in self._objects:
            obj.update(dt, self.bg_x)

        # --- Decorative fish ---
        for fish in self._fishes_back + self._fishes_front:
            fish.update(dt)

        # --- Freed fish ---
        for fish in self._freed_fishes: 
            fish.update(dt)        


        # --- Final mission: timers, trash spawning, outro video ---
        if self._mission_type == "final" and self._mission_active:
            self._music_timer += dt

            # Spawn falling trash od 40. sekundy, frequence se postupne zvysuje
            video_end_time = 150.0
            if self._music_timer >= 40.0 and self._music_timer <= video_end_time:
                self._trash_timer -= dt
                if self._trash_timer <= 0.0:                
                    spawn_interval = 4.0 
                    if self._music_timer >= 60: spawn_interval = 3.0                    
                    if self._music_timer >= 80: spawn_interval = 2.0
                    if self._music_timer >= 102: spawn_interval = 1.0
                    if self._music_timer >= 125: spawn_interval = 0.5
                    if self._music_timer >= 135: spawn_interval = 0.3
                    if self._music_timer >= 145: spawn_interval = 0.2                    
                    self._trash_timer = spawn_interval
                    trash_x = (self.jelly.x - self.bg_x) if self._music_timer < 42.0 else None # spawn first trash near jelly (screen → world coords)
                    self._falling_trash.append(FallingTrash(self.screen_w, self.screen_h, self.bg_w, self.bg_x, world_x=trash_x))

            # Remove inactive trash
            self._falling_trash = [t for t in self._falling_trash if t.active]

            # Outro video at 2:20 (143 s) – fade out the screen and music first
            if not self._outro_triggered and self._music_timer >= video_end_time:
                self._outro_triggered = True
                self._music_fade_start_vol = self._final_music_sound.get_volume() if self._final_music_sound else 0.85
                self._outro_fade = VideoFade(self.screen_w, self.screen_h, speed=300.0)
                self._outro_fade._alpha = 0.0   # start transparent and fade to black
                self._outro_fade._dir = 1       # 1 = fade-out (to black)

            # Fade-out progress before the outro video
            if self._outro_fade is not None and not self._outro_fade_done:
                self._outro_fade._alpha = min(255.0, self._outro_fade._alpha + self._outro_fade._speed * dt)
                # Gradually lower the music volume to 0 alongside the screen fade-out
                progress = min(self._outro_fade._alpha / 255.0, 1.0)
                try:
                    if self._final_music_sound is not None:
                        self._final_music_sound.set_volume(self._music_fade_start_vol * (1.0 - progress))
                except Exception:
                    pass

                if progress >= 1.0:
                    # Fade complete -> stop the music and start the video
                    self._outro_fade_done = True
                    try:
                        if self._final_music_channel is not None:
                            self._final_music_channel.stop()
                        if self._final_music_sound is not None:
                            self._final_music_sound.set_volume(self._music_fade_start_vol)
                    except Exception:
                        pass
                    try:
                        from pyvidplayer2 import Video
                        self._outro_video = Video("video/final.mp4")
                        self._outro_video.resize((self.screen_w, self.screen_h))
                        self._outro_playing = True   # signal for main.py -> leave game_scene
                    except Exception:
                        self._outro_video_done = True  # video failed to start -> go straight to home


        # Update falling trash (even outside the mission, so it lands)
        for trash in self._falling_trash:
            trash.update(dt)

        # --- Mission: start on NPC contact, ongoing completion check ---
        self._try_trigger_mission(can_start_mission)
        self._check_mission_complete()

        # --- Auto-cancel the challenge if Jelly moved away from the object ---
        if hasattr(self, '_challenge_hud') and self._challenge_hud is not None:
            hud = self._challenge_hud
            if hud.joy_game is not None and not hud.joy_game._completed:
                fw, fh = self.jelly.frame_size
                jelly_rect = pygame.Rect(int(self.jelly.x), int(self.jelly.y), fw, fh)
                still_near = False
                if self._challenge_target_obj is not None:
                    still_near = self._challenge_target_obj.active and jelly_rect.colliderect(self._challenge_target_obj.screen_rect)
                elif self._challenge_target_fish is not None:
                    still_near = self._challenge_target_fish.overlaps_jelly(jelly_rect)
                elif hasattr(self, '_challenge_target_trash') and self._challenge_target_trash is not None:
                    still_near = self._challenge_target_trash.active and jelly_rect.colliderect(self._challenge_target_trash.screen_rect)
                if not still_near:
                    hud.stop_games()
                    self._challenge_hud = None
                    self._challenge_target_obj = None
                    self._challenge_target_fish = None
                    self._challenge_target_trash = None

        vx = 0.0
        if keys[pygame.K_LEFT]:
            vx -= self.jelly.speed
        if keys[pygame.K_RIGHT]:
            vx += self.jelly.speed

        # Joystick – axis 0 (horizontal), dead zone 0.15
        if joystick is not None:
            raw_x = joystick.get_axis(0)
            if abs(raw_x) >= self.jelly.JOYSTICK_DEADZONE:
                vx = raw_x * self.jelly.speed

        # --- Horizontal logic ---
        jelly_can_move_x = False

        if vx != 0:
            if self._jelly_free:
                # Phase 2: Jelly moves across the screen.
                #
                # If Jelly is moving toward the center and the background has room
                # to scroll, check whether Jelly reached the center ->
                # if so, switch back to background scrolling (phase 1).

                bg_would_scroll = self._bg_can_scroll(vx)

                if bg_would_scroll and self._jelly_passed_center(vx):
                    # Jelly just passed the center -> snap to center and switch to phase 1
                    self.jelly.x = self._home_x
                    self._jelly_free = False
                    # The rest of the movement is handled by phase 1 below
                    self.bg_x -= vx * dt
                    self.bg_x = max(self._bg_max_scroll, min(0.0, self.bg_x))
                    self.mid_layer_x -= vx * dt / 5
                    for fish in self._fishes_back:
                        fish.x -= vx * dt / 5
                    for fish in self._fishes_front + self._freed_fishes:
                        fish.x -= vx * dt
                    for trash in self._falling_trash:
                        trash.x -= vx * dt
                    for e in self._spell_effects:
                        e.scroll(vx * dt)
                else:
                    # Jelly moves normally across the screen
                    jelly_can_move_x = True

            else:
                # Phase 1: scroll the background, Jelly stays in place.
                if self._bg_can_scroll(vx):
                    self.bg_x -= vx * dt
                    self.bg_x = max(self._bg_max_scroll, min(0.0, self.bg_x))
                    self.mid_layer_x -= vx * dt / 5
                    for fish in self._fishes_back:
                        fish.x -= vx * dt / 5
                    for fish in self._fishes_front + self._freed_fishes:
                        fish.x -= vx * dt
                    for trash in self._falling_trash:
                        trash.x -= vx * dt
                    for e in self._spell_effects:
                        e.scroll(vx * dt)
                else:
                    # Background hit its end -> switch to phase 2
                    self._jelly_free = True
                    jelly_can_move_x = True

        # --- Forward input to Jelly (animation + vertical movement) ---
        self.jelly.handle_input(keys, joystick)

        if not jelly_can_move_x:
            self.jelly._vel_x = 0.0

        self.jelly.update(dt)

        # --- Clamp Jelly ---
        fw, fh = self.jelly.frame_size
        self.jelly.y = max(self.screen_h * 0.3, min(self.jelly.y, self.screen_h - fh))

        if jelly_can_move_x:
            self.jelly.x = max(0.0, min(self.jelly.x, self.screen_w - fw))
        elif not self._jelly_free:
            # Phase 1: keep Jelly exactly centered
            self.jelly.x = self._home_x

        # --- Spell effects – shift with background scroll + tick animation ---
        self._spell_effects = [e for e in self._spell_effects if not e.done]
        for e in self._spell_effects:
            e.update(dt)

        # --- Rotace ikonky can_interact ---
        self._interact_angle = (self._interact_angle - 45 * dt) % 360   # 90°/s

    def draw(
        self,
        surface: pygame.Surface,
        underlay_override: pygame.Surface | None = None,
    ) -> None:
        """
        Draws the scene onto the surface.

        Parameters
        ----------
        underlay_override : animated water frame passed in from main.py
        """
        # If the outro video is playing, skip drawing the game scene – main.py calls draw_outro()
        if self._outro_playing:
            return

        # Bottom layer (animated water)
        if underlay_override:
            surface.blit(underlay_override, (0, 0))

        # Mid Layer
        if self.mid_layer:
            surface.blit(self.mid_layer, (int(self.mid_layer_x), 0))

        # Decorative fish (background) – icon behind a trapped fish, then the fish
        self._draw_interact_icon_fish(surface, self._fishes_back)
        for fish in self._fishes_back:
            fish.draw(surface)

        # Background with alpha
        surface.blit(self.bg, (int(self.bg_x), 0))

        # NPC
        self.npc.draw(surface)

        # Interactive objects (icon drawn BEHIND the object -> icon first, then the object)
        self._draw_interact_icon_objects(surface)
        for obj in self._objects:
            obj.draw(surface)

        # Jelly
        self.jelly.draw(surface)

        # Spell effects (one-shot animation at the interaction spot)
        for e in self._spell_effects:
            e.draw(surface)

        # Decorative fish (foreground) – icon behind a trapped fish, then the fish
        self._draw_interact_icon_fish(surface, self._fishes_front)
        for fish in self._fishes_front:
            fish.draw(surface)

        # Freed fish
        for fish in self._freed_fishes:
            fish.draw(surface)

        # Falling trash (final mission)
        for trash in self._falling_trash:
            trash.draw(surface)

        # HUD – mission progress bar
        if self._mission_type == "final":
            if self._mission_active or self._mission_complete:
                self._draw_final_hud(surface)
        elif self._mission_active or self._mission_complete:
            self._draw_mission_hud(surface)

        # Fade-out to black before the outro video starts
        if self._outro_fade is not None and not self._outro_fade_done:
            alpha = int(self._outro_fade._alpha)
            if alpha > 0:
                self._outro_fade._surf.set_alpha(alpha)
                surface.blit(self._outro_fade._surf, (0, 0))

    def draw_outro(self, surface: pygame.Surface) -> None:
        """
        Draws only the outro video, full screen.
        Called by main.py in the 'outro' state instead of game_scene.draw().
        Sets _outro_video_done = True once the video ends naturally.
        """
        if self._outro_video is None:
            self._outro_video_done = True
            return
        if self._outro_video.active:
            self._outro_video.draw(surface, (0, 0), force_draw=True)
        else:
            self._outro_video.stop()
            self._outro_video = None
            self._outro_playing   = False
            self._outro_video_done = True

    def stop_outro(self) -> None:
        """
        Immediately stops the outro video and fully resets its state.
        Called by main.py when the player skips the outro.

        This must clear the same flags draw_outro() clears on a natural
        finish (_outro_video, _outro_playing, _outro_video_done). Otherwise
        _outro_playing stays True, and the very next time the final scene's
        update()/draw() runs (e.g. right after the player presses Play on
        the home screen) main.py sees outro_playing still True and bounces
        straight back into the 'outro' state for one extra cycle -- which
        is what made a skip need a second Play press to actually start
        the game.
        """
        if self._outro_video is not None:
            try:
                self._outro_video.stop()
            except Exception:
                pass
        self._outro_video = None
        self._outro_playing = False
        self._outro_video_done = True

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------

    def _challenge_active(self) -> bool:
        """True while the challenge HUD is currently running."""
        return (
            hasattr(self, '_challenge_hud')
            and self._challenge_hud is not None
            and self._challenge_hud.joy_game is not None
        )

    def _jelly_rect(self) -> pygame.Rect:
        fw, fh = self.jelly.frame_size
        return pygame.Rect(int(self.jelly.x), int(self.jelly.y), fw, fh)

    def _draw_can_interact_at(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draws the can_interact.png icon centered on the given rect, with rotation."""
        if self._can_interact_img is None:
            return
        img = pygame.transform.rotate(self._can_interact_img, self._interact_angle)
        iw, ih = img.get_size()
        surface.blit(img, (rect.centerx - iw // 2, rect.centery - ih // 2))

    def _draw_interact_icon_objects(self, surface: pygame.Surface) -> None:
        """
        Draws the icon BEHIND the interactive object or falling trash
        that Jelly is colliding with. Call right BEFORE the obj.draw() loop.
        """
        if self._can_interact_img is None or self._challenge_active():
            return
        if not self._mission_active:
            return
        jr = self._jelly_rect()
        for obj in self._objects:
            if obj.active and not obj.is_done and jr.colliderect(obj.screen_rect):
                self._draw_can_interact_at(surface, obj.screen_rect)
                return
        if self._mission_type == "final":
            for trash in self._falling_trash:
                if trash.active and not trash._fading and jr.colliderect(trash.screen_rect):
                    self._draw_can_interact_at(surface, trash.screen_rect)
                    return

    def _draw_interact_icon_fish(self, surface: pygame.Surface, fish_list: list) -> None:
        """
        Draws the icon BEHIND the trapped fish from the given layer that Jelly is colliding with.
        Call right BEFORE the fish.draw() loop, separately for each layer.
        """
        if self._can_interact_img is None or self._challenge_active():
            return
        if not self._mission_active:
            return
        if self._mission_type not in ("manta", "whale", "final"):
            return
        jr = self._jelly_rect()
        for fish in fish_list:
            if fish.is_trapped and fish.overlaps_jelly(jr):
                self._draw_can_interact_at(surface, fish.get_rect())
                return

    def _mission_progress(self) -> float:
        """
        Returns the current mission progress as a value 0.0-1.0.

        turtle, whale : fraction of completed interactive_object instances
        manta         : average of completed interactive_object instances + freed fish
        """
        if self._mission_type in ("turtle", "whale"):
            if not self._objects:
                return 1.0
            return sum(1 for o in self._objects if o.is_done) / len(self._objects)

        elif self._mission_type == "manta":
            obj_total = len(self._objects)
            fish_total = sum(1 for f in self._fishes_front + self._fishes_back if f.trapped)
            total = obj_total + fish_total
            if total == 0:
                return 1.0
            done_obj  = sum(1 for o in self._objects if o.is_done)
            done_fish = sum(1 for f in self._fishes_front + self._fishes_back
                           if f.trapped and not f.is_trapped)
            return (done_obj + done_fish) / total

        return 0.0

    def _draw_final_hud(self, surface: pygame.Surface) -> None:
        """
        Horizontal progress bar centered at the top of the screen.
        Shows the count of remaining active (uncleaned) objects.
        Shows the matching message on game-over or completion.
        """
        active   = sum(1 for o in self._objects if not o.is_done)
        active  += sum(1 for f in self._fishes_front + self._fishes_back if f.is_trapped)
        active  += sum(1 for t in self._falling_trash if t.active and not t._fading)
        total    = 100          # limit = game over

        BAR_W    = int(self.screen_w * 0.55)
        BAR_H    = 22
        RADIUS   = 11
        PAD_Y    = 18
        cx       = self.screen_w // 2

        bx = cx - BAR_W // 2
        by = PAD_Y + 28          # pod nadpisem

        # --- Fill color based on how full it is ---
        ratio = min(active / total, 1.0)
        if ratio < 0.5:
            r = int(80 + 175 * (ratio / 0.5))
            g = 220
        else:
            r = 255
            g = int(220 - 180 * ((ratio - 0.5) / 0.5))
        fill_col = (r, g, 60)

        # --- Semi-transparent panel background ---
        panel_w = BAR_W + 32
        panel_h = BAR_H + 56
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0, 0, 0, 120), panel.get_rect(), border_radius=14)
        surface.blit(panel, (cx - panel_w // 2, PAD_Y - 6))

        # --- Nadpis ---
        self._final_hud_font_big   = load_font(int(self.screen_h * 0.022))
        self._final_hud_font_small = load_font(int(self.screen_h * 0.018))

        if self._mission_complete:
            title_text  = "Ocean Cleaned!"
            title_color = (80, 220, 120)
        elif active == 0:
            title_text  = "Good job! You are the true hero!"
            title_color = (80, 220, 120)
        else:
            title_text  = f"Trash in ocean: {active}"
            title_color = (230, 230, 255)

        title_surf = self._final_hud_font_big.render(title_text, True, title_color)
        surface.blit(title_surf, (cx - title_surf.get_width() // 2, PAD_Y))

        # --- Progress bar track ---
        track_surf = pygame.Surface((BAR_W, BAR_H), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (50, 50, 80, 200), track_surf.get_rect(), border_radius=RADIUS)
        surface.blit(track_surf, (bx, by))

        # --- Fill ---
        fill_w = max(0, int(BAR_W * ratio))
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, BAR_H), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*fill_col, 220), fill_surf.get_rect(), border_radius=RADIUS)
            surface.blit(fill_surf, (bx, by))

        # --- Warning line at 80% ---
        warn_x = bx + int(BAR_W * 0.8)
        pygame.draw.line(surface, (255, 200, 50, 180), (warn_x, by), (warn_x, by + BAR_H), 2)

        # --- Border ---
        border_surf = pygame.Surface((BAR_W, BAR_H), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (255, 255, 255, 50), border_surf.get_rect(), width=1, border_radius=RADIUS)
        surface.blit(border_surf, (bx, by))

    @staticmethod
    def _progress_color(progress: float, alpha: int = 230) -> tuple[int, int, int, int]:
        """
        Returns the (R,G,B,A) color for the given progress value 0.0-1.0.
        Smooth transition: red (0%) -> orange (50%) -> green (100%).
        """
        progress = max(0.0, min(1.0, progress))

        RED    = (220,  60,  60)
        ORANGE = (255, 165,   0)
        GREEN  = ( 80, 200, 120)

        if progress <= 0.5:
            t = progress / 0.5
            c1, c2 = RED, ORANGE
        else:
            t = (progress - 0.5) / 0.5
            c1, c2 = ORANGE, GREEN

        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return (r, g, b, alpha)

    def _draw_mission_hud(self, surface: pygame.Surface) -> None:
        """
        Draws the mission progress bar in the top-left corner of the screen.

        Layout (all in px, relative to screen_w/screen_h):
        ┌──────────────────────────────┐
        │  [icon]  Mission  [░░░░███] │  ← 20 px from the left/top edge
        └──────────────────────────────┘
        """
        PAD_X       = 20    # gap from the left edge
        PAD_Y       = 20    # gap from the top edge
        BAR_W       = 160   # bar width
        BAR_H       = 14    # bar height
        RADIUS      = 7     # corner rounding
        LABEL_GAP   = 8     # gap between the text and the bar

        progress = self._mission_progress() if not self._mission_complete else 1.0

        # --- Barvy ---
        COLOR_BG        = (20,  20,  20,  100)   # semi-transparent panel background
        COLOR_TRACK     = (60,  60,  90,  200)   # empty part of the bar
        COLOR_FILL      = self._progress_color(progress)
        COLOR_TEXT      = (230, 230, 255, 255)
        COLOR_DONE_TEXT = ( 80, 200, 120, 255)

        # --- Font ---
        self._hud_font = load_font(int(self.screen_h * 0.02))

        label = "Complete" if self._mission_complete else "Progress"
        pct   = f"{int(progress * 100)} %"

        label_surf = self._hud_font.render(label, True, COLOR_DONE_TEXT if self._mission_complete else COLOR_TEXT)
        pct_surf   = self._hud_font.render(pct,   True, COLOR_TEXT)

        label_w, label_h = label_surf.get_size()
        pct_w,   _       = pct_surf.get_size()

        # Full panel width
        panel_w = max(label_w + LABEL_GAP + pct_w + 16, BAR_W + 16)
        panel_h = label_h + LABEL_GAP + BAR_H + 14

        # --- Panel background (rounded rectangle) ---
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, COLOR_BG, panel.get_rect(), border_radius=RADIUS + 2)
        surface.blit(panel, (PAD_X, PAD_Y))

        # --- Text row (label left, percentage right) ---
        text_y = PAD_Y + 7
        surface.blit(label_surf, (PAD_X + 8, text_y))
        surface.blit(pct_surf,   (PAD_X + panel_w - pct_w - 8, text_y))

        # --- Bar ---
        bar_x = PAD_X + 8
        bar_y = text_y + label_h + LABEL_GAP
        bar_w = panel_w - 16

        # Empty track
        track_surf = pygame.Surface((bar_w, BAR_H), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, COLOR_TRACK, track_surf.get_rect(), border_radius=RADIUS)
        surface.blit(track_surf, (bar_x, bar_y))

        # Filled part
        fill_w = max(0, int(bar_w * progress))
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, BAR_H), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, COLOR_FILL, fill_surf.get_rect(), border_radius=RADIUS)
            surface.blit(fill_surf, (bar_x, bar_y))

        # Bar border
        border_surf = pygame.Surface((bar_w, BAR_H), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (255, 255, 255, 60), border_surf.get_rect(), width=1, border_radius=RADIUS)
        surface.blit(border_surf, (bar_x, bar_y))

    def reset(self) -> None:
        """Resets the scene to its default state (call when leaving the map)."""
        self.mid_layer_x = 0.0
        self.bg_x = 0.0
        self._jelly_free = False
        self.jelly.set_position(self._home_x, self._home_y)
        # The mission is NOT reset – a completed mission stays completed across sessions.