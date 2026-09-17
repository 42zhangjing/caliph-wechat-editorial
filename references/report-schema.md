# Report JSON Schema

`render_editorial.py` 接收已经完成编辑的 `report.json`。它不读取微信数据库；内容由模型依据 `source-normalized.json` 写入，并在渲染前由 `validate_report.py` 审核。

推荐结构：

```json
{
  "kind": "daily",
  "style": "normal",
  "group_name": "群名",
  "period": {"start": "2026-09-17", "end": "2026-09-17"},
  "edition": "第 001 期 · 日报",
  "layout": {"page_mode": "auto"},
  "brand": {
    "logo": "https://caliph.chengyu.dev/brand/caliph.svg"
  },
  "masthead": {
    "kicker": "DAILY GROUP EDITORIAL",
    "title": "群名编辑部",
    "subtitle": "2026 年 9 月 17 日现场记录"
  },
  "lead": {
    "kicker": "今日主线 · 09.17",
    "title": "一个具体、可追溯的头条",
    "dek": "一句解释为什么值得读的副标题",
    "body": "100—220 字开场",
    "tags": ["AI", "产品"],
    "image": "/optional/local/image.jpg",
    "image_alt": "可选图说"
  },
  "sections": [
    {
      "eyebrow": "09:20 · FIELD NOTE",
      "title": "故事节点标题",
      "body": "140—320 字故事正文",
      "tone": "ink",
      "priority": "major",
      "evidence": "group_observation",
      "quotes": [
        {"text": "素材中的短原话", "speaker": "群友", "time": "09:24"}
      ],
      "image": "/optional/local/story-image.jpg",
      "image_alt": "可选图说"
    }
  ],
  "people": [
    {"name": "群友", "role": "提问 / 查证", "count": 12, "note": "本期贡献"}
  ],
  "stats": [
    {"value": "550", "label": "条消息"},
    {"value": "18", "label": "位发言者"}
  ],
  "closing": {
    "title": "留下的问题",
    "body": "一个真实的未决问题或编辑收束"
  },
  "footer": "本地素材编辑 · 群聊原话与编辑判断分离"
}
```

## 顶层字段

- `kind`：`daily` 或 `weekly`。
- `style`：`normal` 或 `roast`。省略时按 `normal`。
- `group_name`：真实显示群名；输出目录和文件名会使用其清理后的版本。
- `period`：必须与素材范围一致。
- `edition`：可读期号，不参与文件名唯一性。
- `layout.page_mode`：默认 `auto`；只有人工指定页结构时使用 `manual`。
- `brand.logo`：可选品牌 Logo。省略时 renderer 默认使用 `https://caliph.chengyu.dev/brand/caliph.svg`，显示在每版页脚；它与群头像是两个独立层级。可改成本地 SVG/PNG 路径或其它公开品牌 URL。

## Brand

CALIPH Logo 代表出版品牌，群头像代表本期群聊来源。默认版式不会用 CALIPH Logo 替代群头像。

默认品牌地址：

```text
https://caliph.chengyu.dev/brand/caliph.svg
```

如果 `brand.logo` 指向本地文件，renderer 会复制到报告 assets 并改成相对路径。如果使用公开 `https://` URL，则保留公开品牌 URL；任何私人头像、群聊配图和本地素材仍必须本地化，不能暴露 `/Users/...` 路径。

品牌 Logo 默认小尺寸出现在页脚，承担签名作用，不与报头争夺视觉层级。

## Lead

- 第一版只渲染一次完整 Lead。
- 后续页面使用 compact masthead 和 continuation strip。
- 无 `lead.image` 时自动切换 text-only 版式，不保留空白图片栏。
- `lead.body` 建议 100—220 字；超过 420 字 validator 会给出警告。
- `tags` 控制在 2—5 个，写主题词，避免抽象价值标签。

## Sections

日报建议 3—6 个，周报建议 4—7 个。

每个 section：

