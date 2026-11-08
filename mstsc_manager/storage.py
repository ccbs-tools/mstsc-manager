from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from . import APP_NAME
from .log import APP_DATA_DIR, logger
from .models import Connection


def app_data_dir() -> Path:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DATA_DIR


def config_path() -> Path:
    return app_data_dir() / "connections.json"


def known_hosts_path() -> Path:
    p = app_data_dir() / "known_hosts"
    p.touch(exist_ok=True)
    return p


def sessions_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(app_data_dir())
    d = Path(base) / "ccbs" / APP_NAME / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_connections() -> list[Connection]:
    p = config_path()
    if not p.exists():
        logger.info("config not found, starting empty: {}", p)
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.error("failed to read config {}: {!r}", p, e)
        return []
    conns = [Connection.from_dict(item) for item in data.get("connections", [])]
    logger.info("loaded {} connection(s) from {}", len(conns), p)
    return conns


def save_connections(conns: list[Connection]) -> None:
    p = config_path()
    tmp = p.with_suffix(".json.tmp")
    payload = {"version": 1, "connections": [c.to_dict() for c in conns]}
    new_text = json.dumps(payload, ensure_ascii=False, indent=2)
    # 内容没变就不写，避免无意义地刷新备份
    if p.exists():
        try:
            if p.read_text(encoding="utf-8") == new_text:
                return
            # 上一版留作 connections.json.bak，误操作时可手工恢复
            shutil.copyfile(p, p.with_suffix(".json.bak"))
        except OSError as e:
            logger.warning("could not back up config: {!r}", e)
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, p)
    logger.debug("saved {} connection(s) to {}", len(conns), p)
