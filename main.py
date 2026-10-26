import pygame
import sys
import os
from jelly_character import JellyCharacter
from npc_character import NPCCharacter
from map_screen import MapScreen
from home_screen import HomeScreen
from game_scene import GameScene
from engine import load_frames, draw_loading_screen, FadeTransition, VideoFade, BackgroundMusic, SkipHoldIndicator
from ambient_fish import load_ambient_fishes, load_animated_ambient_fishes
from controller_hud import ControllerHUD
from pyvidplayer2 import Video
from subtitle_overlay import SubtitleOverlay, SubtitleCue

# engine
pygame.init()
pygame.joystick.init()
pygame.mouse.set_visible(False)

# Connect the joystick (index 0 = first joystick)
joystick = None
if pygame.joystick.get_count() > 0:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Joystick: {joystick.get_name()}")

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
# if DEVELOPMENT: pygame.display.set_mode((1080, 720))
screen_w, screen_h = screen.get_size()
pygame.display.set_caption('A Jelly’s Odyssey - The Last Hope')
icon = pygame.image.load('imgs/icon.png')
pygame.display.set_icon(icon)
clock = pygame.time.Clock()

# Background music
bg_music = BackgroundMusic(volume=0.35)

# Level spot names
SPOT_TURTLE = "turtle"
SPOT_MANTA = "manta"
SPOT_WHALE = "whale"
SPOT_FINAL = "final"

# Home
t_frames = load_frames(screen, SPOT_TURTLE)
m_frames = load_frames(screen, SPOT_MANTA)
w_frames = load_frames(screen, SPOT_WHALE)
f_frames = m_frames
frames = t_frames
map_spot = SPOT_TURTLE
current_frame = 0
frame_delay = 5
counter = 0

# Home screen
home_screen = HomeScreen(screen_w, screen_h, bg_frames=w_frames, joystick=joystick)
 
# Map
map_screen = MapScreen(screen_w, screen_h)

# Jelly
jelly = JellyCharacter("imgs/jelly_blue.png", x=300, y=200, scale=0.7)


# Fish
draw_loading_screen(screen, 'Fishes', 0, 100)
back_fishes = load_ambient_fishes(screen_w, screen_h, folder="imgs/fishes", count_per_image=2, front_layer=False)
draw_loading_screen(screen, 'Fishes', 25, 100)
front_fishes = load_ambient_fishes(screen_w, screen_h, folder="imgs/fishes", count_per_image=1, front_layer=True)
draw_loading_screen(screen, 'Fishes', 50, 100)
trapped_fishes = load_ambient_fishes(screen_w, screen_h, folder="imgs/fishes_trapped", count_per_image=1, front_layer=True, trapped=True)
draw_loading_screen(screen, 'Fishes', 75, 100)
animated_fishes_front = load_animated_ambient_fishes(screen_w, screen_h, folder="imgs/fishes_animated", count_per_image=1)
animated_fishes_background = load_animated_ambient_fishes(screen_w, screen_h, folder="imgs/fishes_animated/background", count_per_image=1)
front_fishes += animated_fishes_front
back_fishes = animated_fishes_background + back_fishes
draw_loading_screen(screen, 'Fishes', 100, 100)

# Game
draw_loading_screen(screen, 'Game scenes', 0, 100)
game_scene_turtle = GameScene(screen_w, screen_h, jelly, SPOT_TURTLE, back_fishes, front_fishes)
draw_loading_screen(screen, 'Game scenes', 25, 100)
game_scene_manta = GameScene(screen_w, screen_h, jelly, SPOT_MANTA, back_fishes, trapped_fishes)
draw_loading_screen(screen, 'Game scenes', 50, 100)
game_scene_whale = GameScene(screen_w, screen_h, jelly, SPOT_WHALE, back_fishes, front_fishes)
draw_loading_screen(screen, 'Game scenes', 75, 100)
game_scene_final = GameScene(screen_w, screen_h, jelly, SPOT_FINAL, back_fishes, trapped_fishes)
draw_loading_screen(screen, 'Game scenes', 100, 100)

