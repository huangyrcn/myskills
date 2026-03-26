---
name: skill-manager
description: >
  管理agent skills：搜索、安装、更新、重装已有skills，以及开发自写skills。
  Use this skill whenever the user mentions ANYTHING related to skills management,
  even if they don't use the word "skill" explicitly. This includes:
  「安装skill」「搜索skill」「找skill」「更新skills」「sync skills」「update skills」
  「重新安装」「reinstall」「重装仓库」「拉最新版本」「更新技能包」「update」
  「install skill」「find skill」「create skill」「写skill」「卸载」「remove skill」
  Also trigger when user mentions fork repos, skill repos (myskills, aris-skills),
  or npx skills commands. ALL skill-related operations MUST go through this skill.
argument-hint: "[search|install|list|update|create] [关键词或仓库名]"
allowed-tools: Bash, Read, Write, WebFetch
---

# Skill Manager

管理agent skills的完���指南：寻找已有skills、安装更新、以及开发自己的skills。

> **强约束：所有 skill 相关操作必须通过本 skill 执行。**
> 禁止直接运行 `npx skills` 命令或手动修改 `~/.claude/skills/`、`~/.agents/skills/`，
> 除非��� skill 明确指示这样做。

## Quick Reference

| 操作 | 命令 |
|------|------|
| **搜索skill** | `npx skills find <关键词>` |
| **安装skill** | `npx skills add <owner/repo> -g -y` |
| **列出已安装** | `npx skills list` |
| **更新skills** | `npx skills update` |
| **卸载skill** | `npx skills remove <name>` |

---

## 1. 寻找已有Skills

**首选方法：CLI搜索**
```bash
npx skills find "arxiv"
npx skills find "web search"
npx skills find "paper"
```

**备选方法：**

| 方式 | 说明 |
|------|------|
| 网站浏览 | https://skills.sh/ — 官方skill registry |
| GitHub搜索 | `topic:claude-skill` 或 `filename:SKILL.md` |

**选择标准（优先级递减）**：
1. 官方来源 — anthropics/*, vercel-labs/*, modelcontextprotocol/*
2. 安装量 — > 1K 表示广泛使用
3. 活跃度 — 最近30天有更新
4. 文档质量 — SKILL.md完整清晰

---

## 2. 安装Skills

### 从GitHub安装
```bash
npx skills add <owner/repo> -g -y
```

**参数说明**：
- `<owner/repo>` — GitHub仓库，格式：用户名/仓库名
- `-g` — 全局安装（所有项目可用）
- `-y` — 自动确认（非交互模式）

**示例**：
```bash
npx skills add huangyrcn/myskills -g -y
npx skills add anthropics/claude-code-skills -g -y
```

### 安装后位置
```
~/.agents/skills/<name>/     ← 实际文件
~/.claude/skills/<name>/     ← symlink (Claude Code加载)
```

---

## 3. 管理自写Skills

### 完整开发流程

```
┌─────────────────────────────────────────────────────────────┐
│ 步骤1: 本地开发                                              │
│ ~/myskills/skills/<name>/SKILL.md                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ git add . && git commit -m "message"
                      │ git push origin main
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 步骤2: 发布到GitHub                                          │
│ https://github.com/<your-name>/myskills                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ npx skills add <your-name>/myskills -g -y
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 步骤3: 安装到各机器                                          │
│ ~/.agents/skills/<name>/ → 自动symlink到各Agent平台          │
└─────────────────────────────────────────────────────────────┘
```

### 更新Skills（两步流程）

当用户说「更新skill」「sync skills」「update skills」时，按以下顺序执行：

**Step 1: 推送自己的myskills（如有本地改动）**
```bash
cd ~/myskills
git status  # 检查是否有未提交的改动
# 如果有改动：
git add . && git commit -m "update skills"
git push origin main
```

**Step 2: 从GitHub拉取所有skills**
```bash
npx skills update
```

> 注意：`npx skills update` 会更新所有已安装的skills（包括第三方）。
> 第三方skills直接从它们各自的GitHub仓库拉取，无需手动操作。
> 只有自己的myskills需要先push，才能被update拉到。

### 本地快速测试
```bash
# 直接symlink测试（跳过git流程）
ln -s ~/myskills/skills/<name> ~/.agents/skills/<name>
```

---

## 4. 目录结构总览

```
~/myskills/                    # 本地开发目录
└── skills/<name>/SKILL.md

~/.agents/skills/              # 规范存储（npx安装位置）
├── <name>/                    # skill文件
└── .skill-lock.json           # 安装记录

~/.claude/skills/              # Claude Code加载路径
└── <name> → symlink           # 指向 ~/.agents/skills/<name>/

~/.openclaw/workspace/skills/  # OpenClaw加载路径
└── <name> → symlink
```

---

## 5. SKILL.md 模板

```yaml
---
name: my-skill
description: >
  简短描述功能，包含触发关键词。
  Make sure to use this skill when [具体场景].
argument-hint: "[参数说明]"
allowed-tools: Bash, Read, Write
---

# Skill Title

## 功能说明
简要说明skill做什么。

## Workflow
1. 步骤1
2. 步骤2
3. 步骤3
```

**关键点**：
- `description`决定触发时机，必须包含关键词
- 保持在500行以内，使用引用文件处理长内容

---

## 6. 常见问题

**Q: skill不触发？**
A: 检查description是否包含正确的触发关键词，确保用户请求与描述匹配。

**Q: 如何在多台机器同步？**
A: 本地git push后，其他机器运行`npx skills update`。

**Q: 本地开发如何快速测试？**
A: 直接symlink：`ln -s ~/myskills/skills/<name> ~/.agents/skills/<name>`