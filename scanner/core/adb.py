"""ADB binary discovery and timeout constants — stdlib only.

Search order for the adb binary (matches the main tool):
  1. ANDROID_HOME / ANDROID_SDK_ROOT environment variables
  2. Standard SDK install locations (Linux, macOS, Windows)
  3. `adb` on PATH (via shutil.which)
  4. Bare 'adb' fallback (fails at call time with a clear error)
"""

import os
import shutil
from pathlib import Path

# ------------------------------------------------------------------
#  Timeout constants (seconds) — every ADB call site pulls from
#  here; change timing in one place only.
# ------------------------------------------------------------------

TIMEOUTS = {
    'adb_version': 5,       # `adb version` availability probe
    'server_start': 10,     # `adb start-server`
    'getprop': 5,           # single property read
    'devices_list': 10,     # `adb devices -l`
    'shell_short': 10,      # pm path, short shell commands
    'shell_medium': 30,     # dumpsys of a single package
    'shell_long': 60,       # general shell commands
    'dumpsys_bulk': 120,    # full `dumpsys package` (hundreds of apps)
    'install': 120,         # APK pull over USB
}


def find_adb_path() -> str:
    """Locate the ADB binary across platforms, no hardcoding."""
    home = Path.home()
    candidates: list = []

    # 1. Environment variables
    sdk_env = (os.environ.get('ANDROID_HOME')
               or os.environ.get('ANDROID_SDK_ROOT'))
    if sdk_env:
        base = Path(sdk_env)
        candidates.extend([
            base / 'platform-tools' / 'adb',
            base / 'platform-tools' / 'adb.exe',
        ])

    # 2. Standard Linux locations
    candidates.extend([
        home / 'Android' / 'Sdk' / 'platform-tools' / 'adb',
        home / '.local' / 'share' / 'Android' / 'Sdk'
             / 'platform-tools' / 'adb',
        home / 'opt' / 'android-sdk' / 'platform-tools' / 'adb',
        Path('/usr/lib/android-sdk/platform-tools/adb'),
        Path('/opt/android-sdk/platform-tools/adb'),
    ])

    # 3. Standard macOS locations
    candidates.extend([
        home / 'Library' / 'Android' / 'sdk' / 'platform-tools' / 'adb',
        Path('/usr/local/share/android-sdk/platform-tools/adb'),
    ])

    # 4. Standard Windows locations
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        win_base = Path(local_appdata)
        candidates.append(
            win_base / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe')
    candidates.append(
        home / 'AppData' / 'Local' / 'Android'
        / 'Sdk' / 'platform-tools' / 'adb.exe')

    # 5. First existing candidate wins
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    # 6. PATH
    which_result = shutil.which('adb')
    if which_result:
        return which_result

    # 7. Fallback — subprocess will raise FileNotFoundError with a
    #    readable message, which the UI turns into a friendly panel.
    return 'adb'


ADB_PATH = find_adb_path()
