# FastAPI 사용 방법

API는 광고 문구 검토와 신규 광고 문구 생성을 제공합니다.
판정 모델, RAG, 제안·생성 및 재검사는 서비스와 LangGraph 워크플로에서 구현합니다.

## 실행

프로젝트 루트에서 실행합니다.

```powershell
uv sync --extra dev
uv run uvicorn api.main:app --reload --port 8000
```

`http://localhost:8000/docs`에서 **Try it out**으로 요청할 수 있습니다.
실제 서비스 실행에는 환경 설정과 검색 인프라가 필요합니다.

## 요청

- `GET /health`: 서버 생존 확인 (모델/검색기 가용성 검사는 아님).
- `POST /review`: 단일 문구. `copy_text` 최대 5,000자, 기존 화면과 응답 호환.
- `POST /review/bulk`: 문장별 검토. `full_text` 최대 50,000자, 100문장.
- `POST /generate`: 자유로운 `instruction`과 선택적 `ingredients`·제품 정보를 동일한 LangGraph로 처리합니다. 성분은 필수가 아닙니다. 응답 후보에 검토 상태와 후보별 검토 근거를 포함합니다.
- `POST /chat`: 자연어 의도 파악 → 대화 맥락 반영 → 통합 생성/검토/근거 기반 규정 질문 답변. 성분 누락은 추가 질문 사유가 아닙니다.
- `GET /search`: Qdrant Cloud + BM25 규정 검색.

`/review/bulk` 요청 예시:

```json
{
  "full_text": "보습을 돕습니다. 촉촉한 피부 케어!\n매끈한 사용감",
  "product": {
    "product_id": "CREAM_001",
    "name": "수분 크림",
    "category": "일반",
    "functional_type": null,
    "owned_evidence": [
      {
        "test_type": "인체적용시험",
        "item": "보습 개선",
        "value": "4주 후 42.5% 개선",
        "institute": "시험 기관명"
      }
    ]
  }
}
```

단일 요청은 `full_text` 대신 `copy_text`를 사용합니다.
제품은 `일반` 또는 `기능성`이며, 보유 시험이 없으면 `owned_evidence`를 생략하거나 `[]`로 보냅니다.
기능성 제품은 `functional_type`에 해당 유형을 전달합니다.

문장은 줄바꿈, 느낌표, 물음표, 공백 또는 텍스트 끝 앞의 마침표로 분리합니다.
소수(`42.5%`)는 보존하고, 모든 문장에 같은 제품/시험 자료를 전달합니다.
정규식 기반이므로 약어 등 복잡한 문장은 줄바꿈으로 구분하는 편이 안전합니다.
동기 엔드포인트의 작업 스레드에서 문장 순서대로 서비스를 호출합니다.

## 응답

`/review`는 객체 하나, `/review/bulk`는 입력 문장 순서의 객체 배열을 반환합니다.
각 객체에는 `request_id`, `input_text`, `result`, `timing`이 들어갑니다.
`result`에는 `status`, `level`(0 가능 / 1 조건부 / 2 불가), `citations`(근거 조항),
`suggestion`(수정 문구), `next_test`(다음 시험), `review_notes` 등이 들어갑니다.
판단보류이면 `level`은 `null`입니다. 실제 판정 내용은 기존 서비스가 제공합니다.
입력 누락, 공백 문구, 잘못된 제품 유형, 길이/문장 수 초과는 HTTP 422입니다.
일괄 검토 중 서비스 오류가 발생하면 요청 전체가 실패하고 부분 결과를 반환하지 않습니다.

`/generate`는 `생성완료` 또는 `생성보류`와 함께 검증을 통과한 후보만 반환합니다.
후보에는 강도(`strong`, `balanced`, `safe`), 사용한 실증자료, 근거 ID와 검증 결과가 포함됩니다.

## 테스트 및 현재 범위

```powershell
uv run pytest tests/integration/test_api.py -q
```

API 테스트는 외부 인프라 없이 테스트 서비스를 주입합니다.
테스트 응답은 연결 확인용 `판단보류`이며 실제 법적 판정이 아닙니다.
외부 인프라를 사용하는 실제 생성 검증에는 OpenAI 및 Qdrant Cloud 환경변수가 필요합니다.
