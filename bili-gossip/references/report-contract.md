# 报告数据契约

渲染器读取UTF-8 JSON。未提供的可选模块会自动隐藏。

```json
{
  "event": {
    "title": "事件标题",
    "category": "综艺心理学",
    "source_label": "全网整理",
    "report_note": "",
    "occurred_at": "2026-06-01",
    "generated_at": "2026-07-16T11:36:00+08:00",
    "heat_label": "",
    "heat_source": {
      "name": "热榜或搜索热度来源",
      "url": "https://example.com/hot"
    },
    "summary": "不超过50字的已确认事实摘要"
  },
  "timeline": [
    {
      "date": "2026-06-01",
      "text": "已确认事件节点",
      "important": true,
      "sources": [
        {
          "name": "来源名称",
          "url": "https://example.com",
          "type": "official|first_party|authoritative_media|portal|weibo_factcheck|douyin_truth|bilibili|social",
          "is_primary": false
        }
      ]
    }
  ],
  "evidence_videos": [
    {
      "avid": 1,
      "bvid": "BV...",
      "title": "视频标题",
      "up_name": "UP主",
      "cover": "https://...",
      "url": "https://www.bilibili.com/video/BV...",
      "timestamp": "",
      "description": "根据公开视频标题、简介和页面信息整理的相关性说明",
      "play": 300000,
      "duration_seconds": 180,
      "public_web": true
    }
  ],
  "lesson_videos": [],
  "install_command": "请从 https://github.com/jiubanszd/bili-gossip-skill/tree/main/bili-gossip 安装 bili-gossip Skill。"
}
```

`is_primary`只用于官方机构、当事人或工作室的一手原文。普通事实节点需要至少两个不同域名的有效来源；`heat_label`没有`heat_source.url`时会被校验脚本删除。

时间字段按以下语义填写：`generated_at`是报告实际生成时间；`timeline[].date`是各事实节点的发生日期；`occurred_at`优先表示引发本轮讨论的核心事件或触发点日期，不要默认填写人物履历的最早日期。无法识别单一触发点时可以省略`occurred_at`，并按旧闻考古或背景复盘组织内容。时间线选点关注近期讨论但不强制包含当前年份，也不按固定时间窗口凑节点。

`cover`优先填写B站公开视频页`og:image`中的`https`原图URL。Agent未能直接取得时，先运行`enrich_public_video_metadata.py`补齐；请求失败允许为空，由模板显示占位图。封面缺失不影响事实节点，也不应导致已满足其他门槛的视频被删除。

## 报告整理规则

- `prepare_web_only.py`会清空`opinions`、`danmaku`及相关互动量，并删除所有视频时间戳。
- 视频必须具有真实B站视频链接、`bvid`和标题；低于30万播放或短于2分钟且数据明确时直接删除。
- 公开页面无法确认播放量或时长时允许保留视频入口并输出警告，不把未确认数据写成确定事实。
