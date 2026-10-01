"""Read-only device inspection: apps, permissions, device info.

Everything in this module OBSERVES the device — no command here
modifies app state, permissions, or packages. Read-only by design.

All adb invocations use argv lists (never interpolated strings) so
package/permission names can never break out of the command.
App enumeration uses ONE bulk `dumpsys package` call.
"""

import subprocess
from typing import Dict, List, Set

from .adb import ADB_PATH, TIMEOUTS

# ------------------------------------------------------------------
#  Catalog of privacy-relevant (dangerous) runtime permissions.
# ------------------------------------------------------------------

DANGEROUS_PERMISSIONS = [
    'ACCESS_FINE_LOCATION', 'ACCESS_COARSE_LOCATION',
    'ACCESS_BACKGROUND_LOCATION', 'CAMERA', 'RECORD_AUDIO',
    'READ_CONTACTS', 'WRITE_CONTACTS', 'GET_ACCOUNTS',
    'READ_CALENDAR', 'WRITE_CALENDAR', 'READ_SMS', 'SEND_SMS',
    'RECEIVE_SMS', 'RECEIVE_MMS', 'RECEIVE_WAP_PUSH',
    'READ_CALL_LOG', 'WRITE_CALL_LOG', 'CALL_PHONE',
    'READ_PHONE_STATE', 'ADD_VOICEMAIL', 'USE_SIP',
    'PROCESS_OUTGOING_CALLS', 'BODY_SENSORS',
    'ACTIVITY_RECOGNITION', 'POST_NOTIFICATIONS',
    'READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE',
    'READ_MEDIA_IMAGES', 'READ_MEDIA_VIDEO', 'READ_MEDIA_AUDIO',
    'BLUETOOTH_CONNECT', 'BLUETOOTH_SCAN', 'BLUETOOTH_ADVERTISE',
    'UWB_RANGING', 'ACCESS_NEARBY_DEVICES', 'NEARBY_WIFI_DEVICES',
    'ACCESS_MEDIA_LOCATION', 'BODY_SENSORS_BACKGROUND',
    'READ_MEDIA_VISUAL_USER_SELECTED',
]

# Shared lock-flag vocabulary: how lock reasons are humanized
# in the report (ROM-protected grants).
LOCK_LABELS = {
    'SYSTEM_FIXED': 'system',
    'GRANTED_BY_ROLE': 'role',
}


def lock_reason(flags) -> str:
    """Humanized label for a lock-flags set: '', 'role', 'system + role'."""
    known = sorted((flags or set()) & set(LOCK_LABELS))
    return ' + '.join(LOCK_LABELS[f] for f in known)


class AppInfo:
    """Data holder for one installed application (read-only)."""

    def __init__(self, package_name: str, label: str = '',
                 version_name: str = '', version_code: int = 0,
                 is_system: bool = False):
        self.package_name = package_name
        self.label = label or package_name
        self.version_name = version_name or '?'
        self.version_code = version_code or 0
        self.is_system = is_system
        self.permissions_requested: Set[str] = set()
        self.permissions_granted: Set[str] = set()
        # {leaf: set of lock flags} — why a grant cannot be revoked.
        self.locked_perms: Dict[str, Set[str]] = {}
        # Per-user-0 state, parsed from the 'User 0:' line.
        self.installed_user0 = True
        self.enabled_user0 = True

    @property
    def is_active(self):
        """Runnable for user 0: installed and not disabled."""
        return bool(self.installed_user0 and self.enabled_user0)

    def __repr__(self):
        return f"<AppInfo {self.package_name} v{self.version_name}>"


# ------------------------------------------------------------------
#  Low-level executor
# ------------------------------------------------------------------

def _run_shell_argv(serial: str, cmd_args: List[str],
                    timeout: int = None) -> subprocess.CompletedProcess:
    """Run `adb -s <serial> shell <argv-list>`.

    argv lists throughout: package and permission names can never
    break out of the command.
    """
    if timeout is None:
        timeout = TIMEOUTS['shell_long']
    cmd = [ADB_PATH, '-s', serial, 'shell'] + list(cmd_args)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout)


