"""Native one-folder chooser (separate process: GUI must run on its main thread)."""
from __future__ import annotations
import json
import subprocess
import sys


def choose(title):
    if sys.platform == 'darwin':
        script = 'on run argv\nPOSIX path of (choose folder with prompt (item 1 of argv))\nend run'
        output = subprocess.run(['/usr/bin/osascript', '-e', script, title], capture_output=True, text=True)
        if output.returncode:
            if '(-128)' in output.stderr:
                return None
            raise RuntimeError('The macOS folder picker failed.')
        return output.stdout.removesuffix('\n')
    import tkinter as tk
    from tkinter import filedialog
    gui = tk.Tk()
    try:
        gui.withdraw()
        gui.attributes('-topmost', True)
        return filedialog.askdirectory(parent=gui, title=title, mustexist=True) or None
    finally:
        gui.destroy()


if __name__ == '__main__':
    if sys.argv[1] == '--error':
        import tkinter as tk
        from tkinter import messagebox
        gui = tk.Tk()
        try:
            gui.withdraw()
            messagebox.showerror('Yorevia Web', sys.argv[2], parent=gui)
        finally:
            gui.destroy()
    else:
        print(json.dumps(choose(sys.argv[1]), ensure_ascii=False))
