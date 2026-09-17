---
name: caliph-wechat-editorial
description: "基于已解密的 yichen 微信本地 vault，把群聊整理成现代编辑风格的日报、周报、PNG 分享图或 A3 PDF 群报；支持普通版与毒舌版。触发词：群日报、群周报、微信群日报、群报、做成报纸、A3 群报、毒舌版、群聊出版。只负责内容分析与输出，不负责抓 key、解密、刷新微信或操作微信界面。"
---

# Caliph WeChat Editorial

把已经存在的微信本地素材做成可阅读、可分享、可归档、可打印的编辑产品。整体风格是现代 editorial publication：保留报头、网格、纸媒层级和人物感，同时使用更克制的留白、现代字体层级、数据标签与跨页节奏。

默认输出普通版；用户说“毒舌版 / roast / 来个毒的”时输出毒舌版；用户说“两版都要”时共享同一份事实骨架分别生成两版。

## 安全边界

- 这是内容输出层，不执行微信数据采集和解密。
- 不运行 `extract_keys.py`、`decrypt_all_dbs.py`、`vchat decrypt`、`wxrefresh`、PyWxDump、Frida 或任何抓 key/重新解密流程。
- 不依赖或安装第三方 `group-daily`。
- 不打开微信 UI，不发送消息，不上传群聊内容，不自动访问外部支付或赞赏页面。
- 如果用户要求最新数据，先调用现有 `yichen-wechat-local-vault` 的增量素材流程；本 Skill 自己不实现增量解密。
- 不把明文数据库、密钥、wxid、内部 username、原始数据库路径或完整聊天原文复制到项目仓库、公开目录或回复正文。

## 默认偏好

如果存在 `EXTEND.md`，先读取并应用。推荐位置：

1. 当前项目 `.caliph-wechat-editorial/EXTEND.md`
2. `~/.config/caliph-wechat-editorial/EXTEND.md`
3. Skill 根目录旁的用户配置文件

没有配置时使用以下默认值：

```yaml
default_style: normal
default_formats: png,pdf
output_root: /Users/chengyu/Downloads/微信群报
include_group_avatar: true
include_people_avatars: true
language: zh-CN
page_mode: auto
```

用户本次明确要求始终覆盖默认配置。

## 模式选择

### 时间

- “今天 / 昨天做日报”：`daily`，按本地时区自然日。
- “这周 / 最近完整 7 天 / 近七天做周报”：`weekly`，明确写入起止日期。
- 用户给了明确日期范围时，以用户范围为准。

### 风格

- `normal`：默认。冷静、具体、现代、克制，有编辑判断但不替群友下人格结论。
- `roast`：毒舌版。允许更锋利、更好笑、更有封面感的标题和点评；事实骨架、引用、统计与普通版保持一致。
- `both`：先完成并审计普通版，以同一 story map 重写毒舌版，再分别做引用审计和 style lint。

毒舌版只调侃本期公开言论、公开行为和可见矛盾；不碰外貌、体重、健康、家庭、私人关系，不做医学或心理诊断，不推断未公开身份属性。槽点不足时保持轻微调侃，不硬凑。

### 输出格式

- 用户未指定：默认输出高清分页 PNG + PDF。
- 用户说 HTML：额外输出 HTML。
- 可选格式：`html`、`png`、`pdf`，可任意组合。
- PNG 每页独立输出，使用 `_p01`、`_p02`…编号。

## 默认头像规则

日报和周报默认带头像，无需用户额外说明。

1. 默认尝试导出群头像。
2. 默认尝试导出所有进入“本期角色”的人物头像。
3. 找不到头像时使用首字占位，不因此中断报告。
4. 用户明确说“不要头像 / 无头像版”时才跳过头像导出。
5. 同名成员发生身份歧义时不得猜头像；保留占位并在工作记录中提示。

## 输出目录与命名

默认根目录：

```text
/Users/chengyu/Downloads/微信群报
```

按群名分目录，适配多个群：

```text
微信群报/
└── <群名>/
```

文件名统一包含群名、报告类型、日期范围和风格：

```text
<群名>_日报_2026-09-17_普通版.pdf
<群名>_日报_2026-09-17_毒舌版_p01.png
<群名>_周报_2026-09-11--2026-09-17_普通版.html
```

