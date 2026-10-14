# 화장품 광고 문구 판정 및 교정 에이전트 (SKN 35기 3차 프로젝트)

화장품 표시·광고 법령, 식약처 고시, 실증 지침을 기반으로 광고 문구의 위반 여부를 사전 심사하고, 사내 보유 실증 자료 범위 내에서 가장 설득력 있는 문구로 교정해 주는 AI 컴플라이언스 시스템입니다.

---

## 광고문 생성과 통합 챗봇

**광고문 생성** 하나의 화면에서 제품 설명과 원하는 타깃·톤·채널·길이를 입력합니다. 성분·제품명·실증 정보는 선택 항목이며, 성분을 몰라도 요청한 콘셉트로 초안을 만듭니다. 기존 두 생성 메뉴는 이 화면으로 통합했습니다. 실제 동일 제품의 자료일 때만 왼쪽 프로젝트 정보를 선택하세요.

**통합 챗봇** 메뉴와 왼쪽 하단 토끼 버튼은 같은 대화를 공유합니다. “자외선 차단하는 선크림 광고 만들어줘”, “성분은 몰라, 그냥 만들어줘”, “두 번째 문구를 웃기고 짧게 바꿔줘” 같은 자연어 요청을 처리합니다. 번호 없는 후속 수정은 첫 후보를 기본으로 다듬습니다. 인사·기능 안내와 규정 질문도 대화로 처리하고, 규정 질문은 검색 근거를 확인한 경우에만 구체적으로 답합니다.

LangChain 구조화 출력으로 요청과 대화 맥락을 해석하고, LangGraph가 문구 생성·검토·질문 답변 중 필요한 작업을 실행합니다. 챗봇과 생성 화면은 동일한 생성 그래프를 사용합니다: **규정 검색 → 초안 생성 → 금지어·수치·제품 사실 검사 → 후보별 RAG 검토 → 필요 시 재작성(최대 2회)**. 근거를 찾지 못하거나 검토가 실패한 후보를 검토통과로 표시하지 않습니다.

생성 요청은 실제 기능성 심사·보고나 효능 시험의 증명이 아닙니다. 선크림 요청에서 심사·SPF/PA 정보가 없으면 외출·선케어 루틴 중심의 문구를 우선 작성하고, 수치·지속시간·입증되지 않은 차단 효과를 만들지 않습니다. 자동 검토는 법률 준수를 보장하지 않습니다.

`POST /generate`는 `instruction`(작성 요청), `product`, 선택적 `ingredients`, `product_description`, `reference_copy`, `channel`, 자유로운 `tone`, `length`, `keywords`를 받습니다. 이전 `ingredients` 기반 요청도 같은 그래프로 처리하며 응답 계약은 `domain.schemas.GenerateResponse`로 통일했습니다. `POST /chat`은 `message`, 선택적 `context`, 최근 `history`, `product`를 받고 `review`/`generate`/`answer`/`clarify` 결과와 갱신된 맥락을 반환합니다. 성분 누락으로 생성 질문을 반복하지 않습니다.

실제 실행에는 `.env`의 모델 API 키와 검색 인프라가 필요합니다. `UI_DATA_MODE=api`는 별도 FastAPI 서버를 사용하고, `local`은 FastAPI를 내장 실행합니다. 데모 모드에서 실제 AI 결과를 만들어 표시하지 않습니다. 대화는 Streamlit 세션 안에서 유지되며, 제품·실증 기준이 바뀌면 새 대화를 시작합니다.

---

## 1. 아키텍처 및 디렉토리 구조 요약

