# Beaurette — Streamlit UI

화장품 광고 문구를 **규정 문서를 근거로** 검토하고 더 안전한 문구를 제안하는 RAG 챗봇의 화면입니다.
화면 담당 파일은 `app/` 와 `.streamlit/` 에만 있고, 백엔드(`src/`·`api/`)는 건드리지 않습니다.

## 실행

```bash
uv sync --extra dev
uv run streamlit run app/streamlit_app.py      # 저장소 루트에서 실행 (.streamlit/config.toml 을 읽음)
```

| 환경변수 | 값 | 뜻 |
|---|---|---|
| `UI_DATA_MODE` | `mock`(기본) / `api` | Mock 응답으로 동작할지, FastAPI 서버(`API_BASE_URL`)에 붙을지 |
| `UI_MOCK_DELAY` | `1`(기본) / `0` | Mock 검토 단계 연출 속도. `0` 이면 기다리지 않음(리허설·점검용) |

API 모드: `uv run uvicorn api.main:app --port 8000` 을 띄운 뒤 `UI_DATA_MODE=api` 로 실행합니다.
연결 상태는 화면 오른쪽 위와 사이드바 아래에 표시됩니다. API 가 실패하면 Mock 으로 바꿔치기하지 않고 오류를 보여 줍니다.

## 화면 구조

```
┌ 왼쪽 (탐색) ────────┬ 가운데 (대화) ─────────────────────────┬ 오른쪽 (근거 · RAG) ─────┐
│ 로고                │ 대화 제목 · 데이터 상태                 │ 근거 n건 · 법령/지침/사례 │
│ [새 대화]           │                                       │ 검색한 표현              │
│ 작업                │  사용자 문구 ───────────────▶ (오른쪽)  │ 표현 단계 (실증 기준)     │
│  검토 대화          │  뷰렛 AI · 규정 문서 n건을 근거로        │ ┌ 근거 │ 원문 문서 │ 과정 ┐│
│  상세페이지 검토     │  [판정] 한 줄 요약                     │ │ [1] 화장품법 제13조 …   ││
│  규정 · 가이드라인   │  ┌ 답변 문서 ──────────────────────┐  │ │   스니펫 (관련 표현 표시) ││
│ 프로젝트 (검토 기준) │  │ 검토한 문구 · 문제 표현 [1][2]   │  │ │ [2] 시행규칙 별표5 …     ││
│  제품 ▾             │  │ 수정 제안 [복사] · 다른 표현      │  │ └────────────────────────┘│
│  ☑ 실증 자료        │  │ 출처 [1][2][3]                  │  │                          │
│ 최근 대화           │  └────────────────────────────────┘  │                          │
│ ● 데모 데이터        │ 검토 기준 줄 · [입력창]                 │                          │
└────────────────────┴───────────────────────────────────────┴──────────────────────────┘
```

| 화면 | 파일 | 내용 |
|---|---|---|
| 홈 (첫 화면, `/`) | `views/home.py` | 서비스 소개 — 문제 · 검토 방식 · 기능 · 근거 자료. 「시작하기」로 검토 대화에 들어간다. 사이드바 없음 |
| 검토 대화 (`/review`) | `views/review.py` | 질문 → AI 답변(판정 · 검토한 문구 · 문제 표현 · 수정 제안 · 다른 표현 · 출처), 오른쪽 근거 · 원문 문서 · 검토 과정 |
| 상세페이지 검토 | `views/bulk.py` | 긴 글을 문장 단위로 검토, 문장별 결과 · 교정본 복사/내려받기 |
| 규정 · 가이드라인 | `views/library.py` | 조항 검색(하이브리드 검색 결과) · 관리지침 금지 표현 · 식약처 적발 사례 |

- 답변의 `[n]` 번호 = 오른쪽 근거 번호. 답이 어떤 조항에서 나왔는지 바로 찾게 했다.
- **프로젝트**(검토 기준 = 제품 · 보유 실증 자료)는 왼쪽에서 바꾼다. 실증 자료를 해제하면 "검토 기준이 바뀌었습니다" 안내가 뜨고,
  다시 검토하면 그 자료 없이 쓸 수 있는 단계까지만 제안한다 (발표 데모 핵심 장면: Lv2 → Lv1).