# ------------------------------------------------------------------
#  Device info (ONE bulk getprop call)
# ------------------------------------------------------------------

def get_device_info(serial: str) -> Dict:
    """Device identifiers for the report header."""
    result = subprocess.run(
        [ADB_PATH, '-s', serial, 'shell', 'getprop'],
        capture_output=True, text=True, timeout=TIMEOUTS['getprop'])

    props: Dict[str, str] = {}
    for line in (result.stdout or '').splitlines():
        if ']: [' in line:
            try:
                key = line.split('[', 1)[1].split(']: ')[0]
                value = line.split(']: [', 1)[1].rsplit(']', 1)[0]
                props[key] = value.strip()
            except IndexError:
                continue

    return {
        'serial': serial,
        'model': props.get('ro.product.model', 'Unknown'),
        'brand': props.get('ro.product.brand', 'Unknown'),
        'product': props.get('ro.product.name', 'Unknown'),
        'android_version':
            props.get('ro.build.version.release', 'Unknown'),
        'sdk_level': props.get('ro.build.version.sdk', 'Unknown'),
    }


def list_devices() -> List[Dict]:
    """Connected devices (USB or network), state 'device' only.

    Uses the bulk-prop path per device so the returned dicts match
    get_device_info()'s shape exactly.
    """
    subprocess.run(
        [ADB_PATH, 'start-server'],
        capture_output=True, text=True, timeout=TIMEOUTS['server_start'])
    result = subprocess.run(
        [ADB_PATH, 'devices'],
        capture_output=True, text=True, timeout=TIMEOUTS['devices_list'])
    if result.returncode != 0:
        return []
    serials = []
    for line in (result.stdout or '').strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            serials.append(parts[0])
    return [get_device_info(s) for s in serials]


# ------------------------------------------------------------------
#  Installed-app enumeration (ONE bulk dumpsys call)
# ------------------------------------------------------------------

def get_installed_apps(serial: str,
                       include_system: bool = True) -> List[AppInfo]:
    """Enumerate installed apps with permissions.

    `dumpsys package` succeeds when a device is reachable; failure
    (no device / unauthorized) raises RuntimeError with a readable
    message for the UI to show.
    """
    result = _run_shell_argv(
        serial, ['dumpsys', 'package'],
        timeout=TIMEOUTS['dumpsys_bulk'])
    if result.returncode != 0 and not result.stdout:
        raise RuntimeError(
            result.stderr.strip() or
            'Impossibile leggere le app dal dispositivo '
            '(dispositivo scollegato o non autorizzato?)')
    return _parse_dumpsys(result.stdout, include_system)


