"""
CNKI MCP Server — 知网论文检索 MCP 服务

选择器配置模块：所有 XPath/CSS 选择器集中管理。
知网改版时只需修改此文件，无需改动业务逻辑。

每个字段的值是一个列表，按优先级排列，找到第一个匹配即停止。
格式: ["策略:选择器", ...]
  策略: css, xpath, id
"""

# ============================================================
# 知网首页 / 搜索页选择器
# ============================================================
SEARCH_PAGE = {
    # 搜索输入框
    "search_input": [
        "css:#txt_SearchText",
        "css:input[name='search']",
        "xpath://input[@id='txt_SearchText']",
    ],
    # 搜索按钮
    "search_button": [
        "css:.search-btn",
        "css:button.search-btn",
        "xpath://button[contains(@class,'search-btn')]",
        "xpath://input[@class='search-btn']",
    ],
    # 搜索类型下拉框
    "search_type_dropdown": [
        "css:#DBFieldBox",
        "xpath://select[@id='DBFieldBox']",
    ],
    # 搜索结果行
    "result_rows": [
        "xpath://table[@class='result-table-list']//tbody//tr",
        "xpath://div[@id='gridTable']//table//tbody//tr",
        "css:table.result-table-list tbody tr",
        "css:#gridTable table tbody tr",
    ],
    # 结果中的标题链接
    "result_title": [
        "css:a.fz14",
        "xpath:.//a[@class='fz14']",
        "xpath:.//td[@class='name']//a",
    ],
    # 结果中的作者
    "result_authors": [
        "xpath:.//td[@class='author']//a",
        "xpath:.//td[contains(@class,'author')]//a",
    ],
    # 结果中的来源期刊
    "result_source": [
        "xpath:.//td[@class='source']//a",
        "xpath:.//td[contains(@class,'source')]",
    ],
    # 结果中的日期
    "result_date": [
        "xpath:.//td[@class='date']",
        "xpath:.//td[contains(@class,'date')]",
    ],
    # 结果中的被引次数
    "result_cited": [
        "xpath:.//td[@class='quote']//a",
        "xpath:.//span[contains(@class,'quote')]",
    ],
    # 结果中的下载次数
    "result_download": [
        "xpath:.//td[@class='download']//a",
        "xpath:.//span[contains(@class,'download')]",
    ],
    # 结果中的链接（用于获取详情页 URL）
    "result_url": [
        "xpath:.//a[@class='fz14']/@href",
        "xpath:.//td[@class='name']//a/@href",
    ],
    # 下一页按钮
    "next_page": [
        "css:#PageNext",
        "xpath://a[@id='PageNext']",
        "xpath://a[contains(text(),'下一页')]",
    ],
    # 搜索结果总数
    "result_count": [
        "css:.pagerTitleCell",
        "xpath://span[@class='pagerTitleCell']",
        "xpath://div[@class='pagerTitle']",
    ],
}