```text
├── configs/            # YAML 기반 환경 및 알고리즘 하이퍼파라미터
├── data/
│   ├── 01_raw/         # 원본 법령/고시/지침 PDF, 보도자료
│   ├── 02_processed/   # 정제된 청크 및 BM25 인덱스 파일
│   ├── assets/         # 금지어 사전, 표현 사다리, 가상 제품 카드 JSON
│   └── golden_set/     # Dev / Holdout 평가 벤치마크 데이터
├── docker/             # 선택 사항: 로컬 개발용 Qdrant 컨테이너 설정
├── eval/               # R0~R4 베이스라인 평가 파이프라인
├── finetune/           # QLoRA 기반 판정 모델 독립 학습 파이프라인
├── indexing/           # 오프라인 데이터 파이프라인 (01~05)
├── src/cosmetic_agent/ # 핵심 비즈니스 로직 (Clean Architecture & LangGraph)
│   ├── common/         # 환경변수, 로깅, 커스텀 예외
│   ├── domain/         # Pydantic 결과 계약, 규칙 엔진, 문구 검증기
│   ├── rag/            # Qdrant Cloud + BM25 RRF 하이브리드 검색, 질의 변환
│   ├── models/         # Rule / GPT Few-shot / QLoRA 판정 모델 인터페이스
│   ├── workflow/       # LangGraph 9단계 StateGraph 노드/엣지
│   └── service.py      # 싱글톤 파사드 서비스
├── api/                # FastAPI 서빙 레이어 (/health, /review, /generate, /search)
├── app/                # Streamlit 사용자 대시보드
└── tests/              # 단위 테스트 및 계약 검증 테스트
```

---

## 2. 역할 분담 및 담당 파일 가이드 (Work Breakdown)

각 팀원은 본인의 역할에 해당하는 파일들을 열어 `# TODO (팀원 구현 영역)` 주석을 확인하며 작업을 진행합니다.

| 역할 | 맡는 폴더 및 파일 | 주요 작업 내용 |
| :--- | :--- | :--- |
| **팀장 · 통합** | • `src/cosmetic_agent/workflow/graph.py`<br>• `src/cosmetic_agent/workflow/edges.py`<br>• `src/cosmetic_agent/service.py`<br>• `api/` 전체<br>• `configs/base.yaml`, `README.md` | • LangGraph 전체 노드·엣지 연결 및 루프 조건 완성<br>• FastAPI 엔드포인트 연동 및 문장 분할 배치 처리<br>• 전체 모듈 통합 및 일정/품질 관리 |
| **데이터 · 규칙** | • `data/01_raw/`, `data/02_processed/`<br>• `data/assets/*.json` (4종 + 제품카드)<br>• `indexing/` (01~05 스크립트)<br>• `src/cosmetic_agent/rag/` 전체 | • 법령/고시 PDF 수집 및 조(Article) 단위 정규식 청킹<br>• Qdrant Cloud + BM25 인덱스 생성 파이프라인 완성<br>• `banned_terms.json`, `claim_ladder.json` 실제 데이터 채우기<br>• RRF 하이브리드 검색 알고리즘 구현 |
| **프롬프트 · 판정** | • `src/cosmetic_agent/workflow/prompts.py`<br>• `src/cosmetic_agent/workflow/nodes.py`<br>• `src/cosmetic_agent/models/gpt_judge.py`<br>• `src/cosmetic_agent/domain/schemas.py`<br>• `src/cosmetic_agent/domain/verifier.py` | • GPT 판정 및 대안 문구 생성 프롬프트 엔지니어링<br>• Pydantic `ReviewResult` 계약 검증 규칙 추가<br>• 제안 문구의 숫자 날조 및 금지어 역검증(`verifier.py`) 로직 구현<br>• 혼동쌍 분석을 통한 Few-shot 예시 튜닝 |
| **평가** | • `data/golden_set/` (dev, holdout)<br>• `eval/metrics/eval_metrics.py`<br>• `eval/run_eval.py`<br>• `tests/` 단위/통합 테스트 | • 30~50건 골든셋(Dev/Holdout) 정답 라벨링<br>• R0(규칙) → R1(Zero-shot) → R2(Few-shot) → R4(최종) 비교 평가 실행기 작성<br>• 단위 테스트(`test_rules`, `test_schemas`) 확장 |
| **파인튜닝** | • `finetune/dataset/`<br>• `finetune/recipes/qlora_qwen.py`<br>• `src/cosmetic_agent/models/ft_judge.py`<br>• `finetune/MODEL_CARD.md` | • GPT 활용 300~500건 판정 학습 데이터 증강 및 수동 검수<br>• Train/Dev 데이터 누수(Leakage) 점검<br>• Colab T4 기반 Qwen-3B 4-bit QLoRA 학습 실행<br>• 서빙 어댑터 연동 및 모델 카드 작성 |
| **화면 · 발표** | • `app/streamlit_app.py`<br>• `app/components/cards.py`<br>• `app/components/sidebar.py`<br>• 발표 자료(PPT) | • Streamlit 화면 구현 (제품 선택, 보유 근거 체크, 신호등 결과 카드)<br>• 근거 조항 펼쳐보기(Accordion), 제안 문구 원클릭 복사<br>• 시연 시나리오 기획 및 최종 발표 자료 제작 |

