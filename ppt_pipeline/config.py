"""配置读写与默认值。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "url": "",
    "video_dir": "./video_output",
    "output_dir": "./ppt_output",
    "cookies_from_browser": "",
    "cookies_file": "",
    "ytdlp_js_runtime": "",
    "ytdlp_remote_components": "",
    "crop_left": 0.35,
    "crop_top": 0.0,
    "crop_width": 0.65,
    "crop_height": 1.0,
    "similarity": 0.45,
    "extract_method": "evp",
    "scene_threshold": 27.0,
    "start_time": "",
    "end_time": "",
    "output_ppt_only": True,
    "output_full_screen": False,
    "extract_images": True,
    "force_download": False,
    "force_crop": False,
}


def _config_path(project_root: Path | None = None) -> Path:
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    return project_root / CONFIG_FILENAME


def load_config(project_root: Path | None = None) -> dict[str, Any]:
    path = _config_path(project_root)
    if not path.is_file():
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)
    out = dict(DEFAULT_CONFIG)
    for k, v in data.items():
        if k in out:
            out[k] = v
    # 旧 config 无 video_dir 时与 output_dir 一致，避免找不到已下载视频
    if "video_dir" not in data and "output_dir" in data:
        out["video_dir"] = out["output_dir"]
    return out


def save_config(config: dict[str, Any], project_root: Path | None = None) -> None:
    path = _config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