- `eyebrow`：时间 + 短栏目，例如 `16:20 · HARDWARE`。
- `title`：具体标题。
- `body`：故事正文。
- `tone`：`ink` / `red` / `blue` / `accent`。
- `priority`：`major` / `minor`，供自动分页估算使用。
- `evidence`：主要证据等级，见下节。
- `quotes`：只放能在 `source-normalized.json` 中逐字定位的短引用。
- `image` / `image_alt`：可选本地图片。renderer 会复制到 HTML 自己的 assets 目录并改写成相对路径。

故事编号由原始 section 顺序决定并跨页连续，不在 JSON 中重复维护 `01/02/03`。

## Evidence

`evidence` 只能使用：

- `direct_quote`：故事核心由可定位原话直接支持。
- `group_observation`：对聊天过程的编辑概括。
- `linked_claim`：来自群内分享的链接、转述、截图文字等，本次未完成外部核验。
- `externally_verified`：本次明确完成外部核验。
- `editorial_inference`：编辑层面的结构推断，需要克制措辞。

如果一个 section 同时包含多种材料，填主要证据状态；正文中继续保留必要限定。

## Quotes

引用对象：

```json
{"text": "逐字原话", "speaker": "显示名", "time": "09:24"}
```

`validate_report.py --source source-normalized.json` 会用 `speaker + text` 做逐字回查，并优先用 `time` 缩小候选范围。找不到引用时验证失败。

不要为了让句子更顺而改写 `text`。需要润色时改成间接引语并从 `quotes` 移出。

## People

`people` 是本期角色卡，不建立长期人格结论。

- 推荐 4—8 人。
- `role` 写本期承担的动作或位置，如“资料投放 / 现实验算”。
- `note` 控制 1—2 行。
- `count` 可省略；即使保留，也只作为弱化的数据标签。
- 真实头像不写进 `report.json` 也可以，由 `--avatars` manifest 注入。

## Stats

- 最多 6 项。
- 只放与叙事有关的真实数字。
- 不需要凑满 6 格；renderer 会按实际数量调整列数。

## Closing

写一个真实未决问题、下一步追踪项或克制收束。避免万能结论和模板式价值拔高。

编辑生成的 `lead`、`sections`、`people`、`closing` 默认不得使用 `不是……而是……` 和 `并非……而是……` 模板句；逐字引用除外。validator 会检查编辑字段。

## Manual pages（仅特殊版式）

默认不写 `pages`，让 renderer 自动分页。确需人工控制时：

```json
{
  "layout": {"page_mode": "manual"},
  "pages": [
    {"label": "第 1 版", "section_indices": [0, 1]},
    {"label": "第 2 版", "kicker": "POLICY / CONFLICT", "section_indices": [2, 3], "show_extras": true}
  ]
}
```

规则：

- section index 不能越界或重复。
- `show_extras` 控制人物、数据和 closing 是否附在该页；默认最后一页展示。
- 不为凑页数重复 Lead、故事或金句。
- 实际 A3 高度仍由浏览器 preflight 最终判断；overflow 时停止出版。

## 头像

日报和周报默认启用群头像与入选人物头像。用 `scripts/extract_avatars.py` 从已解密的 `head_image.db` 导出私有头像目录：

```text
avatars/
├── avatars.json
├── group-avatar.jpg
└── avatar-001.jpg
```

manifest 只保存显示名到本地图片路径的映射，不进入 Git、云盘或对话正文。同名映射存在歧义时使用首字占位，不猜测。

## 输出

renderer 默认输出 `png,pdf`，根目录：

```text
/Users/chengyu/Downloads/微信群报/<群名>/
```

命名示例：

```text
吃瓜备用_日报_2026-09-17_普通版.pdf
吃瓜备用_日报_2026-09-17_普通版_p01.png
吃瓜备用_周报_2026-09-11--2026-09-17_毒舌版_p02.png
```

传 `--formats html,png,pdf` 时同时保留 HTML。私人/本地素材使用相对 assets 路径；CALIPH 公共品牌 Logo 可保留公开 HTTPS 地址。
