"""
CNKI MCP Server — 浏览器管理模块

管理 Chrome 实例池，提供：
- 反检测配置
- 实例复用 + 空闲超时回收
- 线程安全
- 自动清理
"""

import random
import time
import threading
import logging
from contextlib import contextmanager
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

from .selectors import USER_AGENTS

logger = logging.getLogger("cnki-mcp.browser")

# 空闲超时（秒），超过此时间未使用的浏览器实例将被关闭
IDLE_TIMEOUT = 600  # 10 分钟


class BrowserError(Exception):
    """浏览器操作错误基类"""


class BrowserInitError(BrowserError):
    """浏览器初始化失败"""


class ElementNotFoundError(BrowserError):
    """页面元素未找到"""


class BrowserInstance:
    """包装一个 Chrome 实例，记录最后使用时间"""

    def __init__(self, driver: webdriver.Chrome):
        self.driver: webdriver.Chrome = driver
        self.last_used: float = time.time()
        self.in_use: bool = False

    def touch(self) -> None:
        self.last_used = time.time()

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_used


def _build_chrome_options(headless: bool = True) -> Options:
    """构建 Chrome 选项，包含反检测配置"""
    options = Options()

    # ---- 反检测 ----
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # ---- 稳定性 ----
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")
    options.add_argument("--silent")

    # ---- UA ----
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    # ---- 窗口 ----
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")

    # ---- 禁用自动化特征 ----
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)

    return options


def create_browser(headless: bool = True) -> webdriver.Chrome:
    """
    创建一个配置好反检测的 Chrome 实例。

    Raises:
        BrowserInitError: 初始化失败时抛出
    """
    try:
        options = _build_chrome_options(headless=headless)

        # 自动管理 ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # 设置超时，防止页面加载无限卡住
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)

        # 注入 JS 隐藏 webdriver 属性
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                // 也覆盖 chrome 对象
                window.chrome = {
                    runtime: {}
                };
                // 覆盖 permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({state: Notification.permission}) :
                    originalQuery(parameters)
                );
            """
        })

        logger.info("Chrome 浏览器实例已创建 (headless=%s)", headless)
        return driver

    except WebDriverException as e:
        raise BrowserInitError(f"无法启动 Chrome 浏览器: {e}") from e


class BrowserPool:
    """
    Chrome 浏览器实例池。

    特性:
    - 单例复用，避免频繁创建/销毁浏览器
    - 空闲超时自动回收
    - 线程安全
    """

    def __init__(self, headless: bool = True, idle_timeout: int = IDLE_TIMEOUT):
        self._headless = headless
        self._idle_timeout = idle_timeout
        self._instance: Optional[BrowserInstance] = None
        self._lock = threading.Lock()
        self._closed = False

    def _cleanup_idle(self) -> None:
        """回收空闲超时的实例"""
        if self._instance is None:
            return
        if not self._instance.in_use and self._instance.idle_seconds > self._idle_timeout:
            logger.info("浏览器实例空闲 %.0fs，自动回收", self._instance.idle_seconds)
            try:
                self._instance.driver.quit()
            except Exception:
                pass
            self._instance = None

    def acquire(self) -> webdriver.Chrome:
        """
        获取一个可用的浏览器实例。
        如果有空闲实例则复用，否则创建新实例。

        Raises:
            BrowserInitError: 创建失败时抛出
            RuntimeError: 池已关闭时抛出
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("BrowserPool 已关闭")

            # 清理过期实例
            self._cleanup_idle()

            # 创建新实例
            if self._instance is None:
                driver = create_browser(headless=self._headless)
                self._instance = BrowserInstance(driver)

            # 标记使用中
            self._instance.in_use = True
            self._instance.touch()
            return self._instance.driver

    def release(self, driver: webdriver.Chrome) -> None:
        """归还浏览器实例到池中"""
        with self._lock:
            if self._instance is not None and self._instance.driver is driver:
                self._instance.in_use = False
                self._instance.touch()

    def discard(self, driver: webdriver.Chrome) -> None:
        """丢弃一个出错的浏览器实例"""
        with self._lock:
            try:
                driver.quit()
            except Exception:
                pass
            if self._instance is not None and self._instance.driver is driver:
                self._instance = None

    def close(self) -> None:
        """关闭池中所有浏览器实例"""
        with self._lock:
            self._closed = True
            if self._instance is not None:
                try:
                    self._instance.driver.quit()
                except Exception:
                    pass
                self._instance = None
            logger.info("BrowserPool 已关闭")

    @property
    def status(self) -> dict:
        """返回池状态信息"""
        with self._lock:
            if self._instance is None:
                return {"active": False, "in_use": False, "idle_seconds": 0}
            return {
                "active": True,
                "in_use": self._instance.in_use,
                "idle_seconds": round(self._instance.idle_seconds, 1),
            }

    @contextmanager
    def session(self):
        """上下文管理器：自动获取和归还浏览器实例"""
        driver = self.acquire()
        try:
            yield driver
        except Exception:
            self.discard(driver)
            raise
        else:
            self.release(driver)


