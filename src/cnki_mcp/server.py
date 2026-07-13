"""
CNKI MCP Server — MCP 服务主模块

提供 3 个 MCP Tool:
  - search_cnki:      搜索知网论文
  - get_paper_detail: 获取论文详情
  - find_best_match:  标题最佳匹配

提供 2 个 MCP Resource:
  - cnki://search-types: 可用搜索类型
  - cnki://status:       浏览器池状态

基于 FastMCP 3.x + Selenium 构建。
"""

from __future__ import annotations

import random
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastmcp import FastMCP

from .browser import (
    BrowserPool,
    safe_find,
    safe_find_one,
    safe_get_text,
    safe_get_texts,
    safe_click,
    human_type,
    BrowserError,
)
from .selectors import (
    SEARCH_PAGE,
    DETAIL_PAGE,
    SEARCH_TYPE_VALUES,
    SEARCH_TYPE_ALIASES,
    SORT_TYPES,
    SORT_ALIASES,
)

# ---- 日志 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("cnki-mcp.server")

# ---- 浏览器池（模块级单例，在 lifespan 中初始化/销毁） ----
_browser_pool: Optional[BrowserPool] = None


def _get_pool() -> BrowserPool:
    """获取浏览器池（工具函数内部调用）"""
    global _browser_pool
    if _browser_pool is None:
        raise RuntimeError("BrowserPool 尚未初始化，请检查服务是否正确启动")
    return _browser_pool


# ---- 应用生命周期 ----
@asynccontextmanager
async def lifespan():
    """启动时创建浏览器池，关闭时回收"""
    global _browser_pool
    logger.info("正在启动 CNKI MCP Server...")
    _browser_pool = BrowserPool(headless=True)
    logger.info("BrowserPool 已初始化 (headless=True)")
    try:
        yield
    finally:
        if _browser_pool:
            _browser_pool.close()
            _browser_pool = None
        logger.info("CNKI MCP Server 已关闭")


# ---- FastMCP 应用 ----
mcp = FastMCP(
    name="CNKI 论文检索服务",
    instructions="知网(CNKI)论文搜索与详情获取 MCP 服务。支持主题、关键词、篇名、作者等 15 种搜索类型。",
    lifespan=lifespan,
)

# ============================================================
# 辅助函数
# ============================================================

def resolve_search_type(raw: str) -> str:
    """将用户输入的搜索类型解析为中文名"""
    if not raw:
        return "主题"
    key = raw.strip().lower()
    if key in SEARCH_TYPE_ALIASES:
        return SEARCH_TYPE_ALIASES[key]
    for cn_name in SEARCH_TYPE_VALUES:
        if cn_name == raw.strip():
            return cn_name
    logger.warning("未知搜索类型 '%s'，回退到 '主题'", raw)
    return "主题"


def resolve_sort(raw: str) -> str:
    """将用户输入的排序方式解析为中文名"""
    if not raw:
        return "相关度"
    key = raw.strip().lower()
    if key in SORT_ALIASES:
        return SORT_ALIASES[key]
    for cn_name in SORT_TYPES:
        if cn_name == raw.strip():
            return cn_name
    return "相关度"


def parse_search_results(driver, max_results: int = 20) -> list[dict]:
    """解析当前页面的搜索结果行"""
    rows = safe_find(driver, SEARCH_PAGE["result_rows"], timeout=10)
    if not rows:
        return []

    papers = []
    for row in rows[:max_results]:
        try:
            paper = {
                "title": safe_get_text(driver, SEARCH_PAGE["result_title"], timeout=2, parent=row),
                "authors": safe_get_texts(driver, SEARCH_PAGE["result_authors"], timeout=2, parent=row),
                "source": safe_get_text(driver, SEARCH_PAGE["result_source"], timeout=2, parent=row),
                "date": safe_get_text(driver, SEARCH_PAGE["result_date"], timeout=2, parent=row),
                "cited_count": safe_get_text(driver, SEARCH_PAGE["result_cited"], timeout=2, parent=row),
                "download_count": safe_get_text(driver, SEARCH_PAGE["result_download"], timeout=2, parent=row),
                "url": _safe_get_url(driver, row),
            }
            if paper["title"]:
                papers.append(paper)
        except Exception as e:
            logger.debug("解析搜索结果行失败: %s", e)
            continue

    return papers


