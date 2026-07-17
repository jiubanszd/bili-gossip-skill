#!/usr/bin/env python3
"""Render a V2 deep-gossip report from structured JSON."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import tempfile
import webbrowser
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "report_template.html"
TV_LOGO_PATH = ROOT.parent / "assets" / "tv-logo.png"


def image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        parsed_date = parse_date(text)
        return datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None


def short_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_number(value: Any) -> str:
    number = to_int(value)
    if number >= 100_000_000:
        return f"{number / 100_000_000:.1f}亿"
    if number >= 10_000:
        return f"{number / 10_000:.1f}万"
    return str(number)


def freshness(event_date: date | None, updated_date: date) -> tuple[str, str]:
    if event_date and (updated_date - event_date).days <= 30:
        return "新瓜", "status-new"
    return "旧瓜", "status-old"


def normalize_percentages(opinions: dict[str, Any]) -> tuple[int, int, int]:
    values = [
        max(0.0, float(opinions.get("support", 0) or 0)),
        max(0.0, float(opinions.get("neutral", 0) or 0)),
        max(0.0, float(opinions.get("oppose", 0) or 0)),
    ]
    total = sum(values)
    if total <= 0:
        return 0, 0, 0
    support = round(values[0] * 100 / total)
    neutral = round(values[1] * 100 / total)
    oppose = 100 - support - neutral
    return support, neutral, oppose


def render_sources(sources: list[dict[str, Any]]) -> str:
    items = []
    for source in sources:
        name = esc(source.get("name") or "查看来源")
        url = esc(source.get("url"))
        if url:
            items.append(f'<a class="source" href="{url}" target="_blank" rel="noreferrer">{name} ↗</a>')
        else:
            items.append(f'<span class="source">{name}</span>')
    return "".join(items)


def section_heading(title: str) -> str:
    return (
        '<h2 class="section-title">'
        '<span class="tv-badge" aria-hidden="true">'
        '<span class="tv-label section-number"></span></span>'
        f'<span>{esc(title)}</span></h2>'
    )


def render_timeline(items: list[dict[str, Any]]) -> str:
    valid = [item for item in items if item.get("date") and item.get("text")]
    valid.sort(key=lambda item: str(item.get("date")))
    rows = []
    for item in valid[:6]:
        text = esc(item.get("text"))
        if item.get("important"):
            text = f"<strong>{text}</strong>"
        rows.append(
            '<div class="timeline-item">'
            '<span class="timeline-dot"></span>'
            f'<div class="timeline-date">{esc(item.get("date"))}</div>'
            f'<div class="timeline-text">{text}</div>'
            f'<div class="sources">{render_sources(item.get("sources") or [])}</div>'
            "</div>"
        )
    if not rows:
        return ""
    source_rich = sum(1 for item in valid[:6] if len(item.get("sources") or []) >= 2) >= 2
    if source_rich:
        variant = "source-heavy"
    elif len(valid) <= 3:
        variant = "compact"
    else:
        variant = "standard"
    return (
        f'<section class="section section--timeline timeline--{variant}">{section_heading("事情是这样的")}'
        f'<div class="timeline-shell"><div class="timeline">{"".join(rows)}</div></div></section>'
    )


def render_opinions(report: dict[str, Any]) -> str:
    metrics = report.get("metrics") or {}
    engagement = to_int(metrics.get("comment_count")) + to_int(metrics.get("danmaku_count"))
    opinions = report.get("opinions") or {}
    support, neutral, oppose = normalize_percentages(opinions)
    if engagement < 100 or support + neutral + oppose == 0:
        return ""

    if neutral >= 40:
        variant = "neutral"
    elif max(support, oppose) >= 70:
        variant = "dominant"
    else:
        variant = "balanced"

    cards = []
    sides = opinions.get("sides") or []
    for index, side in enumerate(sides[:2]):
        tone = "support" if index == 0 else "oppose"
        arguments = "".join(f"<li>{esc(arg)}</li>" for arg in (side.get("arguments") or [])[:3])
        if arguments:
            cards.append(
                f'<div class="argument-card {tone}"><h3>{esc(side.get("label"))}</h3>'
                f"<ul>{arguments}</ul></div>"
            )
    return (
        f'<section class="section section--opinions opinion--{variant}">{section_heading("观点阵营")}'
        f'<div class="focus"><div class="focus-label">争议焦点</div><p>{esc(opinions.get("focus"))}</p></div>'
        '<div class="stance-labels">'
        f'<span class="support">支持 {support}%</span><span class="neutral">中立 {neutral}%</span>'
        f'<span class="oppose">质疑 {oppose}%</span></div>'
        '<div class="stance-bar" aria-label="观点阵营占比">'
        f'<div class="stance-support" style="width:{support}%"></div>'
        f'<div class="stance-neutral" style="width:{neutral}%"></div>'
        f'<div class="stance-oppose" style="width:{oppose}%"></div></div>'
        f'<div class="argument-grid">{"".join(cards)}</div>'
        f'<div class="data-note">数据来源：UP主立场60% + 高赞评论/弹幕情绪40%，样本互动量 {engagement}</div>'
        "</section>"
    )


def render_danmaku(report: dict[str, Any]) -> str:
    total = to_int((report.get("metrics") or {}).get("danmaku_count"))
    items = sorted(report.get("danmaku") or [], key=lambda item: to_int(item.get("likes")), reverse=True)[:5]
    if total < 50 or not items:
        return ""
    contents = [str(item.get("content") or "") for item in items]
    if len(items) == 3:
        variant = "rank"
    elif len(items) >= 4 and max((len(item) for item in contents), default=0) <= 22:
        variant = "grid"
    else:
        variant = "long"
    rows = "".join(
        '<div class="danmaku-item">'
        f'<span class="danmaku-likes">{format_number(item.get("likes"))} 赞</span>'
        f'<span class="danmaku-content">「{esc(item.get("content"))}」</span></div>'
        for item in items
        if item.get("content")
    )
    if not rows:
        return ""
    return (
        f'<section class="section section--danmaku danmaku--{variant}">{section_heading("弹幕神了")}'
        f'<div class="danmaku-list">{rows}</div></section>'
    )


def video_identity(video: dict[str, Any]) -> str:
    return str(video.get("bvid") or video.get("avid") or video.get("url") or "")


def render_video_card(video: dict[str, Any], lesson: bool = False) -> str:
    cover = esc(video.get("cover"))
    cover_html = (
        f'<img src="{cover}" alt="" loading="eager" referrerpolicy="no-referrer">'
        if cover
        else '<div class="video-cover-fallback">封面</div>'
    )
    timestamp = short_text(video.get("timestamp"), 32)
    kicker = "延展补课"
    if not lesson:
        if video.get("public_web"):
            kicker = "查看视频"
        else:
            kicker = f"原片 {timestamp}" if timestamp else "查看原片"
    meta = [f'UP主 @{esc(video.get("up_name"))}' if video.get("up_name") else ""]
    if video.get("play") is not None:
        meta.append(f'播放 {format_number(video.get("play"))}')
    return (
        f'<a class="video-card" href="{esc(video.get("url"))}" target="_blank" rel="noreferrer">'
        f'<div class="video-cover">{cover_html}<span class="play-button">▶</span></div>'
        '<div class="video-body">'
        f'<div class="video-kicker">{esc(kicker)}</div>'
        f'<div class="video-title">{esc(video.get("title"))}</div>'
        f'<div class="video-description">{esc(video.get("description"))}</div>'
        f'<div class="video-meta">{"".join(f"<span>{item}</span>" for item in meta if item)}</div>'
        "</div></a>"
    )


def render_videos(report: dict[str, Any]) -> tuple[str, str]:
    evidence = [item for item in (report.get("evidence_videos") or []) if item.get("url") and item.get("title")][:3]
    evidence_ids = {video_identity(item) for item in evidence}
    lessons = [
        item for item in (report.get("lesson_videos") or [])
        if item.get("url") and item.get("title") and video_identity(item) not in evidence_ids
    ][:3]

    evidence_html = ""
    if evidence:
        evidence_variant = {1: "single", 2: "double"}.get(len(evidence), "stacked")
        cards = "".join(render_video_card(item) for item in evidence)
        evidence_html = (
            f'<section class="section section--videos video--{evidence_variant}">{section_heading("互联网有记忆哦")}'
            f'<div class="video-list">{cards}</div></section>'
        )

    lesson_html = ""
    if len(lessons) >= 2:
        lesson_variant = "double" if len(lessons) == 2 else "stacked"
        cards = "".join(render_video_card(item, lesson=True) for item in lessons)
        lesson_html = (
            f'<section class="section section--videos lesson video--{lesson_variant}">{section_heading("来阿B补课")}'
            '<p class="data-note">顺着人物和事件继续扒，以下视频与证据模块不重复。</p>'
            f'<div class="video-list">{cards}</div></section>'
        )
    return evidence_html, lesson_html


def render_header(report: dict[str, Any]) -> str:
    event = report.get("event") or {}
    generated = parse_datetime(event.get("generated_at")) or datetime.now().astimezone()
    occurred = parse_date(event.get("occurred_at"))
    status, status_class = freshness(occurred, generated.date())
    heat = short_text(event.get("heat_label"), 16)
    heat_html = f'<span class="status-pill heat">{esc(heat)}</span>' if heat else ""
    summary = short_text(event.get("summary"), 50)
    summary_html = (
        '<div class="summary"><div class="summary-title">省流版</div>'
        f"<p>{esc(summary)}</p></div>"
        if summary else ""
    )
    source_label = short_text(event.get("source_label"), 16) or "UP主深扒"
    return (
        '<header>'
        '<div class="tag-row"><span class="brand-tv" aria-hidden="true">'
        '<span class="tv-label">瓜</span></span><span class="tag tag-brand">深度吃瓜</span>'
        f'<span class="tag tag-source">{esc(source_label)}</span>'
        f'<span class="tag tag-category">{esc(event.get("category") or "热点事件")}</span></div>'
        '<div class="title-line">'
        f'<h1>{esc(event.get("title") or "深度吃瓜报告")}</h1>'
        f'<span class="status-pill {status_class}">{status}</span>{heat_html}</div>'
        f'<div class="updated">报告生成于 {generated.strftime("%Y-%m-%d %H:%M")}</div>{summary_html}</header>'
    )


def render_fallback() -> str:
    return (
        f'<section class="section section--fallback">{section_heading("瓜还没熟")}'
        '<div class="fallback">'
        '<div class="fallback-title">瓜还没熟，别急。</div>'
        '<p>目前能确认的信息还不够，强行出报告等于端上生瓜蛋子。可以过几天再搜，或先把关键词存起来。</p>'
        "</div></section>"
    )


def render(report: dict[str, Any]) -> str:
    event = report.get("event") or {}
    timeline_html = render_timeline(report.get("timeline") or [])
    opinions_html = render_opinions(report)
    danmaku_html = render_danmaku(report)
    evidence_html, lesson_html = render_videos(report)
    body_sections = timeline_html + opinions_html + danmaku_html + evidence_html + lesson_html
    if not timeline_html:
        body_sections = render_fallback()

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    default_install_command = (
        "请从 https://github.com/jiubanszd/bili-gossip-skill/tree/main/"
        "bili-gossip 安装 bili-gossip Skill。"
    )
    install_command = (
        report.get("install_command")
        or os.getenv("BILI_SKILL_INSTALL_COMMAND")
        or default_install_command
    )
    report_note = short_text(event.get("report_note"), 80)
    replacements = {
        "{{PAGE_TITLE}}": esc(event.get("title") or "深度吃瓜报告"),
        "{{TV_LOGO_DATA_URI}}": image_data_uri(TV_LOGO_PATH),
        "{{REPORT_NOTE}}": esc(report_note),
        "{{CONTENT}}": render_header(report) + body_sections,
        "{{COPY_DISABLED}}": "" if install_command else "disabled",
        "{{COPY_LABEL}}": "复制安装口令" if install_command else "安装口令待接入",
        "{{INSTALL_COMMAND}}": json.dumps(install_command, ensure_ascii=False),
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template


def main() -> int:
    parser = argparse.ArgumentParser(description="生成深度吃瓜V2 HTML报告")
    parser.add_argument("--input", type=Path, required=True, help="UTF-8报告JSON路径")
    parser.add_argument("--output", type=Path, help="输出HTML路径")
    parser.add_argument("--open", action="store_true", help="生成后在默认浏览器打开")
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8-sig"))

    output = args.output or Path(tempfile.gettempdir()) / f"bili-gossip-v2-{int(datetime.now().timestamp())}.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(report), encoding="utf-8")
    if args.open:
        webbrowser.open(output.resolve().as_uri())
    print(json.dumps({"html": str(output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
