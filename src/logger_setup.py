import logging
from pathlib import Path
from typing import Optional


def configure_logging(cfg: Optional[object] = None) -> None:
    """Configure root logging using values from config parser-like object.

    Expects `cfg` to have sections/keys as in `config.ini` (optional).
    """
    log_level = logging.INFO
    log_file = None
    console = True

    try:
        if cfg is not None and cfg.has_section("misc"):
            lvl = cfg.get("misc", "log_level", fallback="INFO")
            log_level = getattr(logging, lvl.upper(), logging.INFO)
            log_file = cfg.get("misc", "log_file", fallback=None)
            console = cfg.getboolean("misc", "log_to_console", fallback=True)
    except Exception:
        pass

    root = logging.getLogger()
    root.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        root.addHandler(ch)

    if log_file:
        try:
            # ensure parent dir exists if possible
            parent = Path(log_file).parent
            if parent and not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    # will be caught by FileHandler creation below
                    pass

            fh = logging.FileHandler(str(log_file))
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            root.warning("Unable to create log file handler: %s", log_file)
            # attempt to fallback to a writable location, preferably misc.state_dir
            try:
                alt_dir = None
                if cfg is not None and hasattr(cfg, "get"):
                    try:
                        alt_dir = cfg.get("misc", "state_dir", fallback=None)
                    except Exception:
                        alt_dir = None
                if not alt_dir:
                    alt_dir = str(Path.home() / ".local" / "rpi-handsfree")
                alt_path = Path(alt_dir)
                alt_path.mkdir(parents=True, exist_ok=True)
                alt_log = alt_path / Path(log_file).name
                try:
                    fh2 = logging.FileHandler(str(alt_log))
                    fh2.setFormatter(formatter)
                    root.addHandler(fh2)
                    root.warning("Falling back to log file: %s", str(alt_log))
                except Exception:
                    root.warning("Unable to create fallback log file handler: %s", str(alt_log))
            except Exception:
                root.warning("No writable log directory available; continuing without file logging")
