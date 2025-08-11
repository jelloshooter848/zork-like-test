#!/usr/bin/env python3
"""
Creates a GUI version of the Zork-Like game using tkinter
This runs the game in its own window with a terminal-like interface
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import sys
from io import StringIO
import subprocess
import os

class GameGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🏰 Village of Theron - Text Adventure")
        self.root.geometry("900x700")
        self.root.configure(bg="#2c3e50")
        
        # Game process
        self.game_process = None
        self.game_running = False
        
        self.setup_ui()
        self.start_game()
    
    def setup_ui(self):
        # Title
        title = tk.Label(
            self.root, 
            text="🏰 VILLAGE OF THERON 🏰", 
            font=("Courier", 16, "bold"),
            fg="#ecf0f1", 
            bg="#2c3e50"
        )
        title.pack(pady=10)
        
        # Game output area
        self.output_area = scrolledtext.ScrolledText(
            self.root,
            font=("Courier", 11),
            bg="#34495e",
            fg="#ecf0f1",
            insertbackground="#ecf0f1",
            wrap=tk.WORD,
            height=30,
            width=100
        )
        self.output_area.pack(padx=20, pady=10, expand=True, fill=tk.BOTH)
        
        # Input frame
        input_frame = tk.Frame(self.root, bg="#2c3e50")
        input_frame.pack(padx=20, pady=10, fill=tk.X)
        
        # Input label
        input_label = tk.Label(
            input_frame,
            text=">",
            font=("Courier", 12, "bold"),
            fg="#e74c3c",
            bg="#2c3e50"
        )
        input_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Input entry
        self.input_entry = tk.Entry(
            input_frame,
            font=("Courier", 11),
            bg="#34495e",
            fg="#ecf0f1",
            insertbackground="#ecf0f1",
            relief=tk.FLAT,
            bd=5
        )
        self.input_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))
        self.input_entry.bind("<Return>", self.send_command)
        self.input_entry.focus()
        
        # Send button
        send_btn = tk.Button(
            input_frame,
            text="Send",
            font=("Courier", 10),
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            command=self.send_command
        )
        send_btn.pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("🎵 Initializing game...")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Courier", 9),
            fg="#95a5a6",
            bg="#2c3e50",
            anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=5)
    
    def start_game(self):
        """Start the game in a subprocess"""
        try:
            # Ensure we're using the virtual environment
            if os.path.exists("venv/bin/python"):
                python_exe = "venv/bin/python"
            elif os.path.exists("venv/Scripts/python.exe"):
                python_exe = "venv/Scripts/python.exe"
            else:
                python_exe = "python3"
            
            self.game_process = subprocess.Popen(
                [python_exe, "generative_zork_like.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.game_running = True
            self.status_var.set("🎮 Game running - Type commands below")
            
            # Start reading output in a separate thread
            threading.Thread(target=self.read_output, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start game: {e}")
    
    def read_output(self):
        """Read game output continuously"""
        while self.game_running and self.game_process:
            try:
                output = self.game_process.stdout.readline()
                if output:
                    self.root.after(0, self.display_output, output)
                elif self.game_process.poll() is not None:
                    break
            except Exception as e:
                break
    
    def display_output(self, text):
        """Display text in the output area"""
        self.output_area.insert(tk.END, text)
        self.output_area.see(tk.END)
    
    def send_command(self, event=None):
        """Send command to the game"""
        command = self.input_entry.get().strip()
        if command and self.game_process:
            try:
                self.game_process.stdin.write(command + "\n")
                self.game_process.stdin.flush()
                
                # Show user input in a different color
                self.output_area.insert(tk.END, f"> {command}\n")
                self.output_area.see(tk.END)
                
                self.input_entry.delete(0, tk.END)
                
                # Update status for special commands
                if command.lower() in ("quit", "exit"):
                    self.status_var.set("🔚 Game ending...")
                elif command.lower().startswith("music"):
                    self.status_var.set("🎵 Music command sent")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send command: {e}")
    
    def on_closing(self):
        """Clean up when closing"""
        if self.game_process:
            self.game_process.terminate()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = GameGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()