# ============================================================
# 页面操作辅助函数
# ============================================================

def safe_find(
    driver: webdriver.Chrome,
    selectors: list[str],
    timeout: float = 10,
    parent=None,
) -> list:
    """
    按优先级尝试多个选择器查找元素。

    每个选择器格式: "策略:值"，策略为 css / xpath / id。
    返回找到的元素列表（可能为空）。

    Args:
        driver: WebDriver 实例
        selectors: 选择器列表，按优先级排列
        timeout: 等待超时（秒）
        parent: 父元素，默认在 driver 上查找

    Returns:
        匹配的元素列表
    """
    root = parent if parent is not None else driver
    last_error = None

    for sel in selectors:
        try:
            strategy, _, value = sel.partition(":")
            value = value.strip()

            if strategy == "css":
                by = By.CSS_SELECTOR
            elif strategy == "xpath":
                by = By.XPATH
            elif strategy == "id":
                by = By.ID
            else:
                logger.warning("未知选择器策略: %s", strategy)
                continue

            elements = WebDriverWait(root, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
            if elements:
                logger.debug("选择器匹配成功: %s → %d 个元素", sel, len(elements))
                return elements

        except TimeoutException:
            last_error = f"超时: {sel}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    logger.debug("所有选择器均未匹配: %s (最后错误: %s)", selectors, last_error)
    return []


def safe_find_one(
    driver: webdriver.Chrome,
    selectors: list[str],
    timeout: float = 10,
    parent=None,
):
    """safe_find 的单元素版本，返回第一个匹配元素或 None"""
    elements = safe_find(driver, selectors, timeout, parent)
    return elements[0] if elements else None


def safe_get_text(
    driver: webdriver.Chrome,
    selectors: list[str],
    timeout: float = 5,
    parent=None,
) -> str:
    """查找元素并返回其文本内容，未找到返回空字符串"""
    el = safe_find_one(driver, selectors, timeout, parent)
    return el.text.strip() if el else ""


def safe_get_texts(
    driver: webdriver.Chrome,
    selectors: list[str],
    timeout: float = 5,
    parent=None,
) -> list[str]:
    """查找多个元素并返回文本列表"""
    elements = safe_find(driver, selectors, timeout, parent)
    return [el.text.strip() for el in elements if el.text.strip()]


def safe_get_attr(
    driver: webdriver.Chrome,
    selectors: list[str],
    attr: str,
    timeout: float = 5,
    parent=None,
) -> str:
    """查找元素并返回指定属性值"""
    el = safe_find_one(driver, selectors, timeout, parent)
    return el.get_attribute(attr).strip() if el else ""


def safe_click(
    driver: webdriver.Chrome,
    selectors: list[str],
    timeout: float = 10,
) -> bool:
    """查找并点击元素，先尝试普通点击，被拦截时用 JS 点击"""
    el = safe_find_one(driver, selectors, timeout)
    if el:
        try:
            el.click()
            return True
        except Exception:
            # 普通点击被拦截（如下拉建议遮挡），用 JS 点击兜底
            try:
                driver.execute_script("arguments[0].click();", el)
                return True
            except Exception as e:
                logger.warning("JS 点击也失败: %s", e)
    return False


def human_type(driver: webdriver.Chrome, element, text: str) -> None:
    """模拟人类打字速度逐字符输入"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.03, 0.10))
