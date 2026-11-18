# Check Instrument Reminder: Design Doc

Nov 18, 2026 · @Laval Nicolas

## Overview and goals

Check Instrument Reminder is a single Windows executable. Task Scheduler launches it every 30 minutes, and it covers the screen with a "Have you checked the instrument?" dialog until the user clicks Yes or No.

**Goals**

- Show a Yes/No reminder every 30 minutes while the user is logged on.
- Block the desktop until the user answers, so the instrument check can't be skipped unnoticed.
- Ship as one `.exe` with no Python install needed on the target PC.
- After Yes or No, ask for the user's name, then log date, time, name and answer to a CSV in the app's folder as an audit trail of checks.
- Buildable to be published on GitHub

**Non-goals**

- A tamper-proof lock. Task Manager or an admin can always end the process.
- Running at the secure Windows lock screen (Win+L). No app can draw there.

## Requirements

| ID | Requirement | Type |
| --- | --- | --- |
| R1 | Prompt appears every 30 minutes while the user is logged on | Functional |
| R2 | Dimmed overlay covers all monitors; dialog centred on the primary monitor | Functional |
| R3 | Only Yes or No dismisses it; Esc and the close button are ignored | Functional |
| R4 | After Yes/No, a second screen asks for a name (Save disabled until one is typed); date, time, name, answer and Windows user logged to instrument\_check\_log.csv beside the .exe | Functional |
| R5 | Title, message, button text and dimming editable without rebuilding | Functional |
| R6 | Never shows two prompts at once, even if the last one is still open | Functional |
| R7 | Single `.exe`, no Python needed on the target PC | Non-functional |
| R8 | No admin rights needed to install or run | Non-functional |
| R9 | No console window; near-zero resources between prompts (not resident) | Non-functional |

## Architecture

The app isn't a resident background service. Windows Task Scheduler is the timer, and the `.exe` runs once per trigger: it shows the prompt, logs the answer and exits. That keeps it to zero memory between checks, and if it crashes, the next run simply starts fresh.

&#91;embedded content: run flow · one scheduled run, start to finish\]

If a prompt is still open when the next 30-minute trigger fires, the new run sees it and exits, so prompts never stack up.

## Component design

Everything lives in one Python 3 file, `reminder.py`, using only the standard library (tkinter, ctypes, csv, json).

| Component | What it does | Key detail |
| --- | --- | --- |
| Single-instance guard | Exits if a prompt is already open | Named Windows mutex `Local\CheckInstrumentReminderMutex` |
| Overlay | Dims and covers every monitor | Borderless, always on top, 85% opacity, sized to the virtual screen via `GetSystemMetrics` |
| Dialog | Screen 1: title, message, Yes (green) and No (red). Screen 2: name field with Back and Save; Enter also saves | Centred on the primary monitor; `grab_set` sends all app input to it |
| Focus keeper | Stops other windows burying the prompt | Re-raises and refocuses the dialog every 500 ms |
| Close blockers | Only Yes/No can dismiss | Alt+F4, Esc and the window-close message are swallowed |
| Logger | Records each answer | Appends `date,time,name,answer,windows_user` to `instrument_check_log.csv beside the .exe (falls back to %LOCALAPPDATA% if that folder isn't writable)` |
| Config loader | Lets you change text without rebuilding | Reads `config.json` beside the `.exe`; a bad or missing file falls back to defaults |

**config.json fields:** `title`, `message` (use `\n` for a line break), `yes_text`, `no_text`, `overlay_opacity` (0 to 1), name\_prompt, save\_text.

## Build and packaging

PyInstaller turns `reminder.py` into one `CheckInstrumentReminder.exe` with Python bundled inside. It must be built on Windows, because PyInstaller can't cross-compile.

**Option A: build locally (Windows PC with Python 3)**

1. Put all the project files in one folder.
2. Double-click `build.bat`. It installs PyInstaller and runs:

```
python -m PyInstaller --onefile --noconsole --name CheckInstrumentReminder reminder.py
```

3. The finished file is `dist\CheckInstrumentReminder.exe`.

**Option B: build in the cloud (no Python needed)**

Push the folder to a GitHub repo. The included `.github/workflows/build.yml` builds on a Windows runner and posts a zip with the `.exe`, the install scripts and `config.json` under the run's Artifacts.

`--noconsole` stops a black console window flashing up. `--onefile` gives a single portable file, which takes a second or two longer to start than a folder build.

## Deployment

1. Copy `CheckInstrumentReminder.exe`, `config.json`, `install_task.bat` and `uninstall_task.bat` into a permanent folder, e.g. `C:\Tools\CheckInstrumentReminder`.
2. Edit `config.json` if you want different wording. The check log is created in this folder, so choose one users can write to (not Program Files).
3. Double-click `install_task.bat`. It registers the scheduled task for the current user, with no admin rights needed:

```
schtasks /Create /TN "CheckInstrumentReminder" /TR "\"<folder>\CheckInstrumentReminder.exe\"" /SC MINUTE /MO 30 /F
```

4. To test straight away, open Task Scheduler, right-click **CheckInstrumentReminder** and choose **Run**.
5. To remove it, run `uninstall_task.bat`.

The task runs only while the user is logged on, which is what puts the prompt on their desktop. The 30-minute repeat counts from the moment the task is created, not from the top of the hour.

## Limitations and security

- **Not a true lock.** The overlay blocks clicks and keys aimed at other windows, but Ctrl+Alt+Del and Task Manager still work, so a determined user can end it. That's by design: an app that couldn't be stopped would be a hazard.
- **Win+L lock screen.** If the PC is locked when the task fires, the prompt waits behind the lock screen and shows on unlock.
- **Laptop asleep.** Scheduled runs missed during sleep are skipped, not queued.
- **Antivirus.** Unsigned PyInstaller `.exe` files are sometimes flagged as false positives. Code-signing or an IT allow-list entry fixes this.
- **Log integrity.** `instrument_check_log.csv` is a plain file the user can edit, and the name is typed in, not verified against the Windows login (the windows\_user column records that separately). For a formal audit trail, write to a shared or read-only location instead (see Future work).

## Testing and future work

**Test checklist (on the target PC)**

- [ ] Running the `.exe` directly shows the overlay on every monitor
- [ ] Esc and clicking outside the dialog do nothing
- [ ] Yes and No each open the name screen; Save closes the prompt and adds a row to `instrument_check_log.csv`
- [ ] Launching a second copy while one is open does nothing
- [ ] Changing `config.json` changes the wording on the next run
- [ ] The scheduled task fires twice over a 60-minute window
- [ ] No console window appears at any point

**Possible next steps**

