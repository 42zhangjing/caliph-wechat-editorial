---
name: caliph-wechat-editorial
description: "基于已解密的 yichen 微信本地 vault，把群聊整理成有编辑感的日报、周报或 A3 印刷版群报；触发词：群日报、群周报、微信群日报、做成报纸、A3 群报、群聊出版。只负责内容分析与输出，不负责抓 key、解密、刷新微信或操作微信界面。"
---

# Caliph Wechat Editorial

把已经存在的微信本地素材做成可阅读、可归档、可打印的编辑产品。默认使用本机 yichen vault，输出留在本机；不要把明文数据库、密钥、wxid 或完整聊天原文复制到工作区或回复中。

## 边界

- 这是内容输出层，不是微信数据采集层。
- 不运行 `extract_keys.py`、`decrypt_all_dbs.py`、`vchat decrypt`、`wxrefresh`、PyWxDump、Frida 或任何抓 key/重新解密流程。
- 不依赖或安装第三方 `group-daily`；它的上游流程可能强制刷新/解密微信。
- 不打开微信 UI，不发送消息，不上传群聊内容，不自动访问外部支付或赞赏页面。
- 如果用户要求最新数据，先调用现有 `yichen-wechat-local-vault` 的增量流程，再继续本 Skill 的内容步骤；本 Skill 自己不实现增量解密。

## 模式选择

- “今天/昨天做日报”：日模式，按本地时区的自然日处理。
- “这周/近七天做周报”：周模式，按明确的起止日期处理。
- “做报纸版/A3/印刷版”：出版模式，使用分页 A3 HTML/PDF；版数由故事量决定，优先 2 或 4 版，内容特别丰富才用 6 版。
- “看看群里聊了什么”：先生成编辑素材和简短预览，不直接把几百条原文贴进对话。

## 工作流

1. 确认群名和时间范围。若用户没有指定范围，日报默认今天 00:00 到现在，周报默认最近完整 7 天。
2. 找到 yichen `digest-source` 生成的 source JSON；如果没有，调用 yichen Skill 的只读查询/素材流程生成它。不要寻找或切换第二微信容器。
3. 用 `scripts/prepare_source.py` 去掉 `sender_username`、数据库表名等内部字段，生成供写作使用的本地素材包。
4. 先从消息中提炼 3—8 个故事节点，再写标题、开场、正文、金句、人物高光和数据。不要从发言量排行榜直接推导“重要人物”。
5. 如果用户要真实头像，在写作完成后用 `scripts/extract_avatars.py` 从已解密的 `head_image.db` 导出群头像和被选人物的头像；头像清单只保存显示名到本地图片路径的映射，不输出内部 username。没有人物头像时保留首字占位。
6. 事实、群友原话和编辑推断分开：原话必须能在素材包中定位；图片/视频看不到时只写“图片/视频内容不可见”，不可编造画面。
7. 将内容写成 report JSON，交给 `scripts/render_editorial.py` 输出 HTML；用户要求印刷时再生成 PDF，并可传入 `--avatars` 和 `--group-avatar`。
8. 检查输出：标题层级、中文断行、页数、A3 尺寸、是否截断、是否泄露内部标识。通过后再向用户提供文件链接和简短导读。

## 内容风格

采用“编辑部短报”而不是会议纪要：一个有钩子的头条，几条有时间和人物的故事线，少量真实金句，最后留一个余韵。日报重现场感，周报重变化、转折和群体画像。

- 标题要具体，避免“今天群里热闹非凡”一类空话。
- 每个故事节点回答：发生了什么、谁推动、为什么值得写、留下了什么结果。
- 人物写“本期发言中的角色/贡献”，不把一次发言上升为稳定人格或心理诊断。
- 对争议、成人内容、政治或私人话题使用必要的概括，不在成品中扩散不必要的露骨细节。
- 把图片、链接、文件视为线索，不把链接标题自动当成事实。
- 统计只服务叙事；不默认做全员排行、24 小时曲线或信息密度很低的 dashboard。

## 输出位置

默认写入用户配置的本地报告目录，建议为：

```text
~/Documents/wechat-local-vault/editorial/<群名>/<日期或周次>/
```

至少保留：`source-normalized.json`、`report.json`、`report.html`；如果用了头像，再保留私有的 `avatars/`（其中可包含 `group-avatar.jpg`）；生成 PDF 时再保留 `report.pdf`。这些文件包含聊天隐私，不要加入项目仓库、云盘同步目录或 Git 提交。

详细字段和审稿标准见 [references/report-schema.md](references/report-schema.md)；日/周报的编辑方法见 [references/editorial-workflow.md](references/editorial-workflow.md)。