- Mock 응답은 화면에 항상 "데모 데이터"로 표시하고, 성능 수치는 보여 주지 않는다.

## 폴더

```
app/
  streamlit_app.py        진입 파일 (경로 처리 · 페이지 설정 · CSS 주입 · 사이드바 · 내비게이션)
  views/                  화면 4개 (home · review · bulk · library) — 레이아웃과 위젯만, HTML 은 components 가 만든다
  components/
    styles/base.css       디자인 토큰(:root) + 공통 컴포넌트 CSS — 색·글자·반경은 여기서만 바꾼다
    styles/pages.css      상세페이지 · 라이브러리 전용 CSS
    styles/home.css       홈 전용 CSS (명조 제목 · 격자 · 움직임)
    landing.py            홈 섹션 (데이터 → HTML 순수 함수) + 움직임 스크립트. 예시는 Mock 엔진 결과, 숫자는 data/ 실측
    cards.py              가운데 답변 블록 (데이터 → HTML 순수 함수)
    panels.py             오른쪽 근거 · RAG 패널 (데이터 → HTML 순수 함수)
    suggest.py            최신 답변의 수정 제안 — 후보 고르기(근거 최대 · 균형 · 가장 안전) · 복사 · 이 문구로 다시 검토
    progress.py           검토 진행 카드 — backend.review_events() 가 실제로 낸 이벤트만 그린다
    interact.py           위험 표현 ↔ 오른쪽 근거 연동 (브라우저 스크립트)
    blocks.py             확장 블록 (차트 · 추가 질문) — 응답에 ui.blocks 가 있을 때만
    sidebar.py            왼쪽 탐색 · 프로젝트 · 최근 대화
    context.py            프로젝트(검토 기준) 위젯과 current() — 화면들은 current() 로 읽기만 한다
    threads.py            대화 기록 (세션 안에서만 유지)
    theme.py              CSS 주입, 판정 → 상태 이름(수정 필요 · 실증 필요 · 사용 가능 · 전문가 검토)
    brand.py, icons.py, layout.py  캐릭터·로고 · 아이콘 · 공통 도우미
  services/
    backend.py            화면이 부르는 유일한 데이터 함수 (Mock / API 전환)
    mock.py               데모용 Mock 판정 엔진 (응답에 mock=True)
    data_sources.py       data/ 원문(법령 XML · 관리지침 · 적발 사례 · 규칙 자산) 읽기
    contract.py           화면이 받는 데이터 모양(TypedDict)과 예시 응답
  static/                 글꼴(Pretendard · IBM Plex Mono · 홈 제목용 Noto Serif KR, OFL) · 로고 · 캐릭터(rabbit-*.webp) · 홈의 검토 화면 캡처(landing/)
```

## 디자인 원칙

방향: **"근거 편집실"** — 문서를 근거로 답하는 LLM 챗봇. 참고: DietCheck 의 제품감(종이색 · 숲색 하나 · 장식 절제),
COOA 의 도메인 구조(위험도 · 권장 문구 · RA 검토 권고), 팀 캐릭터(실험복 토끼 연구원).

- **색**: 종이색 바탕 `#F6F3EC` · 사이드바 `#EFEBE2` · 면 `#FFFDF9` + 잉크 `#17201B` + 강조색 숲색 `#1F5A47` 하나.
  판정 색은 채도를 낮춰(테라코타 `#A8471F` · 황토 `#865B10`) **점 · 왼쪽 선 · 밑줄**로만 쓴다. 넓은 색 면 · 큰 경고 박스는 쓰지 않는다.
- **형태**: 반경 6 · 8 · 10 · 12px, 1px 선, 그림자 없음. 오른쪽 패널만 한 장의 면으로 묶고, 그 안은 상자 대신 선으로 나눈다.
- **글자**: Pretendard 여섯 단계 — 첫 화면 24 · 페이지 제목 20 · 핵심 문구 17 · 본문 15 · 보조 13.5 · 메타 12.5px.
  굵기 400 · 600 · 700. 숫자 · 조항 번호는 IBM Plex Mono. 보조 글자 대비 4.5:1 이상.
