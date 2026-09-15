"""Launch the packaged (or source) Sales OS in a browser.

The launcher keeps mutable state outside the bundled application and deliberately
does not terminate processes it did not start.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


APP_NAME = "KidProductionz Sales OS"
DESKTOP_LAUNCHER_VERSION = "2026-09-14-v4"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def runtime_root() -> Path:
    """Return the source root or PyInstaller's extracted bundle root."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parent


def data_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return root / APP_NAME

def bootstrap_log(message: str) -> None:
    try:
        # Isolate diagnostic package provenance from older launcher logs.
        log_name = 'bootstrap-v4.log' if 'V4 Diagnostic' in Path(sys.executable).name else 'bootstrap.log'
        path = data_root() / 'logs' / log_name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as fh:
            fh.write(message.rstrip() + '\n')
    except Exception:
        pass


def load_env() -> Path | None:
    """Load a packaged per-user .env, falling back to the source .env."""
    candidates = [data_root() / ".env", runtime_root() / ".env"]
    for path in candidates:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
        logging.info("Packaged env loaded: %s", path)
        return path
    logging.info("No packaged env found")
    return None

def migrate_packaged_state() -> None:
    """Copy existing source state into packaged app data on first run only."""
    if not getattr(sys, 'frozen', False):
        return
    target = data_root()
    target.mkdir(parents=True, exist_ok=True)
    packaged_db = target / 'kidproductionz.db'
    exe_root = Path(sys.executable).resolve().parents[2] if getattr(sys, 'frozen', False) else runtime_root()
    candidates = [runtime_root() / 'data' / 'kidproductionz.db', exe_root / 'data' / 'kidproductionz.db']
    source_db = next((p for p in candidates if p.is_file()), None)
    backups = target / 'backups'
    stamp = time.strftime('%Y%m%d_%H%M%S')
    for existing in (source_db, packaged_db):
        if existing and existing.is_file():
            backups.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, backups / f'{existing.stem}_{stamp}{existing.suffix}')
    if not packaged_db.exists() and source_db:
        shutil.copy2(source_db, packaged_db)
        logging.info('Migrated existing KidProductionz database to packaged data directory.')
    elif packaged_db.exists():
        logging.info('Packaged KidProductionz database already exists; leaving it unchanged.')
    project_env = exe_root / '.env'
    packaged_env = target / '.env'
    if not packaged_env.exists() and project_env.is_file():
        shutil.copy2(project_env, packaged_env)
        logging.info('Copied existing application configuration to packaged data directory.')
    # Preserve immutable campaign artifacts for packaged read APIs.
    source_artifacts = exe_root / 'validation_outputs'
    target_artifacts = target / 'validation_outputs'
    if source_artifacts.is_dir() and not target_artifacts.exists():
        shutil.copytree(source_artifacts, target_artifacts)
        logging.info('Migrated existing campaign artifacts to packaged data directory.')


