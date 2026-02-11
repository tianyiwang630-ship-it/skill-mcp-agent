"""
轻量 BM25 搜索引擎 - 零外部依赖

用于 tool_search 在 MCP 工具中按关键词匹配 server。
支持中英文分词。
"""

import math
import re
from typing import List, Dict, Tuple


def tokenize(text: str) -> List[str]:
    """分词：小写化，按非字母数字分割，支持中文字符"""
    return re.findall(r'[\w\u4e00-\u9fff]+', text.lower())


class BM25Index:
    """BM25 搜索索引"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[List[str]] = []
        self.doc_ids: List[str] = []
        self.df: Dict[str, int] = {}
        self.avgdl: float = 0.0
        self.N: int = 0

    def add_document(self, doc_id: str, text: str):
        """添加文档到索引"""
        tokens = tokenize(text)
        self.corpus.append(tokens)
        self.doc_ids.append(doc_id)

        seen = set()
        for token in tokens:
            if token not in seen:
                self.df[token] = self.df.get(token, 0) + 1
                seen.add(token)

        self.N = len(self.corpus)
        total_len = sum(len(doc) for doc in self.corpus)
        self.avgdl = total_len / self.N if self.N > 0 else 0.0

    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        搜索索引，返回 [(doc_id, score)]，按 score 降序，只返回 score > 0 的结果
        """
        query_tokens = tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self.corpus):
            score = 0.0
            dl = len(doc_tokens)

            tf_map: Dict[str, int] = {}
            for t in doc_tokens:
                tf_map[t] = tf_map.get(t, 0) + 1

            for qt in query_tokens:
                if qt not in tf_map:
                    continue

                tf = tf_map[qt]
                df = self.df.get(qt, 0)

                idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)
                tf_norm = (tf * (self.k1 + 1)) / \
                          (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))

                score += idf * tf_norm

            if score > 0:
                scores.append((self.doc_ids[i], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