- **캐릭터**: 로고 마크 · AI 아바타 · 첫 화면(빈 상태) 세 곳에만. 장식으로 늘리지 않는다.
- **예시**: 첫 화면 시작 문구 3개(판정 셋이 하나씩 나오게)뿐.
- **움직임**: 뜻이 있는 것만 — 새 답변이 처음 도착할 때 한 번(판정 → 검토한 문구에 밑줄이 그어짐 → 문제 표현 → 수정 제안 → 출처,
  오른쪽은 표현 단계 막대 → 근거 조항), 강도를 바꾼 직후 문구 교체, 근거 번호를 누르면 그 조항에 형광펜.
  다시 그릴 때는 반복하지 않고(`is-arrive` 는 처음 한 번만 붙는다), 시스템 "동작 줄이기"면 전부 멈춘다. 가짜 진행률 · 가짜 타이핑은 없다.
- **홈**: 색 · 반경 · 선은 위와 같고, 제목만 명조(Noto Serif KR 600 — KS X 1001 한글 2,350자 subset, 327KB)로 쓴다.
  격자는 최대 1200px · 간격 24px, 같은 줄의 칸은 높이를 맞추고 칸 안 그림 영역은 높이를 고정한다(기능 카드는 subgrid).
  움직임은 교정 동작(밑줄 → 판정 → 근거 → 제안 → 역검증, 예시 3개를 돌아가며) · 적발 발표 띠 · 화면에 들어올 때 한 번 올라오기 ·
  숫자 세기 · 실증을 켜고 끄면 제안 단계가 바뀌는 반복. CSS 기본값이 최종 상태라 스크립트가 없거나 "동작 줄이기"여도 내용은 다 보인다.
- Streamlit 내부 구조에 기대는 CSS 는 `data-testid` 두 개(메인 여백 · 헤더)와 키 컨테이너 안의 위젯 라벨 숨김뿐이고,
  나머지는 `st.container(key=…)` 가 붙이는 `.st-key-*` 클래스로만 꾸민다. 홈만 예외로 사이드바 숨김 · 상단 바 고정에 몇 개 더 쓴다(`home.css` 위쪽).

## 팀원 연결 지점

**데이터는 `app/services/backend.py` 한 곳만 바꾸면 된다.** 화면은 이 함수들만 부른다.

| 함수 | API | 비고 |
|---|---|---|
| `review_events(copy_text, product)` | `POST /review/stream` (있으면) → 없으면 `POST /review` | 검토 진행 이벤트 + 결과. 아래 「진행 이벤트」 |
| `review_copy(copy_text, product)` | `POST /review` | `ReviewResponse` 그대로 |
| `review_page(full_text, product)` | `POST /review/bulk` | 문장 분할은 `api/text.py` 와 같은 규칙 |
| `search_rules(query, scope)` | `GET /search` | `[{content, metadata}]` |
| `health()` | `GET /health` | 연결 상태 표시 |
| `list_products()` · `kb_stats()` · `enforcement_trends()` 등 | (없음) | `data/` 파일을 직접 읽음 |

`product` 는 `schemas.ProductCard` 모양이고, `owned_evidence` 에는 왼쪽 「프로젝트」에서 체크한 실증만 담아 보낸다.

**응답 필드 → 화면 위치** (필수 부분은 `src/cosmetic_agent/domain/schemas.py` 의 `ReviewResponse`):

| 응답 필드 | 화면 | 그리는 함수 |
|---|---|---|
| `result.status` · `level` · `violation_type` | 판정 태그 · 한 줄 요약 | `cards.assistant_message` |
| `result.citations[]` (source · article · authority · content_snippet) | 오른쪽 근거 목록 · 답변 아래 출처 줄 · 「근거 n건」 | `panels.evidence_list` · `cards._sources` · `panels.rag_header` |
| `result.suggestion` · `next_test` · `review_notes` | 수정 제안 · "더 강하게 쓰려면" · 요약 | `cards._suggestion` · `cards._next_test` |
| `timing.total_ms` | 응답 시간 | `cards.assistant_message` |

