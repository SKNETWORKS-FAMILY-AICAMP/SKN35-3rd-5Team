"""
[rag/query_rewriter.py]
마케팅 구어체 표현을 법령 및 식약처 규정 용어로 변환하는 질의 재작성기.
"""
from pathlib import Path
import json
import re
from ..common.config import settings


class QueryRewriter:
    def __init__(self, term_map_path: Path | None = None):
        self.term_map_path = term_map_path or settings.TERM_MAP_PATH
        self.term_map = self._load_term_map(self.term_map_path)

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
        query = copy_text
        expansions: list[str] = []

        # 등록된 마케팅 표현은 원문을 보존하면서 규정 용어를 덧붙인다.
        for phrase, regulatory_term in self.term_map.items():
            if phrase in copy_text:
                expansions.append(regulatory_term)

        # 특정 평가 문구가 아닌 일반적인 위반 유형 신호만 사용한다.
        medical_signal = re.search(
            r"(치료|재생|질병|흉터|염증|예방|세포)", copy_text
        )
        hair_growth_signal = re.search(
            r"(발모|육모|양모|모발.{0,10}(성장|자라|증가)|머리카락.{0,10}(성장|자라|증가))",
            copy_text,
        )
        if medical_signal or hair_growth_signal:
            expansions.append("의약품으로 잘못 인식할 우려가 있는 효능 효과 표시 광고")
        if re.search(r"(\d+(?:\.\d+)?\s*%|입증|임상|시험|개선)", copy_text):
            expansions.append("광고 주장 실증자료 시험결과 객관적 과학적 근거 직접적인 관계")
        if re.search(r"(미백|주름|자외선|탈모|기능성)", copy_text):
            expansions.append("기능성화장품 심사 범위 효능 효과")
        if re.search(r"(최고|완벽|폭발적|즉시|단번|100\s*%)", copy_text):
            expansions.append("소비자 오인 과장된 표시 광고")

        if retry_count > 0:
            expansions.append("화장품법 시행규칙 표시 광고 준수사항")

        # 순서를 유지하며 중복 확장어를 제거한다.
        unique_expansions = list(dict.fromkeys(expansions))
        if unique_expansions:
            query = f"{query} {' '.join(unique_expansions)}"
        return query