# Audio – preload all game sounds into RAM (bubbles, NPC speech)
draw_loading_screen(screen, 'Audio', 0, 100)
GameScene.preload_audio()
draw_loading_screen(screen, 'Audio', 100, 100)

# Fade
fade = FadeTransition(screen_w, screen_h)

# Fade-in after the outro video ends
outro_fade = VideoFade(screen_w, screen_h, speed=300.0)
outro_fade._done = True  # inactive until the outro starts

# "Continue" controller hint (controller-x.png) – shown once turtle+manta+whale are done
# and only when a controller is connected
_continue_img = None
if os.path.isfile("imgs/controller-x.png"):
    _continue_img = pygame.image.load("imgs/controller-x.png").convert_alpha()
    _max_h = int(screen_h * 0.15)
    if _continue_img.get_height() > _max_h:
        _k = _max_h / _continue_img.get_height()
        _continue_img = pygame.transform.smoothscale(
            _continue_img, (max(1, int(_continue_img.get_width() * _k)), _max_h)
        )
_continue_alpha: float = 0.0   # blink (0-255)
_continue_dir:   int   = 1     # blink direction

# Intro video
intro_played = False        # True = video already played, skip it next time
intro_video: Video | None = None

# Fade overlay shared between pre_intro and post_intro
_fade_surf = pygame.Surface((screen_w, screen_h))
_fade_surf.fill((0, 0, 0))
intro_fade_alpha: float = 0.0   # current black-overlay alpha
INTRO_FADE_SPEED = 350.0        # alpha/s
intro_skip_allowed = False      # True once the fade-in into the video finishes
intro_rumble_triggered = False  # True once the rumble at second 23-25 has fired
intro_skip_hold = SkipHoldIndicator(screen_w, screen_h, hold_time=1.0)

# Titulky intro 
intro_subtitles = SubtitleOverlay(screen_w, screen_h)
intro_subtitles.load([
    SubtitleCue(start=1.0,  end=6.0, text="Pavel Jančík presents"),
    SubtitleCue(start=7.0,  end=12.0, text="Story based on true events"),
    SubtitleCue(start=23.0,  end=27.5, text="The Last Hope", y_position=0.65),
])

# Outro subtitles (final video)
_outro_quote = (
    '"Unless someone like you cares a whole awful lot,\n'
    'nothing is going to get better. It\'s not."\n\n'
    'Dr. Seuss, The Lorax'
)
_music = (
    'Moana 2 - My Wish For You (Innocent Warrior)\n\n'
    'Frozen Planet II - Crisis\n\n'
    'KPop Demon Hunters - Free [instrumental]\n\n'
)
_ost = (
    '01 - Eel\n\n'
    '02 - Shallows\n\n'
    '03 - Atolls\n\n'
    '04 - Echoes\n\n'
    '05 - Flow\n\n'
)
outro_subtitles_h1 = SubtitleOverlay(screen_w, screen_h)
outro_subtitles_h1.load([
    SubtitleCue(start=60.0, end=65.0, text="A Jelly’s Odyssey", font_size=70),
    SubtitleCue(start=65.0, end=70.0, text="Music", y_position=0.42),
    SubtitleCue(start=70.0, end=75.0, text="Soundtrack", y_position=0.38),
    SubtitleCue(start=75.0, end=80.0, text="Narrated by"),   
    SubtitleCue(start=80.0, end=85.0, text="Created by"),    
])
outro_subtitles_h2 = SubtitleOverlay(screen_w, screen_h)
h2_size = 20
outro_subtitles_h2.load([
    SubtitleCue(start=60.0, end=65.0, text="The Last Hope", font_size=h2_size, y_position=0.6),
    SubtitleCue(start=65.0, end=70.0, text=_music, font_size=h2_size,  y_position=0.55),
    SubtitleCue(start=70.0, end=75.0, text=_ost, font_size=h2_size,  y_position=0.55),
    SubtitleCue(start=75.0, end=80.0, text="David Attenborough", font_size=h2_size, y_position=0.55),
    SubtitleCue(start=80.0, end=85.0, text="Pavel Jančík, 2026", font_size=h2_size, y_position=0.55),
    SubtitleCue(start=85.0, end=110.0, text=_outro_quote, font_size=h2_size),
    
])

