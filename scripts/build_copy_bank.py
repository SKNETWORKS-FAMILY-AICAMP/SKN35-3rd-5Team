"""수집한 광고 표현 재료 → data/copy_bank/bank.jsonl (생성 재료로 쓰는 표현 은행).

입력: 수집 결과 jsonl (한 줄에 {"type", "form", "text", "source_url", "risk"}).
  type: sensory_vocab(감각 어휘) | scene(사용 장면) | template(문장 구조) | angle(설득 각도) | mz_word
원문은 저장소에 넣지 않는다(공개 저장소). 수집 단계에서 짧은 어휘·장면·추상화한 구조로 바꾼 것만 받는다.

거르는 기준
- 수집 단계에서 risk 로 표시한 것
- 규칙 엔진(RuleEngine) 기준 일반 화장품에서 0단계가 아닌 표현
- 생성 검증기가 지우거나 탈락시키는 말(흡수·스며·완벽·확실 등), 실증이 필요한 순위·후기·배수·임상·인증
- 너무 긴 항목(원문 문장을 옮겨 왔을 가능성)
실행: uv run python scripts/build_copy_bank.py <수집 jsonl>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cosmetic_agent.domain.copy_knowledge import form_words  # noqa: E402
from cosmetic_agent.domain.rules import RuleEngine  # noqa: E402

OUT = ROOT / "data" / "copy_bank" / "bank.jsonl"
TYPES = {"sensory_vocab": 25, "scene": 40, "template": 60, "angle": 80, "mz_word": 12}
DROP_RE = re.compile(r"흡수|스며|침투|피부\s*속|듬뿍|풍부|농축|고함량|완벽|확실|확연|눈에\s*띄|놀라운|걱정\s*(?:없|끝)|"
                     r"되찾|되살|리셋|진정|재생|치료|예방|여드름|아토피|염증|살균|항균|최고|최초|유일|1위|100\s*%|"
                     r"천연|유기농|줄기세포|의사|의약|피부과|"
                     r"베스트셀러|판매|랭킹|순위|리뷰|후기|배수|\d+\s*배|깊게|깊이|임상|인증|특허")
GENERAL = {"product_id": "BANK", "name": "", "category": "일반", "functional_type": None, "owned_evidence": []}


def clean(rows: list[dict]) -> tuple[list[dict], dict[str, int]]:
    engine = RuleEngine()
    kept, dropped, seen = [], {"risk": 0, "type": 0, "length": 0, "words": 0, "rule": 0, "dup": 0}, set()
    for row in rows:
        kind, text = row.get("type"), re.sub(r"\s+", " ", str(row.get("text") or "")).strip()
        if row.get("risk"):
            dropped["risk"] += 1
        elif kind not in TYPES or not text:
            dropped["type"] += 1
        elif len(text) > TYPES[kind]:
            dropped["length"] += 1
        elif DROP_RE.search(text):
            dropped["words"] += 1
        elif engine.evaluate(text, GENERAL)["level"] != 0:
            dropped["rule"] += 1
        else:
            form = form_words({"form": row.get("form") or ""})[0]  # 수집 제형명을 form_vocab 제형으로 맞춘다 ("" = 공통)
            key = (kind, form, text)
            if key in seen:
                dropped["dup"] += 1
                continue
            seen.add(key)
            kept.append({"type": kind, "form": form, "text": text, "source_url": row.get("source_url", "")})
    return kept, dropped


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("사용법: uv run python scripts/build_copy_bank.py <수집 jsonl>")
    rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
    kept, dropped = clean(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    print(f"입력 {len(rows)} → 저장 {len(kept)} ({OUT.relative_to(ROOT)}) · 제외 {dropped}")


if __name__ == "__main__":
    main()
