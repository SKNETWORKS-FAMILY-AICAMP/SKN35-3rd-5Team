# 화장품 광고 문구 판정 및 교정 에이전트 (SKN 35기 3차 프로젝트)

화장품 표시·광고 법령, 식약처 고시, 실증 지침을 기반으로 광고 문구의 위반 여부를 사전 심사하고, 사내 보유 실증 자료 범위 내에서 가장 설득력 있는 문구로 교정해 주는 AI 컴플라이언스 시스템입니다.

---

## 성분으로 광고·홍보 문구 만들기

### 통합 챗봇

최신 `dev`의 홈·시장 비교·제품 등록 기능과 함께 사용할 수 있습니다. 기존 **성분으로 문구 만들기**와 **통합 챗봇**은 유지하고, `dev`의 생성 화면은 **제품 기준 광고문 생성** 메뉴(`app/views/project_generate.py`)로 제공합니다. `POST /generate`는 성분 기반 요청(`ingredients`)과 제품·실증 기반 요청(`instruction`)을 모두 지원하며 각 요청에 맞는 기존 응답 계약을 반환합니다. 챗봇은 `api` 또는 별도 백엔드 없이 FastAPI를 내장 실행하는 `local` 모드에서 실제 서비스에 연결됩니다.

기존 검토·생성 화면과 함께 왼쪽 작업 메뉴의 **통합 챗봇** 또는 화면 왼쪽 하단의 동그란 채팅 버튼을 사용할 수 있습니다. 작은 팝업과 전체 챗봇 화면은 같은 대화를 공유합니다. `“이 광고 문구를 검토하고 고쳐줘”`, `“판테놀과 히알루론산이 들어간 크림의 SNS 광고문 만들어줘”`, `“두 번째 후보를 더 발랄하게 바꿔줘”`처럼 요청하면 모델이 의도와 필요한 정보를 추출하고 기존 검토·생성 서비스를 실행합니다. 정보가 부족하면 추가 질문을 합니다.

챗봇은 기본적으로 일반 화장품·실증 없는 새 제품 기준이며, 전체 챗봇 화면에서 프로젝트 제품·실증 자료 사용을 선택할 수 있습니다. 제품/실증 기준을 바꾸면 이전 성분이 다른 제품에 적용되지 않도록 새 대화를 시작합니다. 대화는 현재 Streamlit 세션 안에서 유지되며 새로 연결하거나 서버를 재시작하면 사라질 수 있습니다. 실제 사용에는 `UI_DATA_MODE=api`, 모델 API 키, 검토 서버와 검색 인프라가 필요합니다. 데모 모드에서 챗봇 결과를 만들어 보여주지 않습니다.

`POST /chat`은 `message`, 선택적 `context`(성분·채널·어조·작성 요청·이전 후보), `history`(최근 12개 메시지), `product`를 받습니다. 응답은 `intent`(`review`/`generate`/`clarify`), `message`, 갱신된 `context`, 검토 또는 생성 결과입니다. 기능성과 실증 자료는 자연어에서 자동 추가하지 않습니다. 생성 후보는 기존 규칙 검사와 후보별 검토를 그대로 수행합니다.

문구 분위기의 **눈길 끄는** 옵션은 질문형·명령형·루틴 중심의 감성적 비유로 광고 도입을 강화합니다. 효능·수치 근거의 기준과 후보별 검토는 동일하게 유지합니다. API의 `tone`에도 `눈길 끄는`을 지정할 수 있습니다.

왼쪽 작업 메뉴의 **성분으로 문구 만들기**에서 실제 성분을 쉼표/줄바꿈으로 입력하고 제품명, 제품 구분, 채널, 어조를 선택합니다. 기본은 실증 없는 새 제품입니다. 프로젝트 자료를 사용하려면 실제 동일 제품의 근거인지 확인하세요. 성분 자체의 효능을 완제품의 효과로 추정하지 않도록 생성한 뒤 금지 표현·수치 검증과 기존 RAG 검토를 후보별로 수행합니다. 검토 실패·판단보류·위반 후보는 검토통과로 표시하지 않습니다. 자동 검토는 법률 준수를 보장하지 않습니다.

실제 생성에는 `.env`의 `OPENAI_API_KEY`와 실행 환경의 `UI_DATA_MODE=api`, 기존 검토 API 및 검색 인프라가 필요합니다. 데모 모드에서는 실제 생성 결과를 제공하지 않습니다. API는 `POST /generate`이며 요청은 `ingredients`(성분명 배열), `product`(기존 제품 카드), `channel`(SNS/상세페이지/배너), `tone`(담백한/감성적인/발랄한/눈길 끄는)입니다. 응답은 후보별 문구·상태·확인 사유·검토 근거를 반환합니다.

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
