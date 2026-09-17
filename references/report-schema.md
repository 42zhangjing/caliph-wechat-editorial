# Report JSON Schema

`render_editorial.py` 接收一份已经完成编辑的 `report.json`。它不读取微信数据库，也不负责判断事实；内容由模型依据规范化素材包写入。

最小结构：

```json
{
  "kind": "daily",
  "group_name": "群名",
  "period": {"start": "2026-09-16", "end": "2026-09-16"},
  "edition": "第 001 期",
  "masthead": {
    "kicker": "GROUP EDITORIAL",
    "title": "群名编辑部",
    "subtitle": "当日现场记录"
  },
  "lead": {
    "title": "一个具体、可追溯的头条",
    "dek": "一句解释为什么值得读的副标题",
    "body": "100—180 字开场",
    "tags": ["AI", "争议"]
  },
  "sections": [
    {
      "eyebrow": "09:20 · FIELD NOTE",
      "title": "故事节点标题",
      "body": "150—250 字故事正文",
      "tone": "ink",
      "quotes": [
        {"text": "素材中的短原话", "speaker": "群友", "time": "09:24"}
      ]
    }
  ],
  "people": [
    {"name": "群友", "role": "提问者", "count": 12, "note": "本期贡献"}
  ],
  "stats": [
    {"value": "550", "label": "条消息"},
    {"value": "18", "label": "位发言者"}
  ],
  "closing": {
    "title": "留下的问题",
    "body": "一个真实的未决问题或编辑收束"
  }
}
```

## 字段规则

- `kind` 只能是 `daily` 或 `weekly`。
- `period` 必须与素材范围一致。
- `sections` 按阅读顺序排列；日报建议 3—6 个，周报建议 4—7 个。
- `quotes` 只放可在 source JSON 中逐字定位的短引用；没有可靠原话时留空。
- `people` 是本期角色卡，不是长期人格档案；`count` 可省略。
- `stats` 最多 6 项，只放与叙事有关的真实数字。
- 所有 HTML 特殊字符由渲染器转义；不要在字段中注入脚本。

## 头像

头像是可选的本地增强层，不写进 `report.json` 也可以使用首字占位。需要展示真实头像时，先用 `scripts/extract_avatars.py` 从已解密的 `head_image.db` 导出私有 `avatars/avatars.json` 和可选的 `avatars/group-avatar.jpg`，再把人物清单传给渲染器的 `--avatars` 参数、把群头像传给 `--group-avatar`。清单只保存显示名到本地图片路径的映射，不应进入 Git、云盘或对话正文。

## 分页

如需 A3 多页，在顶层增加：

```json
"pages": [
  {"label": "第 1 版", "section_indices": [0, 1]},
  {"label": "第 2 版", "section_indices": [2, 3], "append_people": true}
]
```

`append_people` 用于指定人物卡、统计栏和编辑手记附在某一页；省略时默认附在最后一页。没有 `pages` 时，渲染器输出适合屏幕阅读的单页长文；有 `pages` 时，按页输出 A3 版式。每页应有 1—3 个故事节点，不要为凑页数重复内容。
