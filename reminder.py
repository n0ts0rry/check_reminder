"""Check Instrument Reminder.

Launched by Windows Task Scheduler every 30 minutes. Covers every monitor with
a dimmed overlay and shows a Yes/No prompt, then asks for the user's name and
logs the answer to instrument_check_log.csv beside the executable.

Standard library only (tkinter, ctypes, csv, json).
"""

import csv
import ctypes
import getpass
import json
import os
import sys
import tkinter as tk
from datetime import datetime

APP_NAME = "CheckInstrumentReminder"
MUTEX_NAME = "Local\\CheckInstrumentReminderMutex"
LOG_NAME = "instrument_check_log.csv"
CONFIG_NAME = "config.json"
ERROR_ALREADY_EXISTS = 183
REFOCUS_MS = 500

DEFAULTS = {
    "title": "Instrument Check",
    "message": "Have you checked the instrument?",
    "yes_text": "Yes",
    "no_text": "No",
    "overlay_opacity": 0.85,
    "name_prompt": "Please enter your name:",
    "save_text": "Save",
    "no_reminder": "Please check the instrument now, then answer again.",
}


def app_dir():
    """Folder holding the .exe (frozen) or this script (dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# Single-instance guard
# --------------------------------------------------------------------------
def acquire_single_instance():
    """Return a mutex handle, or None if another prompt is already open."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle or kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if handle:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        return None
    return handle


# --------------------------------------------------------------------------
# Config loader
# --------------------------------------------------------------------------
def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(app_dir(), CONFIG_NAME), encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key, default in DEFAULTS.items():
                value = data.get(key)
                if isinstance(default, str) and isinstance(value, str) and value:
                    cfg[key] = value
                elif key == "overlay_opacity" and isinstance(value, (int, float)):
                    cfg[key] = max(0.0, min(1.0, float(value)))
    except (OSError, ValueError):
        pass  # missing or bad file -> defaults
    return cfg


# --------------------------------------------------------------------------
# Logger
# --------------------------------------------------------------------------
def _append_row(path, row):
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["date", "time", "name", "answer", "windows_user"])
        writer.writerow(row)


def log_answer(name, answer):
    now = datetime.now()
    try:
        win_user = getpass.getuser()
    except Exception:
        win_user = os.environ.get("USERNAME", "")
    row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), name, answer, win_user]
    try:
        _append_row(os.path.join(app_dir(), LOG_NAME), row)
    except OSError:
        fallback = os.path.join(os.environ.get("LOCALAPPDATA", app_dir()), APP_NAME)
        try:
            os.makedirs(fallback, exist_ok=True)
            _append_row(os.path.join(fallback, LOG_NAME), row)
        except OSError:
            pass


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
def set_dpi_aware():
    """So GetSystemMetrics and Tk agree on pixel sizes on scaled displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class ReminderApp:
    def __init__(self, cfg):
        self.cfg = cfg
        self.answer = None
        user32 = ctypes.windll.user32

        # Overlay: root window spanning the whole virtual screen.
        self.root = tk.Tk()
        self.root.title(cfg["title"])
        self.root.overrideredirect(True)
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        self.root.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.root.configure(bg="black")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", cfg["overlay_opacity"])
        self._block_close(self.root)
        self.root.bind("<Button>", lambda e: self._raise_dialog())

        # Dialog: centred on the primary monitor.
        self.dlg = tk.Toplevel(self.root)
        self.dlg.title(cfg["title"])
        self.dlg.configure(bg="white")
        self.dlg.resizable(False, False)
        self.dlg.attributes("-topmost", True)
        self.dlg.transient(self.root)
        self._block_close(self.dlg)

        self.frame = None
        self.focus_target = None
        self.show_question()

        self.dlg.update_idletasks()
        w, h = 520, 260
        pw, ph = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        self.dlg.geometry(f"{w}x{h}+{(pw - w) // 2}+{(ph - h) // 2}")
        self.dlg.grab_set()
        self._keep_focus()

    # -- close blockers / focus keeper -------------------------------------
    def _block_close(self, win):
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        for seq in ("<Alt-F4>", "<Escape>"):
            win.bind(seq, lambda e: "break")

    def _raise_dialog(self):
        try:
            self.root.lift()
            self.dlg.lift()
            self.dlg.attributes("-topmost", True)
            # Only reclaim focus if it has left the dialog; never steal it
            # from a widget inside (e.g. the name entry) or typing breaks.
            current = self.dlg.focus_get()
            if current is None or current.winfo_toplevel() is not self.dlg:
                (self.focus_target or self.dlg).focus_force()
        except tk.TclError:
            pass

    def _keep_focus(self):
        self._raise_dialog()
        self.root.after(REFOCUS_MS, self._keep_focus)

    # -- screens -----------------------------------------------------------
    def _new_frame(self):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = tk.Frame(self.dlg, bg="white", padx=24, pady=20)
        self.frame.pack(fill="both", expand=True)
        tk.Label(self.frame, text=self.cfg["title"], bg="white",
                 font=("Segoe UI", 16, "bold")).pack(pady=(0, 10))
        return self.frame

    def show_question(self, nudge=False):
        self.focus_target = None
        f = self._new_frame()
        tk.Label(f, text=self.cfg["message"].replace("\\n", "\n"), bg="white",
                 font=("Segoe UI", 13), wraplength=460, justify="center").pack(pady=(0, 8))
        tk.Label(f, text=self.cfg["no_reminder"] if nudge else "", bg="white", fg="#c62828",
                 font=("Segoe UI", 11, "bold"), wraplength=460).pack(pady=(0, 12))
        row = tk.Frame(f, bg="white")
        row.pack()
        btn = dict(font=("Segoe UI", 12, "bold"), fg="white", width=10, bd=0,
                   relief="flat", cursor="hand2")
        tk.Button(row, text=self.cfg["yes_text"], bg="#2e7d32", activebackground="#1b5e20",
                  command=lambda: self.show_name(self.cfg["yes_text"]), **btn).pack(side="left", padx=12, ipady=6)
        tk.Button(row, text=self.cfg["no_text"], bg="#c62828", activebackground="#8e0000",
                  command=lambda: self.show_question(nudge=True), **btn).pack(side="left", padx=12, ipady=6)

    def show_name(self, answer):
        self.answer = answer
        f = self._new_frame()
        tk.Label(f, text=self.cfg["name_prompt"], bg="white",
                 font=("Segoe UI", 12)).pack(pady=(0, 8))
        self.name_var = tk.StringVar()
        entry = tk.Entry(f, textvariable=self.name_var, font=("Segoe UI", 12), width=30)
        entry.pack(pady=(0, 16), ipady=3)
        row = tk.Frame(f, bg="white")
        row.pack()
        tk.Button(row, text="Back", font=("Segoe UI", 11), width=10,
                  command=self.show_question).pack(side="left", padx=10)
        self.save_btn = tk.Button(row, text=self.cfg["save_text"], font=("Segoe UI", 11, "bold"),
                                  width=10, state="disabled", command=self.save)
        self.save_btn.pack(side="left", padx=10)
        self.name_var.trace_add("write", lambda *_: self.save_btn.config(
            state="normal" if self.name_var.get().strip() else "disabled"))
        entry.bind("<Return>", lambda e: self.save())
        self.focus_target = entry
        entry.focus_force()

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            return
        log_answer(name, self.answer)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if acquire_single_instance() is None:
        return
    set_dpi_aware()
    ReminderApp(load_config()).run()


if __name__ == "__main__":
    main()
