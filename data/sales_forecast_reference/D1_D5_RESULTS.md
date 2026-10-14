# D1·D5 결과 확인본

작성일: 2026-10-14. `FORECAST_DATA_PLAN.md`에 따라 D1 → D5 순서로 작성했다.
D2 이후 수집·가격 보강·매출 계산·UI 적용·커밋/푸시는 진행하지 않았다.

## D1 · 처분 기준표

원문: `data/01_raw/law/화장품법_시행규칙.xml`의 제29조제1항·별표7 제2호 더목.
기존 XML의 시행일은 2026-04-02, 별표7 개정 표시는 2025-02-07이다.
XML이 연결한 [공식 별표 PDF 9페이지](https://www.law.go.kr/LSW/flDownload.do?flSeq=162933391)를 내려받아 시각적으로 열과 공란도 대조했다.
별표5는 위반 내용, 별표7은 처분 기간을 정한다.

| 별표5 제2호 | 1차 | 2차 | 3차 | 4차 이상 |
|---|---:|---:|---:|---|
| 가·나·카목 | 3개월 | 6개월 | 9개월 | **원문 공란 → null·개별 검토** |
| 다~차목 | 2개월 | 4개월 | 6개월 | 12개월 |

같은 기간이어도 **표시 위반은 해당 품목 판매업무정지 / 광고 위반은 해당 품목 광고업무정지**다.
광고업무정지를 판매 금지 또는 품목 매출 0으로 바꾸지 않는다.

`penalty_schedule.json`의 핵심 구조:

```json
{
  "schedules": [{
    "schedule_id": "ANNEX7_2_DEO_1",
    "rule_items": ["2가", "2나", "2카"],
    "violation_types": ["기능성오인", "의약품오인"],
    "sanction": {"표시": "해당 품목 판매업무정지", "광고": "해당 품목 광고업무정지"},
    "months_by_offense": [3, 6, 9],
    "verified_against_raw": true
  }],
  "mapping_policy": {"violation_type_only_lookup_allowed": false},
  "detection_probability": null,
  "revenue_loss": null
}
```

이는 형식 예시이며 실제 파일에는 두 처분군 전체, 4차 이상 공란 상태, 원문 열, 출처 SHA-256, law_id 11개 연결표가 있다.
violation_types는 현재 규칙 자산에 명시된 연결에서 추출했다. 엔진에 아직 없는 유형은 빈 목록이며 억지로 라벨을 부여하지 않았다.
`LAW_시행규칙_별표5-2가`처럼 구체적인 law_id를 우선한다. 같은 대분류에 다른 목이 들어갈 수 있어 violation_type만으로 기간을 고르지 않는다.
복수 위반의 기간을 그냥 더하거나 4차 이상 공란을 직전 값으로 채우지 않는다.

일반기준도 확인했다:

- 복수 위반의 무거운 기준 및 업무정지 가산·병과, 반복 절차 중 가산과 최대 12개월 조건.
- 같은 위반의 최근 1년 처분 이력과 실제 처분일/재적발일 기준. 다른 품목의 품목업무정지 차수는 구분.
- 무단 광고·공익상 필요·기소유예/선고유예 등의 감경 또는 면제 가능성과 적용 조건.
- 수입대행업의 명칭 치환, 3차 이상 과징금 부과대상 제외 등.

`penalty_schedule_source_excerpt.txt`에 해당 원문을 보존했다.
법령 표의 기간만으로 실제 손실액·적발 확률·법적 최대 손실액을 계산하지 않는다.
‘기준 매출×기간’은 후속 단계에서 별도 가정을 붙일 경우에도 매출 노출 시나리오이며 법령이 보장하는 손해 추정값이 아니다.

## D5 · 문구 효과 크기 분포

입력: 기존 `copy_comparison/headline_comparisons.jsonl` **148쌍**, 실험당 1쌍.
공식 Upworthy 탐색용 자료에서 동일 실험·이미지, 각 노출 1,000 이상, 노출 비율 1.2 이하,
무작위 배정 위험 기간 제외 조건으로 이미 추출된 자료를 재사용했다. 새 자료나 확증용 자료를 수집하지 않았다.

계산: **abs((B 클릭/B 노출) ÷ (A 클릭/A 노출) − 1)**.
가중치 없는 선별 표본의 기술통계, 선형 보간 분위수 `h=(n−1)×p` 사용.

| 지표 | 결과 |
|---|---:|
| p25 | 9.24% |
| 중앙값 | 19.11% |
| p75 | 37.44% |
| p90 | 63.10% |
| CTR 차이 95% 구간이 0을 포함하지 않는 쌍 | 29 / 148 = 19.59% |
| B 클릭률이 더 높은 쌍 / 더 낮은 쌍 | 71 / 77 |
| A 클릭률이 0이라 상대 차이 계산에서 제외한 쌍 | 0 |

`copy_effect_size_distribution.json`의 핵심 구조:

```json
{
  "dataset_id": "D5",
  "input_pair_count": 148,
  "absolute_relative_ctr_change": {
    "unit": "ratio",
    "quantiles_percent": {"p25": 9.2387, "median": 19.1122, "p75": 37.4410, "p90": 63.1023}
  },
  "interval_zero_exclusion": {"count": 29, "valid_interval_count": 148, "percent": 19.5946},
  "automatic_cosmetics_revenue_transfer_allowed": false,
  "cosmetics_revenue_uplift": null
}
```

실제 파일은 반올림 전 값을 기록했다. JSON은 비율과 %를 별도 필드로 둔다.
**9.24~37.44%는 상승·하락을 포함한 절대 변화 크기의 p25~p75**다.
좋은 추천 문구의 상승률, 특정 화장품 매출 변화, 사용자별 예측 구간으로 해석하지 않는다.
미국 뉴스 제목 클릭이며 화장품 구매·매출에 자동 적용하지 않는다.
A/B 순서는 승자 순서가 아니고, 분모가 A라 순서를 뒤집으면 변화 크기도 달라진다.
0 미포함 비율은 다중비교 보정 전 구간의 기술통계이며 ‘효과가 입증된 문구 비율’이 아니다.

표시 문구: **‘다른 분야 실험에서 관찰된 문구 효과 크기를 참고한 가정 범위’**.
출처: [공식 탐색용 자료](https://osf.io/download/3vqmp/),
[자료 설명](https://upworthy.natematias.com/about-the-archive.html),
[2024년 품질 정정](https://upworthy.natematias.com/2024-06-upworthy-archive-update.html).

## 재현·검증

```powershell
.\.venv\Scripts\python.exe scripts/build_forecast_d1_d5.py
uv run --no-sync pytest -q
```

D1은 대조한 XML 해시가 바뀌면 중단해 재검토를 요구한다.
D5는 원시 클릭·노출로 다시 계산하고 통계 표준 라이브러리로 분위수를 별도 검증한다.
검증 결과: 전용 테스트 3개 통과, `uv run --no-sync pytest -q` 전체 155개 통과, 신규 코드 Ruff 통과.
미확인 값을 0으로 채우거나 추천 문구별 매출 숫자·적발 확률·브랜드 배분 실적을 만들지 않았다.
