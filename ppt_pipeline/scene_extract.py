"""基于 PySceneDetect 的场景关键帧提取：每场景取一帧，再合成 PDF。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from . import evp_utils


def _hms_to_seconds(hms: str) -> float | None:
    if not hms or hms.strip() == "":
        return None
    parts = hms.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except ValueError:
        return None


def run_extract_scenedetect(
    output_dir: Path,
    video_full: Path,
    video_cropped: Path | None,
    crop: tuple[float, float, float, float] | None,
    start_time: str,
    end_time: str,
    output_ppt_only: bool,
    output_full_screen: bool,
    extract_images: bool,
    project_root: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
    scene_threshold: float = 27.0,
) -> dict[str, Path]:
    """
    用 PySceneDetect 检测场景边界，每个场景取中间时刻一帧，再合成 PDF。
    与 evp 二选一；适合需要「关键帧更准」、少重影的场景。
    """
    from scenedetect import open_video, SceneManager, ContentDetector

    def _log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    output_dir = Path(output_dir).resolve()
    video_for_detect = video_cropped if video_cropped and video_cropped.is_file() else video_full
    start_sec = _hms_to_seconds(start_time) if start_time else None
    end_sec = _hms_to_seconds(end_time) if end_time else None

    _log("PySceneDetect: 正在检测场景…")
    video = open_video(str(video_for_detect))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=float(scene_threshold)))
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    # 每个场景取中间时刻（秒）
    times_sec: list[float] = []
    for start_tc, end_tc in scene_list:
        s = start_tc.get_seconds()
        e = end_tc.get_seconds()
        mid = (s + e) / 2.0
        if start_sec is not None and mid < start_sec:
            continue
        if end_sec is not None and mid > end_sec:
            continue
        times_sec.append(mid)

    times_sec.sort()
    # 相邻关键帧至少间隔 2 秒，避免同一页多帧
    min_gap = 2.0
    filtered: list[float] = []
    for ts in times_sec:
        if not filtered or (ts - filtered[-1]) >= min_gap:
            filtered.append(ts)
    times_sec = filtered

    if not times_sec:
        first = start_sec if start_sec is not None else 0.0
        times_sec = [first]
        _log("未检测到场景变化，使用单帧。")

    _log(f"共 {len(times_sec)} 个关键帧。")

    result: dict[str, Path] = {}
    frames_dir = output_dir / "frames_scenedetect"
    frames_dir.mkdir(parents=True, exist_ok=True)

    if output_ppt_only:
        _log("正在抽取 PPT 区域帧…")
        paths = evp_utils.extract_frames_at_times(video_for_detect, times_sec, frames_dir)
        if not paths:
            raise RuntimeError("场景关键帧抽取失败")
        out_ppt = output_dir / "slides_ppt_only.pdf"
        evp_utils.frames_to_pdf(paths, out_ppt)
        result["slides_ppt_only"] = out_ppt
        if extract_images:
            img_dir = output_dir / "images_ppt_only"
            img_dir.mkdir(parents=True, exist_ok=True)
            for i, p in enumerate(paths, 1):
                shutil.copy(p, img_dir / f"page_{i:03d}.png")
            result["images_ppt_only"] = img_dir

    if output_full_screen and video_full.is_file():
        _log("正在抽取全屏帧…")
        full_dir = output_dir / "frames_full"
        full_dir.mkdir(parents=True, exist_ok=True)
        paths_full = evp_utils.extract_frames_at_times(video_full, times_sec, full_dir)
        if paths_full:
            out_full = output_dir / "slides_full.pdf"
            evp_utils.frames_to_pdf(paths_full, out_full)
            result["slides_full"] = out_full
            if extract_images:
                img_dir = output_dir / "images_full"
                img_dir.mkdir(parents=True, exist_ok=True)
                for i, p in enumerate(paths_full, 1):
                    shutil.copy(p, img_dir / f"page_{i:03d}.png")
                result["images_full"] = img_dir

    return result
