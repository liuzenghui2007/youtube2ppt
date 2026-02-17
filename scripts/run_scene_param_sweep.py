#!/usr/bin/env python3
"""
无头跑多组场景检测参数，每组结果写入独立子目录，便于对比。
用法（在项目根下）：
  python scripts/run_scene_param_sweep.py
  python scripts/run_scene_param_sweep.py --video-dir ./video_output --out-base ./ppt_output/param_sweep
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证可导入 ppt_pipeline
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="多组场景参数无头提取，结果分目录存放")
    parser.add_argument(
        "--video-dir",
        type=Path,
        default=PROJECT_ROOT / "video_output",
        help="视频目录，内含 video.mp4",
    )
    parser.add_argument(
        "--out-base",
        type=Path,
        default=PROJECT_ROOT / "ppt_output" / "param_sweep",
        help="所有跑结果的基础目录，每组一个子目录",
    )
    parser.add_argument(
        "--crop",
        default="",
        help='裁剪 "left,top,width,height"，不传则用 config.json',
    )
    args = parser.parse_args()

    from ppt_pipeline import load_config, run_crop, run_extract, parse_crop

    cfg = load_config(PROJECT_ROOT)
    video_dir = args.video_dir.resolve()
    out_base = args.out_base.resolve()
    video_full = video_dir / "video.mp4"
    video_cropped = video_dir / "video_cropped.mp4"

    if not video_full.is_file():
        print("错误：未找到视频文件", video_full, file=sys.stderr)
        print("请先下载视频或指定 --video-dir", file=sys.stderr)
        sys.exit(1)

    if args.crop:
        crop = parse_crop(args.crop)
    else:
        crop = (
            float(cfg.get("crop_left", 0.35)),
            float(cfg.get("crop_top", 0)),
            float(cfg.get("crop_width", 0.65)),
            float(cfg.get("crop_height", 1.0)),
        )

    out_base.mkdir(parents=True, exist_ok=True)
    if not video_cropped.is_file():
        print("正在裁剪视频…")
        run_crop(video_full, video_dir, crop, force=False)

    # 多组参数：(子目录名, threshold, min_scene_len, static, duplicate, min_gap, max_gap_sec, interval_fill_sec)
    param_sets = [
        ("01_default", 12.0, 5, 2.0, 1.5, 0.5, 45.0, 15.0),
        ("02_sensitive", 8.0, 3, 0.0, 0.0, 0.5, 45.0, 15.0),
        ("03_medium", 10.0, 5, 0.0, 0.0, 0.5, 45.0, 15.0),
        ("04_low_filter", 12.0, 5, 0.0, 0.0, 0.5, 45.0, 15.0),
        ("05_conservative", 18.0, 8, 5.0, 3.0, 1.0, 0.0, 15.0),
        ("06_very_sensitive", 6.0, 3, 0.0, 0.0, 0.3, 45.0, 15.0),
        ("07_fill_aggressive", 10.0, 5, 0.0, 0.0, 0.5, 30.0, 10.0),
        ("08_no_fill", 10.0, 5, 0.0, 0.0, 0.5, 0.0, 15.0),
    ]

    def progress_cb(msg: str) -> None:
        print("  ", msg)

    results: list[tuple[str, int, str]] = []

    for i, (name, th, min_len, static, dup, gap, max_gap, fill_intv) in enumerate(param_sets, 1):
        run_dir = out_base / name
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[{i}/{len(param_sets)}] {name}  th={th} min={min_len} static={static} dup={dup} gap={gap} max_gap={max_gap} fill={fill_intv}")
        try:
            run_extract(
                run_dir,
                video_full,
                video_cropped if video_cropped.is_file() else None,
                crop,
                float(cfg.get("similarity", 0.45)),
                cfg.get("start_time", "") or "",
                cfg.get("end_time", "") or "",
                True,
                False,
                True,
                True,
                PROJECT_ROOT,
                progress_callback=progress_cb,
                extract_method="scenedetect",
                scene_threshold=th,
                scene_min_scene_len=min_len,
                scene_static_threshold=static,
                scene_duplicate_threshold=dup,
                scene_min_gap=gap,
                scene_max_gap_sec=max_gap,
                scene_interval_fill_sec=fill_intv,
            )
            # 统计帧数
            frames_dir = run_dir / "frames_scenedetect"
            images_dir = run_dir / "images_ppt_only"
            if frames_dir.is_dir():
                count = len(list(frames_dir.glob("*.png")))
            elif images_dir.is_dir():
                count = len(list(images_dir.glob("page_*.png")))
            else:
                count = 0
            results.append((name, count, str(run_dir)))
            print(f"  -> 共 {count} 帧，结果目录: {run_dir}")
        except Exception as e:
            results.append((name, -1, f"错误: {e}"))
            print(f"  -> 失败: {e}")

    print("\n" + "=" * 60)
    print("汇总（按帧数排序，便于对比）")
    print("=" * 60)
    for name, count, path in sorted(results, key=lambda x: (-x[1] if x[1] >= 0 else -999)):
        status = str(count) if count >= 0 else "失败"
        print(f"  {name}: {status} 帧  -> {path}")
    print("\n全部结果目录:", out_base)

if __name__ == "__main__":
    main()
