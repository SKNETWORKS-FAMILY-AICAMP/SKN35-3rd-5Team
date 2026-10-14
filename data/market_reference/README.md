# 화장품 공개 문구·소재·사업 맥락 데이터 v0.1

수집일: 2026-10-13. 기존 법령·골든셋과 분리한 시장 참고 데이터다.
공식 브랜드몰·올리브영·무신사 뷰티·뷰티컬리 공식 자료에서 제품11개, 판매 구성13개,
문구 관찰28개, 제품 대표 이미지 URL8개, 회사 매출 맥락1개, 출처26개를 연결했다.
브랜드 채널 실적·제품군 판매 이력 등 공개 지표15개와 회사6개·관계7개를 별도로 연결했다.
판매 구성에는 과거 행사 발표2개가 포함되어 있으며 현재 구매 가능한 상품13개를 확인했다는 뜻은 아니다.
플랫폼·회사 연결 범위는 [PLATFORM_COMPANY_MAP.md](PLATFORM_COMPANY_MAP.md)를 참고한다.
범위와 활용 기준은 [SALES_AVAILABILITY.md](SALES_AVAILABILITY.md)를 참고한다.
문구별 실제 광고 성과 데이터는 0건이다. 미확인 값을 0이나 추정 매출로 채우지 않았다.

팀 공유용 표는 [OBSERVATIONS.md](OBSERVATIONS.md), 시스템 입력용은 `market_context.jsonl`이다.

## 파일과 연결 기준

| 파일 | 담긴 내용 | 연결 키 |
|---|---|---|
| `sources.json` | 공식 출처 URL, 열람일, 페이지 범위, 캐시 한계 | source_id |
| `platform_expansion.json` | 추가 플랫폼의 출처·제품·구성·문구·이미지·지표 | 기존 파일과 ID로 합쳐 검증/내보내기 |
| `platforms.json` | 올리브영·무신사 뷰티·뷰티컬리의 수집 범위 | platform_id |
| `companies.json`, `company_relations.json` | 회사 역할·브랜드 운영·플랫폼 협력 | company_id → brand/platform; 제조 관계는 별도 증거 필요 |
| `company_context.jsonl` | 회사/산업 맥락용 문서 | COMPANY_CO_*; 효능·규정·문구 성과와 분리 |
| `coverage_summary.json` | 생성 시 검증한 데이터 수량·미확보 범위 | 수집/앱 연결 상태 확인 |
| `products.json` | 제품 정체성·상품명 기반 성분 태그 | product_id |
| `offers.json` | 채널·국가·본품/리필·가격·옵션 조건 | offer_id → product_id |
| `copy_observations.jsonl` | 짧은 원문, 위치, 소구 태그, 제한 조건 | observation_id → offer_id/source_id |
| `creative_assets.json` | 페이지에서 확인한 대표 이미지 URL | asset_id → offer_id |
| `business_context.json` | 회사 단위 매출과 공개 범위 | context_id → source_id; 문구에 연결 금지 |
| `public_outcomes.json` | 브랜드 채널 매출 구간·제품군 누적 판매·어워즈 | signal_id → brand/product_id/source_id; 광고 성과와 분리 |
| `internal_performance.schema.json` | 실제 회사 광고 성과를 받을 JSON Schema | creative_id + version + offer/channel/audience + period |
| `internal_performance.json` | 실제 성과 자료가 들어갈 자리, 현재 빈 records | 캠페인 내보내기 자료 수령 후 입력 |
| `market_context.jsonl` | 분리된 시장 참고용 RAG 문서 | MARKET_COPY_* → observation_id |

ANUA 단품30mL와 올리브영30mL+리필30mL는 같은 제품 계열이지만 다른 판매 구성이다.
키엘의 두 크림은 서로 다른 제품이다. 토리든의 브랜드/라인 문구는 특정 상품에 강제 연결하지 않는다.
한 판매 페이지에서 관찰한 문구들이 실제로 동일한 유료 광고에 함께 노출됐다는 뜻은 아니다.

## 무엇을 확인했고 무엇이 비어 있는가

- 공개 문구·가격·구성: 웹 도구가 반환한 페이지의 관찰값. 결제 가격이나 실시간 재고를 보장하지 않는다.
- 소구 태그: 분석자가 붙인 분류다. 브랜드가 공개한 전략이나 성과 점수가 아니다.
- 시험 조건: 제품 페이지 각주를 요약했다. 시험 원본·개인별 반응·자사 제품에 적용 가능한 효능 근거가 아니다.
- 타깃: 페이지에 기재된 사용 대상 또는 메시지 대상만 기록했다. 임상 참여자의 나이·성별을 광고 타깃으로 옮기지 않는다.
- 광고 이미지: 제품 페이지의 대표 이미지 URL8개를 연결했다. 유료 광고 원본이 아니며 이미지의 색상·모델·레이아웃·OCR는 아직 검수하지 않았다. 파일은 내려받지 않았다.
- 매출: 더파운더즈 공식 회사 소개의2025년7,000억원대 달성 표기는 회사 규모 맥락이다. 정확한 감사 수치·ANUA 단일 브랜드·PDRN 세럼 매출로 해석하지 않는다.
- 문구별 매출·노출·클릭·구매·광고비·유료 광고 타깃: 이번 출처에서 확인하지 못해 전부 null이다.
- 리뷰·평점: 페이지 버전과 집계 범위가 달라 이번 버전에서는 제외했다. 리뷰 개수를 판매량으로 환산하지 않는다.
- 추이: 수집일 한 시점의 데이터다. 과거 가격·문구 변경 시점이나 매출 추세를 복원했다고 주장하지 않는다.