群名进入路径前必须清理 `/ \\ : * ? " < > |`、控制字符、末尾空格和末尾句点；保留中文与 emoji。

HTML 中禁止写入 `/Users/...` 一类本机绝对资源 URL。图片必须复制到 HTML 旁的私有 assets 目录并使用相对链接，或在未来显式启用 embed 模式。

## 三轮编辑工作流

正式报告统一执行 `SCAN → STORY MAP → WRITE → AUDIT → STYLE LINT → LAYOUT PREFLIGHT → EXPORT`。

### Round 1 — SCAN / STORY MAP

1. 确认群名、时间范围、素材最后一条消息时间和可用媒体信息。
2. 找到 yichen `digest-source` 生成的 source JSON；没有时调用 yichen Skill 的只读素材流程生成。
3. 用 `scripts/prepare_source.py` 清除内部字段，生成 `source-normalized.json`。规范化消息会得到 `M000001` 形式的安全 anchor，方便后续审稿定位。
4. 按消息顺序扫描全部素材，先列出 3—10 个候选话题，再收敛到日报 3—6 个、周报 4—7 个核心故事。
5. 每个候选故事至少记录：时间范围、参与者、发生了什么、转折点、1—3 个安全 anchor、是否依赖不可见图片/视频。
6. 先完成 story map，不急着写漂亮标题。发言量只做统计，不直接决定人物重要性。

### Round 2 — WRITE

先写故事正文，再根据已经完成的正文写 Lead。这样 Lead 概括真实成稿，不提前替整天/整周下结论。

每个故事节点回答：

- 发生了什么；
- 谁推动了讨论；
- 讨论怎样变化；
- 为什么值得留下；
- 有什么明确结果或未决问题。

报告写入 `report.json`，详细字段见 `references/report-schema.md`。

### Round 3 — AUDIT

正式渲染前必须审计：

- story map 中的重要节点是否遗漏；
- 每个逐字引用是否能在 `source-normalized.json` 找到同一发送者与原文；
- “X 说 / X 分享 / X 提到”等归因是否与素材一致；
- 标题和 dek 是否把群内转发、外链标题或推测升级成已证实外部事实；
- 同一段争论是否把相邻发言错误合并给某一个人；
- 人物卡是否只描述本期角色与贡献；
- 周报是否体现变化和转折，避免把七份日报顺序拼起来。

使用 `scripts/validate_report.py report.json --source source-normalized.json` 做机器审稿。引用校验失败、非法页面索引、关键字段缺失、style 硬规则命中时停止出版，先修 `report.json`。

## 文案声音：CALIPH Editorial Voice

### 普通版

- 冷静、具体、精炼、自然。
- 优先写可见动作、时间、观点变化和讨论结果。
- 保留群友有辨识度的真实表达，但短引用优先。
- 少做空泛拔高，少写万能总结句。
- 一个准确动词能表达时，不叠加两层抽象名词。
- 标题要具体，避免“今天群里热闹非凡”“围绕某话题展开讨论”。
- Lead 保持 100—220 字左右，周报允许略长；故事正文通常 140—320 字，实际以内容密度为准。

### 强制减少模板化对比句

编辑生成的标题、dek、正文、人物说明和收束中，默认不使用：

- `不是……而是……`
- `并非……而是……`

逐字引用群友原话时保持原文，不为满足风格规则篡改引用。

`validate_report.py` 会把上述编辑句式视为 style error。写作时直接表达事实关系，例如把“真正值得追踪的不是 A，而是 B”改成“接下来继续追踪 B，以及 A 是否发生变化”。

同时减少以下常见 AI 编辑腔；确有内容需要时偶发使用，不连续堆叠：

- 真正值得关注的是……
- 某种意义上……
- 归根结底……
- 值得注意的是……
- 这背后反映了……
- 机械的“一方面……另一方面……”

### 毒舌版

- 共用普通版已审计的 story map、数字和引用。
- 标题可以更损、更短、更有反差；正文仍需提供信息，不写纯段子墙。
- 允许 callback joke 和轻度夸张，但必须让读者看得出依据来自本期公开聊天。
- 嘲讽观点与行为，不贬低发言者作为人的价值。
- 毒舌版同样执行引用审计与 style lint。

## 事实与证据等级

