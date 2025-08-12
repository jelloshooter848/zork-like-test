# generative_zork_like.py
"""
Claude-only text adventure with:
- Gold + shop + buy (start with 15 gold; buy 'rusty_sword')
- Turn-based cave combat (Cave Beast ambush on first cave entry)
- Quest completion + 'THE END' when you take the gem

API key loading order:
  1) ANTHROPIC_API_KEY env var
  2) ./secrets/anthropic.key
  3) ~/.anthropic/anthropic.key

Run:
  # recommended: use a virtual environment
  python3 -m venv venv
  source venv/bin/activate
  pip install anthropic
  mkdir -p secrets
  echo "YOUR-ANTHROPIC-KEY" > secrets/anthropic.key

  python generative_zork_like.py
"""

import os
import json
import random
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import font, ttk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)  # Auto-reset colors after each print
    COLORS_AVAILABLE = True
except ImportError:
    # Fallback if colorama not installed
    class MockColors:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = BRIGHT = RESET_ALL = ""
    Fore = Back = Style = MockColors()
    COLORS_AVAILABLE = False

# Try to import audio libraries
AUDIO_AVAILABLE = False
try:
    import pygame
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    AUDIO_AVAILABLE = True
    AUDIO_BACKEND = "pygame"
except ImportError:
    try:
        import playsound
        AUDIO_AVAILABLE = True
        AUDIO_BACKEND = "playsound"
    except ImportError:
        try:
            import winsound  # Windows only
            AUDIO_AVAILABLE = True
            AUDIO_BACKEND = "winsound"
        except ImportError:
            AUDIO_AVAILABLE = False
            AUDIO_BACKEND = None

# ---------- API key loading ----------
def load_anthropic_key() -> str:
    """
    Returns the Anthropic API key as a string, or '' if not found.
    Priority:
      1) ANTHROPIC_API_KEY environment variable
      2) ./secrets/anthropic.key (next to this script)
      3) ~/.anthropic/anthropic.key
    """
    # 1) env var
    k = os.getenv("ANTHROPIC_API_KEY")
    if k:
        return k.strip()

    # 2) ./secrets/anthropic.key (preferred local path)
    try:
        p = Path(__file__).parent / "secrets" / "anthropic.key"
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    # 3) ~/.anthropic/anthropic.key (home fallback)
    try:
        p = Path.home() / ".anthropic" / "anthropic.key"
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    return ""

