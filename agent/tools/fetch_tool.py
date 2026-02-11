"""
Fetch Tool - 获取 URL 内容并转换为干净的可读文本
"""

import re
import json
import html
import hashlib
from pathlib import Path
from typing import Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

from agent.tools.base_tool import BaseTool


class FetchTool(BaseTool):
    """URL 内容获取工具 - 抓取网页并提取干净文本"""

    @property
    def name(self) -> str:
        return "fetch"

    PREVIEW_THRESHOLD = 15000  # 超过此值存文件，conversation 只放预览

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "fetch",
                "description": (
                    "获取指定 URL 的网页内容，自动清理 HTML/XML 标签、脚本、样式、导航等噪音，返回干净的纯文本。"
                    "适用于：搜索到链接后抓取页面详情、阅读文章/新闻全文、获取 API 数据。"
                    "内容会自动截断到 max_length。如果只需要关键信息，建议设置较小的 max_length（如 3000）以节省上下文。"
                    "注意：本工具无法获取需要 JavaScript 渲染的 SPA 页面（如 Yahoo Finance、Google Finance 等），"
                    "对于此类网站，建议改用提供 API 或服务端渲染的数据源。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要获取内容的 URL"
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "返回内容的最大字符数（默认 5000，建议不超过 8000）",
                            "default": 5000
                        }
                    },
                    "required": ["url"]
                }
            }
        }

    def execute(self, **kwargs) -> str:
        """获取 URL 内容并返回干净文本"""
        url = kwargs.get('url', '')
        max_length = kwargs.get('max_length', 5000)
        # 验证 URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
                parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return f"错误: 不支持的协议 '{parsed.scheme}'，仅支持 http/https"
            if not parsed.netloc:
                return "错误: 无效的 URL"
        except Exception as e:
            return f"错误: URL 解析失败: {e}"

        # 发送请求
        try:
            req = Request(url, headers=self.DEFAULT_HEADERS)
            with urlopen(req, timeout=15) as response:
                content_type = response.headers.get("Content-Type", "")
                charset = self._extract_charset(content_type)
                raw = response.read(500_000)  # 最多读 500KB
                body = self._decode(raw, charset)

        except HTTPError as e:
            return f"HTTP 错误 {e.code}: {e.reason}\nURL: {url}"
        except URLError as e:
            return f"请求失败: {e.reason}\nURL: {url}"
        except TimeoutError:
            return f"请求超时（15秒）\nURL: {url}"
        except Exception as e:
            return f"请求异常: {type(e).__name__}: {e}\nURL: {url}"

        # 解析内容
        if "application/json" in content_type:
            text = self._format_json_text(body)
        else:
            if "xml" in content_type:
                body = self._clean_xml(body)
            text = self._html_to_text(body)
            text = self._clean_text(text)

        # 统一出口：存文件 / 截断
        return self._finalize_output(text, url, max_length)

    # ========================================
    # 通用后处理（存文件 / 截断）
    # ========================================

    def _finalize_output(self, text: str, url: str, max_length: int) -> str:
        """通用后处理：大内容存文件返回预览，小内容按 max_length 截断"""
        if not text.strip():
            return f"页面内容为空或无法提取文本\nURL: {url}"

        if len(text) > self.PREVIEW_THRESHOLD:
            filename = hashlib.md5(url.encode()).hexdigest()[:8] + ".txt"
            temp_dir = getattr(self, 'temp_dir', None) or Path("temp/fetch_results")
            fetch_dir = temp_dir / "fetch_results"
            fetch_dir.mkdir(parents=True, exist_ok=True)
            filepath = fetch_dir / filename
            filepath.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")

            preview = text[:3000]
            return (
                f"URL: {url}\n\n{preview}\n\n"
                f"... (内容较长，共 {len(text)} 字符，已保存到 {filepath})\n"
                f"如需查看完整内容，请使用 read 工具读取上述文件路径，支持 offset/limit 分段读取。"
            )

        if len(text) > max_length:
            text = text[:max_length] + f"\n\n... (内容已截断，共 {len(text)} 字符)"

        return f"URL: {url}\n\n{text}"

    # ========================================
    # 编码处理
    # ========================================

    def _extract_charset(self, content_type: str) -> str:
        match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
        return match.group(1).strip('"\'') if match else "utf-8"

    def _decode(self, raw: bytes, charset: str) -> str:
        for enc in [charset, "utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")

    # ========================================
    # HTML -> 文本
    # ========================================

    def _html_to_text(self, raw_html: str) -> str:
        """HTML 转纯文本，优先用 bs4，回退到正则"""
        try:
            from bs4 import BeautifulSoup
            return self._bs4_extract(raw_html)
        except ImportError:
            return self._regex_extract(raw_html)

    def _bs4_extract(self, raw_html: str) -> str:
        """使用 BeautifulSoup 提取干净文本"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. 移除完全无用的标签（连内容一起删除）
        for tag in soup([
            "script", "style", "noscript", "iframe", "svg",
            "link", "meta", "template",     # head 区标签
            "nav", "footer", "header",      # 导航/页脚/页头
            "aside",                         # 侧边栏
            "form", "button", "input", "select", "textarea",  # 表单
            "img", "video", "audio", "source", "picture",      # 媒体
            "object", "embed", "canvas",     # 嵌入对象
        ]):
            tag.decompose()

        # 2. 移除隐藏元素
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            tag.decompose()
        for tag in soup.find_all(attrs={"hidden": True}):
            tag.decompose()
        for tag in soup.find_all(attrs={"aria-hidden": "true"}):
            tag.decompose()

        # 3. 移除 JSON-LD / 结构化数据
        for tag in soup.find_all("script", type=re.compile(r'application/(ld\+json|json)', re.I)):
            tag.decompose()

        # 4. 尝试定位主内容区域
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id=re.compile(r'^(content|main|article|post|entry)$', re.I))
            or soup.find(class_=re.compile(r'^(content|main|article|post|entry)[-_]?(body|text|content)?$', re.I))
            or soup.body
            or soup
        )

        # 5. 提取文本
        text = main.get_text(separator="\n", strip=True)

        return text

    def _regex_extract(self, raw_html: str) -> str:
        """正则提取文本（无 bs4 时的回退）"""
        text = raw_html

        # 移除整块内容
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<noscript[^>]*>.*?</noscript>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

        # XML 处理指令 <?xml ... ?> / CDATA
        text = re.sub(r'<\?[^>]+\?>', '', text)
        text = re.sub(r'<!\[CDATA\[.*?\]\]>', '', text, flags=re.DOTALL)

        # 块级标签 -> 换行
        text = re.sub(r'<(?:br|p|div|h[1-6]|li|tr|blockquote|section|article)[^>]*/?>', '\n', text, flags=re.I)

        # 移除所有剩余标签
        text = re.sub(r'<[^>]+>', '', text)

        # 解码 HTML 实体
        text = html.unescape(text)

        return text

    # ========================================
    # XML 清理
    # ========================================

    def _clean_xml(self, raw_xml: str) -> str:
        """清理 XML 内容（RSS、SOAP 等）"""
        # 移除 XML 声明
        text = re.sub(r'<\?xml[^>]*\?>', '', raw_xml)
        # 移除 CDATA
        text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
        # 移除命名空间前缀 <ns:tag> -> <tag>
        text = re.sub(r'<(/?)[\w-]+:', r'<\1', text)
        return text

    # ========================================
    # 通用文本清理
    # ========================================

    def _clean_text(self, text: str) -> str:
        """清理提取后的文本，去除噪音"""
        # HTML 实体（可能残留）
        text = html.unescape(text)

        # 移除零宽字符、控制字符（保留换行和空格）
        text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]', '', text)
        text = re.sub(r'[^\S\n]+', ' ', text)  # 多个空白合并（保留换行）

        # 清理每行
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                cleaned.append('')
                continue

            # 跳过明显的噪音行
            # 过短的纯符号行（如 "|||", "---", ">>>"）
            if len(line) <= 3 and not any(c.isalnum() for c in line):
                continue
            # Cookie / 隐私提示
            if re.match(r'^(cookie|privacy|accept|dismiss|close|skip|loading)', line, re.I):
                continue
            # 纯数字行（可能是 ID 之类的）
            if re.match(r'^\d+$', line) and len(line) > 6:
                continue

            cleaned.append(line)

        text = '\n'.join(cleaned)

        # 合并连续空行（最多保留一个）
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 合并过多的连续短行（可能是菜单/导航残留）
        # 如果连续 5+ 行都只有 1-3 个字，压缩为一行
        lines = text.split('\n')
        result = []
        short_streak = []
        for line in lines:
            if 0 < len(line) <= 4 and not re.search(r'\d', line):
                short_streak.append(line)
            else:
                if len(short_streak) >= 5:
                    # 压缩连续短行为一行
                    result.append(' | '.join(short_streak))
                else:
                    result.extend(short_streak)
                short_streak = []
                result.append(line)
        # 处理末尾
        if len(short_streak) >= 5:
            result.append(' | '.join(short_streak))
        else:
            result.extend(short_streak)

        return '\n'.join(result).strip()

    # ========================================
    # JSON 格式化
    # ========================================

    def _format_json_text(self, body: str) -> str:
        """JSON 格式化（只负责解析和美化，截断由 _finalize_output 统一处理）"""
        try:
            data = json.loads(body)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return body


# ============================================
# 测试
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("Fetch Tool Test")
    print("=" * 70)

    tool = FetchTool()

    # 测试 1: 获取百度
    print("\nTest 1: Fetch baidu.com\n")
    result = tool.execute(url="https://www.baidu.com", max_length=500)
    print(result[:500])

    # 测试 2: 获取 JSON API
    print("\n\nTest 2: Fetch JSON API\n")
    result = tool.execute(url="https://httpbin.org/json", max_length=1000)
    print(result[:500])

    # 测试 3: 无效 URL
    print("\n\nTest 3: Invalid URL\n")
    result = tool.execute(url="not-a-url")
    print(result)
