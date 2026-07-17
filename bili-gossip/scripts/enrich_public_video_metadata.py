#!/usr/bin/env python3
"""Fill missing Bilibili video covers from public video-page metadata."""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
)
VIDEO_GROUPS = ("evidence_videos", "lesson_videos")
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(r"([:\w-]+)\s*=\s*([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)
VALID_BVID_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")


def normalize_cover_url(value: str) -> str:
    value = html.unescape(value or "").strip()
    if value.startswith("//"):
        value = "https:" + value
    elif value.startswith("http://"):
        value = "https://" + value[len("http://") :]
    if not value.startswith("https://"):
        return ""
    if ".hdslb.com/" in value:
        value = value.split("@", 1)[0]
    return value


def extract_cover_from_html(page_html: str) -> str:
    for tag in META_TAG_RE.findall(page_html or ""):
        attrs = {name.lower(): value for name, _, value in ATTR_RE.findall(tag)}
        if attrs.get("property", "").lower() == "og:image":
            return normalize_cover_url(attrs.get("content", ""))
    return ""


def fetch_public_video_page(url: str, timeout: float = 12.0) -> str:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com/"},
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
        if "gzip" in (response.headers.get("Content-Encoding") or "").lower():
            body = gzip.decompress(body)
        return body.decode("utf-8", errors="replace")


def enrich_video(
    video: dict[str, Any],
    fetcher: Callable[[str], str] = fetch_public_video_page,
) -> tuple[dict[str, Any], str]:
    enriched = dict(video)
    existing = normalize_cover_url(str(enriched.get("cover") or ""))
    if existing:
        enriched["cover"] = existing
        return enriched, ""

    bvid = str(enriched.get("bvid") or "").strip()
    if not VALID_BVID_RE.fullmatch(bvid):
        return enriched, "cover not fetched because bvid is missing or invalid"

    page_url = f"https://www.bilibili.com/video/{bvid}/"
    try:
        cover = extract_cover_from_html(fetcher(page_url))
    except Exception as exc:  # Network failures must not block report generation.
        return enriched, f"cover request failed for {bvid}: {exc}"
    if not cover:
        return enriched, f"public page metadata has no cover for {bvid}"

    enriched["cover"] = cover
    return enriched, ""


def enrich_report(report: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    enriched = dict(report)
    warnings: list[str] = []
    for group_name in VIDEO_GROUPS:
        output_videos = []
        for index, video in enumerate(report.get(group_name) or [], start=1):
            if not isinstance(video, dict):
                output_videos.append(video)
                warnings.append(f"{group_name} video {index} is not an object")
                continue
            output_video, warning = enrich_video(video)
            output_videos.append(output_video)
            if warning:
                warnings.append(f"{group_name} video {index}: {warning}")
        enriched[group_name] = output_videos
    return enriched, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从B站公开视频页补齐视频封面")
    parser.add_argument("--input", required=True, help="报告JSON路径")
    parser.add_argument("--output", required=True, help="补齐封面后的JSON路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    report = json.loads(input_path.read_text(encoding="utf-8"))
    enriched, warnings = enrich_report(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output_path), "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