# ---------- Music System ----------
class MusicManager:
    def __init__(self):
        self.enabled = AUDIO_AVAILABLE
        self.volume = 0.3
        self.current_track = None
        self.current_category = None
        self.music_thread = None
        self.stop_music = False
        
        # Music tracks mapping - one track per category for consistency
        self.tracks = {
            "village": "07 - Town.ogg",
            "forest": "08 - Overworld.ogg", 
            "cave": "15 - Dungeon.ogg",
            "ruins": "12 - Timeworn Pagoda.ogg",
            "combat": "13 - Danger.ogg",
            "boss": "14 - Barbarian King.ogg",
            "victory": "17 - Victory.ogg",
            "defeat": "20 - Game Over.ogg",
            "indoor": "23 - Inn.ogg"
        }
        
        # Location to music category mapping
        self.location_music = {
            "village_square": "village",
            "blacksmith_shop": "indoor", 
            "healer_tent": "indoor",
            "elder_hut": "indoor",
            "forest_path": "forest",
            "iron_mine": "cave",
            "hidden_cave": "cave",
            "deep_ruins": "ruins",
            "sealed_tower": "ruins"
        }
    
    def set_volume(self, volume: float):
        """Set music volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if AUDIO_BACKEND == "pygame" and pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.volume)
    
    def play_track(self, category: str, loop: bool = True):
        """Play a music track from the given category"""
        if not self.enabled or category not in self.tracks:
            return
            
        # Don't restart if same category is playing
        if self.current_category == category and self.music_thread and self.music_thread.is_alive():
            return
            
        self.stop_current_track()
        self.current_category = category
        
        # Get the specific track for this category
        track = self.tracks[category]
        
        # Create music directory path
        music_dir = Path("music")
        track_path = music_dir / track
        
        # Only play if file exists
        if track_path.exists():
            if AUDIO_BACKEND == "pygame":
                self._play_pygame(track_path, loop)
            else:
                self._play_fallback(track_path, loop)
        else:
            # File doesn't exist, but update status to show what would be playing
            self.current_track = f"{track} (missing)"
            self.current_category = category
    
    def _play_pygame(self, track_path, loop):
        """Play using pygame mixer"""
        try:
            # Check if pygame mixer is initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            
            # Stop any current music cleanly
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
            # Load and play new track
            pygame.mixer.music.load(str(track_path))
            pygame.mixer.music.set_volume(self.volume)
            # Use -1 for infinite loop, 0 for play once
            pygame.mixer.music.play(loops=-1 if loop else 0)
            self.current_track = track_path.name
            
        except pygame.error as e:
            # Pygame-specific error - try to reinitialize
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                pygame.mixer.music.load(str(track_path))
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play(loops=-1 if loop else 0)
                self.current_track = track_path.name
            except Exception:
                self.current_track = f"{track_path.name} (error)"
        except Exception as e:
            # Other errors
            self.current_track = f"{track_path.name} (error)"
    
    def _play_fallback(self, track_path, loop):
        """Fallback audio playback"""
        def play_music():
            try:
                if AUDIO_BACKEND == "playsound":
                    # playsound doesn't support looping
                    while not self.stop_music:
                        playsound.playsound(str(track_path), block=True)
                        if not loop:
                            break
                elif AUDIO_BACKEND == "winsound":
                    flags = winsound.SND_FILENAME
                    if loop:
                        flags |= winsound.SND_LOOP | winsound.SND_ASYNC
                    winsound.PlaySound(str(track_path), flags)
                    
                self.current_track = track_path.name
            except Exception as e:
                # Mark track as error for status reporting
                self.current_track = f"{track_path.name} (error)"
        
        if AUDIO_BACKEND in ["playsound", "winsound"]:
            self.stop_music = False
            self.music_thread = threading.Thread(target=play_music, daemon=True)
            self.music_thread.start()
        else:
            # No audio backend available
            self.current_track = f"{track_path.name} (no backend)"
    
    def stop_current_track(self):
        """Stop currently playing music"""
        self.stop_music = True
        
        if AUDIO_BACKEND == "pygame" and pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        elif AUDIO_BACKEND == "winsound":
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except:
                pass
        
        if self.music_thread and self.music_thread.is_alive():
            self.music_thread.join(timeout=0.5)
    
    def play_location_music(self, location_key: str):
        """Play appropriate music for a location"""
        category = self.location_music.get(location_key, "village")
        self.play_track(category)
    
    def play_combat_music(self, is_boss: bool = False):
        """Play combat music"""
        category = "boss" if is_boss else "combat"
        self.play_track(category)
    
    def play_victory_music(self):
        """Play victory music"""
        self.play_track("victory", loop=False)
    
    def play_defeat_music(self):
        """Play defeat music"""
        self.play_track("defeat", loop=False)
    
    def toggle_music(self):
        """Toggle music on/off"""
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop_current_track()
        return self.enabled
    
    def restart_music(self, world=None):
        """Restart the music system - useful after crashes"""
        try:
            # Stop any current music
            self.stop_current_track()
            
            # Re-initialize pygame mixer if needed
            if AUDIO_BACKEND == "pygame":
                try:
                    if pygame.mixer.get_init():
                        pygame.mixer.quit()
                    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                except Exception as e:
                    return f"❌ Failed to restart pygame mixer: {e}"
            
            # Clear current state
            self.current_track = None
            self.current_category = None
            self.stop_music = False
            
            # Try to get world context - first from parameter, then from globals
            current_world = world
            if not current_world:
                try:
                    # Try to access global w variable
                    import sys
                    current_frame = sys._getframe(1)
                    current_world = current_frame.f_globals.get('w')
                except:
                    current_world = None
            
            # Resume appropriate music based on current context if world is available
            if current_world:
                try:
                    if hasattr(current_world, 'flags') and current_world.flags.get("in_combat"):
                        # Check if it's a boss fight
                        is_boss = (hasattr(current_world, 'active_monster') and current_world.active_monster and 
                                  getattr(current_world.active_monster, 'hp', 0) >= 50)
                        self.play_combat_music(is_boss=is_boss)
                    elif hasattr(current_world, 'player') and current_world.player.location:
                        self.play_location_music(current_world.player.location)
                except Exception:
                    # If resuming music fails, that's okay - we still restarted the system
                    pass
            
            return "🎵 Music system restarted successfully"
            
        except Exception as e:
            return f"❌ Failed to restart music system: {e}"
    
    def is_music_playing(self):
        """Check if music is actually playing (not just enabled)"""
        if not self.enabled or not AUDIO_AVAILABLE:
            return False
            
        if AUDIO_BACKEND == "pygame":
            try:
                return pygame.mixer.music.get_busy()
            except:
                return False
        elif AUDIO_BACKEND in ["playsound", "winsound"]:
            return self.music_thread and self.music_thread.is_alive()
        
        return False
    
    def get_status(self):
        """Get current music status"""
        if not AUDIO_AVAILABLE:
            return "🔇 No audio libraries available"
        elif not self.enabled:
            return "🔇 Music disabled"
        elif self.current_track:
            playing_status = "🎵" if self.is_music_playing() else "⏸️"
            if "(missing)" in self.current_track:
                return f"🎵 Would play: {self.current_track.replace(' (missing)', '')} ({self.current_category}) - File not found"
            elif "(error)" in self.current_track:
                return f"❌ Error with: {self.current_track.replace(' (error)', '')} ({self.current_category}) - Try 'music restart'"
            else:
                return f"{playing_status} {self.current_track} ({self.current_category})"
        else:
            return "🎵 Music enabled, no track playing"

# Global music manager instance
music_manager = MusicManager()

# ---------- Game Dashboard Class ----------
class GameDashboard:
    """Tabbed window for displaying game information (map, inventory, quests, etc.)"""
    
    def __init__(self):
        self.root = None
        self.window = None
        self.notebook = None
        self.tabs = {}
        self.last_selected_tab = 0
        self.window_width = 900
        self.window_height = 700
        
    def calculate_window_position(self):
        """Calculate optimal window position for side-by-side layout"""
        try:
            # Create temporary root to get screen dimensions
            if not self.root:
                temp_root = tk.Tk()
                temp_root.withdraw()
                screen_width = temp_root.winfo_screenwidth()
                screen_height = temp_root.winfo_screenheight()
                temp_root.destroy()
            else:
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
            
            # Position dashboard on the right side, accounting for game window on left
            game_window_width = 800  # Expected game window width
            margin = 10
            
            # Calculate dashboard position (right side of screen)
            available_width = screen_width - game_window_width - (3 * margin)
            self.window_width = min(650, max(400, available_width))
            
            dashboard_x = screen_width - self.window_width - margin
            dashboard_y = 50  # Top margin
            
            # Calculate height to match game window if possible
            available_height = screen_height - dashboard_y - 100
            if available_height < self.window_height:
                self.window_height = max(500, available_height)
            
            # If screen is very wide, we can afford more width
            if screen_width >= 1800:
                self.window_width = min(1000, screen_width - dashboard_x - 20)
            
            # Ensure position is not negative
            dashboard_x = max(50, dashboard_x)
            dashboard_y = max(50, dashboard_y)
            
            return dashboard_x, dashboard_y
            
        except Exception as e:
            print(f"[info] Could not calculate optimal position: {e}")
            # Fallback to reasonable default position
            return 950, 50
    
    def create_window(self):
        """Create the tabbed dashboard window if it doesn't exist"""
        if not TKINTER_AVAILABLE:
            return False
        
        # Create root window if it doesn't exist
        if self.root is None:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the root window
            
        if self.window is not None:
            # Window already exists, just bring it to front
            try:
                self.window.lift()
                self.window.focus_force()
                return True
            except tk.TclError:
                # Window was destroyed, create new one
                self.window = None
                
        self.window = tk.Toplevel(self.root)
        self.window.title("🎮 Game Dashboard - Zork Adventure")
        
        # Calculate optimal position for side-by-side layout
        pos_x, pos_y = self.calculate_window_position()
        geometry_string = f"{self.window_width}x{self.window_height}+{pos_x}+{pos_y}"
        self.window.geometry(geometry_string)
        
        self.window.configure(bg='black')
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        self.create_tabs()
        
        # Restore last selected tab
        if self.last_selected_tab < len(self.tabs):
            self.notebook.select(self.last_selected_tab)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        return True
    
    def create_tabs(self):
        """Create all the tabs for the dashboard"""
        tab_configs = [
            ("🗺️ Map", "map"),
            ("📦 Inventory", "inventory"), 
            ("📋 Quests", "quests"),
            ("🏆 Achievements", "achievements"),
            ("👥 Relations", "relationships")
        ]
        
        for tab_title, tab_key in tab_configs:
            # Create frame for tab
            frame = tk.Frame(self.notebook, bg='black')
            
            # Create text widget with scrollbars
            text_widget = tk.Text(
                frame,
                bg='black',
                fg='white',
                font=('Courier New', 10),
                wrap=tk.NONE,
                state=tk.DISABLED,
                padx=10,
                pady=10
            )
            
            # Add scrollbars
            v_scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
            h_scrollbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text_widget.xview)
            text_widget.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Pack scrollbars and text widget
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Store tab info
            self.tabs[tab_key] = {
                'frame': frame,
                'text_widget': text_widget,
                'title': tab_title
            }
            
            # Add tab to notebook
            self.notebook.add(frame, text=tab_title)
    
    def on_tab_changed(self, event):
        """Handle tab change events"""
        self.last_selected_tab = self.notebook.index(self.notebook.select())
    
    def update_tab_content(self, tab_key: str, content: str):
        """Update content of a specific tab"""
        if tab_key not in self.tabs:
            return False
            
        text_widget = self.tabs[tab_key]['text_widget']
        
        # Enable editing, clear content, insert new content
        text_widget.configure(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        
        # Strip ANSI codes and insert content
        clean_content = self._strip_ansi_codes(content)
        text_widget.insert(1.0, clean_content)
        
        # Disable editing and scroll to top
        text_widget.configure(state=tk.DISABLED)
        text_widget.see(1.0)
        
        return True
    
    def show_dashboard(self, w: "World"):
        """Show dashboard and update all tab content"""
        if not self.create_window():
            return False
        
        # Force window update to ensure tabs are fully created
        if self.window:
            self.window.update()
        
        # Schedule initial tab population after a brief delay
        def delayed_update():
            self.update_all_tabs(w)
        
        if self.window:
            self.window.after(100, delayed_update)  # 100ms delay
        
        return True
    
    def update_all_tabs(self, w: "World"):
        """Update content for all tabs"""
        if not self.is_visible():
            return
        
        # Ensure tabs are created
        if not self.tabs:
            return
            
        # Update each tab with current game data
        try:
            self.update_tab_content("map", get_world_map(w, no_colors=True))
            self.update_tab_content("inventory", show_enhanced_inventory(w))
            self.update_tab_content("quests", quests(w))
            self.update_tab_content("achievements", show_achievements_list(w))
            self.update_tab_content("relationships", show_relationships(w))
        except Exception as e:
            print(f"[debug] Tab update error: {e}")
    
    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes from text"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def hide_window(self):
        """Hide the dashboard window"""
        if self.window:
            self.window.withdraw()
    
    def is_visible(self) -> bool:
        """Check if window is currently visible"""
        if not self.window:
            return False
        try:
            return self.window.winfo_viewable()
        except tk.TclError:
            return False

# Create global dashboard instance
game_dashboard = GameDashboard()

# Create global game window instance
game_window = None

# Helper functions for dual interface support
def game_print(text: str = ""):
    """Print text to game window or terminal"""
    global game_window
    if game_window and game_window.window:
        game_window.print_to_game(text)
    else:
        print(text)

def game_input(prompt: str = "> ") -> str:
    """Get input from game window or terminal"""
    global game_window
    if game_window and game_window.window:
        return game_window.get_input(prompt)
    else:
        return input(prompt)

# ---------- Game Window Class ----------
class GameWindow:
    """Main game window for text-based interface"""
    
    def __init__(self):
        self.root = None
        self.window = None
        self.text_area = None
        self.input_var = None
        self.input_field = None
        self.actions_frame = None
        self.actions_label = None
        # Dashboard components integrated into game window
        self.notebook = None
        self.tabs = {}
        self.last_selected_tab = 0
        self.command_history = []
        self.history_index = -1
        self.waiting_for_input = False
        self.input_result = None
        # Wider window for unified layout
        self.window_width = 1200
        self.window_height = 700
        
    def calculate_game_window_position(self):
        """Calculate position for unified game window (centered)"""
        try:
            if not self.root:
                temp_root = tk.Tk()
                temp_root.withdraw()
                screen_width = temp_root.winfo_screenwidth()
                screen_height = temp_root.winfo_screenheight()
                temp_root.destroy()
            else:
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
            
            # Calculate optimal width for unified layout (about 80% of screen)
            self.window_width = min(1200, int(screen_width * 0.8))
            
            # Calculate height
            available_height = screen_height - 100
            self.window_height = min(700, available_height)
            
            # Center the window
            game_x = (screen_width - self.window_width) // 2
            game_y = (screen_height - self.window_height) // 2
            
            return game_x, game_y
            
        except Exception as e:
            print(f"[info] Could not calculate game window position: {e}")
            return 50, 50
    
    def create_window(self):
        """Create the unified game window with integrated dashboard"""
        if not TKINTER_AVAILABLE:
            return False
            
        # Create root window if it doesn't exist
        if self.root is None:
            self.root = tk.Tk()
            self.root.title("🎮 Zork Adventure - Unified Interface")
            
            # Calculate position
            pos_x, pos_y = self.calculate_game_window_position()
            geometry_string = f"{self.window_width}x{self.window_height}+{pos_x}+{pos_y}"
            self.root.geometry(geometry_string)
            
            self.root.configure(bg='black')
            self.window = self.root
        else:
            return True
        
        # Create main horizontal split container
        main_container = tk.Frame(self.window, bg='black')
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create left panel for game content (60% width)
        left_panel = tk.Frame(main_container, bg='black')
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 2))
        
        # Create right panel for dashboard (40% width)  
        right_panel = tk.Frame(main_container, bg='black', width=int(self.window_width * 0.4))
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(2, 5))
        right_panel.pack_propagate(False)  # Maintain fixed width
        
        # === LEFT PANEL: Game Content ===
        # Create text area frame with scrollbar
        text_frame = tk.Frame(left_panel, bg='black')
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Create text area for game output
        self.text_area = tk.Text(
            text_frame,
            bg='black',
            fg='green',
            font=('Courier New', 11),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=0
        )
        
        # Create scrollbar for text area
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=scrollbar.set)
        
        # Pack text area and scrollbar
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create input frame
        input_frame = tk.Frame(left_panel, bg='black')
        input_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Create prompt label
        prompt_label = tk.Label(
            input_frame, 
            text="> ", 
            bg='black', 
            fg='green',
            font=('Courier New', 11)
        )
        prompt_label.pack(side=tk.LEFT)
        
        # Create input field
        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(
            input_frame,
            textvariable=self.input_var,
            bg='black',
            fg='green',
            font=('Courier New', 11),
            insertbackground='green',
            relief=tk.FLAT,
            borderwidth=0
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Bind events
        self.input_field.bind('<Return>', self.on_enter)
        self.input_field.bind('<Up>', self.on_up_arrow)
        self.input_field.bind('<Down>', self.on_down_arrow)
        
        # Create actions panel
        self.actions_frame = tk.Frame(left_panel, bg='black')
        self.actions_frame.pack(fill=tk.X)
        
        # Create actions display
        self.actions_label = tk.Label(
            self.actions_frame,
            text="",
            bg='black',
            fg='green',
            font=('Courier New', 10),
            justify=tk.LEFT,
            anchor='nw',
            wraplength=0,
            width=0,
            pady=5
        )
        self.actions_label.pack(fill=tk.X)
        
        # === RIGHT PANEL: Dashboard ===
        self.create_integrated_dashboard(right_panel)
        
        # Focus on input field
        self.input_field.focus()
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        return True
    
    def create_integrated_dashboard(self, parent):
        """Create the integrated dashboard in the right panel"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        tab_configs = [
            ("🗺️ Map", "map"),
            ("📦 Inventory", "inventory"), 
            ("📋 Quests", "quests"),
            ("🏆 Achievements", "achievements"),
            ("👥 Relations", "relationships")
        ]
        
        for tab_title, tab_key in tab_configs:
            # Create frame for tab
            frame = tk.Frame(self.notebook, bg='black')
            
            # Create text widget with scrollbars
            text_widget = tk.Text(
                frame,
                bg='black',
                fg='white',
                font=('Courier New', 9),  # Slightly smaller for dashboard
                wrap=tk.NONE,
                state=tk.DISABLED,
                padx=5,
                pady=5
            )
            
            # Add scrollbars
            v_scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
            h_scrollbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text_widget.xview)
            text_widget.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Pack scrollbars and text widget
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Store tab info
            self.tabs[tab_key] = {
                'frame': frame,
                'text_widget': text_widget,
                'title': tab_title
            }
            
            # Add tab to notebook
            self.notebook.add(frame, text=tab_title)
        
        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Restore last selected tab
        if self.last_selected_tab < len(self.tabs):
            self.notebook.select(self.last_selected_tab)
    
    def on_tab_changed(self, event):
        """Handle tab change events"""
        self.last_selected_tab = self.notebook.index(self.notebook.select())
    
    def update_dashboard_tab(self, tab_key: str, content: str):
        """Update content of a specific dashboard tab"""
        if tab_key not in self.tabs:
            return False
            
        text_widget = self.tabs[tab_key]['text_widget']
        
        # Enable editing, clear content, insert new content
        text_widget.configure(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        
        # Strip ANSI codes and insert content
        clean_content = self._strip_ansi_codes(content)
        text_widget.insert(1.0, clean_content)
        
        # Disable editing and scroll to top
        text_widget.configure(state=tk.DISABLED)
        text_widget.see(1.0)
        
        return True
    
    def update_all_dashboard_tabs(self, w: "World"):
        """Update content for all dashboard tabs"""
        if not self.tabs:
            return
            
        # Update each tab with current game data
        try:
            self.update_dashboard_tab("map", get_world_map(w, no_colors=True))
            self.update_dashboard_tab("inventory", show_enhanced_inventory(w))
            self.update_dashboard_tab("quests", quests(w))
            self.update_dashboard_tab("achievements", show_achievements_list(w))
            self.update_dashboard_tab("relationships", show_relationships(w))
        except Exception as e:
            print(f"[debug] Dashboard tab update error: {e}")
    
    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes from text"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def print_to_game(self, text: str):
        """Print text to the game window"""
        if not self.text_area:
            return
            
        self.text_area.configure(state=tk.NORMAL)
        self.text_area.insert(tk.END, text + '\n')
        self.text_area.configure(state=tk.DISABLED)
        self.text_area.see(tk.END)  # Auto-scroll to bottom
        
        # Process pending events to update display
        if self.root:
            self.root.update_idletasks()
    
    def get_input(self, prompt: str = "> ") -> str:
        """Get input from the user"""
        if not self.window:
            return input(prompt)  # Fallback to terminal input
        
        # Show prompt if needed
        if prompt and prompt != "> ":
            self.print_to_game(prompt.rstrip())
        
        # Wait for user input
        self.waiting_for_input = True
        self.input_result = None
        
        # Focus input field
        self.input_field.focus()
        
        # Wait for input
        while self.waiting_for_input and self.window:
            try:
                self.root.update()
            except tk.TclError:
                # Window was closed
                return "quit"
        
        return self.input_result or "quit"
    
    def on_enter(self, event):
        """Handle Enter key press"""
        command = self.input_var.get().strip()
        
        if command:
            # Add to history
            self.command_history.append(command)
            self.history_index = len(self.command_history)
            
            # Display command in text area
            self.print_to_game(f"> {command}")
            
            # Clear input field
            self.input_var.set("")
            
            # Set result and stop waiting
            self.input_result = command
            self.waiting_for_input = False
    
    def on_up_arrow(self, event):
        """Handle up arrow for command history"""
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.input_var.set(self.command_history[self.history_index])
    
    def on_down_arrow(self, event):
        """Handle down arrow for command history"""
        if self.command_history:
            if self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.input_var.set(self.command_history[self.history_index])
            else:
                self.history_index = len(self.command_history)
                self.input_var.set("")
    
    def on_close(self):
        """Handle window close event"""
        self.waiting_for_input = False
        self.input_result = "quit"
        if self.root:
            self.root.quit()
    
    def generate_compact_actions(self, w: "World") -> str:
        """Generate descriptive action options for the actions panel in two-column layout"""
        options = []
        loc = w.locations[w.player.location]
        
        # Combat has priority - use single line for combat
        if w.flags.get("in_combat"):
            combat_options = ["1.Attack Monster", "2.Defend Yourself", "3.Flee Combat"]
            return "  ".join(combat_options) + "    [? for help]"
        
        # Always available options
        options.extend(["1.Look Around", "2.Check Inventory", "3.View Quests"])
        
        # Movement options - show more exits with full names
        if loc.exits:
            for i, exit in enumerate(loc.exits[:3], 4):  # Show up to 3 exits
                exit_name = exit.replace("_", " ").title()
                options.append(f"{i}.Go to {exit_name}")
        
        # NPCs with full names
        if loc.npcs:
            start_num = len(options) + 1
            for i, npc_key in enumerate(loc.npcs[:2], start_num):  # Show up to 2 NPCs
                npc_name = w.npcs[npc_key].name
                options.append(f"{i}.Talk to {npc_name}")
        
        # Items with full names
        if loc.items:
            start_num = len(options) + 1
            for i, item in enumerate(loc.items[:2], start_num):  # Show up to 2 items
                item_name = item.replace("_", " ").title()
                options.append(f"{i}.Take {item_name}")
        
        # Location-specific actions
        start_num = len(options) + 1
        if loc.key == "blacksmith_shop":
            options.append(f"{start_num}.Browse Shop")
            start_num += 1
        elif loc.key == "healer_tent":
            options.append(f"{start_num}.Browse Healer Shop")
            start_num += 1
        
        # Healing option if available
        if w.player.hp < w.player.max_hp and "healer" in loc.npcs:
            options.append(f"{start_num}.Get Healing")
            start_num += 1
        
        # Utility options
        if w.player.explored_areas:
            options.append(f"{start_num}.View Map")
            start_num += 1
        
        options.append(f"{start_num}.Save Game")
        
        # Format in two columns for better readability
        return self.format_two_columns(options)
    
    def format_two_columns(self, options: list) -> str:
        """Format options in a clean two-column layout"""
        if len(options) <= 3:
            # For few options, use single line
            return "  ".join(options) + "    [? for help]"
        
        # Calculate column width (30 characters should work well)
        col_width = 30
        lines = []
        
        # Split options into two columns
        mid_point = (len(options) + 1) // 2
        left_column = options[:mid_point]
        right_column = options[mid_point:] + ["[? for help]"]
        
        # Create formatted lines
        for i in range(max(len(left_column), len(right_column))):
            left = left_column[i] if i < len(left_column) else ""
            right = right_column[i] if i < len(right_column) else ""
            
            # Pad left column to consistent width
            left_padded = left.ljust(col_width)
            line = f"{left_padded}{right}"
            lines.append(line.rstrip())  # Remove trailing spaces
        
        return "\n".join(lines)
    
    def update_actions_panel(self, w: "World"):
        """Update the actions panel with current context"""
        if not self.actions_label:
            return
            
        actions_text = self.generate_compact_actions(w)
        self.actions_label.configure(text=actions_text)

# Create global game window instance
game_window = GameWindow()

# ---------- Color utilities ----------
def colorize_npc(text: str) -> str:
    """Color NPC names and dialogue"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.CYAN}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def colorize_item(text: str) -> str:
    """Color item names"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.YELLOW}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def colorize_combat(text: str) -> str:
    """Color combat text"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.RED}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def colorize_quest(text: str) -> str:
    """Color quest-related text"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.GREEN}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def colorize_location(text: str) -> str:
    """Color location names"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.BLUE}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def colorize_command(text: str) -> str:
    """Color command options"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.MAGENTA}{text}{Style.RESET_ALL}"

def colorize_success(text: str) -> str:
    """Color success messages"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}"

def colorize_warning(text: str) -> str:
    """Color warning messages"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"

def colorize_error(text: str) -> str:
    """Color error messages"""
    global game_window
    if game_window and game_window.window:
        return text  # No colors for tkinter
    return f"{Fore.RED}{text}{Style.RESET_ALL}"

# ---------- ASCII Art ----------
def get_location_art(location_key: str) -> str:
    """Get ASCII art for a location"""
    art = {
        "village_square": """
    ╭─────────────────────────────────────╮
    │          VILLAGE SQUARE             │
    │                                     │
    │       🏠     ⚒️        🌳          |   
    │      ELDR   BlkSmth   FOREST        │
    │       Hut    Shop      Path         │
    │                                     │
    │           🗼        🏠             │
    │          Sealed    Healer           |
    |          Tower      Tent            │
    ╰─────────────────────────────────────╯""",
        
        "blacksmith_shop": """
    ╭─────────────────────────────────────╮
    │           BLACKSMITH SHOP           │
    │                                     │
    │           ⚒️🗡️⚔️        X          │
    │         Buy Weapons     Exit        │
    │                                     │
    │           💰 SHOP OPEN 💰          │
    ╰─────────────────────────────────────╯""",
        
        "forest_path": """
    ╭─────────────────────────────────────╮
    │            FOREST PATH              │
    │                                     │
    │       🌲🌲🌲    🕳️      ⛏️        │
    │       Village    Hidden    Iron     │
    │        Square     Cave     Mine     │
    │                                     │
    │                                     │
    ╰─────────────────────────────────────╯""",
        
        "iron_mine": """
    ╭─────────────────────────────────────╮
    │             IRON MINE               │
    │                                     │
    │               ⛏️💎                 │
    │                Iron                 │
    │                 Ore                 │
    │                                     │
    │                                     │
    ╰─────────────────────────────────────╯""",
        
        "healer_tent": """
    ╭─────────────────────────────────────╮
    │         HEALER'S TENT              │
    │                                     │
    │    🕯️✨    🧪🌿    ❤️            │
    │  Candles  Herbs   Healing           │
    │   Light  Potions   Magic            │
    │                                     │
    │        💚 CARE 💚                 │
    ╰─────────────────────────────────────╯""",
        
        "elder_hut": """
    ╭─────────────────────────────────────╮
    │          ELDER'S HUT               │
    │                                     │
    │    📚🔮    🛏️😷    ⭐            │
    │   Books   Cursed   Ancient          │
    │   Magic    Elder   Wisdom           │
    │                                     │
    │       🌟 CURSED 🌟                │
    ╰─────────────────────────────────────╯""",
        
        "hidden_cave": """
    ╭─────────────────────────────────────╮
    │          HIDDEN CAVE               │
    │                                     │
    │    🕳️👹    💎✨    🚪            │
    │   Dark   Gem     Deep               │
    │  Depths  Shine   Passage            │
    │                                     │
    │      ⚠️ DANGER ⚠️                 │
    ╰─────────────────────────────────────╯""",
        
        "deep_ruins": """
    ╭─────────────────────────────────────╮
    │          DEEP RUINS                │
    │                                     │
    │    🏛️👻    📜⚡    🗿            │
    │  Ancient Guardian  Scroll           │
    │   Ruins   Awake   Magic             │
    │                                     │
    │     ⚡ ANCIENT POWER ⚡            │
    ╰─────────────────────────────────────╯""",
        
        "sealed_tower": """
    ╭─────────────────────────────────────╮
    │         SEALED TOWER               │
    │                                     │
    │    🗼🔒    🗝️✨    💰            │
    │   Tower   Key    Treasure           │
    │  Sealed  Magic   Awaits             │
    │                                     │
    │      🏆 FINAL GOAL 🏆             │
    ╰─────────────────────────────────────╯"""
    }
    
    return art.get(location_key, "")

# ---------- Item and Creature Art ----------  
def get_creature_art(creature_name: str) -> str:
    """Get ASCII art for creatures"""
    art = {
        "Cave Beast": """
    ╭──────────────────────────╮
    │       ⚠️ DANGER! ⚠️       │
    │                          │
    │     🐺      👹      🦇    │
    │   Prowling  Cave   Flying │
    │    Beast   Demon   Terror │  
    │                          │
    │      💀 COMBAT 💀       │
    ╰──────────────────────────╯""",
        
        "Ancient Guardian": """
    ╭──────────────────────────╮
    │    ⚡ ANCIENT POWER ⚡    │
    │                          │
    │     🗿      👻      ⚔️    │
    │   Stone   Spirit  Weapons │
    │  Guardian  Guide   Ready  │
    │                          │
    │     🏛️ GUARDIAN 🏛️      │
    ╰──────────────────────────╯"""
    }
    return art.get(creature_name, "")

def get_item_art(item_name: str) -> str:
    """Get ASCII art for special items"""
    art = {
        "iron_ore": """
    ╭──────────────────────────╮
    │        🔨 MATERIAL 🔨    │
    │                          │
    │     ⛏️      🪨      ⚒️    │
    │   Mining   Iron    Forge  │
    │    Tools   Ore    Ready   │
    │                          │
    │    💎 VALUABLE ORE 💎    │
    ╰──────────────────────────╯""",
        
        "glimmering_gem": """
    ╭──────────────────────────╮
    │       ✨ TREASURE ✨      │
    │                          │
    │     💎      🌟      ✨    │
    │  Precious  Magic   Divine │
    │    Gem     Light   Power  │
    │                          │
    │      🔮 MAGICAL 🔮       │
    ╰──────────────────────────╯""",
        
        "ancient_scroll": """
    ╭──────────────────────────╮
    │      📜 KNOWLEDGE 📜      │
    │                          │
    │     📚      🔮      ⚡    │
    │  Ancient  Mystery Secret  │
    │  Wisdom   Symbols  Runes  │
    │                          │
    │     🗝️ IMPORTANT 🗝️      │
    ╰──────────────────────────╯"""
    }
    return art.get(item_name, "")

# ---------- Mini-Map System ----------
def get_mini_map(w: "World") -> str:
    """Generate a mini-map showing explored areas and connections"""
    if not w.player.explored_areas:
        return colorize_warning("🗺️ Mini-Map: No areas explored yet!")
    
    # Location coordinates for map layout
    coords = {
        "village_square": (4, 2),
        "blacksmith_shop": (2, 1),
        "forest_path": (6, 2),
        "iron_mine": (8, 1), 
        "healer_tent": (2, 3),
        "elder_hut": (1, 2),
        "hidden_cave": (6, 4),
        "deep_ruins": (8, 4),
        "sealed_tower": (6, 0),
        "secret_chamber": (4, 5)
    }
    
    # Location symbols
    symbols = {
        "village_square": "🏛️",
        "blacksmith_shop": "⚒️",
        "forest_path": "🌲",
        "iron_mine": "⛏️",
        "healer_tent": "🏥",
        "elder_hut": "🏠",
        "hidden_cave": "🕳️",
        "deep_ruins": "🏛️",
        "sealed_tower": "🗼",
        "secret_chamber": "💎"
    }
    
    # Create 10x7 grid to accommodate secret_chamber
    grid = [["  " for _ in range(10)] for _ in range(7)]
    
    # Place explored locations
    for location in w.player.explored_areas:
        if location in coords:
            x, y = coords[location]
            symbol = symbols.get(location, "?")
            if location == w.player.location:
                symbol = colorize_success(f"[{symbols.get(location, '?')}]")  # Current location
            else:
                symbol = colorize_item(symbols.get(location, "?"))
            grid[y][x] = symbol
    
    # Add connections between explored areas  
    connections = [
        ("village_square", "blacksmith_shop", "─"),
        ("village_square", "forest_path", "─"),
        ("village_square", "healer_tent", "│"),
        ("village_square", "elder_hut", "─"),
        ("village_square", "sealed_tower", "│"),
        ("forest_path", "iron_mine", "─"),
        ("forest_path", "hidden_cave", "│"),
        ("hidden_cave", "deep_ruins", "─"),
        ("hidden_cave", "secret_chamber", "│")
    ]
    
    for loc1, loc2, connector in connections:
        if loc1 in w.player.explored_areas and loc2 in w.player.explored_areas:
            x1, y1 = coords[loc1]
            x2, y2 = coords[loc2]
            
            # Add connection line
            if connector == "─":  # horizontal
                for x in range(min(x1, x2) + 1, max(x1, x2)):
                    if grid[y1][x] == "  ":
                        grid[y1][x] = "─"
            elif connector == "│":  # vertical
                for y in range(min(y1, y2) + 1, max(y1, y2)):
                    if grid[y][x1] == "  ":
                        grid[y][x1] = "│"
    
    # Convert grid to string
    map_str = colorize_command("🗺️ MINI-MAP") + f" ({len(w.player.explored_areas)}/10 areas)\n"
    map_str += "╭" + "─" * 20 + "╮\n"
    for row in grid:
        map_str += "│" + "".join(row) + "│\n"
    map_str += "╰" + "─" * 20 + "╯\n"
    map_str += colorize_success("[🏛️]") + " = Current Location"
    
    return map_str

def load_map_config():
    """Load world map configuration from JSON file"""
    try:
        config_path = Path(__file__).parent / "world_map.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load world_map.json: {e}")
    
    # Fallback to hardcoded config if file loading fails
    return {
        "config": {"grid_size": [15, 11], "show_captions": False},
        "locations": {
            "village_square": {"coords": [6, 4], "symbol": "🏛️", "name": "Village Square", "caption": ""},
            "blacksmith_shop": {"coords": [3, 3], "symbol": "⚒️", "name": "Blacksmith Shop", "caption": ""},
            "forest_path": {"coords": [9, 4], "symbol": "🌲", "name": "Forest Path", "caption": ""},
            "iron_mine": {"coords": [12, 3], "symbol": "⛏️", "name": "Iron Mine", "caption": ""},
            "healer_tent": {"coords": [3, 5], "symbol": "🏥", "name": "Healer's Tent", "caption": ""},
            "elder_hut": {"coords": [1, 4], "symbol": "🏠", "name": "Elder's Hut", "caption": ""},
            "hidden_cave": {"coords": [9, 7], "symbol": "🕳️", "name": "Hidden Cave", "caption": ""},
            "deep_ruins": {"coords": [12, 7], "symbol": "🏛️", "name": "Deep Ruins", "caption": ""},
            "sealed_tower": {"coords": [9, 1], "symbol": "🗼", "name": "Sealed Tower", "caption": ""},
            "secret_chamber": {"coords": [6, 9], "symbol": "💎", "name": "Secret Chamber", "caption": ""}
        },
        "connections": [
            {"from": "village_square", "to": "blacksmith_shop", "style": "─"},
            {"from": "village_square", "to": "forest_path", "style": "─"},
            {"from": "village_square", "to": "healer_tent", "style": "│"},
            {"from": "village_square", "to": "elder_hut", "style": "─"},
            {"from": "village_square", "to": "sealed_tower", "style": "│"},
            {"from": "forest_path", "to": "iron_mine", "style": "─"},
            {"from": "forest_path", "to": "hidden_cave", "style": "│"},
            {"from": "hidden_cave", "to": "deep_ruins", "style": "─"},
            {"from": "hidden_cave", "to": "secret_chamber", "style": "│"}
        ]
    }

def get_world_map(w: "World", no_colors: bool = False) -> str:
    """Generate a comprehensive ASCII world map showing all locations"""
    
    # Load configuration from JSON file
    map_config = load_map_config()
    
    config = map_config.get("config", {})
    locations_data = map_config.get("locations", {})
    connections_data = map_config.get("connections", [])
    
    # Get grid size from config
    grid_width, grid_height = config.get("grid_size", [15, 11])
    
    # Create grid based on config
    grid = [["   " for _ in range(grid_width)] for _ in range(grid_height)]
    
    # Place all locations (explored and unexplored)
    for location_key, location_info in locations_data.items():
        x, y = location_info.get("coords", [0, 0])
        symbol = location_info.get("symbol", "❓")
        
        if location_key in w.player.explored_areas:
            if location_key == w.player.location:
                # Current location - bright highlight
                if no_colors:
                    grid[y][x] = f"[{symbol}]"
                else:
                    grid[y][x] = colorize_success(f"[{symbol}]")
            else:
                # Explored location
                if no_colors:
                    grid[y][x] = f" {symbol} "
                else:
                    grid[y][x] = colorize_item(f" {symbol} ")
        else:
            # Unexplored location - dimmed
            if no_colors:
                grid[y][x] = " ? "
            else:
                grid[y][x] = colorize_warning(" ? ")
    
    # Add connection paths for explored areas
    for connection in connections_data:
        loc1 = connection.get("from")
        loc2 = connection.get("to") 
        connector = connection.get("style", "─")
        
        if (loc1 in w.player.explored_areas and loc2 in w.player.explored_areas and
            loc1 in locations_data and loc2 in locations_data):
            
            x1, y1 = locations_data[loc1].get("coords", [0, 0])
            x2, y2 = locations_data[loc2].get("coords", [0, 0])
            
            # Add connection line
            if connector == "─":  # horizontal
                for x in range(min(x1, x2) + 1, max(x1, x2)):
                    if grid[y1][x] == "   ":
                        grid[y1][x] = " ─ "
            elif connector == "│":  # vertical
                for y in range(min(y1, y2) + 1, max(y1, y2)):
                    if grid[y][x1] == "   ":
                        grid[y][x1] = " │ "
    
    # Create the map display
    title = config.get("title", "🗺️ WORLD MAP")
    total_locations = len(locations_data)
    
    if no_colors:
        map_str = f"\n{title} — Explored: {len(w.player.explored_areas)}/{total_locations} locations\n"
    else:
        map_str = "\n" + colorize_command(title) + f" — Explored: {len(w.player.explored_areas)}/{total_locations} locations\n"
    
    # Dynamic border width based on grid size
    border_width = grid_width * 3 + 2  # Account for 3-char cells plus padding
    map_str += "╭" + "─" * border_width + "╮\n"
    
    for row in grid:
        map_str += "│" + "".join(row) + "│\n"
    
    map_str += "╰" + "─" * border_width + "╯\n"
    
    # Add location captions if enabled
    if config.get("show_captions", True):
        map_str += "\nLOCATION DETAILS:\n"
        for location_key in w.player.explored_areas:
            if location_key in locations_data:
                location_info = locations_data[location_key]
                name = location_info.get("name", location_key)
                caption = location_info.get("caption", "")
                symbol = location_info.get("symbol", "?")
                
                if location_key == w.player.location:
                    if no_colors:
                        prefix = f"[{symbol}] "
                    else:
                        prefix = colorize_success(f"[{symbol}] ")
                else:
                    if no_colors:
                        prefix = f" {symbol}  "
                    else:
                        prefix = colorize_item(f" {symbol}  ")
                
                if caption:
                    map_str += f"{prefix}{name} — {caption}\n"
                else:
                    map_str += f"{prefix}{name}\n"
    
    # Add legend from config
    legend_config = map_config.get("legend", {})
    if legend_config:
        if no_colors:
            map_str += "\nLEGEND:\n"
        else:
            map_str += "\n" + colorize_command("LEGEND:") + "\n"
        
        for legend_key, legend_text in legend_config.items():
            if no_colors:
                map_str += legend_text + "\n"
            else:
                if "Current Location" in legend_text:
                    map_str += colorize_success(legend_text.replace("[🏛️]", "[🏛️]")) + "\n"
                elif "Explored Area" in legend_text:
                    map_str += colorize_item(legend_text.replace(" 🏛️ ", " 🏛️ ")) + "\n"
                elif "Unexplored Area" in legend_text:
                    map_str += colorize_warning(legend_text.replace(" ? ", " ? ")) + "\n"
                else:
                    map_str += legend_text + "\n"
    
    # Add compass from config
    compass_config = map_config.get("compass", {})
    if compass_config.get("enabled", True):
        compass_style = compass_config.get("style", "   N\n W ⊕ E\n   S")
        if no_colors:
            map_str += "\n" + compass_style + "\n"
        else:
            # Apply colors to compass directions
            colored_compass = compass_style
            for direction in ["N", "E", "S", "W"]:
                colored_compass = colored_compass.replace(direction, colorize_command(direction))
            map_str += "\n" + colored_compass + "\n"
    
    return map_str

# ---------- Achievement System ----------
ACHIEVEMENTS = {
    "first_steps": {
        "name": "First Steps",
        "description": "Visit your first location",
        "icon": "👣"
    },
    "explorer": {
        "name": "Explorer",
        "description": "Visit 5 different locations",
        "icon": "🗺️"
    },
    "completionist": {
        "name": "Completionist", 
        "description": "Visit all 10 locations",
        "icon": "🌍"
    },
    "rich_merchant": {
        "name": "Rich Merchant",
        "description": "Accumulate 50+ gold",
        "icon": "💰"
    },
    "warrior": {
        "name": "Warrior",
        "description": "Win your first combat",
        "icon": "⚔️"
    },
    "quest_starter": {
        "name": "Quest Starter",
        "description": "Complete your first quest",
        "icon": "📜"
    },
    "hero": {
        "name": "Hero",
        "description": "Complete all 6 main quests",
        "icon": "🏆"
    },
    "socializer": {
        "name": "Socializer",
        "description": "Talk to all 3 NPCs",
        "icon": "💬"
    },
    "treasure_hunter": {
        "name": "Treasure Hunter",
        "description": "Find the ancient treasure",
        "icon": "💎"
    },
    "secret_keeper": {
        "name": "Secret Keeper",
        "description": "Discover and complete a hidden quest",
        "icon": "🗝️"
    }
}

def check_achievements(w: "World") -> List[str]:
    """Check and award new achievements, returns list of newly earned ones"""
    new_achievements = []
    
    # First Steps - visit first location
    if "first_steps" not in w.player.achievements and len(w.player.explored_areas) >= 1:
        w.player.achievements.append("first_steps")
        new_achievements.append("first_steps")
    
    # Explorer - visit 5 locations  
    if "explorer" not in w.player.achievements and len(w.player.explored_areas) >= 5:
        w.player.achievements.append("explorer")
        new_achievements.append("explorer")
    
    # Completionist - visit all 10 locations
    if "completionist" not in w.player.achievements and len(w.player.explored_areas) >= 10:
        w.player.achievements.append("completionist")
        new_achievements.append("completionist")
    
    # Rich Merchant - 50+ gold
    if "rich_merchant" not in w.player.achievements and w.player.gold >= 50:
        w.player.achievements.append("rich_merchant")
        new_achievements.append("rich_merchant")
    
    # Quest Starter - complete first quest (exclude hidden quest)
    main_quests = ["prove_worth", "clear_cave", "heal_elder", "retrieve_scroll", "forge_key", "final_treasure"]
    completed_main_quests = [q for q in main_quests if w.player.quests.get(q) == "completed"]
    
    if "quest_starter" not in w.player.achievements and len(completed_main_quests) >= 1:
        w.player.achievements.append("quest_starter")
        new_achievements.append("quest_starter")
    
    # Hero - complete all 6 main quests (hidden quest doesn't count)
    if "hero" not in w.player.achievements and len(completed_main_quests) >= 6:
        w.player.achievements.append("hero")
        new_achievements.append("hero")
    
    # Socializer - talk to all NPCs (check for actual player conversations)
    talked_to_npcs = []
    for npc_key, npc in w.npcs.items():
        # Check if any memory entries contain player conversations
        if any("Player said:" in memory_entry for memory_entry in npc.memory):
            talked_to_npcs.append(npc_key)
    if "socializer" not in w.player.achievements and len(talked_to_npcs) >= 3:
        w.player.achievements.append("socializer")
        new_achievements.append("socializer")
    
    # Treasure Hunter - complete final quest
    if "treasure_hunter" not in w.player.achievements and w.player.quests.get("ancient_treasure") == "completed":
        w.player.achievements.append("treasure_hunter")
        new_achievements.append("treasure_hunter")
    
    # Secret Keeper - complete hidden side quest
    if "secret_keeper" not in w.player.achievements and w.player.quests.get("lost_trinket") == "completed":
        w.player.achievements.append("secret_keeper")
        new_achievements.append("secret_keeper")
    
    return new_achievements

def show_achievement_notification(achievement_key: str) -> str:
    """Show notification for newly earned achievement"""
    if achievement_key not in ACHIEVEMENTS:
        return ""
    
    achievement = ACHIEVEMENTS[achievement_key]
    return colorize_success(f"\n🎉 ACHIEVEMENT UNLOCKED: {achievement['icon']} {achievement['name']}\n   {achievement['description']}")

def show_achievements_list(w: "World") -> str:
    """Show all achievements and progress"""
    output = colorize_command("🏆 ACHIEVEMENTS") + f" ({len(w.player.achievements)}/{len(ACHIEVEMENTS)})\n\n"
    
    for key, achievement in ACHIEVEMENTS.items():
        if key in w.player.achievements:
            status = colorize_success("✅ UNLOCKED")
        else:
            status = colorize_warning("🔒 LOCKED")
        
        output += f"{achievement['icon']} {achievement['name']} - {status}\n"
        output += f"   {achievement['description']}\n\n"
    
    return output.strip()

# ---------- Game Over System ----------
def handle_game_completion() -> str:
    """Handle game completion with menu options"""
    completion_screen = f"""
{colorize_success("═══════════════════════════════════════")}
{colorize_success("           GAME COMPLETED!             ")}
{colorize_success("═══════════════════════════════════════")}

{colorize_quest("🏆 Congratulations, Hero! 🏆")}
{colorize_quest("You have completed your epic journey!")}

{colorize_command("What would you like to do?")}

{colorize_command("1.")} Play Again
{colorize_command("2.")} Load Saved Game  
{colorize_command("3.")} Quit Game

{colorize_warning("Enter your choice (1-3):")}"""
    
    game_print(completion_screen)
    
    while True:
        try:
            choice = game_input("> ").strip()
            
            if choice == "1":
                print(f"\n{colorize_success('Starting new game...')}\n")
                return "__RESTART__"
            elif choice == "2":
                # Show available saves
                try:
                    saves_dir = Path("saves")
                    if saves_dir.exists():
                        save_files = [f.stem for f in saves_dir.glob("*.json")]
                        if save_files:
                            print(f"\n{colorize_command('Available saves:')}")
                            for i, save_name in enumerate(save_files, 1):
                                print(f"  {colorize_command(str(i))}. {save_name}")
                            print(f"  {colorize_command('0')}. Cancel")
                            
                            while True:
                                load_choice = game_input("\nEnter save number to load: ").strip()
                                try:
                                    if load_choice == "0":
                                        break
                                    load_idx = int(load_choice) - 1
                                    if 0 <= load_idx < len(save_files):
                                        save_name = save_files[load_idx]
                                        print(f"\n{colorize_success(f'Loading {save_name}...')}\n")
                                        return f"__LOAD__{save_name}"
                                    else:
                                        game_print(colorize_error("Invalid choice. Try again."))
                                except ValueError:
                                    game_print(colorize_error("Please enter a number."))
                        else:
                            game_print(f"\n{colorize_warning('No save files found.')}")
                    else:
                        game_print(f"\n{colorize_warning('No save files found.')}")
                except Exception:
                    game_print(f"\n{colorize_error('Error loading save files.')}")
            elif choice == "3":
                game_print(f"\n{colorize_success('Thanks for playing! Goodbye.')}")
                return "__QUIT__"
            else:
                game_print(colorize_error("Invalid choice. Please enter 1, 2, or 3."))
                
        except (KeyboardInterrupt, EOFError):
            game_print(f"\n{colorize_success('Thanks for playing! Goodbye.')}")
            return "__QUIT__"

def handle_game_over() -> str:
    """Handle game over with menu options"""
    game_over_screen = f"""
{colorize_error("═══════════════════════════════════════")}
{colorize_error("              GAME OVER                ")}
{colorize_error("═══════════════════════════════════════")}

{colorize_combat("Your adventure has come to an end...")}
{colorize_command("What would you like to do?")}

{colorize_command("1.")} Restart Game
{colorize_command("2.")} Load Saved Game  
{colorize_command("3.")} Quit Game

{colorize_warning("Enter your choice (1-3):")}"""
    
    game_print(game_over_screen)
    
    while True:
        try:
            choice = game_input("> ").strip()
            
            if choice == "1":
                game_print(f"\n{colorize_success('Restarting game...')}\n")
                return "__RESTART__"
            elif choice == "2":
                # Show available saves
                try:
                    saves_dir = Path("saves")
                    if saves_dir.exists():
                        save_files = [f.stem for f in saves_dir.glob("*.json")]
                        if save_files:
                            game_print(f"\n{colorize_command('Available saves:')}")
                            for i, save_name in enumerate(save_files, 1):
                                game_print(f"  {colorize_command(str(i))}. {save_name}")
                            game_print(f"  {colorize_command('0')}. Cancel")
                            
                            while True:
                                load_choice = game_input("\nEnter save number to load: ").strip()
                                try:
                                    if load_choice == "0":
                                        break
                                    load_idx = int(load_choice) - 1
                                    if 0 <= load_idx < len(save_files):
                                        save_name = save_files[load_idx]
                                        print(f"\n{colorize_success(f'Loading {save_name}...')}\n")
                                        return f"__LOAD__{save_name}"
                                    else:
                                        game_print(colorize_error("Invalid choice. Try again."))
                                except ValueError:
                                    game_print(colorize_error("Please enter a number."))
                        else:
                            game_print(f"\n{colorize_warning('No save files found.')}")
                    else:
                        game_print(f"\n{colorize_warning('No save files found.')}")
                except Exception:
                    game_print(f"\n{colorize_error('Error loading save files.')}")
            elif choice == "3":
                game_print(f"\n{colorize_success('Thanks for playing! Goodbye.')}")
                return "__QUIT__"
            else:
                game_print(colorize_error("Invalid choice. Please enter 1, 2, or 3."))
                
        except (KeyboardInterrupt, EOFError):
            game_print(f"\n{colorize_success('Thanks for playing! Goodbye.')}")
            return "__QUIT__"

# ---------- Enhanced NPC System ----------
def update_relationship(npc: "NPC", points_change: int, reason: str = "") -> List[str]:
    """Update NPC relationship and return any level change messages"""
    messages = []
    old_level = npc.relationship_level
    npc.relationship_points = max(0, npc.relationship_points + points_change)
    
    # Update relationship level based on points
    if npc.relationship_points >= 76:
        npc.relationship_level = "ally"
    elif npc.relationship_points >= 26:
        npc.relationship_level = "friendly"
    else:
        npc.relationship_level = "neutral"
    
    # Generate level change message
    if old_level != npc.relationship_level:
        if npc.relationship_level == "friendly" and old_level == "neutral":
            messages.append(f"\n💚 {npc.name} seems to like you more now! (Relationship: {colorize_success('Friendly')})")
        elif npc.relationship_level == "ally" and old_level == "friendly":
            messages.append(f"\n💙 {npc.name} considers you a trusted ally! (Relationship: {colorize_success('Ally')})")
        elif npc.relationship_level == "neutral" and old_level == "friendly":
            messages.append(f"\n💔 {npc.name} seems less friendly towards you. (Relationship: {colorize_warning('Neutral')})")
    
    if reason:
        npc.memory.append(f"Relationship changed by {points_change} ({reason})")
    
    return messages

def set_emotional_state(npc: "NPC", emotion: str, reason: str = "") -> str:
    """Set NPC emotional state and return description"""
    old_emotion = npc.emotional_state
    npc.emotional_state = emotion
    
    if reason:
        npc.memory.append(f"Emotional state changed to {emotion} ({reason})")
    
    emotion_indicators = {
        "happy": "😊",
        "sad": "😢", 
        "angry": "😠",
        "excited": "🤩",
        "worried": "😰",
        "calm": "😌"
    }
    
    indicator = emotion_indicators.get(emotion, "😐")
    if old_emotion != emotion:
        return f" {indicator}"
    return ""

def track_conversation_topic(npc: "NPC", topic: str) -> None:
    """Track what topics have been discussed with this NPC"""
    topic = topic.lower()
    npc.conversation_topics[topic] = npc.conversation_topics.get(topic, 0) + 1

def get_relationship_modifier(npc: "NPC") -> str:
    """Get relationship-based dialogue modifier"""
    modifiers = {
        "neutral": "",
        "friendly": " (They seem to enjoy talking with you.)",
        "ally": " (They trust you completely and speak openly.)"
    }
    return modifiers.get(npc.relationship_level, "")

def get_emotional_context(npc: "NPC") -> str:
    """Get emotional state context for dialogue"""
    contexts = {
        "happy": " They seem cheerful and upbeat.",
        "sad": " There's a sadness in their eyes.",
        "angry": " They appear irritated or upset.",
        "excited": " They're clearly excited about something.",
        "worried": " They look concerned about something.",
        "calm": ""
    }
    return contexts.get(npc.emotional_state, "")

def show_relationships(w: "World") -> str:
    """Display relationship status with all NPCs"""
    output = [colorize_command("👥 RELATIONSHIPS\n")]
    
    for npc_key, npc in w.npcs.items():
        # Relationship level with colors
        level_colors = {
            "neutral": colorize_warning("Neutral"),
            "friendly": colorize_success("Friendly"), 
            "ally": colorize_item("Ally")
        }
        level_text = level_colors.get(npc.relationship_level, npc.relationship_level)
        
        # Emotional state with emoji
        emotion_emojis = {
            "happy": "😊", "sad": "😢", "angry": "😠",
            "excited": "🤩", "worried": "😰", "calm": "😌"
        }
        emotion_emoji = emotion_emojis.get(npc.emotional_state, "😐")
        
        # Progress bar for relationship points
        points = npc.relationship_points
        max_points = 100
        filled = int((points / max_points) * 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        output.append(f"{colorize_npc(npc.name)} {emotion_emoji}")
        output.append(f"  Status: {level_text} ({points}/100)")
        output.append(f"  Progress: [{colorize_item(bar)}]")
        
        # Show most discussed topics
        if npc.conversation_topics:
            top_topics = sorted(npc.conversation_topics.items(), key=lambda x: x[1], reverse=True)[:3]
            topics_text = ", ".join([f"{topic}({count})" for topic, count in top_topics])
            output.append(f"  Topics: {colorize_command(topics_text)}")
        
        output.append("")
    
    return "\n".join(output).strip()

# ---------- Enhanced Inventory System ----------
def get_player_stats(w: "World") -> Dict[str, int]:
    """Calculate player's total stats including equipment bonuses"""
    base_stats = {
        "attack": 2,  # base attack without weapons
        "defense": 0, # base defense 
        "max_hp": w.player.max_hp,
        "hp_regen": 0
    }
    
    # Add weapon stats
    if w.player.equipment.weapon and w.player.equipment.weapon in ITEMS:
        weapon = ITEMS[w.player.equipment.weapon]
        for stat, value in weapon.stats.items():
            base_stats[stat] = base_stats.get(stat, 0) + value
    
    # Add armor stats
    if w.player.equipment.armor and w.player.equipment.armor in ITEMS:
        armor = ITEMS[w.player.equipment.armor]
        for stat, value in armor.stats.items():
            base_stats[stat] = base_stats.get(stat, 0) + value
    
    # Add accessory stats
    if w.player.equipment.accessory and w.player.equipment.accessory in ITEMS:
        accessory = ITEMS[w.player.equipment.accessory] 
        for stat, value in accessory.stats.items():
            base_stats[stat] = base_stats.get(stat, 0) + value
    
    return base_stats

def show_enhanced_inventory(w: "World") -> str:
    """Display enhanced inventory with categories and equipment"""
    output = [colorize_command("📦 INVENTORY") + f" (Gold: {colorize_item(str(w.player.gold))})\n"]
    
    # Equipment Section
    output.append(colorize_command("⚔️ EQUIPMENT:"))
    weapon_name = ITEMS[w.player.equipment.weapon].name if w.player.equipment.weapon else "None"
    armor_name = ITEMS[w.player.equipment.armor].name if w.player.equipment.armor else "None"  
    accessory_name = ITEMS[w.player.equipment.accessory].name if w.player.equipment.accessory else "None"
    
    output.append(f"  Weapon: {colorize_item(weapon_name)}")
    output.append(f"  Armor: {colorize_item(armor_name)}")
    output.append(f"  Accessory: {colorize_item(accessory_name)}")
    output.append("")
    
    # Stats Section
    stats = get_player_stats(w)
    output.append(colorize_command("📊 STATS:"))
    output.append(f"  Attack: {colorize_combat(str(stats['attack']))}")
    output.append(f"  Defense: {colorize_success(str(stats['defense']))}")
    output.append(f"  Max HP: {colorize_success(str(stats['max_hp']))}")
    if stats['hp_regen'] > 0:
        output.append(f"  HP Regen: {colorize_success(str(stats['hp_regen']))}")
    output.append("")
    
    # Categorized Items
    categories = {
        "weapon": "⚔️ WEAPONS:",
        "armor": "🛡️ ARMOR:", 
        "accessory": "💎 ACCESSORIES:",
        "consumable": "🧪 CONSUMABLES:",
        "quest": "📜 QUEST ITEMS:",
        "material": "🔨 MATERIALS:"
    }
    
    for category, header in categories.items():
        category_items = [item for item in w.player.inventory if item in ITEMS and ITEMS[item].category == category]
        if category_items:
            output.append(colorize_command(header))
            for item in sorted(category_items):
                item_obj = ITEMS[item]
                equipped_marker = ""
                if (category == "weapon" and item == w.player.equipment.weapon or
                    category == "armor" and item == w.player.equipment.armor or
                    category == "accessory" and item == w.player.equipment.accessory):
                    equipped_marker = " " + colorize_success("[EQUIPPED]")
                
                stats_text = ""
                if item_obj.stats:
                    stat_parts = []
                    for stat, value in item_obj.stats.items():
                        if isinstance(value, str) or value > 0:
                            stat_parts.append(f"+{value} {stat}")
                    if stat_parts:
                        stats_text = f" ({', '.join(stat_parts)})"
                
                output.append(f"  {colorize_item(item_obj.name)}{stats_text}{equipped_marker}")
            output.append("")
    
    # Items not in database (legacy items)
    other_items = [item for item in w.player.inventory if item not in ITEMS]
    if other_items:
        output.append(colorize_command("❓ OTHER:"))
        for item in sorted(other_items):
            output.append(f"  {colorize_item(item.replace('_', ' ').title())}")
        output.append("")
    
    if not w.player.inventory:
        output.append(colorize_warning("Your inventory is empty."))
    
    return "\n".join(output).strip()

def equip_item(w: "World", item_key: str) -> str:
    """Equip an item from inventory"""
    if item_key not in w.player.inventory:
        return f"You don't have a '{item_key}' to equip."
    
    if item_key not in ITEMS:
        return f"'{item_key}' cannot be equipped."
    
    item = ITEMS[item_key]
    if not item.equipable:
        return f"'{item.name}' cannot be equipped."
    
    # Unequip current item in slot if any
    if item.category == "weapon":
        if w.player.equipment.weapon:
            old_item = ITEMS[w.player.equipment.weapon]
            w.player.equipment.weapon = item_key
            return f"You equip the {colorize_item(item.name)} and put away the {old_item.name}."
        else:
            w.player.equipment.weapon = item_key
            return f"You equip the {colorize_item(item.name)}."
    
    elif item.category == "armor":
        if w.player.equipment.armor:
            old_item = ITEMS[w.player.equipment.armor]
            w.player.equipment.armor = item_key
            return f"You equip the {colorize_item(item.name)} and remove the {old_item.name}."
        else:
            w.player.equipment.armor = item_key
            return f"You equip the {colorize_item(item.name)}."
    
    elif item.category == "accessory":
        if w.player.equipment.accessory:
            old_item = ITEMS[w.player.equipment.accessory]
            w.player.equipment.accessory = item_key
            return f"You equip the {colorize_item(item.name)} and remove the {old_item.name}."
        else:
            w.player.equipment.accessory = item_key
            return f"You equip the {colorize_item(item.name)}."
    
    return f"'{item.name}' cannot be equipped in any slot."

def unequip_item(w: "World", slot: str) -> str:
    """Unequip an item from equipment slot"""
    slot = slot.lower()
    
    if slot == "weapon" and w.player.equipment.weapon:
        item = ITEMS[w.player.equipment.weapon]
        w.player.equipment.weapon = None
        return f"You unequip the {colorize_item(item.name)}."
    
    elif slot == "armor" and w.player.equipment.armor:
        item = ITEMS[w.player.equipment.armor]
        w.player.equipment.armor = None
        return f"You unequip the {colorize_item(item.name)}."
    
    elif slot == "accessory" and w.player.equipment.accessory:
        item = ITEMS[w.player.equipment.accessory]
        w.player.equipment.accessory = None
        return f"You unequip the {colorize_item(item.name)}."
    
    else:
        return f"No item equipped in {slot} slot."

def use_item(w: "World", item_key: str) -> str:
    """Use a consumable item"""
    if item_key not in w.player.inventory:
        return f"You don't have a '{item_key}' to use."
    
    if item_key not in ITEMS:
        return f"You cannot use '{item_key}'."
    
    item = ITEMS[item_key]
    if item.category != "consumable":
        return f"'{item.name}' is not usable."
    
    # Use the item
    w.player.inventory.remove(item_key)
    
    if "heal" in item.stats:
        # Check if already at full health
        if w.player.hp >= w.player.max_hp:
            # Return the item to inventory
            w.player.inventory.append(item_key)
            return f"You're already at full health! The {colorize_item(item.name)} remains unused."
        
        heal_amount = item.stats["heal"]
        old_hp = w.player.hp
        
        if heal_amount == "full":
            w.player.hp = w.player.max_hp
            actual_heal = w.player.hp - old_hp
            return f"You use the {colorize_item(item.name)} and recover {colorize_success('full')} HP! (HP: {w.player.hp}/{w.player.max_hp})"
        else:
            w.player.hp = min(w.player.max_hp, w.player.hp + heal_amount)
            actual_heal = w.player.hp - old_hp
            return f"You use the {colorize_item(item.name)} and recover {colorize_success(str(actual_heal))} HP. (HP: {w.player.hp}/{w.player.max_hp})"
    
    return f"You use the {colorize_item(item.name)}."

# ---------- Enhanced Inventory System ----------
@dataclass
class Item:
    key: str
    name: str
    category: str  # weapon, armor, accessory, consumable, quest, material
    description: str
    stats: Dict[str, int] = field(default_factory=dict)  # {attack: 5, defense: 2, etc}
    value: int = 0
    equipable: bool = False

@dataclass 
class Equipment:
    weapon: Optional[str] = None
    armor: Optional[str] = None
    accessory: Optional[str] = None

# Item Database
ITEMS = {
    "rusty_sword": Item(
        key="rusty_sword",
        name="Rusty Sword", 
        category="weapon",
        description="An old, rusty blade. Better than nothing.",
        stats={"attack": 3},
        value=10,
        equipable=True
    ),
    "broad_sword": Item(
        key="broad_sword",
        name="Broad Sword",
        category="weapon", 
        description="A masterfully forged blade with excellent balance.",
        stats={"attack": 8},
        value=50,
        equipable=True
    ),
    "leather_armor": Item(
        key="leather_armor",
        name="Leather Armor",
        category="armor",
        description="Basic protection from wild beasts.",
        stats={"defense": 3},
        value=25,
        equipable=True
    ),
    "magical_amulet": Item(
        key="magical_amulet", 
        name="Magical Amulet",
        category="accessory",
        description="A mystical amulet that radiates healing energy.",
        stats={"max_hp": 5, "hp_regen": 1},
        value=100,
        equipable=True
    ),
    "iron_ore": Item(
        key="iron_ore",
        name="Iron Ore",
        category="material",
        description="Raw iron ore, perfect for forging.",
        value=15
    ),
    "glimmering_gem": Item(
        key="glimmering_gem",
        name="Glimmering Gem", 
        category="quest",
        description="A mysterious gem that pulses with magical energy.",
        value=200
    ),
    "ancient_scroll": Item(
        key="ancient_scroll",
        name="Ancient Scroll",
        category="quest", 
        description="Ancient runes cover this weathered parchment.",
        value=150
    ),
    "master_key": Item(
        key="master_key",
        name="Master Key",
        category="quest",
        description="An ornate key humming with arcane power.",
        value=300
    ),
    "health_potion": Item(
        key="health_potion",
        name="Health Potion",
        category="consumable",
        description="Restores health when consumed.",
        stats={"heal": 15},
        value=20
    ),
    "elder_sword": Item(
        key="elder_sword",
        name="Elder Sword",
        category="weapon",
        description="A legendary blade forged by ancient masters. Its edge gleams with otherworldly sharpness.",
        stats={"attack": 12},
        value=200,
        equipable=True
    ),
    "ancient_trinket": Item(
        key="ancient_trinket",
        name="Ancient Trinket",
        category="quest",
        description="A small ornate medallion with intricate engravings. It feels warm to the touch.",
        value=300
    ),
    "guardian_armor": Item(
        key="guardian_armor",
        name="Guardian Armor", 
        category="armor",
        description="Ancient plate armor blessed with protective runes. Reduces incoming damage significantly.",
        stats={"defense": 5},
        value=150,
        equipable=True
    ),
    "healing_potion": Item(
        key="healing_potion",
        name="Healing Potion",
        category="consumable",
        description="A magical potion that restores 10 HP when consumed. Can be used anywhere.",
        stats={"heal": 10},
        value=8,
        equipable=False
    ),
    "greater_healing_potion": Item(
        key="greater_healing_potion", 
        name="Greater Healing Potion",
        category="consumable",
        description="A powerful healing elixir that fully restores HP. Can be used anywhere.",
        stats={"heal": "full"},
        value=20,
        equipable=False
    )
}

# ---------- Data models ----------
@dataclass
class NPC:
    key: str
    name: str
    personality: str
    memory: List[str] = field(default_factory=list)
    relationship_level: str = "neutral"  # neutral, friendly, ally
    relationship_points: int = 0  # 0-25=neutral, 26-75=friendly, 76+=ally
    emotional_state: str = "calm"  # calm, happy, sad, angry, excited, worried
    conversation_topics: Dict[str, int] = field(default_factory=dict)  # topic: times_discussed

@dataclass
class Location:
    key: str
    description: str
    exits: List[str]
    npcs: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    visited: bool = False

@dataclass
class Player:
    location: str
    inventory: List[str] = field(default_factory=list)
    quests: Dict[str, str] = field(default_factory=dict)
    gold: int = 0
    hp: int = 20
    max_hp: int = 20
    previous_location: str = ""  # Track where player came from
    explored_areas: List[str] = field(default_factory=list)  # Track visited locations
    achievements: List[str] = field(default_factory=list)  # Unlocked achievements
    equipment: Equipment = field(default_factory=Equipment)  # Equipped items

@dataclass
class Monster:
    key: str
    name: str
    hp: int
    attack_min: int
    attack_max: int

@dataclass
class World:
    player: Player
    locations: Dict[str, Location]
    npcs: Dict[str, NPC]
    flags: Dict[str, bool] = field(default_factory=dict)
    monster: Optional[Monster] = None     # active monster (in combat)

# ---------- Shop ----------
SHOP = {
    "blacksmith": {
        "rusty_sword": 10,
        "guardian_armor": 15,
    },
    "healer": {
        "healing_potion": 8,
        "greater_healing_potion": 20,
    }
}

# ---------- Build world ----------
def build_world() -> World:
    locations = {
        "village_square": Location(
            key="village_square",
            description="Village Square — smithy smoke curls into the sky. A forest path leads north. An ancient tower looms to the east.",
            exits=["blacksmith_shop","forest_path","elder_hut","sealed_tower","healer_tent"],
            npcs=["wanderer"]
        ),
        "blacksmith_shop": Location(
            key="blacksmith_shop",
            description="Blacksmith Shop — heat and hammering. Tools line the walls.",
            exits=["village_square"],
            npcs=["blacksmith"]
        ),
        "forest_path": Location(
            key="forest_path",
            description="Forest Path — tall pines, damp earth. A narrow track disappears into darker woods.",
            exits=["village_square","hidden_cave","iron_mine"]
        ),
        "iron_mine": Location(
            key="iron_mine",
            description="Iron Mine — abandoned shafts echo with your footsteps. Rusty ore glints in the dim light.",
            exits=["forest_path"],
            items=["iron_ore"],
            npcs=["miner"]
        ),
        "healer_tent": Location(
            key="healer_tent",
            description="Healer's Tent — soft candlelight illuminates shelves of herbs and potions. The scent of healing oils fills the air.",
            exits=["village_square"],
            npcs=["healer"]
        ),
        "elder_hut": Location(
            key="elder_hut",
            description="Elder's Hut — a modest dwelling filled with ancient books and herbs. The Elder lies pale in bed.",
            exits=["village_square"],
            npcs=["elder"]
        ),
        "hidden_cave": Location(
            key="hidden_cave",
            description="Hidden Cave — your footsteps echo; the air is cool and still. You notice a faint draft coming from behind some loose rocks.",
            exits=["forest_path","deep_ruins"]
        ),
        "deep_ruins": Location(
            key="deep_ruins",
            description="Deep Ruins — ancient stone corridors carved with mysterious symbols. The air hums with old magic.",
            exits=["hidden_cave"],
            items=[]  # Ancient scroll only appears after defeating Ancient Guardian
        ),
        "sealed_tower": Location(
            key="sealed_tower",
            description="Sealed Tower — a massive door blocks your way, covered in arcane locks. Beyond lies untold treasure.",
            exits=["village_square"],
        ),
        "secret_chamber": Location(
            key="secret_chamber",
            description="Secret Chamber — a small hidden room behind the cave wall. Ancient symbols glow faintly on the walls, and you see something glinting in an alcove.",
            exits=["hidden_cave"],
            items=["ancient_trinket"]
        ),
    }
    npcs = {
        "blacksmith": NPC(
            key="blacksmith",
            name="Rogan the Blacksmith",
            personality="Gruff but helpful, secretly fond of gossip.",
            memory=["Met the player in the village square.","Heard rumors of a lost gem in the cave."],
            emotional_state="calm",
            relationship_level="neutral"
        ),
        "elder": NPC(
            key="elder",
            name="Elder Theron",
            personality="Wise but weakened by a mysterious curse. Speaks in riddles and ancient wisdom.",
            memory=["Has been cursed for weeks, growing weaker.","Knows ancient magic and village history."],
            emotional_state="sad",  # He's cursed and weakening
            relationship_level="neutral"
        ),
        "healer": NPC(
            key="healer",
            name="Mira the Healer",
            personality="Kind and gentle, devoted to helping wounded adventurers. Charges fair prices for healing.",
            memory=["Runs the village healing tent.","Knows herbal remedies and basic healing magic."],
            emotional_state="calm",
            relationship_level="friendly",  # Healers are naturally more friendly
            relationship_points=30
        ),
        "wanderer": NPC(
            key="wanderer",
            name="Kael the Wanderer",
            personality="A mysterious traveler who seems to be searching for something precious. Speaks wistfully of lost artifacts.",
            memory=["Has been wandering the village for days.","Searching for something important but won't say what."],
            emotional_state="worried",
            relationship_level="neutral"
        ),
        "miner": NPC(
            key="miner",
            name="Old Gareth",
            personality="A retired miner who worked the caves for decades. Has many stories about hidden passages and secret chambers.",
            memory=["Worked in the caves for 40 years before retiring.","Knows the underground passages better than anyone."],
            emotional_state="calm",
            relationship_level="neutral"
        )
    }
    player = Player(
        location="village_square",
        inventory=[],                    # start with no sword
        quests={
            "prove_worth": "not_started",        # Quest 1: Get iron ore for blacksmith
            "clear_cave": "not_started",         # Quest 2: Defeat Cave Beast, get gem
            "heal_elder": "not_started",         # Quest 3: Trade gem to heal elder
            "retrieve_scroll": "not_started",    # Quest 4: Get ancient scroll from ruins
            "forge_key": "not_started",          # Quest 5: Get materials, forge master key
            "final_treasure": "not_started",     # Quest 6: Use key to claim treasure
            "lost_trinket": "not_started"        # Hidden Side Quest: Find wanderer's trinket
        },
        gold=15,
        hp=20, max_hp=20,
        explored_areas=["village_square"]        # Start with village explored
    )
    return World(player=player, locations=locations, npcs=npcs, flags={})

# ---------- Conversation System ----------
def conversation_mode(w: World, npc_key: str) -> str:
    """Enter interactive conversation mode with an NPC"""
    if w.flags.get("in_combat"):
        return "No time to chat—you're in a fight!"
    
    loc = w.locations[w.player.location]
    if npc_key not in loc.npcs: 
        return f"There's no one named '{npc_key}' here."
    
    npc = w.npcs[npc_key]
    
    # Enter conversation mode
    w.flags["in_conversation"] = True
    w.flags["conversation_npc"] = npc_key
    
    conversation_header = f"""
{colorize_command("═══════════════════════════════════════")}
{colorize_command(f"      TALKING TO {npc.name.upper()}")}
{colorize_command("═══════════════════════════════════════")}

{colorize_npc(f"{npc.name} looks at you attentively, ready to chat.")}
{colorize_warning("Type your message or 'exit' to end the conversation.")}
"""
    
    game_print(conversation_header)
    
    while w.flags.get("in_conversation", False):
        try:
            user_input = game_input(f"{colorize_command('You:')} ").strip()
            
            if user_input.lower() in ["exit", "quit", "leave", "bye", "goodbye"]:
                w.flags["in_conversation"] = False
                w.flags.pop("conversation_npc", None)
                game_print(f"\n{colorize_success('You end the conversation.')}")
                break
            
            if not user_input:
                game_print(colorize_warning("Say something or type 'exit' to leave."))
                continue
            
            # Process the conversation
            response = talk_to_conversation(w, npc_key, user_input)
            game_print(f"{colorize_npc(f'{npc.name}:')} {response}")
            
        except (KeyboardInterrupt, EOFError):
            w.flags["in_conversation"] = False
            w.flags.pop("conversation_npc", None)
            game_print(f"\n{colorize_success('You end the conversation.')}")
            break
    
    return ""

def talk_to_conversation(w: World, npc_key: str, text: str) -> str:
    """Handle conversation within conversation mode (simplified version of talk_to)"""
    npc = w.npcs[npc_key]
    
    # Track conversation and relationship
    npc.memory.append(f"Player said: {text.strip()} at {w.player.location}")
    
    # Basic relationship gain for talking (+1 point)
    relationship_messages = update_relationship(npc, 1, "friendly conversation")
    
    # Track conversation topics
    words = text.lower().split()
    for word in words:
        if len(word) > 3:  # Only track meaningful words
            track_conversation_topic(npc, word)
    
    # CHECK QUEST INTERACTIONS FIRST - before AI response
    # Quest interactions with wanderer
    if npc_key == "wanderer":
        # Player brings back the trinket
        if "ancient_trinket" in w.player.inventory and any(k in text.lower() for k in ("trinket", "medallion", "found", "artifact")):
            w.player.inventory.remove("ancient_trinket")
            w.player.inventory.append("elder_sword")
            w.player.quests["lost_trinket"] = "completed"
            npc.memory.append("Player returned the ancient trinket.")
            
            # Major relationship boost and happiness
            update_relationship(npc, 25, "returning precious family heirloom")
            set_emotional_state(npc, "happy", "overjoyed to have family trinket back")
            
            # Hidden achievement
            if "trinket_returner" not in w.player.achievements:
                w.player.achievements.append("trinket_returner")
            
            auto_save(w, "quest_lost_trinket")
            return "Kael's eyes fill with tears as he takes the trinket. 'You found it! My family's most precious heirloom!' He reaches into his pack and draws out a magnificent sword. 'This Elder Sword has been in my family for centuries. It's yours now - you've earned it a thousand times over.' \n\n" + colorize_success("(Hidden Quest completed: Lost Trinket)") + "\n" + colorize_item("(Received: Elder Sword - A legendary weapon!)")
    
    # Get enhanced NPC response with context
    out = npc_reply_claude(npc, text, w)
    
    # Quest interactions (keeping existing quest logic for hints)
    quest_result = handle_quest_interactions(w, npc_key, text, npc)
    if quest_result:
        return quest_result
    
    # Return just the response without extra formatting for conversation mode
    return out.strip()

def handle_quest_interactions(w: World, npc_key: str, text: str, npc) -> str:
    """Handle quest interactions during conversation"""
    # Quest interactions with blacksmith
    if npc_key == "blacksmith":
        # Give iron ore to get broad sword
        if "iron_ore" in w.player.inventory and any(k in text.lower() for k in ("ore", "iron", "forge", "sword", "weapon", "craft", "make")):
            w.player.inventory.remove("iron_ore")
            w.player.inventory.append("broad_sword")
            w.player.quests["prove_worth"] = "completed"
            npc.memory.append("Forged broad sword from iron ore for player.")
            
            # Quest reward gold
            w.player.gold += 8
            
            # Major relationship boost and excitement
            update_relationship(npc, 15, "completing prove worth quest")
            set_emotional_state(npc, "excited", "impressed with player's dedication")
            
            auto_save(w, "quest_prove_worth")
            return "The blacksmith's eyes light up as he examines the ore. 'Fine quality iron! Let me forge you a proper weapon.' He works the metal with expert skill, creating a gleaming broad sword. \n\n" + colorize_success("(Quest completed: Prove Your Worth)") + "\n" + colorize_item("(Received: Broad Sword - A superior weapon!)") + "\n" + colorize_item("(Quest reward: +8 gold!)")
        
        # Start first quest
        elif w.player.quests.get("prove_worth") == "not_started" and any(k in text.lower() for k in ("work", "help", "sword", "weapon")):
            w.player.quests["prove_worth"] = "started"
            npc.memory.append("Asked player to prove their worth by bringing iron ore.")
            return npc_reply_claude(npc, text, w) + "\n\n" + colorize_quest("(New quest started: Prove Your Worth - Get iron ore from the mine)")
        
        # Start cave quest after buying sword
        elif "rusty_sword" in w.player.inventory and w.player.quests.get("clear_cave") == "not_started" and any(k in text.lower() for k in ("gem","cave","danger")):
            w.player.quests["clear_cave"] = "started"
            npc.memory.append("Mentioned rumors of a gem in the cave.")
            return npc_reply_claude(npc, text, w) + "\n\n" + colorize_quest("(New quest started: Clear the Cave - Find the shimmering gem)")
        
        # Forge key quest
        elif "ancient_scroll" in w.player.inventory and w.player.quests.get("forge_key") == "not_started" and any(k in text.lower() for k in ("scroll", "runes", "forge", "key")):
            w.player.inventory.remove("ancient_scroll")
            w.player.inventory.append("master_key") 
            w.player.quests["forge_key"] = "completed"
            w.player.quests["final_treasure"] = "started"
            npc.memory.append("Forged master key from ancient scroll for player.")
            auto_save(w, "quest_forge_key")
            return "The blacksmith studies the ancient runes carefully. 'Aye, I know these symbols! This speaks of a master key.' He works for hours at his forge, creating an ornate key that hums with power. \n\n" + colorize_success("(Quest completed: Forge the Key)") + "\n" + colorize_quest("(New quest started: Claim the Ancient Treasure - Use the key on the sealed tower!)")

    # Quest interactions with healer
    elif npc_key == "healer":
        # Healing service
        if any(k in text.lower() for k in ("heal", "help", "hurt", "wounded", "hp", "health", "potion")):
            if w.player.hp >= w.player.max_hp:
                return npc_reply_claude(npc, text, w) + "\n\n" + colorize_npc("'You look perfectly healthy to me, dear.'")
            elif "magical_amulet" in w.player.inventory or w.player.quests.get("heal_elder") == "completed":
                # Free healing for healing the Elder
                w.player.hp = w.player.max_hp
                npc.memory.append("Healed the player for free as thanks for saving Elder Theron.")
                update_relationship(npc, 3, "grateful for saving the Elder")
                return npc_reply_claude(npc, text, w) + f"\n\n" + colorize_success("'You saved Elder Theron! This healing is my gift to you.' Mira's magic flows through you, restoring your health!") + f"\n" + colorize_item(f"(Fully healed - FREE for saving the Elder! HP: {w.player.hp}/{w.player.max_hp})")
            elif w.player.gold >= 5:
                w.player.gold -= 5
                w.player.hp = w.player.max_hp
                npc.memory.append("Healed the player for 5 gold.")
                return npc_reply_claude(npc, text, w) + f"\n\n" + colorize_success("'Let me tend to those wounds.' Mira's magic flows through you, restoring your health!") + f"\n" + colorize_item(f"(Fully healed for 5 gold. HP: {w.player.hp}/{w.player.max_hp})")
            else:
                return npc_reply_claude(npc, text, w) + "\n\n" + colorize_warning("'I'd love to help, but healing costs 5 gold. Come back when you have enough.'")

    # Quest interactions with elder
    elif npc_key == "elder":
        # Heal elder quest
        if "glimmering_gem" in w.player.inventory and w.player.quests.get("heal_elder") == "not_started":
            w.player.quests["heal_elder"] = "started"
            npc.memory.append("Player has the gem that could break the curse.")
            return npc_reply_claude(npc, text, w) + "\n\n" + colorize_quest("(New quest started: Heal the Elder - The gem might break his curse)")
        
        # Give gem to heal elder
        elif w.player.quests.get("heal_elder") == "started" and "glimmering_gem" in w.player.inventory and any(k in text.lower() for k in ("heal", "gem", "curse", "help")):
            w.player.inventory.remove("glimmering_gem")
            w.player.inventory.append("magical_amulet")
            w.player.max_hp += 5
            w.player.hp += 5  # also heal current HP
            w.player.quests["heal_elder"] = "completed"
            w.player.quests["retrieve_scroll"] = "started"
            npc.memory.append("Healed by the gem, gave magical amulet to player.")
            
            # Quest reward gold
            w.player.gold += 10
            
            # Major relationship boost and emotional transformation
            update_relationship(npc, 20, "breaking the curse and saving his life")
            set_emotional_state(npc, "happy", "curse broken, feeling grateful")
            
            auto_save(w, "quest_heal_elder")
            return "Elder Theron's color returns as the gem's power breaks his curse! 'Take this amulet, brave one. Now seek the ancient scroll in the deep ruins beyond the cave.' \n\n" + colorize_success("(Quest completed: Heal the Elder)") + "\n" + colorize_quest("(New quest started: Retrieve the Scroll)") + "\n" + colorize_item("(+5 Max HP from magical amulet!)") + "\n" + colorize_item("(Quest reward: +10 gold!)")

    # Quest interactions with wanderer (Kael)
    elif npc_key == "wanderer":
        # Player brings back the trinket
        if "ancient_trinket" in w.player.inventory and any(k in text.lower() for k in ("trinket", "medallion", "found", "artifact")):
            w.player.inventory.remove("ancient_trinket")
            w.player.inventory.append("elder_sword")
            npc.memory.append("Player returned the ancient trinket.")
            
            # Major relationship boost and happiness
            update_relationship(npc, 25, "returning precious family heirloom")
            set_emotional_state(npc, "happy", "overjoyed to have family trinket back")
            
            # Hidden achievement
            if "trinket_returner" not in w.player.achievements:
                w.player.achievements.append("trinket_returner")
            
            auto_save(w, "quest_lost_trinket")
            return "Kael's eyes fill with tears as he takes the trinket. 'You found it! My family's most precious heirloom!' He reaches into his pack and draws out a magnificent sword. 'This Elder Sword has been in my family for centuries. It's yours now - you've earned it a thousand times over.' \n\n" + colorize_success("(Hidden Quest completed: Lost Trinket)") + "\n" + colorize_item("(Received: Elder Sword - A legendary weapon!)")
        
        # Wanderer mentions lost trinket
        elif any(k in text.lower() for k in ("search", "looking", "lost", "find", "trinket", "artifact")):
            npc.memory.append("Told player about the ancient trinket.")
            return npc_reply_claude(npc, text, w) + "\n\n" + colorize_npc("'Ah, you understand my plight! I've lost my family's ancient trinket - a small medallion passed down for generations. I fear it may be hidden somewhere in the caves beyond the forest. If you could find it... I would reward you with something truly precious.'")

    # Quest interactions with miner 
    elif npc_key == "miner":
        # Miner gives hint about secret chamber
        if any(k in text.lower() for k in ("cave", "hidden", "secret", "chamber", "passage", "room")):
            npc.memory.append("Told player about the secret chamber in hidden cave.")
            update_relationship(npc, 5, "sharing valuable cave knowledge")
            return npc_reply_claude(npc, text, w) + "\n\n" + colorize_npc("'Aye, I worked them caves for forty years, I did. There's more to that hidden cave than meets the eye - behind some loose rocks on the eastern wall, there's a secret chamber. Most folk don't know about it, but I found it years ago. Might be somethin' valuable in there still.'")
    
    return None

# ---------- Engine helpers ----------
def describe_location(w: World) -> str:
    loc = w.locations[w.player.location]
    
    # Play location music (unless in combat)
    if not w.flags.get("in_combat"):
        music_manager.play_location_music(loc.key)
    
    # Check for restored boss monsters (fled from previously)
    boss_key = w.flags.get(f"{loc.key}_boss_key")
    boss_hp = w.flags.get(f"{loc.key}_boss_hp")
    if boss_key and boss_hp and not w.flags.get("in_combat"):
        # Restore the boss monster with its previous HP
        if boss_key == "cave_beast":
            w.monster = Monster(key="cave_beast", name="Cave Beast", hp=boss_hp, attack_min=2, attack_max=5)
        elif boss_key == "ancient_guardian":
            w.monster = Monster(key="ancient_guardian", name="Ancient Guardian", hp=boss_hp, attack_min=4, attack_max=8)
        elif boss_key == "tower_guardian":
            w.monster = Monster(key="tower_guardian", name="Tower Guardian", hp=boss_hp, attack_min=5, attack_max=9)
        
        w.flags["in_combat"] = True
        
        # Play boss music
        music_manager.play_combat_music(is_boss=True)
        
        # Clear the stored boss data since we've restored it
        del w.flags[f"{loc.key}_boss_key"]
        del w.flags[f"{loc.key}_boss_hp"]
        
        creature_art = get_creature_art(w.monster.name)
        return (loc.description + creature_art +
                f"\nThe {w.monster.name} is still here, wounded but ready to fight! (HP {w.monster.hp})"
                "\nCommands: attack, defend, flee")
    
    if not loc.visited:
        if loc.key == "hidden_cave" and not w.flags.get("cave_seeded"):
            # seed gem + start combat
            if "glimmering_gem" not in loc.items:
                loc.items.append("glimmering_gem")
            w.flags["cave_seeded"] = True
            # spawn monster on first entry
            w.monster = Monster(
                key="cave_beast",
                name="Cave Beast",
                hp=25,             # tweak difficulty here (HP)
                attack_min=2,      # min damage
                attack_max=5       # max damage
            )
            w.flags["in_combat"] = True
            
            # Play combat music  
            music_manager.play_combat_music(is_boss=True)
            
            loc.visited = True
            creature_art = get_creature_art("Cave Beast")
            return (loc.description + creature_art + 
                    "\nA Cave Beast lunges from the shadows! You are in combat."
                    "\nCommands: attack, defend, flee")
        elif loc.key == "deep_ruins" and not w.flags.get("ruins_seeded"):
            # spawn tougher monster in ruins - need to defeat to get scroll
            w.flags["ruins_seeded"] = True
            # Check if player has adequate weapon (broad sword or better)
            has_strong_weapon = ("broad_sword" in w.player.inventory or 
                               "elder_sword" in w.player.inventory or
                               any(item for item in w.player.inventory if "sword" in item and item != "rusty_sword"))
            
            if not has_strong_weapon:
                loc.visited = True
                return (loc.description + 
                        "\nAn Ancient Guardian blocks your path to the scroll! Its stone armor looks impervious to weak weapons. You need a stronger blade to face this foe."
                        "\nYou retreat wisely.")
            
            # Only allow scroll access after defeating guardian
            if not w.flags.get("guardian_defeated"):
                w.monster = Monster(
                    key="ancient_guardian",
                    name="Ancient Guardian",
                    hp=35,             # much tougher - needs broad sword
                    attack_min=4,
                    attack_max=8
                )
                w.flags["in_combat"] = True
                loc.visited = True
                creature_art = get_creature_art("Ancient Guardian")
                return (loc.description + creature_art +
                        "\nAn Ancient Guardian awakens from its slumber! Your weapon gleams as it senses the worthy foe. You are in combat."
                        "\nCommands: attack, defend, flee")
            else:
                # Guardian defeated, can access scroll
                if "ancient_scroll" not in loc.items:
                    loc.items.append("ancient_scroll")
        elif loc.key == "iron_mine" and not w.flags.get("mine_seeded") and not w.flags.get("in_combat"):
            # Spawn weak mine rat on first entry - beatable while unarmed
            w.flags["mine_seeded"] = True
            w.monster = Monster(
                key="mine_rat",
                name="Mine Rat",
                hp=8,              # very weak - beatable unarmed
                attack_min=1,      # minimal damage
                attack_max=2       # minimal damage
            )
            w.flags["in_combat"] = True
            loc.visited = True
            creature_art = get_creature_art("Mine Rat")
            return (loc.description + creature_art +
                    "\nA large mine rat scurries out from behind the ore pile! You are in combat."
                    "\nCommands: attack, defend, flee")
        elif loc.key == "deep_ruins" and w.flags.get("guardian_defeated"):
            # Add scroll if guardian was defeated but location was visited before
            if "ancient_scroll" not in loc.items:
                loc.items.append("ancient_scroll")
        loc.visited = True

    # Add ASCII art header
    art = get_location_art(loc.key)
    lines = []
    if art:
        lines.append(colorize_location(art))
        lines.append("")  # Empty line for spacing
    
    lines.append(colorize_location(loc.description))
    if loc.exits: 
        exit_names = [colorize_location(e.replace("_"," ")) for e in loc.exits]
        lines.append("Exits: " + ", ".join(exit_names))
    if loc.npcs: 
        npc_names = [colorize_npc(w.npcs[n].name) for n in loc.npcs]
        lines.append("You see: " + ", ".join(npc_names))
    if loc.items: 
        item_names = [colorize_item(item.replace("_"," ")) for item in loc.items]
        lines.append("On the ground: " + ", ".join(item_names))
    if w.flags.get("in_combat"):
        combat_text = f"🗡 In combat with {colorize_combat(w.monster.name)}! (HP {w.monster.hp})"
        lines.append(combat_text)
    return "\n".join(lines)

def move_player(w: World, dest_key: str) -> str:
    if w.flags.get("in_combat"):
        return "You can't move while in combat! Try: attack, defend, or flee."
    cur = w.locations[w.player.location]
    if dest_key not in cur.exits:
        return "You can't go that way."
    
    # Special case: sealed tower requires master key and final boss fight
    if dest_key == "sealed_tower":
        if "master_key" not in w.player.inventory:
            return "The tower door is sealed with arcane locks. You need a special key to enter."
        elif w.player.quests.get("final_treasure") == "started":
            # Enter the tower but face the final boss
            if not w.flags.get("final_boss_defeated"):
                # Spawn final boss
                w.monster = Monster(
                    key="tower_guardian",
                    name="Tower Guardian",
                    hp=45,  # Slightly reduced HP
                    attack_min=5,  # Reduced from 6
                    attack_max=9   # Reduced from 12
                )
                w.flags["in_combat"] = True
                w.flags["in_final_battle"] = True
                creature_art = get_creature_art("Tower Guardian")
                return ("The master key glows as you approach! The seals dissolve and the tower door swings open.\n" +
                        "Inside the treasure vault, a massive Tower Guardian awakens to protect the ancient treasures!" + 
                        creature_art +
                        "\nThe final battle begins! You are in combat.\n" +
                        "Commands: attack, defend, flee")
            else:
                # Boss already defeated, complete the game
                w.player.quests["final_treasure"] = "completed" 
                auto_save(w, "quest_final_treasure")
                w.flags["game_completed"] = True
                return "With the Tower Guardian defeated, you claim the ancient treasure vault filled with gold and magical artifacts! You have completed your hero's journey!\n\n" + colorize_success("🏆 CONGRATULATIONS! YOU HAVE COMPLETED THE GAME! 🏆")
    
    # Update location history
    w.player.previous_location = w.player.location
    w.player.location = dest_key
    
    # Track explored areas
    if dest_key not in w.player.explored_areas:
        w.player.explored_areas.append(dest_key)
    
    # Random encounters in various locations
    if not w.flags.get("in_combat"):
        import random
        encounter_chance = random.randint(1, 100)
        
        # Forest path encounters (20% chance)
        if dest_key == "forest_path" and encounter_chance <= 20:
            w.monster = Monster(
                key="forest_wolf",
                name="Forest Wolf",
                hp=12,             
                attack_min=2,      
                attack_max=4       
            )
            w.flags["in_combat"] = True
            
            # Play regular combat music for random encounters
            music_manager.play_combat_music(is_boss=False)
            
            creature_art = get_creature_art("Forest Wolf")
            return ("You enter the forest path..." + creature_art +
                    "\nA hungry forest wolf prowls out from behind the trees! You are in combat."
                    "\nCommands: attack, defend, flee")
        
        # Hidden cave encounters (15% chance) - only after Cave Beast defeated
        elif dest_key == "hidden_cave" and w.flags.get("cave_seeded") and encounter_chance <= 15:
            w.monster = Monster(
                key="cave_spider",
                name="Cave Spider",
                hp=10,
                attack_min=1,
                attack_max=3
            )
            w.flags["in_combat"] = True
            creature_art = get_creature_art("Cave Spider")
            return ("You enter the cave..." + creature_art +
                    "\nA cave spider drops from the ceiling! You are in combat."
                    "\nCommands: attack, defend, flee")
        
        # Iron mine encounters (15% chance) - only after Mine Rat defeated
        elif dest_key == "iron_mine" and w.flags.get("mine_seeded") and encounter_chance <= 15:
            w.monster = Monster(
                key="mine_bat",
                name="Mine Bat",
                hp=8,
                attack_min=1,
                attack_max=2
            )
            w.flags["in_combat"] = True
            creature_art = get_creature_art("Mine Bat")
            return ("You enter the mine..." + creature_art +
                    "\nA mine bat swoops down from the shadows! You are in combat."
                    "\nCommands: attack, defend, flee")
        
        # Deep ruins encounters (10% chance) - only after Ancient Guardian defeated
        elif dest_key == "deep_ruins" and w.flags.get("guardian_defeated") and encounter_chance <= 10:
            w.monster = Monster(
                key="stone_imp",
                name="Stone Imp",
                hp=15,
                attack_min=2,
                attack_max=5
            )
            w.flags["in_combat"] = True
            creature_art = get_creature_art("Stone Imp")
            return ("You enter the ruins..." + creature_art +
                    "\nA stone imp emerges from the rubble! You are in combat."
                    "\nCommands: attack, defend, flee")
    
    # Check for new achievements
    new_achievements = check_achievements(w)
    achievement_notifications = ""
    for achievement in new_achievements:
        achievement_notifications += show_achievement_notification(achievement)
    
    result = describe_location(w)
    if achievement_notifications:
        result += achievement_notifications
    
    # Update dashboard and actions panel if they're open
    if TKINTER_AVAILABLE and game_window and game_window.window:
        game_window.update_all_dashboard_tabs(w)
        game_window.update_actions_panel(w)
    
    return result

def take_item(w: World, item: str) -> str:
    if w.flags.get("in_combat"):
        return "No time to snatch items mid-fight!"
    loc = w.locations[w.player.location]
    if item not in loc.items: return f"You don't see a '{item}' here."
    loc.items.remove(item)
    w.player.inventory.append(item)
    # Special item handling with ASCII art
    item_art = get_item_art(item)
    
    if item == "glimmering_gem" and w.player.quests.get("clear_cave") != "completed":
        w.player.quests["clear_cave"] = "completed"
        auto_save(w, "quest_clear_cave")
        return f"You take the {item}. The gem pulses with mysterious energy. Perhaps Elder Theron knows its purpose.{item_art}"
    if item == "iron_ore" and w.player.quests.get("prove_worth") != "completed":
        w.player.quests["prove_worth"] = "completed"
        auto_save(w, "item_iron_ore")
        return f"You take the {item}. This should prove your worth to the blacksmith.{item_art}"
    if item == "ancient_scroll" and w.player.quests.get("retrieve_scroll") != "completed":
        w.player.quests["retrieve_scroll"] = "completed"
        w.player.gold += 8
        auto_save(w, "quest_retrieve_scroll")
        return f"You take the {item}. Ancient runes cover its surface - the blacksmith might understand these.{item_art}" + "\n" + colorize_success("(Quest completed: Retrieve the Scroll)") + "\n" + colorize_item("(Quest reward: +8 gold!)")
    return f"You take the {item}."

def drop_item(w: World, item: str) -> str:
    if w.flags.get("in_combat"):
        return "Not wise to drop things mid-battle."
    if item not in w.player.inventory: return f"You're not carrying a '{item}'."
    w.player.inventory.remove(item)
    w.locations[w.player.location].items.append(item)
    return f"You drop the {item}."

def inventory(w: World) -> str:
    return show_enhanced_inventory(w)

def stats(w: World) -> str:
    player_stats = get_player_stats(w)
    hp_color = Fore.GREEN if w.player.hp > w.player.max_hp * 0.5 else Fore.YELLOW if w.player.hp > w.player.max_hp * 0.2 else Fore.RED
    hp_text = f"{hp_color}{w.player.hp}/{player_stats['max_hp']}{Style.RESET_ALL}"
    
    result = [
        colorize_command("📊 PLAYER STATS"),
        f"HP: {hp_text}",
        f"Attack: {colorize_combat(str(player_stats['attack']))}",
        f"Defense: {colorize_success(str(player_stats['defense']))}",
        f"Gold: {colorize_item(str(w.player.gold))}"
    ]
    
    if player_stats['hp_regen'] > 0:
        result.append(f"HP Regen: {colorize_success(str(player_stats['hp_regen']))}")
    
    if w.flags.get("in_combat"):
        foe_text = colorize_combat(f"{w.monster.name} HP {w.monster.hp}")
        result.append(f"Foe: {foe_text}")
    
    return "\n".join(result)

def quests(w: World) -> str:
    lines = [colorize_quest("Quest Status:")]
    quest_names = {
        "prove_worth": "1. Prove Your Worth (Get iron ore, forge broad sword)",
        "clear_cave": "2. Clear the Cave (Defeat Cave Beast, get gem)", 
        "heal_elder": "3. Heal the Elder (Trade gem for amulet)",
        "retrieve_scroll": "4. Retrieve the Scroll (Need broad sword for Ancient Guardian)",
        "forge_key": "5. Forge the Key (Trade scroll for master key)",
        "final_treasure": "6. Claim the Ancient Treasure (Use key on sealed tower)"
        # lost_trinket quest is hidden - not shown in main quest list
    }
    for quest_key, quest_name in quest_names.items():
        status = w.player.quests.get(quest_key, "not_started")
        if status == "completed":
            lines.append(f"  {colorize_success('✓')} {quest_name}")
        elif status == "started":
            lines.append(f"  {colorize_quest('→')} {colorize_quest(quest_name + ' (Active)')}")
        else:
            lines.append(f"  - {quest_name}")
    return "\n".join(lines)

# ---------- Save/Load System ----------
def world_to_dict(w: World) -> dict:
    """Convert World object to dictionary for JSON serialization"""
    return {
        "player": asdict(w.player),
        "locations": {k: asdict(v) for k, v in w.locations.items()},
        "npcs": {k: asdict(v) for k, v in w.npcs.items()},
        "flags": w.flags,
        "monster": asdict(w.monster) if w.monster else None,
        "save_time": datetime.now().isoformat()
    }

def dict_to_world(data: dict) -> World:
    """Convert dictionary back to World object"""
    # Reconstruct locations
    locations = {}
    for key, loc_data in data["locations"].items():
        locations[key] = Location(**loc_data)
    
    # Reconstruct NPCs
    npcs = {}
    for key, npc_data in data["npcs"].items():
        npcs[key] = NPC(**npc_data)
    
    # Reconstruct player with equipment compatibility
    player_data = data["player"].copy()
    
    # Handle equipment compatibility - old saves had dict, new saves have Equipment object
    if "equipment" in player_data:
        equipment_data = player_data["equipment"]
        if isinstance(equipment_data, dict):
            # Old save format - convert dict to Equipment object
            if "weapon" in equipment_data or "armor" in equipment_data or "accessory" in equipment_data:
                # New dict format with keys
                from dataclasses import fields
                equipment_fields = {f.name for f in fields(Equipment)}
                equipment_kwargs = {k: v for k, v in equipment_data.items() if k in equipment_fields}
                player_data["equipment"] = Equipment(**equipment_kwargs)
            else:
                # Very old format or empty - create default Equipment
                player_data["equipment"] = Equipment()
        # If it's already an Equipment object, leave it as is
    else:
        # No equipment field - create default
        player_data["equipment"] = Equipment()
    
    player = Player(**player_data)
    
    # Reconstruct monster if exists
    monster = Monster(**data["monster"]) if data["monster"] else None
    
    return World(
        player=player,
        locations=locations,
        npcs=npcs,
        flags=data.get("flags", {}),
        monster=monster
    )

def save_game(w: World, save_name: str = "quicksave") -> str:
    """Save world state to JSON file"""
    try:
        # Create saves directory if it doesn't exist
        saves_dir = Path("saves")
        saves_dir.mkdir(exist_ok=True)
        
        # Save to file
        save_path = saves_dir / f"{save_name}.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(world_to_dict(w), f, indent=2)
        
        return colorize_success(f"Game saved to {save_path}")
    except Exception as e:
        return colorize_error(f"Failed to save game: {e}")

def auto_save(w: World, event_type: str = "auto") -> None:
    """Auto-save game state silently"""
    try:
        saves_dir = Path("saves")
        saves_dir.mkdir(exist_ok=True)
        save_path = saves_dir / f"autosave_{event_type}.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(world_to_dict(w), f, indent=2)
    except Exception:
        pass  # Silent auto-save failure

def load_world(save_name: str) -> World:
    """Load world state from JSON file. Returns World or None if failed"""
    try:
        save_path = Path("saves") / f"{save_name}.json"
        if not save_path.exists():
            return None
        
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return dict_to_world(data)
    except Exception:
        return None

def load_game(save_name: str = "quicksave") -> tuple[World, str]:
    """Load world state from JSON file. Returns (world, message)"""
    try:
        save_path = Path("saves") / f"{save_name}.json"
        if not save_path.exists():
            return None, colorize_error(f"Save file '{save_name}' not found.")
        
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        world = dict_to_world(data)
        save_time = data.get("save_time", "unknown time")
        return world, colorize_success(f"Game loaded from {save_path} (saved: {save_time[:19]})")
    except Exception as e:
        return None, colorize_error(f"Failed to load game: {e}")

def list_saves() -> str:
    """List available save files"""
    saves_dir = Path("saves")
    if not saves_dir.exists():
        return "No saves directory found."
    
    save_files = list(saves_dir.glob("*.json"))
    if not save_files:
        return "No save files found."
    
    lines = ["Available saves:"]
    for save_file in sorted(save_files):
        save_name = save_file.stem
        try:
            with open(save_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            save_time = data.get("save_time", "unknown")[:19]
            lines.append(f"  {save_name} (saved: {save_time})")
        except:
            lines.append(f"  {save_name} (corrupted)")
    return "\n".join(lines)

# ---------- Context Menu System ----------
def generate_context_menu(w: World) -> list[str]:
    """Generate context-sensitive menu options based on current game state"""
    options = []
    loc = w.locations[w.player.location]
    
    # Combat has priority
    if w.flags.get("in_combat"):
        options.extend([
            colorize_combat("Attack"),
            colorize_combat("Defend"), 
            colorize_combat("Flee")
        ])
        return options
    
    # Always available options
    options.extend([
        colorize_location("Look around"),
        colorize_command("Check inventory"),
        colorize_quest("View quests")
    ])
    
    # Movement options
    if loc.exits:
        for exit in loc.exits[:3]:  # Limit to first 3 exits to keep menu manageable
            exit_name = exit.replace("_", " ").title()
            options.append(colorize_location(f"Go to {exit_name}"))
    
    # NPCs
    if loc.npcs:
        for npc_key in loc.npcs:
            npc_name = w.npcs[npc_key].name
            options.append(colorize_npc(f"Talk to {npc_name}"))
    
    # Items to take
    if loc.items:
        for item in loc.items[:2]:  # Limit to first 2 items
            item_name = item.replace("_", " ").title()
            options.append(colorize_item(f"Take {item_name}"))
    
    # Special location-based options
    if loc.key == "blacksmith_shop":
        options.append(colorize_command("Browse shop"))
    
    if loc.key == "healer_tent":
        options.append(colorize_command("Browse shop"))
    
    if w.player.hp < w.player.max_hp and "healer" in loc.npcs:
        options.append(colorize_success("Get healing"))
    
    # Map and achievements (only show if player has explored areas)
    if w.player.explored_areas:
        options.append(colorize_command("View map"))
    options.append(colorize_command("View achievements"))
    options.append(colorize_command("View relationships"))
    
    # Save option
    options.append(colorize_command("Save game"))
    
    return options

def display_context_menu(w: World) -> str:
    """Display numbered context menu"""
    options = generate_context_menu(w)
    lines = [colorize_command("Quick Actions:")]
    
    for i, option in enumerate(options, 1):
        lines.append(f"  {colorize_command(str(i))}. {option}")
    
    lines.append(colorize_command("Or type any command directly..."))
    return "\n".join(lines)

def parse_menu_selection(w: World, selection: str) -> str:
    """Convert menu number selection to actual command"""
    try:
        num = int(selection.strip())
        options = generate_context_menu(w)
        
        if 1 <= num <= len(options):
            option = options[num - 1]
            # Extract the action from the colored text
            # This is a bit hacky but works for our menu structure
            if "Look around" in option:
                return "look"
            elif "Check inventory" in option:
                return "inventory"
            elif "View quests" in option:
                return "quests"
            elif "Go to" in option:
                # Extract location name
                location = option.split("Go to ")[-1].replace("\x1b[0m", "").lower().replace(" ", "_")
                # Remove any remaining ANSI codes
                import re
                location = re.sub(r'\x1b\[[0-9;]*m', '', location)
                return f"go {location}"
            elif "Talk to" in option:
                # Extract NPC display name and map to key
                display_name = option.split("Talk to ")[-1].replace("\x1b[0m", "")
                # Remove ANSI codes 
                import re
                display_name = re.sub(r'\x1b\[[0-9;]*m', '', display_name).strip()
                
                # Map display names to NPC keys
                name_to_key = {
                    "Rogan the Blacksmith": "blacksmith",
                    "Elder Theron": "elder", 
                    "Mira the Healer": "healer",
                    "Kael the Wanderer": "wanderer",
                    "Old Gareth the Miner": "miner"
                }
                npc_key = name_to_key.get(display_name, display_name.lower().split()[0])
                return f"talk to {npc_key}"
            elif "Take" in option:
                item_name = option.split("Take ")[-1].replace("\x1b[0m", "").lower().replace(" ", "_")
                import re
                item_name = re.sub(r'\x1b\[[0-9;]*m', '', item_name)
                return f"take {item_name}"
            elif "Browse shop" in option:
                return "shop"
            elif "Get healing" in option:
                return "heal"
            elif "View map" in option:
                return "map"
            elif "View achievements" in option:
                return "achievements"
            elif "View relationships" in option:
                return "relationships"
            elif "Save game" in option:
                return "save"
            elif "Attack" in option:
                return "attack"
            elif "Defend" in option:
                return "defend"  
            elif "Flee" in option:
                return "flee"
        
        return f"Invalid selection: {num}"
    except ValueError:
        return None  # Not a number, treat as regular command

# ---------- Shop ----------
def show_shop(w: World) -> str:
    if w.flags.get("in_combat"): return "Busy fighting!"
    loc = w.locations[w.player.location]
    
    # Find which shop owner is present
    shop_owner = None
    for npc in loc.npcs:
        if npc in SHOP:
            shop_owner = npc
            break
    
    if not shop_owner:
        return "There's no shop here."
    
    stock = SHOP.get(shop_owner, {})
    if not stock: return "The shop is closed."
    
    # Get shop owner's name for display
    owner_name = w.npcs[shop_owner].name if shop_owner in w.npcs else shop_owner.title()
    
    lines = [colorize_command(f"{owner_name}'s Shop")]
    lines.append(f"{colorize_item('For sale:')}")
    for item, price in stock.items():
        item_display = item.replace("_", " ").title()
        lines.append(f"  {colorize_item(item_display)} — {colorize_warning(str(price) + ' gold')}")
    return "\n".join(lines)

def buy_item(w: World, npc_key: str, item: str) -> str:
    if w.flags.get("in_combat"): return "Finish the fight first!"
    loc = w.locations[w.player.location]
    if npc_key not in loc.npcs:
        return f"There's no one named '{npc_key}' here."
    
    stock = SHOP.get(npc_key, {})
    if item not in stock:
        return f"'{item}' isn't for sale."
    price = stock[item]
    if w.player.gold < price:
        return f"You don't have enough gold (need {price})."
    
    w.player.gold -= price
    w.player.inventory.append(item)
    w.npcs[npc_key].memory.append(f"Sold {item} to player for {price} gold at {w.player.location}")
    return f"You buy the {item} for {price} gold."

def get_healing(w: World) -> str:
    """Direct healing transaction without dialogue"""
    if w.flags.get("in_combat"):
        return "You can't get healing while in combat!"
    
    if w.player.location != "healer_tent":
        return "You need to be at the healer's tent to get healing."
    
    if "healer" not in w.locations[w.player.location].npcs:
        return "The healer isn't here right now."
    
    if w.player.hp >= w.player.max_hp:
        return colorize_success("You're already at full health!")
    
    healer = w.npcs["healer"]
    
    # Check if eligible for free healing
    if "magical_amulet" in w.player.inventory or w.player.quests.get("heal_elder") == "completed":
        # Free healing for saving the Elder
        w.player.hp = w.player.max_hp
        healer.memory.append("Healed the player for free as thanks for saving Elder Theron.")
        update_relationship(healer, 3, "grateful for saving the Elder")
        return (colorize_success("'You saved Elder Theron! This healing is my gift to you.'") + "\n" +
                colorize_item("Mira's magic flows through you, restoring your health!") + "\n" +
                colorize_success(f"(Fully healed - FREE for saving the Elder! HP: {w.player.hp}/{w.player.max_hp})"))
    
    # Paid healing
    if w.player.gold < 5:
        return colorize_warning("You need 5 gold for healing. Come back when you have enough.")
    
    # Confirm healing cost
    game_print(colorize_command(f"Healing costs 5 gold. You have {w.player.gold} gold."))
    game_print(colorize_quest(f"Restore HP from {w.player.hp} to {w.player.max_hp}?"))
    try:
        confirm = game_input(colorize_command("Confirm? (y/n): ")).strip().lower()
        if confirm in ['y', 'yes']:
            w.player.gold -= 5
            w.player.hp = w.player.max_hp
            healer.memory.append("Healed the player for 5 gold.")
            return (colorize_success("'Let me tend to those wounds.'") + "\n" +
                    colorize_item("Mira's magic flows through you, restoring your health!") + "\n" +
                    colorize_success(f"(Fully healed for 5 gold. HP: {w.player.hp}/{w.player.max_hp})"))
        else:
            return colorize_warning("Healing cancelled.")
    except (KeyboardInterrupt, EOFError):
        return colorize_warning("Healing cancelled.")

# ---------- Combat ----------
def player_attack_damage(w: World) -> int:
    stats = get_player_stats(w)
    base_damage = stats["attack"]
    # Add some randomness (±25% of base damage)
    variance = max(1, base_damage // 4)
    return random.randint(base_damage - variance, base_damage + variance)

def monster_attack_damage(mon: Monster) -> int:
    return random.randint(mon.attack_min, mon.attack_max)

def do_attack(w: World) -> str:
    if not w.flags.get("in_combat"): return "There's nothing to attack."
    mon = w.monster
    dmg = player_attack_damage(w)
    mon.hp -= dmg
    attack_text = f"You strike the {colorize_combat(mon.name)} for {colorize_combat(str(dmg))} damage. (Foe HP {max(mon.hp,0)})"
    lines = [attack_text]
    if mon.hp <= 0:
        w.flags["in_combat"] = False
        w.monster = None
        victory_text = colorize_success(f"The {mon.name} collapses. You are victorious!")
        lines.append(victory_text)
        
        # Play victory music
        music_manager.play_victory_music()
        
        # Gold drops from monsters
        gold_reward = 0
        if mon.key == "cave_beast":
            gold_reward = 12
        elif mon.key == "ancient_guardian":
            gold_reward = 15
        elif mon.key == "tower_guardian":
            gold_reward = 25
        elif mon.key == "mine_rat":
            gold_reward = 3
        elif mon.key == "forest_wolf":
            gold_reward = 4
        elif mon.key == "cave_spider":
            gold_reward = 3
        elif mon.key == "mine_bat":
            gold_reward = 2
        elif mon.key == "stone_imp":
            gold_reward = 5
        
        if gold_reward > 0:
            w.player.gold += gold_reward
            lines.append(colorize_item(f"You find {gold_reward} gold on the {mon.name}!"))
        
        # Special victory logic for Ancient Guardian
        if mon.key == "ancient_guardian":
            w.flags["guardian_defeated"] = True
            # Immediately add the ancient scroll to the current location
            current_location = w.locations[w.player.location]
            if "ancient_scroll" not in current_location.items:
                current_location.items.append("ancient_scroll")
            lines.append(colorize_quest("The path to the ancient scroll is now clear!"))
            lines.append(colorize_item("You see an ancient scroll among the ruins!"))
        
        # Special victory logic for final boss
        elif mon.key == "tower_guardian":
            w.flags["final_boss_defeated"] = True
            w.flags["game_completed"] = True
            w.player.quests["final_treasure"] = "completed"
            lines.append(colorize_success("🏆 The Tower Guardian falls! You have completed your hero's journey! 🏆"))
            lines.append(colorize_quest("You claim the ancient treasure vault filled with gold and magical artifacts!"))
            auto_save(w, "quest_final_treasure")
        
        # Check warrior achievement for first combat win
        if "warrior" not in w.player.achievements:
            w.player.achievements.append("warrior")
            lines.append(show_achievement_notification("warrior"))
        
        return "\n".join(lines)
    # monster turn
    raw_damage = monster_attack_damage(mon)
    stats = get_player_stats(w)
    mdmg = max(1, raw_damage - stats["defense"])  # defense reduces damage, minimum 1
    w.player.hp -= mdmg
    damage_text = f"The {colorize_combat(mon.name)} hits you for {colorize_combat(str(mdmg))}. (Your HP {max(w.player.hp,0)})"
    lines.append(damage_text)
    if w.player.hp <= 0:
        game_over_text = colorize_error("You fall to the ground. Darkness closes in.")
        lines.append(game_over_text)
        w.flags["in_combat"] = False
        w.flags["game_over"] = True
        
        # Play defeat music
        music_manager.play_defeat_music()
    return "\n".join(lines)

def do_defend(w: World) -> str:
    if not w.flags.get("in_combat"): return "You're not in combat."
    mon = w.monster
    stats = get_player_stats(w)
    defense_bonus = stats["defense"] + 2  # defending gives +2 defense bonus
    mdmg = max(0, monster_attack_damage(mon) - defense_bonus)
    w.player.hp -= mdmg
    out = f"You brace yourself and reduce the blow. You take {mdmg}. (Your HP {max(w.player.hp,0)})"
    if w.player.hp <= 0:
        out += "\nYou collapse."
        w.flags["in_combat"] = False
        w.flags["game_over"] = True
    return out

def do_flee(w: World) -> str:
    if not w.flags.get("in_combat"): return "You're not in combat."
    # 60% success to flee to forest_path
    if random.random() < 0.6:
        w.flags["in_combat"] = False
        current_location = w.player.location
        
        # Store boss monsters back in their locations so they persist
        if w.monster and w.monster.key in ["cave_beast", "ancient_guardian", "tower_guardian"]:
            # Store the monster state in flags for boss monsters
            w.flags[f"{current_location}_boss_hp"] = w.monster.hp
            w.flags[f"{current_location}_boss_key"] = w.monster.key
        
        # Clear current monster (random encounters can be lost)
        w.monster = None
        w.player.location = "forest_path"
        
        # Update dashboard and actions panel if they're open
        if TKINTER_AVAILABLE:
            game_dashboard.update_all_tabs(w)
            if game_window and game_window.window:
                game_window.update_actions_panel(w)
        
        return "You sprint for the exit and escape to the forest path!\n" + describe_location(w)
    # fail: take a hit
    mon = w.monster
    raw_damage = monster_attack_damage(mon)
    stats = get_player_stats(w)
    mdmg = max(1, raw_damage - stats["defense"])  # apply defense
    w.player.hp -= mdmg
    out = f"You try to flee but stumble! The {mon.name} hits you for {mdmg}. (Your HP {max(w.player.hp,0)})"
    if w.player.hp <= 0:
        out += "\nYou collapse."
        w.flags["in_combat"] = False
        w.flags["game_over"] = True
    return out

# ---------- Claude NPC ----------
def npc_reply_claude(npc: NPC, player_text: str, w: World) -> str:
    if w.flags.get("in_combat"):
        return f"{npc.name} shouts over the clash, 'Focus on the fight!'"
    api_key = load_anthropic_key()
    if not api_key:
        # Silent fallback if no key found
        return f"{npc.name} shrugs. '{player_text.strip().capitalize()}… right. Keep your wits.'"
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    loc = w.locations[w.player.location]
    recent = " | ".join(npc.memory[-3:]) if npc.memory else "None"
    system = ("You are an NPC in a text adventure. Stay in character. "
              "Reply in ≤60 words. Do NOT change game state, give items, or move the player.")
    persona = (f"Character: {npc.name}\nPersonality: {npc.personality}\n"
               f"Location: {loc.key} — {loc.description}\nRecent memories: {recent}")
    try:
        resp = client.messages.create(
            model=os.getenv("CLAUDE_MODEL","claude-3-haiku-20240307"),
            system=system,
            max_tokens=120,
            temperature=0.6,
            messages=[
                {"role":"user","content":persona},
                {"role":"user","content":f"Player says: {player_text}"},
            ],
        )
        parts = [b.text for b in resp.content if hasattr(b,"text")]
        text = " ".join(parts).strip() if parts else ""
        return text or f"{npc.name} nods. 'Fair enough.'"
    except Exception:
        return f"{npc.name} frowns. 'Can't talk right now.'"

# ---------- Parser ----------
    npc = w.npcs[npc_key]
    
    # Track conversation and relationship
    npc.memory.append(f"Player said: {text.strip()} at {w.player.location}")
    relationship_messages = []
    
    # Basic relationship gain for talking (+1 point)
    relationship_messages.extend(update_relationship(npc, 1, "friendly conversation"))
    
    # Track conversation topics
    words = text.lower().split()
    for word in words:
        if len(word) > 3:  # Only track meaningful words
            track_conversation_topic(npc, word)
    
    # CHECK QUEST INTERACTIONS FIRST - before AI response
    # Quest interactions with wanderer
    if npc_key == "wanderer":
        # Player brings back the trinket
        if "ancient_trinket" in w.player.inventory and any(k in text.lower() for k in ("trinket", "medallion", "found", "artifact")):
            w.player.inventory.remove("ancient_trinket")
            w.player.inventory.append("elder_sword")
            w.player.quests["lost_trinket"] = "completed"
            npc.memory.append("Player returned the ancient trinket.")
            
            # Major relationship boost and happiness
            quest_messages = update_relationship(npc, 25, "returning precious family heirloom")
            set_emotional_state(npc, "happy", "overjoyed to have family trinket back")
            
            # Hidden achievement
            if "trinket_returner" not in w.player.achievements:
                w.player.achievements.append("trinket_returner")
            
            auto_save(w, "quest_lost_trinket")
            result = "Kael's eyes fill with tears as he takes the trinket. 'You found it! My family's most precious heirloom!' He reaches into his pack and draws out a magnificent sword. 'This Elder Sword has been in my family for centuries. It's yours now - you've earned it a thousand times over.' \n(Quest completed: Lost Trinket) \n(Received: Elder Sword - A legendary weapon!)"
            return result + "".join(quest_messages)
    
    # Get enhanced NPC response with context
    out = npc_reply_claude(npc, text, w)
    
    # Add relationship and emotional context
    relationship_context = get_relationship_modifier(npc)
    emotional_context = get_emotional_context(npc)
    emotional_indicator = set_emotional_state(npc, npc.emotional_state)  # Keep current or update
    
    # Enhance the output with context
    if relationship_context or emotional_context:
        out += relationship_context + emotional_context
    
    # Add relationship level up messages
    if relationship_messages:
        out += "".join(relationship_messages)
    
    # Quest interactions with blacksmith
    if npc_key == "blacksmith":
        # Give iron ore to get broad sword
        if "iron_ore" in w.player.inventory and any(k in text.lower() for k in ("ore", "iron", "forge", "sword", "weapon", "craft", "make")):
            w.player.inventory.remove("iron_ore")
            w.player.inventory.append("broad_sword")
            w.player.quests["prove_worth"] = "completed"
            npc.memory.append("Forged broad sword from iron ore for player.")
            
            # Major relationship boost and excitement
            quest_messages = update_relationship(npc, 15, "completing prove worth quest")
            set_emotional_state(npc, "excited", "impressed with player's dedication")
            
            auto_save(w, "quest_prove_worth")
            result = "The blacksmith's eyes light up as he examines the ore. 'Fine quality iron! Let me forge you a proper weapon.' He works the metal with expert skill, creating a gleaming broad sword. \n(Quest completed: Prove Your Worth) \n(Received: Broad Sword - A superior weapon!)"
            return result + "".join(quest_messages)
        # Start first quest
        elif w.player.quests.get("prove_worth") == "not_started" and any(k in text.lower() for k in ("work", "help", "sword", "weapon")):
            w.player.quests["prove_worth"] = "started"
            npc.memory.append("Asked player to prove their worth by bringing iron ore.")
            return out + "\n(New quest started: Prove Your Worth - Get iron ore from the mine)"
        # Start cave quest after buying sword
        elif "rusty_sword" in w.player.inventory and w.player.quests.get("clear_cave") == "not_started" and any(k in text.lower() for k in ("gem","cave","danger")):
            w.player.quests["clear_cave"] = "started"
            npc.memory.append("Mentioned rumors of a gem in the cave.")
            return out + "\n(New quest started: Clear the Cave - Find the shimmering gem)"
        # Forge key quest
        elif "ancient_scroll" in w.player.inventory and w.player.quests.get("forge_key") == "not_started" and any(k in text.lower() for k in ("scroll", "runes", "forge", "key")):
            w.player.inventory.remove("ancient_scroll")
            w.player.inventory.append("master_key") 
            w.player.quests["forge_key"] = "completed"
            w.player.quests["final_treasure"] = "started"
            npc.memory.append("Forged master key from ancient scroll for player.")
            auto_save(w, "quest_forge_key")
            return "The blacksmith studies the ancient runes carefully. 'Aye, I know these symbols! This speaks of a master key.' He works for hours at his forge, creating an ornate key that hums with power. \n(Quest completed: Forge the Key) \n(New quest started: Claim the Ancient Treasure - Use the key on the sealed tower!)"
    
    # Quest interactions with healer
    elif npc_key == "healer":
        # Healing service
        if any(k in text.lower() for k in ("heal", "help", "hurt", "wounded", "hp", "health", "potion")):
            if w.player.hp >= w.player.max_hp:
                return out + "\n'You look perfectly healthy to me, dear.'"
            elif w.player.gold >= 5:
                w.player.gold -= 5
                w.player.hp = w.player.max_hp
                npc.memory.append("Healed the player for 5 gold.")
                return out + f"\n'Let me tend to those wounds.' Mira's magic flows through you, restoring your health! \n(Fully healed for 5 gold. HP: {w.player.hp}/{w.player.max_hp})"
            else:
                return out + "\n'I'd love to help, but healing costs 5 gold. Come back when you have enough.'"
    
    # Quest interactions with elder
    elif npc_key == "elder":
        # Heal elder quest
        if "glimmering_gem" in w.player.inventory and w.player.quests.get("heal_elder") == "not_started":
            w.player.quests["heal_elder"] = "started"
            npc.memory.append("Player has the gem that could break the curse.")
            return out + "\n(New quest started: Heal the Elder - The gem might break his curse)"
        # Give gem to heal elder
        elif w.player.quests.get("heal_elder") == "started" and "glimmering_gem" in w.player.inventory and any(k in text.lower() for k in ("heal", "gem", "curse", "help")):
            w.player.inventory.remove("glimmering_gem")
            w.player.inventory.append("magical_amulet")
            w.player.max_hp += 5
            w.player.hp += 5  # also heal current HP
            w.player.quests["heal_elder"] = "completed"
            w.player.quests["retrieve_scroll"] = "started"
            npc.memory.append("Healed by the gem, gave magical amulet to player.")
            
            # Major relationship boost and emotional transformation
            quest_messages = update_relationship(npc, 20, "breaking the curse and saving his life")
            set_emotional_state(npc, "happy", "curse broken, feeling grateful")
            
            auto_save(w, "quest_heal_elder")
            result = "Elder Theron's color returns as the gem's power breaks his curse! 'Take this amulet, brave one. Now seek the ancient scroll in the deep ruins beyond the cave.' \n(Quest completed: Heal the Elder) \n(New quest started: Retrieve the Scroll) \n(+5 Max HP from magical amulet!)"
            return result + "".join(quest_messages)
    
    # Quest interactions with wanderer
    elif npc_key == "wanderer":
        # Wanderer mentions lost trinket
        if any(k in text.lower() for k in ("search", "looking", "lost", "find", "trinket", "artifact")):
            w.player.quests["lost_trinket"] = w.player.quests.get("lost_trinket", "started")
            npc.memory.append("Told player about the ancient trinket.")
            return out + "\n'Ah, you understand my plight! I've lost my family's ancient trinket - a small medallion passed down for generations. I fear it may be hidden somewhere in the caves beyond the forest. If you could find it... I would reward you with something truly precious.'"
        
        # Player brings back the trinket
        elif "ancient_trinket" in w.player.inventory and any(k in text.lower() for k in ("trinket", "medallion", "found", "artifact")):
            w.player.inventory.remove("ancient_trinket")
            w.player.inventory.append("elder_sword")
            w.player.quests["lost_trinket"] = "completed"
            npc.memory.append("Player returned the ancient trinket.")
            
            # Major relationship boost and happiness
            quest_messages = update_relationship(npc, 25, "returning precious family heirloom")
            set_emotional_state(npc, "happy", "overjoyed to have family trinket back")
            
            auto_save(w, "quest_lost_trinket")
            result = "Kael's eyes fill with tears as he takes the trinket. 'You found it! My family's most precious heirloom!' He reaches into his pack and draws out a magnificent sword. 'This Elder Sword has been in my family for centuries. It's yours now - you've earned it a thousand times over.' \n(Quest completed: Lost Trinket) \n(Received: Elder Sword - A legendary weapon!)"
            return result + "".join(quest_messages)
    
    # Quest interactions with miner 
    elif npc_key == "miner":
        # Miner gives hint about secret chamber
        if any(k in text.lower() for k in ("cave", "hidden", "secret", "chamber", "passage", "room")):
            npc.memory.append("Told player about the secret chamber in hidden cave.")
            quest_messages = update_relationship(npc, 5, "sharing valuable cave knowledge")
            return out + "\n'Aye, I worked them caves for forty years, I did. There's more to that hidden cave than meets the eye - behind some loose rocks on the eastern wall, there's a secret chamber. Most folk don't know about it, but I found it years ago. Might be somethin' valuable in there still.'" + "".join(quest_messages)
    
    return out

# ---------- Parser ----------
HELP = (
"Commands:\n"
"  look / l\n"
"  go <place>\n"
"  talk to <npc> <text>\n"
"  ask <npc> about <topic>\n"
"  shop / buy <item>\n"
"  take <item> / drop <item>\n"
"  inventory / i (enhanced with categories)\n"
"  stats (show combat stats)\n"
"  equip <item> / unequip <slot>\n"
"  use <item> (consumables)\n"
"  heal (get healing at healer's tent)\n"
"  quests\n"
"  map (show explored areas)\n"
"  worldmap/dashboard (update integrated dashboard tabs)\n"
"  achievements (show progress)\n"
"  relationships (show NPC status)\n"
"  save [name] / load [name]\n"
"  saves (list save files)\n"
"  music (show music status)\n"
"  music on/off (toggle music)\n"
"  music restart (restart music system)\n"
"  volume <0.0-1.0> (set volume)\n"
"  exit (return to previous location)\n"
"  quit\n"
"While in combat: attack, defend, flee"
)

def parse_and_exec(w: World, raw: str) -> str:
    s = raw.strip()
    if not s: return "Say or do something."
    low = s.lower()

    # combat-only commands
    if w.flags.get("in_combat"):
        if low == "attack": return do_attack(w)
        if low == "defend": return do_defend(w)
        if low == "flee":   return do_flee(w)
        if low in ("look","l"): return describe_location(w)
        if low in ("inventory","inv","i","stats"): return stats(w)
        return "You're in combat! Try: attack, defend, or flee."

    # movement with special cases
    if low.startswith(("go ","move ","walk ")):
        target = low.split(maxsplit=1)[1].replace(" ","_")
        
        # Special case: hidden door in hidden cave
        if w.player.location == "hidden_cave" and any(keyword in target.lower() for keyword in ["hidden_door", "secret_door", "door", "secret_chamber", "chamber"]):
            # Update location history
            w.player.previous_location = w.player.location
            w.player.location = "secret_chamber"
            
            # Track explored areas
            if "secret_chamber" not in w.player.explored_areas:
                w.player.explored_areas.append("secret_chamber")
            
            # Check for new achievements
            new_achievements = check_achievements(w)
            achievement_notifications = ""
            for achievement in new_achievements:
                achievement_notifications += show_achievement_notification(achievement)
            
            result = describe_location(w)
            if achievement_notifications:
                result += achievement_notifications
            
            # Update dashboard and actions panel if they're open
            if TKINTER_AVAILABLE:
                game_dashboard.update_all_tabs(w)
                if game_window and game_window.window:
                    game_window.update_actions_panel(w)
            
            return result + "\n\nYou squeeze through a gap behind the loose rocks and discover a hidden chamber!"
        
        return move_player(w, target)

    # look
    if low in ("look","l"): return describe_location(w)

    # inventory / stats / quests
    if low in ("inventory","inv","i"): return inventory(w)
    if low == "stats": return stats(w)
    if low in ("quests","quest","q"): return quests(w)

    # take / drop
    if low.startswith("take "): return take_item(w, s.split(" ",1)[1].strip().replace(" ","_"))
    if low.startswith("drop "): return drop_item(w, s.split(" ",1)[1].strip().replace(" ","_"))

    # shop / buy
    if low == "shop": return show_shop(w)
    if low.startswith("buy "):
        item = s.split(" ",1)[1].strip().replace(" ","_")
        
        # Auto-detect shop owner
        loc = w.locations[w.player.location]
        shop_owner = None
        for npc in loc.npcs:
            if npc in SHOP:
                shop_owner = npc
                break
        
        if not shop_owner:
            return "There's no shop here."
            
        return buy_item(w, shop_owner, item)
    
    # equipment management
    if low.startswith("equip "):
        item = s.split(" ",1)[1].strip().replace(" ","_")
        return equip_item(w, item)
    
    if low.startswith("unequip "):
        slot = s.split(" ",1)[1].strip()
        return unequip_item(w, slot)
    
    if low.startswith("use "):
        item = s.split(" ",1)[1].strip().replace(" ","_")
        return use_item(w, item)

    # healing
    if low in ("heal", "healing", "get healing"):
        return get_healing(w)

    # talk
    if low.startswith(("talk to ","talk ")):
        parts = low.split()
        if len(parts) >= 2 and parts[1] == "to":
            if len(parts) < 3:
                return "Talk to whom?"
            npc_key = parts[2]
            # Always enter conversation mode - no more direct messages
            return conversation_mode(w, npc_key)
        else:
            if len(parts) < 2:
                return "Talk to whom?"
            npc_key = parts[1]
            # Always enter conversation mode - no more direct messages
            return conversation_mode(w, npc_key)

    # ask
    if low.startswith("ask "):
        parts = low.split()
        if len(parts)>=4 and parts[2]=="about":
            npc_key = parts[1]
            topic = s.split("about",1)[1].strip()
            return talk_to(w, npc_key, f"Tell me about {topic}.")
        return "Try: ask <npc> about <topic>."

    # save/load
    if low.startswith("save"):
        parts = s.split()
        save_name = parts[1] if len(parts) > 1 else "quicksave"
        return save_game(w, save_name)
    
    if low.startswith("load"):
        parts = s.split()
        save_name = parts[1] if len(parts) > 1 else "quicksave"
        new_world, message = load_game(save_name)
        if new_world:
            return ("__LOAD__", new_world, message)
        else:
            return message
    
    # music commands
    if low in ("music", "music status"):
        return music_manager.get_status()
    
    if low in ("music off", "music disable", "mute"):
        music_manager.enabled = False
        music_manager.stop_current_track()
        return colorize_success("🔇 Music disabled")
    
    if low in ("music on", "music enable", "unmute"):
        music_manager.enabled = True
        # Resume location music
        music_manager.play_location_music(w.player.location)
        return colorize_success("🎵 Music enabled")
    
    if low.startswith("volume "):
        try:
            volume = float(s.split()[1])
            music_manager.set_volume(volume)
            return f"🔊 Volume set to {int(volume * 100)}%"
        except (ValueError, IndexError):
            return "Usage: volume <0.0-1.0>"
    
    if low in ("music restart", "restart music", "music reset", "reset music"):
        return music_manager.restart_music(w)
    
    if low in ("saves", "list"):
        return list_saves()

    # exit (go back to previous location)
    if low == "exit":
        if not w.player.previous_location:
            return "You haven't been anywhere yet to exit back to."
        if w.flags.get("in_combat"):
            return "You can't exit while in combat! Try: attack, defend, or flee."
        return move_player(w, w.player.previous_location)

    # map
    if low in ["map", "m"]:
        return get_mini_map(w)
    
    # world map - dashboard is integrated in unified interface
    if low in ["worldmap", "world", "fullmap", "dashboard"]:
        if not TKINTER_AVAILABLE or not game_window or not game_window.window:
            return colorize_warning("⚠️ Dashboard is integrated in the unified interface. Use 'map' for text view.")
        
        # Dashboard is always visible in unified interface, just update it
        game_window.update_all_dashboard_tabs(w)
        return colorize_success("🎮 Dashboard updated! Check the tabs on the right side of the interface.")
    
    # dashboard commands no longer needed in unified interface
    if low in ["hidemap", "closemap", "hidedashboard", "closedashboard"]:
        if TKINTER_AVAILABLE and game_window and game_window.window:
            return colorize_success("💡 Dashboard is integrated in the unified interface and always visible.")
        else:
            return colorize_warning("⚠️ Dashboard is integrated in the unified interface.")
    
    # achievements  
    if low in ["achievements", "ach"]:
        return show_achievements_list(w)
    
    # relationships
    if low in ["relationships", "relationship", "rel"]:
        return show_relationships(w)

    # quit
    if low == "quit": return "__QUIT__"

    # name-first talk
    first = low.split()[0]
    if first in w.npcs and first in w.locations[w.player.location].npcs:
        return talk_to(w, first, s[len(first):].strip())

    return "I don't understand. Type 'help' for commands."

# ---------- REPL ----------
def repl():
    global game_window
    w = build_world()
    
    # Initialize dual window interface if tkinter is available
    use_tkinter_interface = False
    if TKINTER_AVAILABLE:
        try:
            # Initialize game window
            game_window = GameWindow()
            if game_window.create_window():
                use_tkinter_interface = True
                
                # Print initial game text to game window
                game_window.print_to_game("=" * 60)
                game_window.print_to_game("WELCOME TO THE VILLAGE OF THERON")
                game_window.print_to_game("=" * 60)
                game_window.print_to_game("You are a wandering adventurer who has arrived in this small village.")
                game_window.print_to_game("The locals speak of ancient treasures and growing dangers.")
                game_window.print_to_game("Elder Theron lies cursed and weak, while the blacksmith seeks worthy")
                game_window.print_to_game("heroes. An ominous sealed tower looms over the village square.")
                game_window.print_to_game("")
                game_window.print_to_game("Your journey begins now. Seek work, prove yourself, and uncover")
                game_window.print_to_game("the mysteries that await. Talk to the villagers to learn more.")
                game_window.print_to_game("")
                game_window.print_to_game("Type 'help' for commands, 'quests' to track progress, or 'quit' to exit.")
                game_window.print_to_game("=" * 60)
                game_window.print_to_game("")
                game_window.print_to_game(describe_location(w))
                
                # Initialize actions panel and dashboard
                game_window.update_actions_panel(w)
                game_window.update_all_dashboard_tabs(w)
                
            else:
                raise Exception("Failed to create game window")
        except Exception as e:
            print(f"[info] Tkinter interface failed: {e}")
            print("[info] Falling back to terminal interface.")
            use_tkinter_interface = False
            game_window = None
    
    # Fallback to terminal interface if tkinter failed
    if not use_tkinter_interface:
        # one-time note if key missing (we'll fall back to stub NPC lines)
        if not load_anthropic_key():
            print("[warn] No Anthropic API key found (using offline stub replies).")
            print("       Set ANTHROPIC_API_KEY or create ./secrets/anthropic.key\n")

        print("=" * 60)
        print("WELCOME TO THE VILLAGE OF THERON")
        print("=" * 60)
        print("You are a wandering adventurer who has arrived in this small village.")
        print("The locals speak of ancient treasures and growing dangers.")
        print("Elder Theron lies cursed and weak, while the blacksmith seeks worthy")
        print("heroes. An ominous sealed tower looms over the village square.")
        print("\nYour journey begins now. Seek work, prove yourself, and uncover")
        print("the mysteries that await. Talk to the villagers to learn more.")
        print("\nType 'help' for commands, 'quests' to track progress, or 'quit' to exit.")
        print("=" * 60)
        print()
        game_print(describe_location(w))
        
        # Dashboard is not available in terminal fallback mode
        print("[info] Dashboard not available in terminal mode. Use individual commands like 'map', 'inventory', etc.")
    
    while True:
        try:
            # Check for game completion
            if w.flags.get("game_completed", False):
                completion_result = handle_game_completion()
                if completion_result == "__QUIT__":
                    break
                elif completion_result == "__RESTART__":
                    # Restart the game
                    w = build_world()
                    game_print("\n" + "=" * 60)
                    game_print("NEW GAME STARTED")
                    game_print("=" * 60)
                    game_print("You are a wandering adventurer who has arrived in this small village.")
                    game_print("The locals speak of ancient treasures and growing dangers.")
                    game_print("Elder Theron lies cursed and weak, while the blacksmith seeks worthy")
                    game_print("heroes. An ominous sealed tower looms over the village square.")
                    game_print("\nYour journey begins now. Seek work, prove yourself, and uncover")
                    game_print("the mysteries that await. Talk to the villagers to learn more.")
                    game_print("\nType 'help' for commands, 'quests' to track progress, or 'quit' to exit.")
                    game_print("=" * 60)
                    game_print()
                    game_print(describe_location(w))
                    
                    # Update integrated dashboard on restart
                    if TKINTER_AVAILABLE and game_window and game_window.window:
                        game_window.update_all_dashboard_tabs(w)
                    
                    continue
                elif completion_result.startswith("__LOAD__"):
                    # Load specified save
                    save_name = completion_result[8:]  # Remove "__LOAD__" prefix
                    try:
                        loaded_world = load_world(save_name)
                        if loaded_world:
                            w = loaded_world
                            print(f"{colorize_success(f'Game loaded from {save_name}!')}")
                            game_print(describe_location(w))
                            continue
                        else:
                            print(colorize_error(f"Failed to load {save_name}. Starting new game..."))
                            w = build_world()
                            game_print(describe_location(w))
                            continue
                    except Exception as e:
                        print(colorize_error(f"Error loading save: {e}. Starting new game..."))
                        w = build_world()
                        game_print(describe_location(w))
                        continue

            # Check for game over
            if w.flags.get("game_over", False):
                game_over_result = handle_game_over()
                if game_over_result == "__QUIT__":
                    break
                elif game_over_result == "__RESTART__":
                    # Restart the game
                    w = build_world()
                    game_print("\n" + "=" * 60)
                    game_print("NEW GAME STARTED")
                    game_print("=" * 60)
                    game_print("You are a wandering adventurer who has arrived in this small village.")
                    game_print("The locals speak of ancient treasures and growing dangers.")
                    game_print("Elder Theron lies cursed and weak, while the blacksmith seeks worthy")
                    game_print("heroes. An ominous sealed tower looms over the village square.")
                    game_print("\nYour journey begins now. Seek work, prove yourself, and uncover")
                    game_print("the mysteries that await. Talk to the villagers to learn more.")
                    game_print("\nType 'help' for commands, 'quests' to track progress, or 'quit' to exit.")
                    game_print("=" * 60)
                    game_print()
                    game_print(describe_location(w))
                    continue
                elif game_over_result.startswith("__LOAD__"):
                    # Load specified save
                    save_name = game_over_result[8:]  # Remove "__LOAD__" prefix
                    try:
                        loaded_world = load_world(save_name)
                        if loaded_world:
                            w = loaded_world
                            print(f"{colorize_success(f'Game loaded from {save_name}!')}")
                            game_print(describe_location(w))
                            continue
                        else:
                            print(colorize_error(f"Failed to load {save_name}. Starting new game..."))
                            w = build_world()
                            game_print(describe_location(w))
                            continue
                    except Exception as e:
                        print(colorize_error(f"Error loading save: {e}. Starting new game..."))
                        w = build_world()
                        game_print(describe_location(w))
                        continue
            
            # Check if in conversation mode
            if w.flags.get("in_conversation", False):
                # Conversation mode is handled within conversation_mode function
                # Just skip regular command processing
                continue
            
            # Update actions panel if using tkinter interface
            if game_window and game_window.window:
                game_window.update_actions_panel(w)
            
            raw = game_input("> ")
        except EOFError:
            game_print("\nGoodbye.")
            break
        
        if raw.strip().lower() in ("help","h","?"):
            game_print(HELP)
            continue
        
        # Check if input is a menu selection
        menu_command = parse_menu_selection(w, raw)
        if menu_command is not None:
            if menu_command.startswith("Invalid"):
                print(colorize_error(menu_command))
                continue
            raw = menu_command
        
        result = parse_and_exec(w, raw)
        
        # Handle special return values
        if result == "__QUIT__":
            game_print("Goodbye."); break
        elif isinstance(result, tuple) and len(result) == 3 and result[0] == "__LOAD__":
            # Load command successful
            _, w, message = result
            game_print(message)
            game_print(describe_location(w))
        else:
            # Normal command output
            game_print(result)

if __name__ == "__main__":
    repl()