outro_subtitles_started = False   # True once reset() has been called for the outro
outro_skip_hold = SkipHoldIndicator(screen_w, screen_h, hold_time=1.0)
game_completed = False   # True once the final outro video has played (skipped or in full) -> map/esc re-enabled
# Joystick HUD
controller_hud = ControllerHUD(screen_w, screen_h, joystick)

def _controller_connected() -> bool:
    """True only while a controller is really connected (the Joystick object survives unplugging)."""
    try:
        return joystick is not None and pygame.joystick.get_count() > 0 and joystick.get_init()
    except Exception:
        return False

state = "home"
while True:
    dt = clock.tick(60) / 1000

    # ── Outro completion check ──────────────────────────────────────────────
    # Checked BEFORE this frame's events are pulled from the queue. If this
    # lived only in the render section (after the event loop), any input that
    # arrived in the same frame the outro finishes would still be dispatched
    # under the stale 'outro' state and get silently dropped (no handler
    # processes keyboard/joystick input for that state) — forcing a second,
    # separate press once the state had actually become 'home'. Resolving the
    # transition first means this frame's events are always routed correctly.
    if state == 'outro':
        _keys_now   = pygame.key.get_pressed()
        _enter_held = _keys_now[pygame.K_RETURN]
        _btn0_held  = joystick.get_button(0) if joystick else False
        _outro_skipped = outro_skip_hold.update(_enter_held or _btn0_held, dt)

        if _outro_skipped or game_scene_final.outro_video_done:
            if _outro_skipped:
                # Safely stop the outro video if game_scene supports it
                if hasattr(game_scene_final, 'stop_outro'):
                    game_scene_final.stop_outro()
                elif hasattr(game_scene_final, '_outro_video') and game_scene_final._outro_video:
                    try:
                        game_scene_final._outro_video.stop()
                    except Exception:
                        pass
                elif hasattr(game_scene_final, 'outro_video') and game_scene_final.outro_video:
                    try:
                        game_scene_final.outro_video.stop()
                    except Exception:
                        pass
            outro_skip_hold.reset()
            outro_subtitles_started = False
            game_completed = True   # final video has played -> re-enable map/esc controls
            state = 'home'
            outro_fade._alpha = 255.0
            outro_fade._dir = -1
            outro_fade._done = False
            outro_fade._fading_out = False
            outro_fade._elapsed = 0.0

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:

            # HOME - keyboard
            if state == 'home':
                result = home_screen.handle_event(event)
                if result:
                    if result["action"] == "play":
                        if not intro_played and os.path.exists("video/init.mp4"):
                            # start fading to black; the video starts once fully faded
                            intro_fade_alpha = 0.0
                            intro_rumble_triggered = False
                            state = 'pre_intro'
                        else:
                            state = 'game'
                    elif result["action"] == "exit":
                        pygame.quit()
                        sys.exit()

            # INTRO - keyboard (hold logic handled in the render section)

            # MAP - keyboard
            elif state == 'map':
                result = map_screen.handle_event(event)
                if result:
                    if result["action"] == "select":
                        state = 'game'
                        fade.start(result["spot"]["name"].lower())
                    elif result["action"] == "back":
                        state = 'game'

            # GAME - keyboard
            elif state == 'game':
                if event.key == pygame.K_m and (map_spot != SPOT_FINAL or game_completed):
                    state = 'map'
                if event.key == pygame.K_ESCAPE and (map_spot != SPOT_FINAL or game_completed):
                    state = 'home'
                if event.key == pygame.K_f:
                    # F -> go to final (only once turtle+manta+whale are complete)
                    all_done = (
                        game_scene_turtle.mission_complete
                        and game_scene_manta.mission_complete
                        and game_scene_whale.mission_complete
                    )
                    if all_done and map_spot != SPOT_FINAL:
                        state = 'game'
                        fade.start(SPOT_FINAL)
                # Forward key events to the HUD (mash=space, dpad=WASD, joy=space)
                controller_hud.handle_key(event)
                if event.key == pygame.K_SPACE:
                    # Space = start the challenge only if none is running
                    if controller_hud.joy_game is None:
                        if map_spot == SPOT_TURTLE:
                            game_scene_turtle.start_interact_challenge(controller_hud, joystick)
                        elif map_spot == SPOT_MANTA:
                            game_scene_manta.start_interact_challenge(controller_hud, joystick)
                        elif map_spot == SPOT_WHALE:
                            game_scene_whale.start_interact_challenge(controller_hud, joystick)
                        elif map_spot == SPOT_FINAL:
                            game_scene_final.start_interact_challenge(controller_hud, joystick)

        # --- Joystick buttons ---
        if event.type == pygame.JOYBUTTONDOWN and joystick:
            btn = event.button

            # HOME – Joystick
            if state == 'home':
                result = home_screen.handle_event(event)
                if result:
                    if result["action"] == "play":
                        if not intro_played and os.path.exists("video/init.mp4"):
                            intro_fade_alpha = 0.0
                            state = 'pre_intro'
                        else:
                            state = 'game'
                    elif result["action"] == "exit":
                        pygame.quit()
                        sys.exit()

            # INTRO – Joystick (hold logic handled in the render section)

            # GAME – Joystick
            elif state == 'game':
                controller_hud.handle_button_press(btn)
                if btn == 3 and (map_spot != SPOT_FINAL or game_completed):   # Y / Triangle → mapa
                    state = 'map'
                elif btn == 2:                # button 2 -> start the final mission
                    all_done = (
                        game_scene_turtle.mission_complete
                        and game_scene_manta.mission_complete
                        and game_scene_whale.mission_complete
                    )
                    if all_done and map_spot != SPOT_FINAL:
                        fade.start(SPOT_FINAL)
                elif btn == 8 and (map_spot != SPOT_FINAL or game_completed):  # Select / Share -> home
                    state = 'home'
                elif btn == 4:                # button 4 -> confirm challenge
                    controller_hud.handle_confirm()
                elif btn == 0:                # A / Cross -> start challenge
                    if map_spot == SPOT_TURTLE:
                        game_scene_turtle.start_interact_challenge(controller_hud, joystick)
                    elif map_spot == SPOT_MANTA:
                        game_scene_manta.start_interact_challenge(controller_hud, joystick)
                    elif map_spot == SPOT_WHALE:
                        game_scene_whale.start_interact_challenge(controller_hud, joystick)
                    elif map_spot == SPOT_FINAL:
                        game_scene_final.start_interact_challenge(controller_hud, joystick)

            # MAP – Joystick
            elif state == 'map':
                if btn == 3:                  # Y / Triangle -> back to game, spot unchanged
                    state = 'game'
                elif btn == 0:                # A / Cross -> pick spot and start the game
                    result = map_screen.handle_select()
                    if result:
                        fade.start(result["spot"]["name"].lower())
                    state = 'game'
                elif btn == 8:                # Select / Share -> home
                    state = 'home'

        # --- Joystick axis ---
        if event.type == pygame.JOYAXISMOTION and joystick:
            if event.axis == 0:
                if state == 'home':
                    home_screen.handle_axis(event.value)
                elif state == 'map':
                    map_screen.handle_axis(event.value)

        # --- D-pad hat ---
        if event.type == pygame.JOYHATMOTION and joystick:
            if state == 'game' and controller_hud.joy_game:
                if hasattr(controller_hud.joy_game, 'handle_hat'):
                    controller_hud.joy_game.handle_hat(event.value)

    # --- rendering ---

    # PRE_INTRO - fade home -> black, then start the video
    if state == 'pre_intro':
        bg_music.stop()
        home_screen.update(dt)
        home_screen.draw(screen)
        intro_fade_alpha = min(255.0, intro_fade_alpha + INTRO_FADE_SPEED * dt)
        _fade_surf.set_alpha(int(intro_fade_alpha))
        screen.blit(_fade_surf, (0, 0))
        if intro_fade_alpha >= 255:
            # screen is black — start the video
            intro_video = Video("video/init.mp4")
            intro_video.resize((screen_w, screen_h))
            intro_subtitles.reset()
            intro_fade_alpha = 255.0
            intro_skip_allowed = False
            intro_rumble_triggered = False
            intro_skip_hold.reset()
            state = 'intro'

    # INTRO - video playing, fade-in from black at the start
    elif state == 'intro':
        if intro_video and intro_video.active:
            intro_video.draw(screen, (0, 0), force_draw=True)
            intro_subtitles.update(dt)
            intro_subtitles.draw(screen)
            # fade-in: lighten the black overlay
            intro_fade_alpha = max(0.0, intro_fade_alpha - INTRO_FADE_SPEED * dt)
            if intro_fade_alpha > 0:
                _fade_surf.set_alpha(int(intro_fade_alpha))
                screen.blit(_fade_surf, (0, 0))
            else:
                intro_skip_allowed = True   # fade-in hotov, skip povolen



            # ── Hold-to-skip ──────────────────────────────────────────────
            if intro_skip_allowed:
                keys = pygame.key.get_pressed()
                _enter_held = keys[pygame.K_RETURN]
                _btn0_held  = joystick.get_button(0) if joystick else False
                _skip_held  = _enter_held or _btn0_held

                _skipped = intro_skip_hold.update(_skip_held, dt)
                intro_skip_hold.draw(screen)

                if _skipped:
                    intro_fade_alpha = 0.0
                    intro_skip_hold.reset()
                    if joystick:
                        try:
                            joystick.stop_rumble()
                        except Exception:
                            pass
                    state = 'post_intro'
        else:
            # video ended naturally -> go to post_intro
            if intro_video:
                intro_video.stop()
                intro_video = None
            intro_skip_hold.reset()
            intro_fade_alpha = 255.0
            state = 'post_intro'

    # POST_INTRO - fade from black to transparent, then go to the game
    elif state == 'post_intro':
        # stop the video if it's still running (skip)
        if intro_video:
            intro_video.stop()
            intro_video = None
        intro_played = True
        # screen is black -> hand control to FadeTransition (skip the fade-out)
        fade.start(map_spot)
        fade._alpha = 255.0
        fade._dir = -1
        fade._pending = None
        state = 'game'

    # HOME - Rendering
    elif state == 'home':
        bg_music.play()
        home_screen.update(dt)
        home_screen.draw(screen)
        if not outro_fade.done:
            outro_fade.update_and_draw(screen, dt)

    # OUTRO - final video (game scene isn't drawn)
    elif state == 'outro':
        bg_music.stop()
        if not outro_subtitles_started:
            outro_subtitles_h1.reset()
            outro_subtitles_started = True

        screen.fill((0, 0, 0))
        game_scene_final.draw_outro(screen)

        outro_subtitles_h1.update(dt)
        outro_subtitles_h1.draw(screen)
        outro_subtitles_h2.update(dt)
        outro_subtitles_h2.draw(screen)

        # Hold-to-skip progress indicator (the hold itself is tracked and
        # resolved at the top of the loop, before events are processed)
        outro_skip_hold.draw(screen)

    # MAP - Rendering
    elif state == 'map':
        bg_music.play()
        game_scene_turtle.dismiss_map_hint()   # map opened -> hide the map hint
        map_screen.update(dt)
        map_screen.draw(screen)

    # GAME - Rendering
    elif state == 'game':
        # Background music: plays everywhere except the final mission (which has its own audio on channel 5).
        # Once the final outro has already played (game_completed), the final mission's own music no
        # longer applies -> bg_music should just keep playing continuously, same as before the final scene.
        if not game_completed and map_spot == SPOT_FINAL and (game_scene_final.mission_active or game_scene_final.mission_complete):
            bg_music.stop()   # smooth fade-out; final music runs on channel 5
        else:
            bg_music.play()
        screen.blit(frames[current_frame], (0, 0))
        counter += 1
        if counter >= frame_delay:
            counter = 0
            current_frame = (current_frame + 1) % len(frames)

        keys = pygame.key.get_pressed()

        # Check whether a mission is currently running in another scene
        any_mission_active = (
            game_scene_turtle.mission_active
            or game_scene_manta.mission_active
            or game_scene_whale.mission_active
            or game_scene_final.mission_active
        )

        if map_spot == SPOT_TURTLE:
            game_scene_turtle.update(dt, keys, joystick, can_start_mission=not any_mission_active)
            game_scene_turtle.draw(screen)
        elif map_spot == SPOT_MANTA:
            game_scene_manta.update(dt, keys, joystick, can_start_mission=not any_mission_active)
            game_scene_manta.draw(screen)
        elif map_spot == SPOT_WHALE:
            game_scene_whale.update(dt, keys, joystick, can_start_mission=not any_mission_active)
            game_scene_whale.draw(screen)
        elif map_spot == SPOT_FINAL:
            game_scene_final.update(dt, keys, joystick, can_start_mission=True)
            game_scene_final.draw(screen)
            # Once the outro video is ready -> switch to the 'outro' state
            if game_scene_final.outro_playing:
                state = 'outro'

        if any_mission_active:
            # During a joy challenge: WASD from the keyboard moves the HUD stick (not Jelly)
            if controller_hud.joy_game is not None and not joystick:
                kb_x = float(keys[pygame.K_d] - keys[pygame.K_a])
                kb_y = float(keys[pygame.K_s] - keys[pygame.K_w])
                controller_hud.joy_axis_x = kb_x
                controller_hud.joy_axis_y = kb_y
            controller_hud.update(dt, joystick)
            # Only draw the HUD while a challenge is running
            if controller_hud.joy_game:
                controller_hud.draw(screen)
            # Close joy_game once completed (the callback has been called)
            if controller_hud.joy_game and controller_hud.joy_game._completed:
                controller_hud.stop_games()

        # --- "Press 3 / F to continue" prompt ---
        _all_three_done = (
            game_scene_turtle.mission_complete
            and game_scene_manta.mission_complete
            and game_scene_whale.mission_complete
        )
        if _all_three_done and map_spot != SPOT_FINAL:
            _continue_alpha += 300.0 * _continue_dir * dt
            if _continue_alpha >= 255.0:
                _continue_alpha = 255.0
                _continue_dir = -1
            elif _continue_alpha <= 60.0:
                _continue_alpha = 60.0
                _continue_dir = 1
            if _controller_connected() and _continue_img is not None:
                _img = _continue_img.copy()
                _img.set_alpha(int(_continue_alpha))
                screen.blit(_img, (screen_w // 2 - _img.get_width() // 2, screen_h // 3))


    # Fade overlay (jen ve stavu 'game')
    if state == 'game':
        new_spot = fade.update_and_draw(screen, clock.get_time())
        if new_spot:
            map_spot = new_spot
            if map_spot == SPOT_WHALE:
                frames = w_frames
            elif map_spot == SPOT_MANTA or map_spot == SPOT_FINAL:
                frames = m_frames
            elif map_spot == SPOT_TURTLE:
                frames = t_frames

    bg_music.update(dt)
    pygame.display.update()