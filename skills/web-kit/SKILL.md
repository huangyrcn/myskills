---
name: web-kit
description: >
  优先使用此 skill 处理所有网页相关操作：搜索和阅读。
  两大能力：(1) ask-search — 基于 SearxNG 的网页搜索，聚合 8 个通用引擎 + 13 个学术引擎 + 7 个新闻源等；
  (2) crwlr — 基于 crawl4ai 的网页抓取，真实远程浏览器渲染 JS，输出干净的 markdown。
  触发场景：搜索信息、查新闻、学术文献调研、读网页内容、URL 转 markdown、提取结构化数据、
  深度爬取站点、读取 JS 动态渲染页面、询问页面相关问题。
  中文触发词："搜索"、"查一下"、"最近新闻"、"读一下这个网页"、"抓取这个页面"、
  "这个链接讲了什么"、"帮我看看这个URL"、"转成markdown"、"爬一下这个网站"、
  "帮我调研"、"文献搜索"。
  英文触发词："search for", "look up", "read this page", "scrape this page",
  "what does this URL say", "crawl this site", "extract data from this page",
  "literature search", "find papers about"。
  相比 web-access 等重型浏览器工具，web-kit 更轻量（一条命令出结果），
  仅在需要登录态、页面交互、点击按钮等场景下才应降级到 web-access。
argument-hint: "ask-search <query> | crwlr crawl <url> [-o format] [-O file] [-q question]"
allowed-tools: Bash
---

# web-kit — 网页搜索 + 阅读

两个 CLI 覆盖"搜"和"读"：

| 场景 | 命令 |
|---|---|
| 搜索 | `ask-search "query"` |
| 读网页 | `crwlr crawl -o md "<url>"` |

典型流程：`ask-search` 找 URL → `crwlr` 读全文。

---

## ask-search 速查

```bash
ask-search "query"                        # 默认 10 条
ask-search "query" -n 5                   # 限制数量
ask-search "query" -c news               # 仅新闻
ask-search "query" -c science             # 学术搜索（arxiv, scholar, pubmed 等）
ask-search "query" -l zh-CN              # 中文结果
ask-search "query" -e google,bing        # 指定引擎
ask-search "query" -u                    # 只返回 URL 列表
ask-search "query" -j                    # 原始 JSON
```

环境变量：`SEARXNG_URL`（当前 `http://192.168.1.178:8082`）

## crwlr 速查

```bash
crwlr crawl -o md "<url>"                         # 页面转 markdown
crwlr crawl -o md -O out.md "<url>"               # 保存到文件
crwlr crawl -q "问题" "<url>"                      # 对页面提问
crwlr crawl -j "提取描述" -o json "<url>"          # 结构化提取
crwlr crawl --deep-crawl bfs --max-pages 20 -o md "<url>"  # 深度爬取
crwlr crawl -bc -o md "<url>"                     # 绕过缓存
```

输出格式：`md`(markdown) | `md-fit`(激进清理) | `json`(含元数据) | `all`(全部)

远程浏览器：Chromium CDP `192.168.1.178:9223`，`crwlr --raw` 可跳过。

## 注意事项

- URL 必须加引号
- 大页面用 `-O` 保存到文件
- 远程 Chromium 不可达时提示用户检查 `192.168.1.178:9223`

## References 索引

| 文件 | 何时加载 |
|---|---|
| `references/engines.md` | 需要了解具体支持哪些搜索引擎、学术引擎、分类时 |
| `references/workflow.md` | 需要多源对比、文献调研、深度爬取、sub-agent 分派等高级工作流时 |