선택 확장 **`ui`** 가 있으면 더 많이 보여 주고, 없으면 해당 블록만 생략한다(모양은 `services/contract.py` 의 `UiExtras`).
API 모드에서 `ui` 가 없으면 `backend._with_rule_highlights` 가 규칙 자산으로 하이라이트만 붙인다.

| `ui` 필드 | 화면에서 쓰는 곳 | 백엔드에서 만들 수 있는 곳 |
|---|---|---|
| `highlights` (위험 표현 위치 · 이유 · 근거 번호 `cites`) | 검토한 문구 밑줄, 문제 표현 목록과 `[n]`, 오른쪽 「검색한 표현」 | `rule_check` 의 `rule_hits` + `judge_claim` |
| `ladder` (표현 단계 · 도달 칸) | 오른쪽 표현 단계 | `RuleEngine.get_ladder_ceiling` |
| `diff` · `reverify` | 수정 제안의 고친 곳 · 역검증 | `suggest_copy` · `verify_copy` |
| `steps` (노드별 상태 · 시간) | 오른쪽 「검토 과정」 탭 | LangGraph 노드 실행 기록 |
| `summary` · `direction` · `alternatives` · `suggestion_source` | 한 줄 요약 · 제안 방향 · 다른 표현 · 출처 | `suggest_copy` 프롬프트 출력 |

| `variants` (대체 문구 후보 · 강한 → 안전) | 수정 제안의 강도 고르기 · 역검증 상태 | `copy_suggester` — 아래 「제안 후보」 |
| `blocks` (`chart` · `question`) | 답변 아래 확장 블록 — **있을 때만** 뜬다 | 데이터가 있거나 사용자 입력이 필요할 때만 보낸다 |

**제안 후보** — `copy_suggester` v6 결과를 `ReviewResponse` 에 그대로 실어 주면 화면이 후보로 옮긴다(`backend._variants_from`).

| 응답 필드 (최상위 또는 `ui` 안) | 뜻 |
|---|---|
| `candidates: list[str]` | 후보 문구, **강한 → 안전 순** 최대 3개 (근거 최대 · 균형 · 가장 안전) |
| `rejected_notes: list[str]` | 역검증에서 탈락한 후보의 사유 (앞에서부터) |
| `used_evidence: list[str]` | 가장 강한 후보가 쓴 보유 실증 |
| `result.suggestion` | 엔진이 고른 후보 — `candidates` 중 하나면 그 칸이 "추천"으로 표시된다 |

`ui.variants` 를 직접 보내도 된다: `{text, tier: strong|balanced|safe, basis, verified: true|false|null, note, chosen}`.

**진행 이벤트** — `POST /review/stream` 이 생기면 NDJSON(한 줄 = 이벤트 하나)으로 받은 것만 진행 카드에 그린다.
없으면(404) 단계 목록 없이 "서버가 검토하는 중 · 경과 n초"(실측)만 보이고 `POST /review` 결과를 기다린다. 퍼센트 막대는 없다.

| 이벤트 | 모양 | 화면 |
|---|---|---|
| 단계 | `{"type": "stage", "key": "rule_check", "status": "start"\|"done"\|"skip", "ms": 12.5}` | 단계 줄 (✓ + 실측 시간). `key` 는 `contract.PIPELINE_STEPS` 의 노드 이름 |
| 조각 | `{"type": "token", "text": "…"}` | LLM 이 요약을 실제로 흘려보낼 때만, 받은 글자를 이어 붙인다 |
| 결과 | `{"type": "result", "resp": ReviewResponse}` | 마지막 한 줄 — 답변으로 바뀐다 |

**화면을 바꾸고 싶을 때**: 레이아웃은 `views/*.py`, 블록의 생김새는 `components/cards.py`·`panels.py` 의 함수 하나,
색·글자·간격은 `styles/base.css` 맨 위 `:root` 토큰. 새 블록을 만들 때도 "데이터 dict → HTML 문자열" 함수로 만든다.