# ============================================================
# 论文详情页选择器
# ============================================================
DETAIL_PAGE = {
    # 中文标题
    "title_cn": [
        "xpath://div[@class='wx-tit']/h1",
        "xpath://h1",
        "xpath://div[contains(@class,'title')]/h1",
        "css:.wx-tit h1",
    ],
    # 英文标题
    "title_en": [
        "xpath://div[@class='wx-tit']/h2",
        "xpath://h2",
        "css:.wx-tit h2",
    ],
    # 作者列表
    "authors": [
        "xpath://h3[@class='author']/span/a",
        "xpath://p[@class='author']/a",
        "xpath://div[contains(@class,'author')]//a",
    ],
    # 机构列表
    "institutions": [
        "xpath://h3[@class='orgn']/span/a",
        "xpath://p[@class='orgn']/a",
        "xpath://div[contains(@class,'orgn')]//a",
    ],
    # 中文摘要
    "abstract_cn": [
        "xpath://span[@id='ChDivSummary']",
        "xpath://div[@id='ChDivSummary']",
        "xpath://*[@id='ChDivSummary']",
    ],
    # 英文摘要
    "abstract_en": [
        "xpath://span[@id='EnChDivSummary']",
        "xpath://div[@id='EnChDivSummary']",
    ],
    # 中文关键词
    "keywords_cn": [
        "xpath://p[@class='keywords']//a",
        "xpath://div[@class='keywords']//a",
        "xpath://span[contains(@id,'KEYWORD')]//a",
    ],
    # 英文关键词
    "keywords_en": [
        "xpath://p[@class='keywords' and @id='catalog_KEYWORD_EN']//a",
        "xpath://div[contains(@class,'keywords') and contains(.,'Key')]//a",
    ],
    # 来源期刊
    "source": [
        "xpath://div[@class='top-tip']//a[contains(@href,'navi.cnki.net')]",
        "xpath://a[@class='KnsjiLink']",
        "xpath://a[contains(@href,'navi.cnki.net')]",
    ],
    # 发表信息（年,卷(期):页）
    "pub_info": [
        "xpath://div[@class='top-tip']//span",
        "xpath://span[contains(@class,'pub')]",
    ],
    # DOI
    "doi": [
        "xpath://li[contains(@class,'top-space') and contains(.,'DOI')]/p",
        "xpath://*[contains(text(),'10.') and contains(text(),'/')]",
        "xpath://p[contains(text(),'DOI')]",
    ],
    # 被引次数
    "cited_count": [
        "xpath://span[@id='refs']//a",
        "xpath://div[@class='total-inform']//span[contains(text(),'被引')]/../em",
    ],
    # 下载次数
    "download_count": [
        "xpath://span[@id='DownLoadParts']//a",
        "xpath://div[@class='total-inform']//span[contains(text(),'下载')]/../em",
    ],
    # 基金
    "fund": [
        "xpath://li[contains(text(),'基金')]/p",
        "xpath://p[@class='funds']/span",
    ],
    # 分类号
    "classification": [
        "xpath://li[contains(text(),'分类号')]/p",
    ],
}

# ============================================================
# 搜索类型映射
# ============================================================

# 中文名 → 表单 value
SEARCH_TYPE_VALUES: dict[str, str] = {
    "主题":     "SU$%=|",
    "篇关摘":   "TKA$%=|",
    "关键词":   "KY$=|",
    "篇名":     "TI$%=|",
    "全文":     "FT$%=|",
    "作者":     "AU$=|",
    "第一作者": "FI$=|",
    "通讯作者": "RP$%=|",
    "作者单位": "AF$%",
    "基金":     "FU$%|",
    "摘要":     "AB$%=|",
    "参考文献": "RF$%=|",
    "分类号":   "CLC$=|??",
    "文献来源": "LY$%=|",
    "DOI":      "DOI$=|?",
}

# 英文别名 → 中文名
SEARCH_TYPE_ALIASES: dict[str, str] = {
    "subject":              "主题",
    "theme":                "主题",
    "keyword":              "关键词",
    "keywords":             "关键词",
    "title":                "篇名",
    "author":               "作者",
    "first_author":         "第一作者",
    "corresponding_author": "通讯作者",
    "affiliation":          "作者单位",
    "institution":          "作者单位",
    "fund":                 "基金",
    "abstract":             "摘要",
    "fulltext":             "全文",
    "full_text":            "全文",
    "reference":            "参考文献",
    "source":               "文献来源",
    "doi":                  "DOI",
    "classification":       "分类号",
}

# 排序方式（中文 → 参数值）
SORT_TYPES: dict[str, str] = {
    "相关度": "0",
    "发表时间": "1",
    "被引": "2",
    "下载": "3",
}

SORT_ALIASES: dict[str, str] = {
    "relevance":  "相关度",
    "time":       "发表时间",
    "date":       "发表时间",
    "cited":      "被引",
    "citation":   "被引",
    "download":   "下载",
    "downloads":  "下载",
}

# ============================================================
# User-Agent 池
# ============================================================
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
]
