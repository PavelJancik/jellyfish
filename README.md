# A Jelly’s Odyssey - The Last Hope

<p align="center">
   <img src="/imgs/screenshot.png" alt="GameScreenshot"/>
</p>

A 2D underwater-adventure game built with **Pygame**. You play as Jelly, a
jellyfish swimming through scrolling ocean scenes, completing short missions
to help sea creatures and clean up the ocean — with full keyboard and
PS-like controller support.

## Project Structure

| File | Description |
|---|---|
| `main.py` | Entry point; game state machine (home, map, game, intro/outro, etc.) |
| `engine.py` | Loading screen, fade transitions, background music, skip-hold indicator, spell effect |
| `jelly_character.py` | Player character: sprite-sheet animation, movement, collision |
| `npc_character.py` | Idle NPC characters that give out missions |
| `ambient_fish.py` | Decorative and freeable fish (static and sprite-sheet animated) |
| `interactive_object.py` | Trash, coral, and trap objects the player interacts with |
| `game_scene.py` | Core scrolling scene logic, missions, HUD, final-scene sequence |
| `controller_hud.py` | On-screen joystick/mash/D-pad mini-game challenges and rumble feedback |
| `home_screen.py` | Animated main menu and controls overlay |
| `map_screen.py` | Spot-selection map screen |
| `subtitle_overlay.py` | Fading subtitle rendering for intro/outro videos |

## Assets

The game expects `imgs/`, `audio/`, `fonts/`, and `video/` folders with the
corresponding sprites, sounds, fonts, and cutscenes (not included in this
listing). See the individual modules' docstrings for the expected file
layout (e.g. `imgs/water_<animal>_front.png`, `imgs/fishes/`,
`imgs/corals/`, `audio/background_music/`).

## License

See `LICENCE.md` for license terms.