"""Tracker detection — APK scanning against known tracker signatures.

Signature database is BUNDLED with the tool (tracker_data/
trackers.json): the scan performs zero network calls. Database
updates happen only when a new version of the tool is published.

Methodology (Exodus Privacy): a tracker counts only when its
class names appear among the classes DEFINED in the app's DEX
files. Loose string mentions do not count.

Reliability notes:
- Pulled APKs live in a per-scan temp dir removed on EVERY exit
  path (success, failure, exception).
- DEX extraction is capped to protect against zip bombs.
- Signature regexes are compiled once per process and paired with
  a fast literal-prefix check, so ~400 patterns are matched
  against multi-MB data efficiently.
"""

import os
import re
import shutil
import struct
import json
import subprocess
import tempfile
import zipfile
from datetime import datetime
from typing import Dict, List, Tuple

from .adb import ADB_PATH, TIMEOUTS

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'tracker_data')
DB_FILE = os.path.join(DATA_DIR, 'trackers.json')

# Per-session scan-result cache: in memory only, never written to
# disk, so no visitor data survives app exit.
_RESULTS_MEMORY: Dict[str, dict] = {}

# Safety caps.
MAX_DEX_TOTAL = 512 * 1024 * 1024      # zip-bomb guard for DEX

# ------------------------------------------------------------------
#  Signature database (bundled, offline)
# ------------------------------------------------------------------

def load_tracker_database() -> dict:
    """Load the bundled signature database.

    Returns {tracker_name: [signatures]} or {} if unreadable. A
    missing or corrupt database must degrade to an empty map —
    the tool still scans apps and permissions, and the UI reports
    that signatures are unavailable.
    """
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}

    if not isinstance(data, dict):
        return {}
    trackers = data.get('trackers', {})
    return trackers if isinstance(trackers, dict) else {}

def database_signature_count(db: dict) -> int:
    """Number of trackers in the loaded database (report footer)."""
    return len(db) if isinstance(db, dict) else 0

# ------------------------------------------------------------------
#  APK pulling (argv-only, guaranteed cleanup)
# ------------------------------------------------------------------

def pull_apk(serial: str, package: str,
             progress_callback=None
             ) -> Tuple[List[str], str]:
    """Pull an app's APK file(s) from the device to a temp directory.

    Returns (list_of_apk_paths, error_message_or_None). On ANY exit
    path that abandons the temp dir (error, timeout, nothing pulled),
    the temp dir is removed before returning — no leaks.

    The caller OWNS the returned paths and must call cleanup_apk()
    when done (ideally from a finally block).
    """
    if not package or not isinstance(package, str):
        return [], 'Nome pacchetto non valido'

    result = subprocess.run(
        [ADB_PATH, '-s', serial, 'shell', 'pm', 'path', package],
        capture_output=True, text=True,
        timeout=TIMEOUTS['shell_short'])

    if result.returncode != 0:
        return [], (result.stderr.strip()
                    or 'Impossibile ottenere il percorso dell\'APK')

    stdout = (result.stdout or '').strip()
    if not stdout:
        return [], 'Nessun percorso APK restituito'

    # Strict parse: only `package:/valid/path.apk` lines count.
    apk_paths = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith('package:'):
            path = line.split('package:', 1)[1].strip()
            if path.startswith('/') and path.endswith('.apk'):
                apk_paths.append(path)
    if not apk_paths:
        return [], 'Impossibile interpretare il percorso dell\'APK'

    temp_dir = tempfile.mkdtemp(prefix='pa_scan_')
    local_paths: List[str] = []
    total = len(apk_paths)

    try:
        for i, remote_path in enumerate(apk_paths):
            if progress_callback:
                progress_callback(i + 1, total)

            filename = os.path.basename(remote_path) or f'split_{i}.apk'
            local_path = os.path.join(temp_dir, filename)

            try:
                proc = subprocess.run(
                    [ADB_PATH, '-s', serial, 'pull',
                     remote_path, local_path],
                    capture_output=True, text=True,
                    timeout=TIMEOUTS['install'])
                if proc.returncode == 0 and os.path.isfile(local_path):
                    local_paths.append(local_path)
            except subprocess.TimeoutExpired:
                return [], (f'Tempo scaduto scaricando l\'APK '
                            f'({i + 1}/{total})')
            except Exception as e:
                return [], f'Errore scaricamento: {e}'

        if not local_paths:
            return [], 'Nessun APK scaricato con successo'
        return local_paths, None

    finally:
        # Remove the temp dir on every failure path. On success the
        # caller owns the dir (cleaned via cleanup_apk).
        if len(local_paths) < len(apk_paths) or not local_paths:
            shutil.rmtree(temp_dir, ignore_errors=True)

