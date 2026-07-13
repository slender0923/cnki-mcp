# CNKI MCP Server

知网(CNKI)论文检索 MCP 服务 —— 让 AI 助手直接搜索和获取知网论文信息。

## 功能

| Tool | 说明 |
|---|---|
| `search_cnki` | 搜索知网论文，支持 15 种搜索类型、分页、排序 |
| `get_paper_detail` | 从详情页提取完整元数据（标题/摘要/作者/DOI等） |
| `find_best_match` | 按字符相似度匹配最相近的论文标题 |

| Resource | 说明 |
|---|---|
| `cnki://search-types` | 列出所有可用搜索类型及别名 |
| `cnki://status` | 查看服务运行状态 |

## 安装

### 前置条件

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- Chrome 浏览器

### 方式一：uvx 直接运行（推荐）

无需手动安装，配置后自动拉取：

```json
{
  "mcpServers": {
    "cnki": {
      "command": "uvx",
      "args": ["cnki-mcp"]
    }
  }
}
```

### 方式二：从 Git 安装

```bash
uvx --from git+https://github.com/你的用户名/cnki-mcp cnki-mcp
```

### 方式三：本地开发安装

```bash
git clone <repo-url> cnki-mcp
cd cnki-mcp
uv sync
# 或 pip install -e .
```

## 配置

### Claude Desktop

编辑 `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cnki": {
      "command": "uvx",
      "args": ["--from", "e:\\data_agent\\cnki-mcp", "cnki-mcp"]
    }
  }
}
```

### Cursor

编辑 Cursor 的 MCP 配置:

```json
{
  "mcpServers": {
    "cnki": {
      "command": "uvx",
      "args": ["--from", "e:\\data_agent\\cnki-mcp", "cnki-mcp"]
    }
  }
}
```

## 支持的搜索类型

| 中文 | 英文别名 | 说明 |
|---|---|---|
| 主题 | subject, theme | 综合搜索（默认） |
| 篇关摘 | — | 篇名+关键词+摘要 |
| 关键词 | keyword, keywords | 关键词搜索 |
| 篇名 | title | 按标题搜索 |
| 全文 | fulltext, full_text | 全文搜索 |
| 作者 | author | 作者名搜索 |
| 第一作者 | first_author | 第一作者搜索 |
| 通讯作者 | corresponding_author | 通讯作者搜索 |
| 作者单位 | affiliation, institution | 机构搜索 |
| 基金 | fund | 基金项目搜索 |
| 摘要 | abstract | 摘要搜索 |
| 参考文献 | reference | 参考文献搜索 |
| 分类号 | classification | 分类号搜索 |
| 文献来源 | source | 期刊/来源搜索 |
| DOI | doi | DOI 精确搜索 |

## 排序方式

| 中文 | 英文 |
|---|---|
| 相关度（默认） | relevance |
| 发表时间 | time, date |
| 被引 | cited, citation |
| 下载 | download, downloads |

## 使用建议

- 每次搜索建议 1-3 页，避免频繁请求触发反爬
- 搜索间隔建议 2-3 秒
- 首次运行会自动下载 ChromeDriver

## 维护

### 知网改版时如何修复

1. 打开浏览器开发者工具，检查知网搜索页/详情页的 HTML 结构
2. 编辑 `src/cnki_mcp/selectors.py`，更新对应的选择器
3. 每个字段支持多选择器回退，格式为 `"策略:选择器"`，策略支持 `css`、`xpath`、`id`

### 添加新的搜索类型

编辑 `selectors.py` 中的 `SEARCH_TYPE_VALUES` 和 `SEARCH_TYPE_ALIASES` 字典。

## 与原始项目的区别

本项目的改进：

1. **选择器配置化** — 所有 XPath/CSS 集中在 `selectors.py`，知网改版只需改一个文件
2. **多选择器回退** — 每个元素有多套选择器策略，一个失败自动尝试下一个
3. **结构化错误处理** — 自定义异常体系，每个步骤独立容错
4. **更好的反检测** — 更多反自动化检测措施
5. **可维护架构** — 清晰的模块分离（浏览器管理 / 选择器配置 / 业务逻辑）
6. **去掉冗余** — 移除 FastAPI 版本，专注 MCP

## License

MIT
