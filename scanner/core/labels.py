"""Human-readable app-name lookup (fully local).

Reads labels.json next to the Blog Tool root once, then serves
dictionary lookups. Unmapped packages fall back to the package
name — the tool is fully functional with an empty map.
"""

import json
import os
import threading

LABELS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'labels.json')

_labels: dict = {}
_loaded = False
_lock = threading.Lock()

def _load():
    global _labels, _loaded
    with _lock:
        if _loaded:
            return
        try:
            with open(LABELS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                _labels = {str(k): str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError):
            _labels = {}
        _loaded = True

def display_name(package):
    """Label for a package, falling back to the package itself."""
    _load()
    return _labels.get(package or '', package or '')

def display_key(cache_key):
    """Label for a results-cache key ('pkg_123' / 'pkg')."""
    _load()
    if not cache_key:
        return cache_key
    if cache_key in _labels:
        return _labels[cache_key]
    if '_' in cache_key:
        base, sep, suffix = cache_key.rpartition('_')
        if sep and base and suffix.isdigit():
            return _labels.get(base, cache_key)
    return _labels.get(cache_key, cache_key)
