# myskills

个人 Claude Code skills 集合。

## Skills

| Skill | 说明 |
|-------|------|
| `skill-manager` | 管理 agent skills：搜索、安装、更新、重装 |
| `paper-pipeline` | 端到端论文工作流：resolve → acquire → repo → reading notes |
| `paper-resolve` | 解析论文引用为 canonical identity，创建 ~/papers/{title_slug}/ |
| `paper-acquire` | 获取论文 raw bundle：PDF、paper.md、LaTeX |
| `paper-repo` | 发现论文实现仓库，验证官方/复现，写入 metadata |
| `paper-reading-notes` | 从 raw bundle 生成研究型阅读笔记 |
| `pdf-to-md` | 通过 MinerU API 的高质量 VLM 模型将 PDF 转换为 Markdown |
| `web-kit` | 统一网页搜索 + 阅读 + 下载工具 |

### Paper Skills 使用指南

推荐使用 `paper-pipeline` 作为默认入口：

```bash
# 端到端：从论文信息到阅读笔记
/paper-pipeline "Attention Is All You Need"
```

也可分步使用：

```bash
# 仅解析论文身份
/paper-resolve "Geom-GCN"

# 仅获取 raw bundle（PDF + paper.md）
/paper-acquire  # 需要先 resolve

# 仅发现仓库
/paper-repo  # 需要先 acquire

# 仅生成阅读笔记
/paper-reading-notes  # 需要先 acquire
```

### 目录结构

```
~/papers/{title_slug}/
  metadata.yaml
  paper/
    paper.pdf
    paper.md      # 归一化后的论文文本
    latex/        # LaTeX 源码（如果有）
  repo/           # 克隆的仓库（如果有）
```

## 安装

```bash
npx skills add huangyrcn/myskills -g -y
```

## License

MIT