每个 `section` 使用 `evidence` 标记主要证据状态：

- `direct_quote`：故事核心直接来自可定位原话。
- `group_observation`：对群聊过程的编辑概括。
- `linked_claim`：来自群内分享的链接标题、转述、截图描述等，未做外部核验。
- `externally_verified`：本次工作明确完成了外部核验，且报告保留核验说明。
- `editorial_inference`：编辑层面的推断或结构判断，需要用克制措辞表达。

链接标题、群友转述、截图文字和政策讨论默认不能升级为 `externally_verified`。

## 图片与媒体

- `[图片]`、`[视频]`、`[文件]` 只代表存在媒体。
- 看不到媒体内容时只写周围聊天能够确认的内容，不描述不可见画面。
- 报告图片若使用本地文件，renderer 会复制到报告自己的 assets 目录，HTML 只保留相对路径。
- Lead 没有图片时自动进入 text-only 版式，不保留空白图片栏。

## 现代视觉系统

普通版采用现代报刊 / 独立杂志语法：12 栏网格、克制色彩、强标题层级、宽松留白、serif 长正文 + sans 标题 + mono 数据标签。

毒舌版沿用同一品牌骨架，增加更强的标题比例、黑黄/高亮信号、反白引用和更有冲击力的节奏。毒舌版不能牺牲正文可读性。

日报与周报使用不同编排逻辑：

- 日报：首页更接近 news front page，强调现场、时间、当天转折。
- 周报：首页更接近 feature opener，强调主题演化、跨日关系和本周悬念。
- 第一版展示完整 Lead。
- 第 2 版起使用 compact masthead + continuation strip，不重复完整 Lead。
- 故事编号跨页连续：01、02、03……
- 人物卡头像默认 50px 左右，发言数降低视觉权重。
- stats 数量跟着内容走，最多 6 项，不为填满模板硬凑。

## 自动分页与版面 preflight

默认 `page_mode: auto`。模型负责故事顺序、`priority` 和内容重要性；renderer 根据标题长度、正文长度、引用数和图片估算物理分页。

只有确需手工控制版面时才设置：

```json
"layout": {"page_mode": "manual"}
```

并提供 `pages`。

渲染后必须做浏览器 preflight：检查每个 A3 `.page` 的真实 `scrollHeight` 与 `clientHeight`。出现 overflow 时停止正式出版，调整分页或内容后再导出；不允许依赖 `overflow:hidden` 静默裁字。

## 头像导出

写作和人物选择完成后，默认调用 `scripts/extract_avatars.py` 从已解密的 `head_image.db` 只读导出群头像和选中人物头像。头像 manifest 只保存显示名与本地图片路径，不进入 Git 或公开回复。

同一个显示名对应多个内部账号时视为歧义。不得随机取其中一个头像；使用首字占位并提示需要进一步消歧。

## 输出与命令

最少保留私有工作文件：

```text
source-normalized.json
report.json
```

正式导出推荐：

```bash
python scripts/validate_report.py report.json --source source-normalized.json
python scripts/render_editorial.py report.json \
  --source source-normalized.json \
  --avatars avatars/avatars.json \
  --group-avatar avatars/group-avatar.jpg
```

默认会输出 PNG + PDF 到：

```text
/Users/chengyu/Downloads/微信群报/<群名>/
```

如需 HTML：

```bash
python scripts/render_editorial.py report.json --source source-normalized.json --formats html,png,pdf
```

## 交付前检查

- 群名和时间范围正确。
- 普通 / 毒舌模式符合用户要求。
- 默认头像已尝试导出；用户要求无头像时才关闭。
- 每个引用通过 source 回查。
- 未核验外部信息没有被标题写成确定事实。
- 编辑文字没有 `不是……而是……` / `并非……而是……` 模板句。
- 日报覆盖当天主要转折；周报呈现跨日变化。
- 第一版 Lead 只出现一次，后续页使用 compact header。
- 故事编号跨页连续。
- HTML 没有绝对本机资源路径。
- A3 preflight 没有 overflow。
- 输出文件名包含群名、类型、日期范围和风格。
- 用户未指定格式时已经生成 PNG + PDF。

详细字段见 [references/report-schema.md](references/report-schema.md)，编辑方法见 [references/editorial-workflow.md](references/editorial-workflow.md)。