---

## 3. 역할별 상세 파일 체크리스트

### 👑 1. 팀장 · 통합 파트
* [ ] [`configs/base.yaml`](configs/base.yaml): 재시도 횟수 상한 및 시스템 제한값 튜닝
* [ ] [`src/cosmetic_agent/workflow/graph.py`](src/cosmetic_agent/workflow/graph.py): 9개 노드와 3개 조건부 엣지가 누락 없이 컴파일되도록 조립
* [ ] [`src/cosmetic_agent/workflow/edges.py`](src/cosmetic_agent/workflow/edges.py): 재검색/재제안 카운터 증가 및 `route_*` 분기 완성
* [ ] [`src/cosmetic_agent/service.py`](src/cosmetic_agent/service.py): 그래프 실행 결과(`final_state`)를 `ReviewResult` 계약에 맞게 최종 조립
* [ ] [`api/routes/review.py`](api/routes/review.py): 상세페이지 일괄 처리(`POST /review/bulk`) 문장 분할 및 `batch()` 연동

### 📚 2. 데이터 · 규칙 파트
* [ ] [`indexing/01_download_regulations.py`](indexing/01_download_regulations.py) ~ [`04_enrich_metadata.py`](indexing/04_enrich_metadata.py): 법령/고시 PDF 텍스트 추출 및 정규식 조항 분리
* [ ] [`indexing/05_build_indexes.py`](indexing/05_build_indexes.py): Qdrant 적재 및 BM25 `.pkl` 파일 덤프
* [ ] [`data/assets/banned_terms.json`](data/assets/banned_terms.json): 식약처 행정처분 및 고시 기준 금지 표현 패턴 추가
* [ ] [`data/assets/claim_ladder.json`](data/assets/claim_ladder.json): 효능별 0~2단계 표현 및 필요 시험 자산 보강
* [ ] [`src/cosmetic_agent/rag/hybrid.py`](src/cosmetic_agent/rag/hybrid.py): Dense 10 + BM25 10 순위를 RRF 점수로 합산하고 법령 최소 2개 보장

### ✍️ 3. 프롬프트 · 판정 파트
* [ ] [`src/cosmetic_agent/workflow/prompts.py`](src/cosmetic_agent/workflow/prompts.py): `JUDGE_PROMPT`와 `SUGGEST_PROMPT`에 실무 Few-shot 예시 추가
* [ ] [`src/cosmetic_agent/models/gpt_judge.py`](src/cosmetic_agent/models/gpt_judge.py): `with_structured_output`으로 일관된 JSON 추출 로직 완성
* [ ] [`src/cosmetic_agent/domain/schemas.py`](src/cosmetic_agent/domain/schemas.py): Pydantic `@model_validator`로 조건부/불가 판정의 필수 필드 검증 강화
* [ ] [`src/cosmetic_agent/domain/verifier.py`](src/cosmetic_agent/domain/verifier.py): 제안 문구의 숫자(정규식 `\d+%`)와 시험성적서 수치 일치 여부 대조

### 📊 4. 평가 파트
* [ ] [`data/golden_set/dev.jsonl`](data/golden_set/dev.jsonl): 실험용 30건 이상 문구와 정답 라벨(level, violation_type, 근거ID) 구축
* [ ] [`data/golden_set/holdout.jsonl`](data/golden_set/holdout.jsonl): 최종 검증용 20건 이상 블라인드 벤치마크 데이터 구축
* [ ] [`eval/metrics/eval_metrics.py`](eval/metrics/eval_metrics.py): Macro-F1 및 검색 Hit@4 함수 구현
* [ ] [`eval/run_eval.py`](eval/run_eval.py): 골든셋 순회 후 R0(규칙) vs R1(GPT) vs R4(최종) 비교표 출력

