"""
[rag/query_rewriter.py]
마케팅 구어체 표현을 법령 및 식약처 규정 용어로 변환하는 질의 재작성기.
"""
from pathlib import Path
import json


class QueryRewriter:
    def __init__(self, term_map_path: Path = Path("data/assets/term_map.json")):
        self.term_map = self._load_term_map(term_map_path)

    @staticmethod
    def _load_term_map(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def rewrite(self, copy_text: str, retry_count: int = 0) -> str:
        """광고 문구를 검색에 최적화된 규정 검색 질의로 변환합니다.

        Args:
            copy_text: 원본 광고 문구
            retry_count: 재검색 횟수 (횟수에 따라 다른 유의어 전략 적용)
        """
        # TODO (팀원 구현 영역):
        # 1. term_map 사전 기반 단어 치환
        # 2. 위반 유형 키워드(의약품 오인, 실증, 기능성) 조합
        return copy_text
