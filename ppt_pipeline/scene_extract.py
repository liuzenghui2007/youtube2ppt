"""基于 PySceneDetect 的场景关键帧提取：每场景取一帧，再合成 PDF。针对纯 PPT 无演讲者优化。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from . import evp_utils


def _is_frame_static(frame: np.ndarray, static_threshold: float = 5.0) -> bool:
    """判断是否为静态帧（编码噪点等），用于过滤误检。拉普拉斯方差小于阈值视为静态。"""
    if frame is None or frame.size == 0:
        return True
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var < static_threshold


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
    output_pptx: bool = True,
    extract_images: bool = True,
    project_root: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
    scene_threshold: float = 12.0,
    scene_min_scene_len: int = 5,
    scene_static_threshold: float = 2.0,
    scene_duplicate_threshold: float = 1.5,
    scene_min_gap: float = 0.5,
    scene_max_gap_sec: float = 45.0,
    scene_interval_fill_sec: float = 15.0,
) -> dict[str, Path]:
    """
    用 PySceneDetect 检测场景边界，每场景取起始帧（纯 PPT 无演讲者优化）。
    支持：min_scene_len、静态/重复过滤；间隔补帧（当两关键帧间隔>max_gap_sec 时按 interval_fill_sec 补点，再连续去重）。
    """
    from scenedetect import open_video, SceneManager, ContentDetector

    def _log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_for_detect = video_cropped if video_cropped and video_cropped.is_file() else video_full
    start_sec = _hms_to_seconds(start_time) if start_time else None
    end_sec = _hms_to_seconds(end_time) if end_time else None

    _log("PySceneDetect: 正在检测场景…")
    video = open_video(str(video_for_detect))
    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(
            threshold=float(scene_threshold),
            min_scene_len=int(scene_min_scene_len),
        )
    )
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()
    _log(f"PySceneDetect 原始场景数：{len(scene_list)}")

    # 纯 PPT 优化：过滤静态噪点与重复场景，并取起始帧时间（非中间）
    times_sec: list[float] = []
    if scene_static_threshold > 0 or scene_duplicate_threshold > 0:
        cap = cv2.VideoCapture(str(video_for_detect))
        prev_frame: np.ndarray | None = None
        try:
            for start_tc, end_tc in scene_list:
                s = start_tc.get_seconds()
                if start_sec is not None and s < start_sec:
                    continue
                if end_sec is not None and s > end_sec:
                    continue
                cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000.0)
                ret, frame = cap.read()
                if not ret or frame is None:
                    times_sec.append(s)
                    continue
                if scene_static_threshold > 0 and _is_frame_static(frame, scene_static_threshold):
                    continue
                if scene_duplicate_threshold > 0 and prev_frame is not None:
                    diff = cv2.absdiff(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                        cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY),
                    )
                    if np.mean(diff) < scene_duplicate_threshold:
                        continue
                times_sec.append(s)
                prev_frame = frame.copy()
        finally:
            cap.release()
    else:
        for start_tc, end_tc in scene_list:
            s = start_tc.get_seconds()
            if start_sec is not None and s < start_sec:
                continue
            if end_sec is not None and s > end_sec:
                continue
            times_sec.append(s)

    times_sec.sort()
    # 相邻关键帧最小间隔（秒），可配置；页数多时可设 0.5，同一页多帧时可设 1～2
    min_gap = max(0.0, float(scene_min_gap))
    filtered: list[float] = []
    for ts in times_sec:
        if filtered and ts == filtered[-1]:
            continue
        if not filtered or (ts - filtered[-1]) >= min_gap:
            filtered.append(ts)
    times_sec = filtered

    if not times_sec:
        first = start_sec if start_sec is not None else 0.0
        times_sec = [first]
        _log("未检测到场景变化，使用单帧。")

    # 间隔补帧：纯 PPT 段场景检测易漏，两关键帧间隔过大时按固定间隔补点
    if (
        scene_max_gap_sec > 0
        and scene_interval_fill_sec > 0
        and len(times_sec) >= 2
    ):
        fill_times: list[float] = []
        for i in range(len(times_sec) - 1):
            a, b = times_sec[i], times_sec[i + 1]
            if b - a > scene_max_gap_sec:
                t = a + scene_interval_fill_sec
                while t < b:
                    fill_times.append(t)
                    t += scene_interval_fill_sec
        if fill_times:
            times_sec = sorted(times_sec + fill_times)
            _log(f"间隔补帧：补 {len(fill_times)} 个时间点，共 {len(times_sec)} 个。")

    _log(f"共 {len(times_sec)} 个关键帧。")
    times_sec_final: list[float] = list(times_sec)

    result: dict[str, Path] = {}
    frames_dir = output_dir / "frames_scenedetect"
    frames_dir.mkdir(parents=True, exist_ok=True)

    def _frame_progress(current: int, total: int) -> None:
        if total > 0 and progress_callback:
            progress_callback("PROGRESS: " + str(round(100 * current / total)))

    if output_ppt_only:
        _log("正在抽取 PPT 区域帧…")
        paths = evp_utils.extract_frames_at_times(
            video_for_detect, times_sec, frames_dir, progress_callback=_frame_progress
        )
        if not paths:
            raise RuntimeError("场景关键帧抽取失败")
        # 连续去重：补帧后相邻帧可能同页，按像素差去掉重复
        kept_indices: list[int]
        if len(paths) > 1 and scene_duplicate_threshold > 0:
            kept_indices = [0]
            for i in range(1, len(paths)):
                cur = cv2.imread(str(paths[i]))
                prev = cv2.imread(str(paths[kept_indices[-1]]))
                if cur is None or prev is None:
                    kept_indices.append(i)
                    continue
                diff = cv2.absdiff(
                    cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY),
                    cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY),
                )
                if np.mean(diff) >= scene_duplicate_threshold:
                    kept_indices.append(i)
            if len(kept_indices) != len(paths):
                _log(f"连续去重后保留 {len(kept_indices)} 帧。")
            paths = [paths[j] for j in kept_indices]
        else:
            kept_indices = list(range(len(paths)))
        times_sec_final[:] = [times_sec[j] for j in kept_indices]

        out_ppt = output_dir / "slides_ppt_only.pdf"
        evp_utils.frames_to_pdf(paths, out_ppt)
        result["slides_ppt_only"] = out_ppt
        if output_pptx:
            evp_utils.frames_to_pptx(paths, output_dir / "slides_ppt_only.pptx")
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
        paths_full = evp_utils.extract_frames_at_times(
            video_full, times_sec_final, full_dir, progress_callback=_frame_progress
        )
        if paths_full:
            out_full = output_dir / "slides_full.pdf"
            evp_utils.frames_to_pdf(paths_full, out_full)
            result["slides_full"] = out_full
            if output_pptx:
                evp_utils.frames_to_pptx(paths_full, output_dir / "slides_full.pptx")
            if extract_images:
                img_dir = output_dir / "images_full"
                img_dir.mkdir(parents=True, exist_ok=True)
                for i, p in enumerate(paths_full, 1):
                    shutil.copy(p, img_dir / f"page_{i:03d}.png")
                result["images_full"] = img_dir

    return result