def _safe_get_url(driver, row) -> str:
    """从搜索结果行提取详情页 URL"""
    try:
        title_link = safe_find_one(driver, SEARCH_PAGE["result_title"], timeout=2, parent=row)
        if title_link:
            return title_link.get_attribute("href") or ""
    except Exception:
        pass
    return ""


def select_search_type_on_page(driver, search_type_cn: str) -> bool:
    """在知网首页切换搜索类型（默认已是"主题"，无需切换）"""
    if search_type_cn == "主题":
        return True

    value = SEARCH_TYPE_VALUES.get(search_type_cn)
    if not value:
        logger.warning("未知搜索类型值: %s", search_type_cn)
        return False

    try:
        clicked = safe_click(driver, SEARCH_PAGE["search_type_dropdown"], timeout=8)
        if not clicked:
            logger.warning("未找到搜索类型下拉框")
            return False

        time.sleep(0.8)

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            option = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, f'#DBFieldList a[value="{value}"]'))
            )
            option.click()
            time.sleep(0.5)
            logger.info("已选择搜索类型: %s", search_type_cn)
            return True
        except Exception as e:
            logger.warning("未找到搜索类型选项 '%s': %s", search_type_cn, e)
            return False

    except Exception as e:
        logger.warning("切换搜索类型失败: %s", e)
        return False


def navigate_to_next_page(driver) -> bool:
    """翻到下一页，成功返回 True"""
    next_btn = safe_find_one(driver, SEARCH_PAGE["next_page"], timeout=5)
    if next_btn is None:
        return False
    try:
        if not next_btn.is_enabled():
            return False
        next_btn.click()
        time.sleep(random.uniform(2, 3))
        return True
    except Exception as e:
        logger.warning("翻页失败: %s", e)
        return False


# ============================================================
# MCP Tools
# ============================================================

@mcp.tool(
    name="search_cnki",
    description="搜索知网(CNKI)论文。支持主题、关键词、篇名、作者、作者单位等多种搜索类型，支持分页和排序。每次建议搜索 1-3 页，间隔 2-3 秒。",
)
async def search_cnki(
    query: str,
    search_type: str = "主题",
    page: int = 1,
    page_size: int = 20,
    sort: str = "相关度",
) -> dict:
    """
    搜索 CNKI 论文。

    Args:
        query:       搜索关键词
        search_type: 搜索类型，支持中文（主题/关键词/篇名/作者/作者单位等）
                     和英文别名（subject/keyword/title/author/affiliation等）
        page:        页码，从 1 开始，建议 1-3 页
        page_size:   每页结果数，默认 20
        sort:        排序方式: 相关度/发表时间/被引/下载 (或英文: relevance/time/cited/download)

    Returns:
        包含搜索结果和元信息的字典
    """
    search_type_cn = resolve_search_type(search_type)
    sort_cn = resolve_sort(sort)

    logger.info(
        "搜索请求: query='%s', type=%s, page=%d, size=%d, sort=%s",
        query, search_type_cn, page, page_size, sort_cn,
    )

    pool = _get_pool()
    all_papers: list[dict] = []
    errors: list[str] = []

    try:
        with pool.session() as driver:
            # 1. 打开知网首页
            driver.get("https://www.cnki.net/")
            time.sleep(random.uniform(1.5, 2.5))

            # 2. 切换搜索类型
            if search_type_cn != "主题":
                select_search_type_on_page(driver, search_type_cn)
                time.sleep(0.5)

            # 3. 输入关键词
            search_box = safe_find_one(driver, SEARCH_PAGE["search_input"], timeout=15)
            if search_box is None:
                return {
                    "success": False,
                    "error": "无法找到搜索输入框，知网页面可能已改版",
                    "query": query,
                    "papers": [],
                }

            human_type(driver, search_box, query)

            # 4. 用回车键提交搜索，避免知网下拉建议遮挡按钮
            time.sleep(0.3)
            from selenium.webdriver.common.keys import Keys
            search_box.send_keys(Keys.RETURN)

            time.sleep(random.uniform(3, 4))

            # 5. 翻到目标页
            for current_page in range(1, page + 1):
                if current_page > 1:
                    if not navigate_to_next_page(driver):
                        errors.append(f"第 {current_page} 页无法访问（可能已到末尾）")
                        break

                if current_page == page:
                    papers = parse_search_results(driver, max_results=page_size)
                    all_papers.extend(papers)
                    logger.info("第 %d 页获取 %d 条结果", current_page, len(papers))

        return {
            "success": True,
            "query": query,
            "search_type": search_type_cn,
            "sort": sort_cn,
            "page": page,
            "page_size": page_size,
            "total_results_in_page": len(all_papers),
            "papers": all_papers,
            "errors": errors if errors else None,
            "tip": "获取详情请使用 get_paper_detail 工具，传入论文 URL",
        }

    except BrowserError as e:
        logger.error("浏览器错误: %s", e)
        return {"success": False, "error": str(e), "query": query, "papers": []}
    except Exception as e:
        logger.exception("搜索异常")
        return {"success": False, "error": f"未知错误: {e}", "query": query, "papers": []}