### 🧠 5. 파인튜닝 파트
* [ ] [`finetune/dataset/generate_synthetic.py`](finetune/dataset/generate_synthetic.py): 금지어 변형 마케팅 문구 300~500건 생성 후 검수
* [ ] [`finetune/dataset/validate_leakage.py`](finetune/dataset/validate_leakage.py): Train 세트와 Dev/Holdout 세트 간 텍스트 누수 0건 검증
* [ ] [`finetune/recipes/qlora_qwen.py`](finetune/recipes/qlora_qwen.py): Colab T4에서 Qwen 3B 4-bit QLoRA 학습
* [ ] [`src/cosmetic_agent/models/ft_judge.py`](src/cosmetic_agent/models/ft_judge.py): 학습된 LoRA 가중치를 로드하여 추론하는 어댑터 연결

### 🖥️ 6. 화면 · 발표 파트
* [ ] [`app/components/sidebar.py`](app/components/sidebar.py): 가상 제품 선택 시 보유 시험 성적서 동적 체크박스 렌더링
* [ ] [`app/components/cards.py`](app/components/cards.py): 가능(초록), 조건부(노랑), 불가(빨강) 신호등 카드 및 근거 조항 아코디언 추가
* [ ] [`app/streamlit_app.py`](app/streamlit_app.py): 상세페이지 일괄 검토 탭에서 문장별 위반 하이라이트 UI 구현

---

## 4. 개발 및 실행 가이드

### 1) Qdrant Cloud 준비

이 프로젝트의 기본 벡터 데이터베이스는 로컬 Docker가 아닌 **Qdrant Cloud**입니다.

1. Qdrant Cloud에서 클러스터를 생성합니다.
2. 클러스터의 HTTPS Endpoint와 API Key를 발급받습니다.
3. API Key는 저장소에 커밋하지 말고 로컬 `.env` 또는 배포 서비스의 Secret 환경변수로 관리합니다.

Qdrant 컬렉션은 별도로 수동 생성하지 않아도 됩니다. `indexing/05_build_indexes.py`가 컬렉션이 없으면 생성하고, 기존 컬렉션이 있으면 청크를 멱등적으로 upsert합니다.

### 2) 환경 변수 설정
```bash
cp .env.example .env
# .env 파일에 OpenAI 및 Qdrant Cloud 접속 정보를 입력합니다.
```

필수 설정 예시:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

QDRANT_URL=https://your-cluster-id.region.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_cloud_api_key_here
QDRANT_COLLECTION_NAME=cosmetic_ad_rules_v2
```

### 3) 패키지 설치
`uv`를 사용하여 가상환경 및 의존성을 동기화합니다:
```bash
uv sync --extra dev
```

### 4) 데이터 파이프라인 실행 (오프라인 1회)

청킹 결과를 만든 뒤 OpenAI 임베딩을 생성하여 Qdrant Cloud에 저장하고, BM25 인덱스를 로컬 파일로 생성합니다.

```bash
uv run python indexing/03_chunk_articles.py
uv run python indexing/05_build_indexes.py
```

> `data/02_processed/bm25_index.pkl`은 실행 환경에 필요한 검색 인덱스입니다. 배포 시 파일을 함께 제공하거나 배포 빌드 과정에서 다시 생성해야 합니다.

인덱싱 결과 검증:

```bash
uv run python scripts/validate_rag.py
```

### 5) 서버 및 대시보드 실행
* **FastAPI 백엔드:**
  ```bash
  uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
  ```
  Swagger Docs: `http://localhost:8000/docs`

* **Streamlit 프론트엔드:**
  ```bash
  uv run streamlit run app/streamlit_app.py
  ```
  Web UI: `http://localhost:8501`

### 6) 단위 테스트 및 결과 계약 검증
```bash
uv run pytest
```
