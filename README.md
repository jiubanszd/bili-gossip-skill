# 深度吃瓜 Skill

输入明星或艺人名字，自动生成可溯源的"深度吃瓜"HTML报告，聚合B站相关视频入口。

当前版本：**v3.0.0**

## 功能

- 并行采集5个数据源（B站搜索、弹幕、网页、UP主元数据、热搜趋势），5分钟内完成
- 7板块报告骨架：省流版、事情是这样的、观点阵营、弹幕神了、互联网有记忆哦、来阿B补课、安装指引
- 视频加权筛选：花名/CP名/拼音变体扩展检索，考古与补课板块互斥去重
- 数据不足时输出兜底文案，不跳过板块
- 响应式HTML输出，移动端适配

## 安装

需要 Node.js 18 或更高版本。在终端运行以下命令；也可以让支持终端操作的 Agent 代为执行：

```shell
npx skills add https://github.com/jiubanszd/bili-gossip-skill/tree/main/bili-gossip -g -y
```

装好后直接输入想问的瓜，即可生成吃瓜报告。

## 使用示例

```
白鹿
鹿晗 关晓彤
杨紫 宋丹丹 综艺争议
```

单个姓名生成人物近况复盘，两个姓名生成双方关系与互动复盘，多人围绕共同事件梳理。

## 环境要求

| 依赖 | 版本 |
|------|------|
| Node.js | 18+ |
| Python | 3.10+ |

Python 脚本仅用于报告渲染，无需额外安装第三方包。

## 文件结构

```
bili-gossip/
├── SKILL.md                          # Agent 指令主文件
├── assets/
│   └── tv-logo.png
├── references/
│   ├── product-rules.md              # 产品规则与板块写作指引
│   └── report-contract.md            # 报告数据契约
└── scripts/
    ├── enrich_public_video_metadata.py
    ├── prepare_web_only.py
    ├── render_report.py
    ├── report_template.html
    └── validate_report.py
```

## License

MIT
