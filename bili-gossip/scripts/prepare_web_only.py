#!/usr/bin/env python3
"""Prepare a public-web-only entertainment report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from validate_report import compact_text, normalize_report


BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]+", re.IGNORECASE)


def to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def bilibili_video_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not hostname.endswith("bilibili.com"):
        return ""
    return url if "/video/" in parsed.path else ""


def normalize_public_video(video: dict[str, Any], index: int, warnings: list[str]) -> dict[str, Any] | None:
    title = compact_text(video.get("title"), 80)
    url = bilibili_video_url(video.get("url"))
    bvid = compact_text(video.get("bvid"), 24)
    if not bvid:
        match = BVID_PATTERN.search(url)
        bvid = match.group(0) if match else ""
    if not title or not url or not bvid:
        warnings.append(f"public video {index} removed because title, Bilibili URL or bvid is missing")
        return None

    play = to_int(video.get("play"))
    duration = to_int(video.get("duration_seconds"))
    if play and play < 300_000:
        warnings.append(f"public video {index} removed because play count is below 300000")
        return None
    if duration and duration < 120:
        warnings.append(f"public video {index} removed because duration is below 120 seconds")
        return None
    if not play:
        warnings.append(f"public video {index} kept but play count could not be verified")
    if not duration:
        warnings.append(f"public video {index} kept but duration could not be verified")

    return {
        "avid": to_int(video.get("avid")),
        "bvid": bvid,
        "title": title,
        "up_name": compact_text(video.get("up_name"), 40),
        "cover": str(video.get("cover") or "").strip(),
        "url": url,
        "timestamp": "",
        "description": compact_text(video.get("description"), 90),
        "play": play or None,
        "duration_seconds": duration or None,
        "public_web": True,
    }


def prepare_web_only(report: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized, warnings = normalize_report(report)
    event = normalized["event"]
    event["source_label"] = "全网整理"
    event["report_note"] = ""

    normalized["metrics"] = {"comment_count": 0, "danmaku_count": 0}
    normalized["opinions"] = {}
    normalized["danmaku"] = []

    evidence: list[dict[str, Any]] = []
    for index, raw_video in enumerate(report.get("evidence_videos") or [], start=1):
        video = normalize_public_video(raw_video, index, warnings)
        if video:
            evidence.append(video)
    normalized["evidence_videos"] = evidence[:3]

    evidence_ids = {video["bvid"].lower() for video in normalized["evidence_videos"]}
    lessons: list[dict[str, Any]] = []
    for index, raw_video in enumerate(report.get("lesson_videos") or [], start=1):
        video = normalize_public_video(raw_video, index, warnings)
        if video and video["bvid"].lower() not in evidence_ids:
            lessons.append(video)
    normalized["lesson_videos"] = lessons[:3]
    return normalized, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="生成公开Web版娱乐复盘报告JSON")
    parser.add_argument("--input", type=Path, required=True, help="Agent Web搜索生成的JSON")
    parser.add_argument("--output", type=Path, required=True, help="公开Web版报告JSON")
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8-sig"))
    prepared, warnings = prepare_web_only(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(prepared, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