출처를 여러 번 열었을 때 토리든 기획 월과 일부 올리브영 리뷰 수가 달랐다.
캐시 시점이 불명확한 행사는 날짜·판매량·실적 비교에 넣지 않았다.
문구의 각주 기호는 제거한 짧은 전사이며, 조건은 qualification에 별도 보존했다.

## 서비스에서 사용하는 방법

1. 기존 규정·자사 보유 근거로 문구의 사용 가능성을 검토한다.
2. 이 데이터에서 동일 카테고리의 성분·보습·기간·구성 혜택·순위 등 소구 방식을 참고한다.
3. 후보를 제안하되 ‘시장 사례에서 사용된 표현’으로 설명한다. 합법·효능 입증·매출 상승 근거라고 설명하지 않는다.
4. 실제 회사 광고 성과를 `internal_performance.schema.json`에 맞춰 연결한다.
5. 같은 제품·판매 구성·채널·타깃·이미지 버전·기간·기여 기간을 대조하고, 무작위 A/B 실험 여부를 확인한다.

예시 질문: ‘PDRN 세럼은 성분 중심 외에 어떤 소구 방식으로 후보를 만들 수 있나?’
→ 공개 데이터에서 성분·유명인 배지·리필 구성 사례를 찾고, 후보별 테스트 가설을 제안할 수 있다.
‘그중 어떤 문구가 가장 잘 팔렸나?’에는 현재 자료만으로 답할 수 없다.

`market_context.jsonl`은 기존 `data/02_processed/chunks.jsonl`에 합치지 않았다.
authority를 부여하지 않고 규정·효능·성과 라벨 사용을 명시적으로 차단했다.
아직 앱의 검색 경로나 Qdrant에는 연결하지 않았다. 향후 별도 컬렉션/필터 및 원문 ID 조회로 연동한다.
공개 문구를 정답 골든셋이나 미세조정 학습 정답으로 쓰지 않는다.

## 내부 성과 수집·전처리 기준

- 최소 수집: 문구 원문·creative ID/version·이미지 버전·제품/판매 구성·국가·채널·타깃 그룹·기간·가격/할인·노출·클릭·세션·구매·매출·광고비·기여 기간·출처.
- 순매출 정의: 취소·반품·세금·배송비 처리 기준을 `measurement_notes`에 합의해 기록한다.
- CTR = clicks / impressions, 구매 CVR = purchases / sessions, ROAS = net_revenue / ad_spend. 분모가0 또는null이면 지표도null.
- 같은 creative ID도 문구나 이미지가 바뀌면 새 version을 부여한다. 동일 기간의 중복 내보내기는 합산하지 않는다.
- 채널별 전환 기여 방식이 다르면 합치지 않는다. 주문·광고 플랫폼 집계의 중복 구매도 제거한다.
- `randomization_verified=false`인 실적은 관찰 비교다. ‘문구 때문에 매출이 올랐다’는 인과 라벨로 사용하지 않는다.
- 타깃은 집계 그룹만 사용하며 고객 개인 정보는 수집하지 않는다.
- 현재는 연결 계약만 정의했다. 실적 수집기·성과 순위 모델·A/B 통계 검정은 아직 구현하지 않았다.

## 이미지 검수 시 추가할 항목

`visual_annotations`에 검수자·검수일·인물/유명인 여부·제품 중심/사용 장면·색상·수치 배지·전후 비교·OCR·검수 신뢰도를 기록한다.
페이지 썸네일을 유료 광고 이미지로 간주하거나 보지 않은 이미지를 설명하지 않는다.
추가 시에도 실제 광고 플랫폼의 creative ID와 연결되기 전에는 성과 라벨을 붙이지 않는다.

재생성/검증:

```powershell
uv run python scripts/build_market_reference.py
uv run python -m pytest tests/unit/test_market_reference.py -q
```

원본 공식 사이트 링크는 sources.json과 관찰표에 있다. 공개 문구의 존재를 기록한 자료이며 타사 표시·광고의 적법성을 판정한 자료가 아니다.
확장 배치의 문구에 생략된 legal_status·performance_status·audience_status는 내보내기 시
각각 not_assessed·not_disclosed_in_collected_sources·unknown으로 정규화한다. 누락을 승인·성과0으로 처리하지 않는다.
