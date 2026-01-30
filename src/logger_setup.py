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
            import os
            parent = os.path.dirname(log_file)
            if parent and not os.path.isdir(parent):
                try:
                    os.makedirs(parent, exist_ok=True)
                except Exception:
                    # will be caught by FileHandler creation below
                    pass

            fh = logging.FileHandler(log_file)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            root.warning("Unable to create log file handler: %s", log_file)
