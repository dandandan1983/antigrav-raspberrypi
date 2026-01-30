from configparser import ConfigParser
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.ini"


def load_config(path: Optional[str] = None) -> ConfigParser:
    """Load and return a ConfigParser for the application.

    If `path` is not provided, the repository root `config.ini` is used.
    """
    cfg = ConfigParser()
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")
    cfg.read(cfg_path)
    return cfg


def get_bool(cfg: ConfigParser, section: str, key: str, fallback: bool = False) -> bool:
    try:
        return cfg.getboolean(section, key)
    except Exception:
        return fallback


def get_int(cfg: ConfigParser, section: str, key: str, fallback: int = 0) -> int:
    try:
        return cfg.getint(section, key)
    except Exception:
        return fallback


def get_str(cfg: ConfigParser, section: str, key: str, fallback: str = "") -> str:
    try:
        return cfg.get(section, key)
    except Exception:
        return fallback