def cleanup_apk(apk_paths: List[str]):
    """Delete temporary APK files and their parent directory."""
    if not apk_paths:
        return
    temp_dir = os.path.dirname(apk_paths[0])
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ------------------------------------------------------------------
#  Signature compilation (module-level, one compile per sig)
# ------------------------------------------------------------------

# Compiled once per process and reused across all scans.
_COMPILED_SIGNATURES: Dict[str, tuple] = {}

# Characters that make a signature a true regex rather than a
# plain string; the leading literal run stops at the first.
_METACHARS = frozenset('.*+?[]{}()|^$')

_MIN_FAST_PREFIX = 3

def _prepare_signature(sig: str) -> tuple:
    """Compile one signature to (pattern, fast_prefix), cached.

    pattern      -- signature compiled as a BYTES regex, once per
                    process. A signature that fails to compile
                    falls back to an escaped literal, so behavior
                    can never regress.
    fast_prefix  -- the leading LITERAL run with backslash-escapes
                    unfolded. Any regex match must CONTAIN these
                    bytes, so if they are absent from the data the
                    regex is skipped entirely — the key performance
                    safeguard when checking hundreds of patterns
                    against multi-MB data. b'' when the literal run
                    is too short or starts with a metacharacter.
    """
    entry = _COMPILED_SIGNATURES.get(sig)
    if entry is not None:
        return entry

    sig_bytes = sig.encode('utf-8', errors='replace')
    try:
        pattern = re.compile(sig_bytes)
    except re.error:
        pattern = re.compile(re.escape(sig_bytes))

    literal = []
    i = 0
    while i < len(sig):
        ch = sig[i]
        if ch == '\\' and i + 1 < len(sig):
            literal.append(sig[i + 1])
            i += 2
            continue
        if ch in _METACHARS:
            break
        literal.append(ch)
        i += 1

    fast = ''.join(literal).encode('utf-8', errors='replace')
    if len(fast) < _MIN_FAST_PREFIX:
        fast = b''

    entry = (pattern, fast)
    _COMPILED_SIGNATURES[sig] = entry
    return entry

def _match_signature(data: bytes, sig: str) -> bool:
    """True if the signature regex matches the byte buffer."""
    pattern, fast = _prepare_signature(sig)
    if fast and fast not in data:
        return False
    return pattern.search(data) is not None

# ------------------------------------------------------------------
#  DEX class-name extraction
# ------------------------------------------------------------------

def _read_uleb128(buf: bytes, off: int) -> Tuple[int, int]:
    """Read one ULEB128 integer. Returns (value, next_offset)."""
    result = 0
    shift = 0
    while True:
        try:
            b = buf[off]
        except IndexError:
            raise ValueError('ULEB128 read past end of data')
        off += 1
        result |= (b & 0x7f) << shift
        if not b & 0x80:
            return result, off
        shift += 7
        if shift > 35:
            raise ValueError('ULEB128 value too long')

def _dex_strings(dex_data: bytes, wanted: set) -> dict:
    """Decode selected entries of a DEX string table.

    `wanted` is a set of string indices; returns {index: string}.
    Malformed entries are skipped, never fatal.
    """
    strings = {}
    if len(dex_data) < 0x70 or dex_data[:4] != b'dex\n':
        return strings
    string_ids_size = struct.unpack_from('<I', dex_data, 0x38)[0]
    string_ids_off = struct.unpack_from('<I', dex_data, 0x3C)[0]
    for idx in wanted:
        if idx >= string_ids_size:
            continue
        try:
            (off,) = struct.unpack_from(
                '<I', dex_data, string_ids_off + idx * 4)
            _utf16_len, off = _read_uleb128(dex_data, off)
            end = dex_data.index(b'\x00', off)
            raw = dex_data[off:end]
        except (ValueError, IndexError, struct.error):
            continue
        strings[idx] = raw.decode('utf-8', errors='replace')
    return strings