def configure_logging(root: Path) -> Path:
    log_dir = data_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "sales-os.log"
    try:
        logging.basicConfig(filename=log_path, level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        return log_path
    except PermissionError:
        # A previous instance may still hold the shared log open; keep startup
        # alive and write this instance to a distinct safe log.
        fallback = log_dir / f"sales-os-{os.getpid()}.log"
        logging.basicConfig(filename=fallback, level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        bootstrap_log(f"normal log locked; using fallback={fallback}")
        return fallback


def health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/api/health"


def is_healthy(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(health_url(host, port), timeout=timeout) as response:
            if response.status != 200:
                return False
            try:
                payload = json.loads(response.read().decode('utf-8'))
                return payload.get('app') == 'ok'
            except (ValueError, UnicodeError, AttributeError):
                return False
    except (OSError, urllib.error.URLError):
        return False


def port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def choose_port(host: str, preferred: int) -> int:
    if is_healthy(host, preferred):
        return preferred
    if port_available(host, preferred):
        return preferred
    for port in range(preferred + 1, preferred + 101):
        if port_available(host, port):
            return port
    raise RuntimeError("No available local port found")


def wait_for_health(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_healthy(host, port):
            return True
        time.sleep(0.25)
    return False

def open_browser(app_url: str) -> bool:
    try:
        opened = webbrowser.open(app_url, new=2)
        logging.info("Browser open requested url=%s result=%s", app_url, opened)
        if opened:
            return True
    except Exception:
        logging.exception("Browser open raised an exception url=%s", app_url)
    try:
        os.startfile(app_url)
        logging.info("Browser open fallback succeeded url=%s", app_url)
        return True
    except Exception:
        logging.exception("Browser open fallback failed url=%s", app_url)
        return False


def main() -> int:
    root = runtime_root()
    state = data_root()
    bootstrap_log(f'Desktop launcher version={DESKTOP_LAUNCHER_VERSION}')
    bootstrap_log('launcher_marker=V4_FRESH_PAYLOAD')
    bootstrap_log(f'executable={sys.executable}')
    bootstrap_log(f'mode={"packaged" if getattr(sys, "frozen", False) else "source"}')
    bootstrap_log(f'app_data={state}')
    bootstrap_log('begin env resolution')
    state.mkdir(parents=True, exist_ok=True)
    log_path = configure_logging(root)
    logging.info("Desktop launcher version=%s", DESKTOP_LAUNCHER_VERSION)
    migrate_packaged_state()
    env_path = load_env()
    bootstrap_log(f'env resolved={env_path}')
    host = os.environ.get("APP_HOST", DEFAULT_HOST)
    preferred = int(os.environ.get("APP_PORT", str(DEFAULT_PORT)))
    if is_healthy(host, preferred):
        logging.info("Existing healthy KidProductionz instance found on port %s; opening existing instance.", preferred)
        open_browser(f"http://{host}:{preferred}")
        return 0
    if port_available(host, preferred):
        logging.info("Port %s is free; starting new KidProductionz instance.", preferred)
        port = preferred
    else:
        logging.info("Port %s is occupied by a non-KidProductionz process.", preferred)
        port = choose_port(host, preferred)
        logging.info("Alternate local port selected: %s", port)
    os.environ.setdefault("PYTHONPATH", str(root / "src"))
    # Packaged state is authoritative: never let a development DATABASE_URL
    # from the process or copied .env point the frozen app back at ./data.
    if getattr(sys, "frozen", False):
        db_path = (state / "kidproductionz.db").resolve()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        os.environ["KIDPRODUCTIONZ_ARTIFACT_ROOT"] = str(state / 'validation_outputs')
    else:
        os.environ.setdefault("DATABASE_URL", f"sqlite:///{(state / 'kidproductionz.db').resolve().as_posix()}")
    bootstrap_log(f'database resolved={os.environ.get("DATABASE_URL")}')
    logging.info("Starting %s root=%s data=%s env=%s port=%s", APP_NAME, root, state, env_path, port)

    # Import only after environment and writable paths are configured.
    bootstrap_log('backend import start')
    import uvicorn
    bootstrap_log('backend import module complete')
    from app.api.main import app
    bootstrap_log('backend import complete')
    bootstrap_log('FastAPI app resolved')

    def open_when_ready() -> None:
        if wait_for_health(host, port):
            logging.info("New KidProductionz server successfully started on port %s", port)
            if not open_browser(f"http://{host}:{port}"):
                logging.error("Browser launch failed after server startup")
        else:
            logging.error("Startup failure: server never became healthy on port %s", port)

    threading.Thread(target=open_when_ready, daemon=True).start()
    logging.info("Frontend=%s health=%s log=%s", root / "app/frontend/dist", health_url(host, port), log_path)
    try:
        bootstrap_log('uvicorn config start')
        config = uvicorn.Config(app, host=host, port=port, workers=1, reload=False, log_config=None)
        bootstrap_log('uvicorn config complete')
        server = uvicorn.Server(config)
        bootstrap_log('uvicorn server created')
        bootstrap_log('uvicorn run entering')
        server.run()
        bootstrap_log('uvicorn run returned')
        logging.error("Application server exited unexpectedly")
    except Exception:
        logging.exception("Fatal application error")
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as exc:
        bootstrap_log(f'UNHANDLED {type(exc).__name__}: {exc}')
        import traceback
        bootstrap_log(traceback.format_exc())
        raise
