# Beaurette — Streamlit UI

화장품 광고 문구 판정·교정 에이전트의 화면입니다. 화면 담당 파일은 `app/` 와 `.streamlit/` 에만 있고,
백엔드(`src/`·`api/`)는 건드리지 않습니다.

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

## 화면

| 화면 | 파일 | 내용 |
|---|---|---|
| 문구 검토 (첫 화면) | `views/review.py` | 대화형 검토. 가운데 질문 → AI 검토 답변(검토한 문구 · 발견된 이슈 · 대체 문구 · 다른 표현), 오른쪽 검토 요약 · 근거 · 참조 문서 · 검토 과정 |
| 상세페이지 검토 | `views/bulk.py` | 긴 글을 문장 단위로 검토, 문장별 결과 · 교정본 복사/내려받기 |
| 규정 라이브러리 | `views/library.py` | 조항 검색(하이브리드 검색 결과) · 관리지침 금지 표현 · 식약처 적발 사례 |

- 3단 구조: 왼쪽 사이드바(브랜드 · 새 검토 · 화면 이동 · 최근 검토) / 가운데 대화 / 오른쪽 근거 패널.
- 답변 속 위첨자 번호(예: `1·4·5`)는 오른쪽 근거 패널의 번호와 같습니다 — 답이 어떤 조항에서 나왔는지 바로 찾게 했습니다.
- **검토 기준**(제품 · 실증 자료)은 가운데 위에서 바꿉니다. 실증 자료를 해제하면 "검토 기준이 바뀌었습니다" 안내가 뜨고,
  다시 검토하면 그 자료 없이 쓸 수 있는 단계까지만 제안합니다(발표 데모 핵심 장면).
- Mock 응답은 화면에 항상 "데모 데이터"로 표시하고, 성능 수치는 보여 주지 않습니다.

## 폴더

```
app/
  streamlit_app.py        진입 파일 (경로 처리 · 페이지 설정 · CSS 주입 · 사이드바 · 내비게이션)
  views/                  화면 3개 (review · bulk · library)
  components/
    styles/base.css       디자인 토큰 + 공통 컴포넌트 CSS (색은 여기와 .streamlit/config.toml 두 곳만)
    styles/pages.css      상세페이지 · 라이브러리 전용 CSS
    theme.py              CSS 주입, 판정 → 상태 이름(수정 필요 · 실증 필요 · 사용 가능 · 전문가 검토)
    cards.py              가운데 답변 블록 (HTML 문자열을 만드는 순수 함수)
    panels.py             오른쪽 근거 패널 카드
    context.py            검토 기준 바 (제품 · 실증 자료)
    sidebar.py, threads.py  사이드바 · 대화 기록(세션 안에서만 유지)
    brand.py, icons.py, layout.py  마스코트 · 아이콘 · 공통 도우미
  services/
    backend.py            화면이 부르는 유일한 데이터 함수 (Mock / API 전환)
    mock.py               데모용 Mock 판정 엔진 (응답에 mock=True)
    data_sources.py       data/ 원문(법령 XML · 관리지침 · 적발 사례 · 규칙 자산) 읽기
    contract.py           화면이 받는 데이터 모양(TypedDict)과 예시 응답
  static/                 글꼴(Pretendard · IBM Plex Mono, OFL) · 로고 · 마스코트
```

## 디자인 원칙

기준은 레퍼런스 시안(3단 워크스페이스)이다. 같은 폭(1440px)으로 축척을 맞춰 글자 크기·칩 높이·여백·색 면적을 재서 맞췄다.

- 색: 오프화이트 바탕(`#FBFAF7`, 사이드바 `#F6F4EF`) + 잉크 글자 + 강조색 딥 세이지(`#2F5D4B`) 하나.
  판정은 칩과 함께 **"검토한 광고 문구" 상자의 바탕색**으로도 보인다 — 수정 필요(로즈) · 실증 필요(앰버) · 사용 가능(세이지) · 전문가 검토(회색).
- 형태: 카드 반경 16px, 안쪽 패널·상자 12px, 버튼 8~10px, 1px 선 + 아주 옅은 그림자.
- 글자: Pretendard 여섯 단계 — 페이지 제목 22 · 카드 제목 19 · 섹션 제목·핵심 문구 17 · 본문 15 · 보조 13.5 · 메타 12.5px. 굵기 400 · 600 · 700. 숫자·조항 ID 는 IBM Plex Mono.
- 컴포넌트 높이: 이슈 칩 36 · 상태 칩 30 · 내비 항목 44 · 새 검토 46 · 후속 질문 칩 36px.
- 근거 번호: 이슈 문장 끝의 동그라미 번호가 오른쪽 "근거" 카드의 번호와 같다.
- 마스코트(새싹)는 로고 · 답변 아바타 · 첫 화면 · 사이드바 아래 카드 네 곳에만 쓴다. 원본 SVG 는 `static/brand/`.
- Streamlit 내부 구조에 기대는 CSS 는 `data-testid` 두 개(메인 여백 · 헤더)와 키 컨테이너 안의 위젯 라벨 숨김뿐이고,
  나머지는 `st.container(key=…)` 가 붙이는 `.st-key-*` 클래스로만 꾸민다.

## 백엔드 연결 지점

화면은 `app/services/backend.py` 의 함수만 부릅니다. 함수 본문의 API 호출부만 보면 됩니다.

| 함수 | API | 비고 |
|---|---|---|
| `review_copy(copy_text, product)` | `POST /review` | `ReviewResponse` 그대로 |
| `review_page(full_text, product)` | `POST /review/bulk` | 문장 분할은 `api/text.py` 와 같은 규칙 |
| `search_rules(query, scope)` | `GET /search` | `[{content, metadata}]` |
| `health()` | `GET /health` | 연결 상태 표시 |
| `list_products()` · `kb_stats()` · `enforcement_trends()` 등 | (없음) | `data/` 파일을 직접 읽음 |

`product` 는 `schemas.ProductCard` 모양이고, `owned_evidence` 에는 화면에서 체크한 실증만 담아 보냅니다.

응답의 필수 부분은 `src/cosmetic_agent/domain/schemas.py` 의 `ReviewResponse` 와 같습니다. 화면은 아래 **선택 확장 `ui`** 가 있으면
더 많이 보여 주고, 없으면 해당 블록만 생략합니다(모양은 `services/contract.py` 의 `UiExtras`).

| `ui` 필드 | 화면에서 쓰는 곳 | 백엔드에서 만들 수 있는 곳 |
|---|---|---|
| `highlights` (위험 표현 위치 · 이유 · 근거 번호) | 검토한 문구 하이라이트, 발견된 이슈 | `rule_check` 의 `rule_hits` + `judge_claim` |
| `ladder` (표현 단계 · 도달 칸) | 검토 요약의 표현 단계 | `RuleEngine.get_ladder_ceiling` |
| `diff` · `reverify` | 대체 문구의 고친 곳 · 역검증 | `suggest_copy` · `verify_copy` |
| `steps` (노드별 상태 · 시간) | 검토 과정 | LangGraph 노드 실행 기록 |
| `summary` · `direction` · `alternatives` · `suggestion_source` | 답변 첫 문장 · 제안 방향 · 다른 표현 · 출처 | `suggest_copy` 프롬프트 출력 |

`citations` 는 이미 계약에 있습니다(현재 `service.py` 가 빈 목록을 돌려줘 근거 패널이 비어 보입니다 — `TODO: final_state['citations'] 복원`).
