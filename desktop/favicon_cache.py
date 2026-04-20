"""
Favicon Cache — fetches and caches website favicons locally.
Thread-safe, non-blocking, gracefully degrades.
"""
import os
import threading
import requests

_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicons")
_lock = threading.Lock()
_session = requests.Session()
_session.trust_env = False  # bypass proxy

def _ensure_dir():
    if not os.path.isdir(_BASE_DIR):
        os.makedirs(_BASE_DIR, exist_ok=True)

def _safe_filename(domain: str) -> str:
    """Sanitize domain to a safe filename."""
    return domain.replace("/", "_").replace(":", "_").replace("?", "_") + ".png"

def get_favicon(domain: str) -> str | None:
    """Return local path to cached favicon, or None if not cached."""
    path = os.path.join(_BASE_DIR, _safe_filename(domain))
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return path
    return None

def fetch_and_cache(domain: str, callback=None):
    """Fetch favicon in a background thread. Calls callback(domain, path) on success."""
    def _fetch():
        _ensure_dir()
        path = os.path.join(_BASE_DIR, _safe_filename(domain))
        
        # Skip if already cached
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            if callback:
                callback(domain, path)
            return
        
        with _lock:
            # Double-check after acquiring lock
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                if callback:
                    callback(domain, path)
                return
            
            try:
                # Try Google's favicon service (high quality)
                url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
                resp = _session.get(url, timeout=5)
                if resp.status_code == 200 and len(resp.content) > 100:
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    if callback:
                        callback(domain, path)
            except Exception:
                pass  # Silently fail — letter avatar will be used

    threading.Thread(target=_fetch, daemon=True).start()

def prefetch_domains(domains: list[str], callback=None):
    """Kick off background fetches for a list of domains."""
    for d in domains:
        if d and not get_favicon(d):
            fetch_and_cache(d, callback)
