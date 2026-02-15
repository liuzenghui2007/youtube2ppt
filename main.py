#!/usr/bin/env python3
"""入口：默认启动 GUI；可选 --cli 跑命令行（下载/预览/提取）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube 视频提取 PPT")
    parser.add_argument("--cli", action="store_true", help="使用命令行模式（否则启动 GUI）")
    parser.add_argument("--download", action="store_true", help="仅执行下载")
    parser.add_argument("--preview", action="store_true", help="仅执行裁剪预览（需已下载且指定 crop）")
    parser.add_argument("--extract", action="store_true", help="仅执行提取")
    parser.add_argument("-u", "--url", default="", help="视频 URL（与 config 二选一）")
    parser.add_argument("-o", "--output-dir", default="", help="PPT/输出目录（默认用 config）")
    parser.add_argument("-v", "--video-dir", default="", help="视频目录（默认用 config 或与 output-dir 一致）")
    parser.add_argument("--crop", default="", help='裁剪比例 "left,top,width,height" 如 0.35,0,0.65,1')
    args = parser.parse_args()

    if not args.cli:
        from gui.app import run_app
        run_app()
        return

    # CLI
    project_root = Path(__file__).resolve().parent
    from ppt_pipeline import load_config, run_download, run_crop, run_preview_frames, parse_crop, run_extract

    cfg = load_config(project_root)
    url = args.url or cfg.get("url", "")
    output_dir = Path(args.output_dir or cfg.get("output_dir", "./ppt_output")).resolve()
    video_dir = Path(args.video_dir or cfg.get("video_dir") or cfg.get("output_dir", "./video_output")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    if args.download:
        if not url:
            print("请提供 -u/--url 或在 config 中设置 url", file=sys.stderr)
            sys.exit(1)
        run_download(
            url, video_dir,
            force=cfg.get("force_download"),
            project_root=project_root,
            cookies_from_browser=cfg.get("cookies_from_browser") or None,
            cookies_file=cfg.get("cookies_file") or None,
            js_runtime=cfg.get("ytdlp_js_runtime") or None,
            remote_components=cfg.get("ytdlp_remote_components") or None,
        )
        print("下载完成:", video_dir / "video.mp4")

    crop = None
    if args.crop or (cfg.get("crop_left") is not None and cfg.get("crop_width", 0) > 0):
        if args.crop:
            crop = parse_crop(args.crop)
        else:
            crop = (
                float(cfg.get("crop_left", 0)),
                float(cfg.get("crop_top", 0)),
                float(cfg.get("crop_width", 1)),
                float(cfg.get("crop_height", 1)),
            )

    if args.preview:
        video_path = video_dir / "video.mp4"
        if not video_path.is_file():
            print("请先执行下载", file=sys.stderr)
            sys.exit(1)
        if not crop:
            print("请提供 --crop 或在 config 中设置 crop_*", file=sys.stderr)
            sys.exit(1)
        run_crop(video_path, video_dir, crop, force=cfg.get("force_crop"))
        paths = run_preview_frames(video_path, output_dir, crop)
        print("预览已生成:", [str(p) for p in paths])

    if args.extract:
        video_full = video_dir / "video.mp4"
        video_cropped = video_dir / "video_cropped.mp4"
        if not video_full.is_file():
            print("请先执行下载", file=sys.stderr)
            sys.exit(1)
        if not crop:
            crop = (0, 0, 1, 1)
        if not video_cropped.is_file():
            run_crop(video_full, video_dir, crop, force=cfg.get("force_crop"))
        run_extract(
            output_dir,
            video_full,
            video_cropped if video_cropped.is_file() else None,
            crop,
            float(cfg.get("similarity", 0.45)),
            cfg.get("start_time", "") or "",
            cfg.get("end_time", "") or "",
            bool(cfg.get("output_ppt_only", True)),
            bool(cfg.get("output_full_screen", False)),
            bool(cfg.get("extract_images", True)),
            project_root,
        )
        print("提取完成，见", output_dir)


if __name__ == "__main__":
    main()
