# Caliph 微信群聊编辑部

一个独立的个人 Codex Skill：把已经解密的本地微信素材整理成有编辑感的日报、周报和可打印的 A3 群报。

本仓库与 `mcncarl/yichen-skills` 完全独立。它可以读取 `yichen-wechat-local-vault` 生成的本地素材包，但不复制该 Skill、不共享 Git 历史，也不抓 key、解密数据库、刷新微信、操作微信界面或上传群聊内容。

## 安装

```bash
npx skills add 42zhangjing/caliph-wechat-editorial
```

也可以把本仓库复制到 Codex 或 Claude Code 支持的本地 Skills 目录。

## 使用

```text
$caliph-wechat-editorial
生成“吃瓜备用”今天的群聊日报，加入群头像和人物头像。
```

```text
$caliph-wechat-editorial
生成“吃瓜备用”最近完整 7 天的群聊周报，重点整理话题变化、转折、人物角色和未决问题。
```

Skill 默认使用已经存在的本地素材。如果要求最新消息，应先通过独立的本地 vault 流程执行已授权的增量同步，再让本 Skill 输出报告。

## 隐私边界

- 规范化素材、报告、头像、HTML 和 PDF 默认保存在本机私有目录。
- 内部 username、数据库标识、密钥和原始数据库不会复制到报告包。
- 可选导出群头像/成员头像时，以只读方式读取 `head_image.db`。
- 仓库只包含 Skill 代码、文档和通用 UI 图标，不包含聊天导出或私人头像。

## 目录

- `SKILL.md`：触发规则、编辑规范和运行边界
- `scripts/prepare_source.py`：清理素材包中的内部字段
- `scripts/extract_avatars.py`：可选导出本地群头像和成员头像
- `scripts/render_editorial.py`：渲染 HTML 和可选 A3 PDF
- `references/`：编辑流程和报告字段说明
- `agents/openai.yaml` / `assets/`：Codex UI 元数据和图标
