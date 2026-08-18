# TIANYU2FM Skills

TIANYU2FM 的开源播客内容生产工具箱：从嘉宾研究、提纲设计到高光筛选、视频粗剪、B-roll 搜集与标题生成。

## Skill Index

| 阶段 | Skill | 用途 |
| --- | --- | --- |
| 采访前 | [`tianyu2fm-scripter`](skills/tianyu2fm-scripter) | 研究嘉宾著作与一手资料，结合已有文稿生成有出处的延续性追问与核心观点转化问题。 |
| 录制后 | [`tianyu2fm-highlight-selector`](skills/tianyu2fm-highlight-selector) | 从完整带时间码 transcript 中挑选忠于原话的片头高光金句。 |
| 视频粗剪 | [`fcp-autocut-multicam`](skills/fcp-autocut-multicam) | 把双人 Final Cut Pro multicam FCPXML 转成可逆的说话人导向粗剪。 |
| 视觉补充 | [`collect-broll`](skills/collect-broll) | 搜索、筛选、下载、去重并验证真实网络 B-roll，保留完整来源记录。 |
| 节目发布 | [`tianyu2fm-title-generator`](skills/tianyu2fm-title-generator) | 基于完整节目内容与平台调研，生成符合 TIANYU2FM 调性的中文标题。 |

每个目录均完整保留 `SKILL.md`、所需 references、scripts 和 agent metadata；具体输入、输出、边界与工作流以各目录内的 `SKILL.md` 为准。

## 使用

把需要的 Skill 目录复制到你的 Codex Skills 目录，例如：

```bash
cp -R skills/tianyu2fm-scripter ~/.codex/skills/
```

也可以直接 clone 整个仓库：

```bash
git clone https://github.com/jackli0508-ship-it/tianyu2fm-skills.git
```

## Index Page

本仓库根目录同时包含 TIANYU2FM Skill Index 网站源码。

```bash
npm install
npm run dev
npm run build
```

## Repository note

此仓库用于公开留存 TIANYU2FM 内容与播客生产相关 Skills 的最新版本。公开素材不等于自动获得第三方内容的商业使用许可；涉及 B-roll 时请遵守原始来源的授权条款。
