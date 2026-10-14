# 표현 은행 (copy bank)

광고문 생성이 단조롭지 않도록, 실제 화장품 광고·상세페이지에서 **쓸거리**를 뽑아 둔 곳입니다.

- `bank.jsonl` — 한 줄에 하나: `{"type", "form", "text", "source_url"}`
  - `sensory_vocab` 감각 어휘 · `scene` 사용 장면 · `template` 문장 구조(자리표시자) · `angle` 설득 각도 · `mz_word`
  - `form` 은 `data/assets/form_vocab.json` 의 제형 이름 (빈 값 = 모든 제형 공통)
- 원문 문장·슬로건은 넣지 않습니다(공개 저장소, 저작권). 수집할 때 짧은 어휘·장면·추상화한 구조로 바꿔 적고 출처 URL만 남깁니다.
  원문 스크랩은 개인 폴더에만 둡니다.
- 만드는 법: `uv run python scripts/build_copy_bank.py <수집 jsonl>`
  위험 표시·규칙 엔진 위반·검증기가 지우는 말·긴 문장(원문 의심)·중복을 거릅니다.
- 쓰는 곳: `cosmetic_agent.domain.copy_knowledge.copy_bank()` → 생성 프롬프트 `[수집 표현 재료]` 블록.
  같은 제형 + 공통 항목에서 장면·구조·어휘를 몇 개씩 무작위로 골라 줍니다. 효능·실증 근거로는 쓰지 않습니다.