def _parse_dumpsys(stdout: str,
                   include_system: bool = True) -> List[AppInfo]:
    """Parse `dumpsys package` into AppInfo objects.

    Dual-grammar support (verified against an /e/OS Android 14 dump
    and an MIUI-era sample):
    - Old grammar: section keys at depth 4, entries at depth 6.
    - New grammar: keys at depth 6, entries at depth 8.
    - MIUI emits lowercase flush-left interjections inside the
      Packages region ('com.miui.system overlay paths:'); these
      must NOT end the region.
    - Real top-level sections start uppercase. Leaving the region
      nulls the current package, so entries in later sections can
      never be attributed to anyone — the 'Circular' false positive.
    """
    apps: List[AppInfo] = []
    current = None
    in_region = False
    in_requests = in_runtime = in_install = False

    def _depth(raw: str) -> int:
        return len(raw) - len(raw.lstrip(' '))

    for line in stdout.splitlines():
        raw = line.rstrip('\r')
        stripped = raw.strip()
        depth = _depth(raw)
        low = stripped.lower()

        if depth == 0 and stripped == 'Packages:':
            in_region = True
            current = None
            in_requests = in_runtime = in_install = False
            continue
        if (depth == 0 and stripped.endswith(':')
                and stripped[:1].isupper()):
            in_region = False
            current = None
            in_requests = in_runtime = in_install = False
            continue
        if not in_region:
            continue

        if stripped.startswith('Package ['):
            try:
                name = raw.split('[', 1)[1].split(']')[0]
            except IndexError:
                current = None
                continue
            if not name:
                current = None
                continue
            current = AppInfo(package_name=name)
            apps.append(current)
            in_requests = in_runtime = in_install = False
            continue
        if current is None:
            continue

        if stripped.startswith('versionName='):
            current.version_name = \
                stripped.split('=', 1)[1].strip()
            continue
        if stripped.startswith('versionCode='):
            try:
                current.version_code = int(
                    stripped.split('=', 1)[1].split(' ')[0])
            except (ValueError, IndexError):
                pass
            continue
        if stripped.startswith(('pkgFlags=', 'flags=')):
            upper = stripped.upper()
            current.is_system = ('SYSTEM' in upper
                                 and 'DEBUGGABLE' not in upper)
            continue
        if stripped.startswith('User 0:'):
            # enabled=0 is DEFAULT (=on), 2/3/4 are the real
            # disabled states, 'false' is the boolean spelling.
            if 'installed=false' in stripped:
                current.installed_user0 = False
            if 'enabled=' in stripped:
                code = stripped.split('enabled=', 1)[1]
                code = code.split()[0].rstrip(',')
                if code == 'false':
                    current.enabled_user0 = False
                elif code.isdigit():
                    current.enabled_user0 = \
                        int(code) not in (2, 3, 4)
            continue
        if depth <= 6 and low.startswith('requested permissions'):
            in_requests, in_runtime, in_install = \
                True, False, False
            continue
        if depth <= 6 and low.startswith('install permissions'):
            in_requests, in_runtime, in_install = \
                False, False, True
            continue
        if depth <= 6 and low.startswith('runtime permissions'):
            in_requests, in_runtime, in_install = \
                False, True, False
            continue

        if depth >= 6 and stripped.startswith(
                'android.permission.'):
            leaf = stripped.split(':', 1)[0].rsplit('.', 1)[-1]
            if in_requests:
                current.permissions_requested.add(leaf)
            elif ': granted=true' in stripped:
                if in_runtime:
                    current.permissions_requested.add(leaf)
                    current.permissions_granted.add(leaf)
                    # Capture lock reason (SYSTEM_FIXED /
                    # GRANTED_BY_ROLE).
                    lock_flags = set()
                    if 'SYSTEM_FIXED' in stripped:
                        lock_flags.add('SYSTEM_FIXED')
                    if 'GRANTED_BY_ROLE' in stripped:
                        lock_flags.add('GRANTED_BY_ROLE')
                    if lock_flags:
                        current.locked_perms.setdefault(
                            leaf, set()).update(lock_flags)
                elif (in_install
                        and leaf in DANGEROUS_PERMISSIONS):
                    current.permissions_granted.add(leaf)
            continue

        if depth < 6 and stripped:
            in_requests = in_runtime = in_install = False

    if not include_system:
        apps = [a for a in apps if not a.is_system]
    return apps


def build_permission_index(apps: List[AppInfo]) -> Dict:
    """{leaf: [packages]} for active apps, plus locked-index map.

    Mirrors the index build used by the report: only apps runnable
    for user 0 count, so uninstalled/disabled apps never inflate
    permission-holder lists.
    """
    index: Dict[str, List[str]] = {}
    locked: Dict[str, Dict[str, Set[str]]] = {}
    for app in apps:
        if not app.is_active:
            continue
        for leaf in app.permissions_granted:
            index.setdefault(leaf, []).append(app.package_name)
        if app.locked_perms:
            locked[app.package_name] = app.locked_perms
    return {'index': index, 'locked': locked}