def _extract_class_names(dex_data: bytes) -> List[str]:
    """Dotted names of all classes DEFINED in this DEX.

    The 'phone book' of what the app is actually built from. A
    tracker counts ONLY when its code is embedded here. Loose
    string mentions do NOT count.
    """
    if len(dex_data) < 0x70 or dex_data[:4] != b'dex\n':
        return []
    try:
        type_ids_size = struct.unpack_from('<I', dex_data, 0x40)[0]
        type_ids_off = struct.unpack_from('<I', dex_data, 0x44)[0]
        class_defs_size = struct.unpack_from('<I', dex_data, 0x60)[0]
        class_defs_off = struct.unpack_from('<I', dex_data, 0x64)[0]
    except struct.error:
        return []

    # 1) Class-definition table -> type indices.
    type_indices = set()
    for i in range(class_defs_size):
        try:
            (class_idx,) = struct.unpack_from(
                '<I', dex_data, class_defs_off + i * 32)
        except struct.error:
            break
        if class_idx < type_ids_size:
            type_indices.add(class_idx)
    if not type_indices:
        return []

    # 2) Type indices -> string-table indices.
    string_indices = set()
    for ti in type_indices:
        try:
            (si,) = struct.unpack_from(
                '<I', dex_data, type_ids_off + ti * 4)
        except struct.error:
            break
        string_indices.add(si)

    # 3) Decode, keep descriptor-shaped names:
    #    Lcom/foo/Bar; -> com.foo.Bar
    strings = _dex_strings(dex_data, string_indices)
    names = []
    for si in string_indices:
        s = strings.get(si, '')
        if s.startswith('L') and s.endswith(';') and '/' in s:
            names.append(s[1:-1].replace('/', '.'))
    return names

def _scan_dex(apk_path: str, tracker_db: dict, hits: dict):
    """Class-table scan of DEX files inside the APK ZIP.

    Only class names DEFINED in each DEX are matched. Guarded
    against zip bombs: cumulative decompressed DEX bytes are
    capped; a single unreadable DEX is skipped.
    """
    try:
        with zipfile.ZipFile(apk_path, 'r') as zf:
            dex_names = [n for n in zf.namelist()
                         if n.endswith('.dex')]
            read_total = 0
            for dex_name in dex_names:
                try:
                    info = zf.getinfo(dex_name)
                    if info.file_size > (MAX_DEX_TOTAL - read_total):
                        break
                    dex_data = zf.read(dex_name)
                    read_total += len(dex_data)
                except Exception:
                    continue
                names = _extract_class_names(dex_data)
                if not names:
                    continue
                blob = '\n'.join(names).encode('utf-8')
                for tracker_name, signatures in tracker_db.items():
                    for sig in signatures:
                        if _match_signature(blob, sig):
                            hits.setdefault(
                                tracker_name, []).append(sig)
    except (zipfile.BadZipFile, OSError):
        pass

# ------------------------------------------------------------------
#  Public scan entry point
# ------------------------------------------------------------------

def scan_apk(apk_paths: List[str], tracker_db: dict,
             progress_callback=None) -> dict:
    """Scan one or more APK files for tracker signatures.

    Returns {tracker_name: [sorted unique matched signatures]}.
    """
    hits: dict = {}
    total = len(apk_paths) or 1
    for idx, apk_path in enumerate(apk_paths):
        try:
            _scan_dex(apk_path, tracker_db, hits)
        except Exception:
            continue      # one bad split never aborts the scan
        if progress_callback:
            progress_callback(idx + 1, total)
    return {name: sorted(set(sigs)) for name, sigs in hits.items()}

# ------------------------------------------------------------------
#  Session results cache (in memory only)
# ------------------------------------------------------------------

def _results_cache_key(package: str, version_code) -> str:
    return f'{package}_{version_code}' if version_code else package

def get_cached_result(package: str, version_code='') -> dict:
    return _RESULTS_MEMORY.get(
        _results_cache_key(package, version_code), {})

def save_cached_result(package: str, version_code, trackers,
                       apk_size: int):
    _RESULTS_MEMORY[_results_cache_key(package, version_code)] = {
        'trackers': trackers,
        'apk_size': apk_size,
        'scanned_at': datetime.now().strftime('%d/%m/%y %H:%M'),
    }

def get_all_cached_results() -> dict:
    return _RESULTS_MEMORY