@mcp.tool(
    name="get_paper_detail",
    description="获取知网论文的详细信息：标题、作者、机构、摘要、关键词、DOI、来源期刊、被引次数、下载次数等。传入论文详情页 URL。",
)
async def get_paper_detail(url: str) -> dict:
    """
    从 CNKI 论文详情页提取完整元数据。

    Args:
        url: 论文详情页 URL（如 https://kns.cnki.net/kcms2/article/abstract?v=...）

    Returns:
        包含论文详细信息的字典
    """
    logger.info("获取论文详情: %s", url[:80])

    pool = _get_pool()
    paper: dict = {
        "url": url,
        "title_cn": "",
        "title_en": "",
        "authors": [],
        "institutions": [],
        "abstract_cn": "",
        "abstract_en": "",
        "keywords_cn": [],
        "keywords_en": [],
        "source": "",
        "year": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "doi": "",
        "cited_count": "",
        "download_count": "",
        "fund": "",
        "classification": "",
    }

    try:
        with pool.session() as driver:
            driver.get(url)
            time.sleep(random.uniform(2, 3))

            paper["title_cn"] = safe_get_text(driver, DETAIL_PAGE["title_cn"], timeout=8)
            paper["title_en"] = safe_get_text(driver, DETAIL_PAGE["title_en"], timeout=3)
            paper["authors"] = safe_get_texts(driver, DETAIL_PAGE["authors"], timeout=5)
            paper["institutions"] = safe_get_texts(driver, DETAIL_PAGE["institutions"], timeout=5)
            paper["abstract_cn"] = safe_get_text(driver, DETAIL_PAGE["abstract_cn"], timeout=5)
            paper["abstract_en"] = safe_get_text(driver, DETAIL_PAGE["abstract_en"], timeout=3)
            paper["keywords_cn"] = [
                kw.rstrip(";；")
                for kw in safe_get_texts(driver, DETAIL_PAGE["keywords_cn"], timeout=5)
            ]
            paper["keywords_en"] = [
                kw.rstrip(";；")
                for kw in safe_get_texts(driver, DETAIL_PAGE["keywords_en"], timeout=3)
            ]
            paper["source"] = safe_get_text(driver, DETAIL_PAGE["source"], timeout=5)

            pub_text = safe_get_text(driver, DETAIL_PAGE["pub_info"], timeout=5)
            if pub_text and "," in pub_text:
                parts = pub_text.split(",")
                paper["year"] = parts[0].strip()
                if len(parts) > 1:
                    rest = parts[1].strip()
                    if "(" in rest and ")" in rest:
                        vol_issue = rest.split("(")
                        paper["volume"] = vol_issue[0].strip()
                        paper["issue"] = vol_issue[1].split(")")[0].strip()
                    if ":" in rest:
                        paper["pages"] = rest.split(":")[-1].strip()

            doi_text = safe_get_text(driver, DETAIL_PAGE["doi"], timeout=3)
            if doi_text:
                paper["doi"] = doi_text.replace("DOI:", "").replace("DOI：", "").strip()

            paper["cited_count"] = safe_get_text(driver, DETAIL_PAGE["cited_count"], timeout=3)
            paper["download_count"] = safe_get_text(driver, DETAIL_PAGE["download_count"], timeout=3)
            paper["fund"] = safe_get_text(driver, DETAIL_PAGE["fund"], timeout=3)
            paper["classification"] = safe_get_text(driver, DETAIL_PAGE["classification"], timeout=3)

        filled_fields = [k for k, v in paper.items() if v and k != "url"]
        logger.info("论文详情获取完成: %d/%d 字段有值", len(filled_fields), len(paper) - 1)

        return {"success": True, **paper}

    except BrowserError as e:
        logger.error("浏览器错误: %s", e)
        return {"success": False, "error": str(e), "url": url}
    except Exception as e:
        logger.exception("获取详情异常")
        return {"success": False, "error": f"未知错误: {e}", "url": url}


