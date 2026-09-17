# Caliph 微信群聊编辑部

一个独立的个人 Codex Skill：把已经解密的本地微信素材整理成现代编辑风格的日报、周报、高清 PNG 分享图和可打印 A3 PDF 群报。

支持两种风格：

- **普通版**：克制、现代、具体，强调话题变化、真实引用和人物贡献。
- **毒舌版**：共享同一事实骨架，以更锋利、更有梗的标题和评论重写；保留明确边界，不做人身攻击。

本仓库与 `mcncarl/yichen-skills` 完全独立。它可以读取 `yichen-wechat-local-vault` 生成的本地素材包，但不抓 key、不解密数据库、不刷新微信、不操作微信界面，也不上传群聊内容。

## 安装

```bash
npx skills add 42zhangjing/caliph-wechat-editorial
```

也可以复制到 Codex 或 Claude Code 支持的本地 Skills 目录。

## 使用

```text
$caliph-wechat-editorial
生成“吃瓜备用”今天的群聊日报。
```

默认行为：

- 普通版；
- 群头像 + 入选人物头像；
- PNG + PDF；
- 自动分页；
- 输出到 `/Users/chengyu/Downloads/微信群报/<群名>/`。

毒舌版：

```text
$caliph-wechat-editorial
生成“吃瓜备用”最近完整 7 天的群聊周报，毒舌版。
```

两版都要：

```text
$caliph-wechat-editorial
把昨天做成普通版和毒舌版两份日报。
```

需要 HTML 时明确说明即可。

## Editorial v2 工作流

```text
source
→ normalize
→ story map
→ write
→ attribution audit
→ style lint
→ layout preflight
→ PNG / PDF / HTML
```

主要约束：

- `prepare_source.py` 删除内部字段，并生成安全消息 anchor。
- `validate_report.py` 检查 report 结构、逐字引用、页面索引和文案 style lint。
- 编辑文字默认不使用 `不是……而是……` / `并非……而是……` 模板句；逐字引用保持原文。
- renderer 默认自动分页；第一版完整 Lead，后续版 compact header；故事编号跨页连续。
- 无 Lead 图片时自动使用 text-only 版式。
- HTML 图片复制到私有 assets 目录，只保留相对路径。
- Chrome preflight 检查每个 A3 页面真实高度，发现 overflow 时停止出版。

## 输出命名

```text
吃瓜备用_日报_2026-09-17_普通版.pdf
吃瓜备用_日报_2026-09-17_普通版_p01.png
吃瓜备用_周报_2026-09-11--2026-09-17_毒舌版.pdf
```

不同群自动进入不同群名目录；文件名也保留群名，方便长期归档。

## 偏好配置

参考 `EXTEND.md.example`：

```yaml
default_style: normal
default_formats: png,pdf
output_root: /Users/chengyu/Downloads/微信群报
include_group_avatar: true
include_people_avatars: true
language: zh-CN
page_mode: auto
```

## 隐私边界

- 规范化素材、报告、头像和生成物默认保存在本机私有目录。
- 内部 username、数据库标识、密钥和原始数据库不会复制到报告包。
- 导出群头像/人物头像时，以只读方式读取 `head_image.db`。
- 同名成员的头像映射存在歧义时跳过真实头像并回退到首字占位。
- 仓库只包含 Skill 代码、文档和通用 UI 图标，不包含聊天导出或私人头像。

## 目录

- `SKILL.md`：触发规则、默认行为、编辑规范和运行边界
- `EXTEND.md.example`：用户默认偏好模板
- `scripts/prepare_source.py`：清理素材并生成安全 anchor
- `scripts/validate_report.py`：report 与引用审稿
- `scripts/extract_avatars.py`：默认头像增强层
- `scripts/render_editorial.py`：现代版式、自动分页、HTML/PNG/PDF 与 preflight
- `references/report-schema.md`：report JSON 字段
- `references/editorial-workflow.md`：三轮编辑与视觉规范
- `tests/`：核心 validator 测试
- `agents/openai.yaml` / `assets/`：Codex UI 元数据和图标
