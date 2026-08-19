#!/usr/bin/env python3
"""Validate and normalize the public-web portion of a gossip report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PRIMARY_SOURCE_TYPES = {"official", "first_party"}
THREE_PART_SUFFIXES = {"com.cn", "net.cn", "org.cn", "gov.cn"}


def compact_text(value: Any, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def iso_date(value: Any) -> str:
    text = str(value or "")[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def http_url(value: Any) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def source_domain(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = hostname.split(".")
    if len(parts) <= 2:
        return hostname
    suffix = ".".join(parts[-2:])
    return ".".join(parts[-3:]) if suffix in THREE_PART_SUFFIXES else suffix


def normalize_source(source: dict[str, Any]) -> dict[str, Any] | None:
    name = compact_text(source.get("name"), 40)
    url = http_url(source.get("url"))
    if not name or not url:
        return None
    source_type = compact_text(source.get("type"), 30) or "other"
    is_primary = bool(source.get("is_primary")) or source_type in PRIMARY_SOURCE_TYPES
    return {"name": name, "url": url, "type": source_type, "is_primary": is_primary}


def normalize_report(report: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    event = dict(report.get("event") or {})
    title = compact_text(event.get("title"), 80)
    if not title:
        raise ValueError("event.title is required")
    event["title"] = title
    event["category"] = compact_text(event.get("category"), 20) or "热点事件"
    event["summary"] = compact_text(event.get("summary"), 200)

    generated_at = compact_text(event.get("generated_at"))
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        generated_at = datetime.now().astimezone().isoformat(timespec="minutes")
        warnings.append("generated_at missing or invalid; renderer time was used")
    event["generated_at"] = generated_at

    occurred_at = iso_date(event.get("occurred_at"))
    if occurred_at:
        event["occurred_at"] = occurred_at
    else:
        event.pop("occurred_at", None)

    heat_label = compact_text(event.get("heat_label"), 16)
    heat_source = dict(event.get("heat_source") or {})
    heat_source_url = http_url(heat_source.get("url"))
    if heat_label and heat_source_url:
        event["heat_label"] = heat_label
        event["heat_source"] = {
            "name": compact_text(heat_source.get("name"), 40) or "热度来源",
            "url": heat_source_url,
        }
    else:
        if heat_label:
            warnings.append("heat_label removed because heat_source.url is missing")
        event.pop("heat_label", None)
        event.pop("heat_source", None)

    timeline: list[dict[str, Any]] = []
    for index, item in enumerate(report.get("timeline") or [], start=1):
        node_date = iso_date(item.get("date"))
        text = compact_text(item.get("text"), 300)
        sources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for raw_source in item.get("sources") or []:
            source = normalize_source(raw_source)
            if source and source["url"] not in seen_urls:
                sources.append(source)
                seen_urls.add(source["url"])

        independent_domains = {source_domain(source["url"]) for source in sources}
        has_primary = any(source["is_primary"] for source in sources)
        if not node_date or not text:
            warnings.append(f"timeline node {index} removed because date or text is missing")
            continue
        if not has_primary and len(independent_domains) < 2:
            warnings.append(f"timeline node {index} removed because it lacks two independent sources")
            continue
        timeline.append({
            "date": node_date,
            "text": text,
            "important": bool(item.get("important")),
            "sources": sources,
        })

    timeline.sort(key=lambda item: item["date"])
    if len(timeline) > 6:
        warnings.append("timeline limited to six verified nodes")
    if not timeline and event.get("summary"):
        event["summary"] = ""
        warnings.append("summary removed because no verified timeline nodes remain")
    normalized = dict(report)
    normalized["event"] = event
    normalized["timeline"] = timeline[:6]
    return normalized, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="校验并整理深度吃瓜公开Web模块")
    parser.add_argument("--input", type=Path, required=True, help="Agent生成的UTF-8报告JSON")
    parser.add_argument("--output", type=Path, required=True, help="校验后的UTF-8报告JSON")
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8-sig"))
    normalized, warnings = normalize_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