@mcp.tool(
    name="find_best_match",
    description="根据论文标题在知网中查找最匹配的论文。使用字符相似度算法匹配第一页搜索结果中与输入标题最相似的论文。",
)
async def find_best_match(title: str, search_type: str = "篇名") -> dict:
    """
    在知网中搜索并找到与输入标题最匹配的论文。

    Args:
        title:       论文标题
        search_type: 搜索类型，默认"篇名"（按标题搜索）

    Returns:
        包含最佳匹配论文信息和相似度的字典
    """
    logger.info("最佳匹配查找: '%s' (type=%s)", title, search_type)

    result = await search_cnki(
        query=title,
        search_type=search_type,
        page=1,
        page_size=20,
        sort="相关度",
    )

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "搜索失败"),
            "query": title,
        }

    papers = result.get("papers", [])
    if not papers:
        return {
            "success": True,
            "query": title,
            "best_match": None,
            "message": "未找到任何结果",
        }

    best_idx = 0
    best_score = 0
    for i, paper in enumerate(papers):
        paper_title = paper.get("title", "")
        score = sum(1 for c in title if c in paper_title)
        if score > best_score:
            best_score = score
            best_idx = i

    best = papers[best_idx]
    return {
        "success": True,
        "query": title,
        "best_match": best,
        "similarity_score": best_score,
        "similarity_metric": "character_overlap",
        "total_candidates": len(papers),
        "tip": "使用 get_paper_detail 获取该论文的详细信息",
    }


# ============================================================
# MCP Resources
# ============================================================

@mcp.resource("cnki://search-types")
def get_search_types() -> str:
    """返回所有可用的搜索类型及其别名"""
    import json
    return json.dumps(
        {
            "types": {
                cn: {
                    "value": SEARCH_TYPE_VALUES.get(cn, ""),
                    "aliases": [en for en, c in SEARCH_TYPE_ALIASES.items() if c == cn],
                }
                for cn in SEARCH_TYPE_VALUES
            },
            "sorts": {
                cn: {
                    "aliases": [en for en, c in SORT_ALIASES.items() if c == cn],
                }
                for cn in SORT_TYPES
            },
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("cnki://status")
def get_status() -> str:
    """返回服务状态"""
    import json
    pool = _browser_pool
    return json.dumps(
        {
            "service": "CNKI MCP Server",
            "version": "0.1.0",
            "browser_pool": pool.status if pool else {"active": False},
        },
        ensure_ascii=False,
        indent=2,
    )


# ============================================================
# 入口
# ============================================================

def main():
    """MCP 服务入口（stdio 模式）"""
    logger.info("启动 CNKI MCP Server (stdio 模式)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
