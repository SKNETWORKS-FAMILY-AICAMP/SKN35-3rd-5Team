# RAG 검색 평가

- 실행일: 2026-10-14
- 평가셋: `dev`
- 평가 문항: 33개 (`required_citation`이 있는 문항)
- Top K: 4
- Qdrant 컬렉션: `cosmetic_ad_rules_v2` (59 points)

## 검색 방식별 결과

| 검색 방식 | Hit@1 | Hit@2 | Strict Hit@4 | Evidence Coverage@4 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 21.2% | 30.3% | 42.4% | 66.7% | 0.3351 |
| BM25 | 39.4% | 45.5% | 57.6% | 81.8% | 0.4904 |
| Hybrid | 42.4% | 48.5% | 69.7% | 81.8% | 0.5404 |

## 실패 유형

| 유형 | 건수 |
| --- | ---: |
| `not_retrieved` | 1 |
| `outside_top_k` | 4 |
| `related_citation_only` | 4 |
| `rrf_rank_drop` | 1 |

## Hybrid Hit@K 실패 문항

| ID | 정답 청크 | 실패 유형 | Dense 순위 | BM25 순위 | Hybrid 순위 |
| --- | --- | --- | ---: | ---: | ---: |
| G_DEV_002 | `LAW_시행규칙_별표5-2사` | `related_citation_only` | - | - | - |
| G_DEV_004 | `GUIDE_관리지침_별표1_생리활성` | `related_citation_only` | 11 | 19 | 19 |
| G_DEV_006 | `GUIDE_관리지침_별표1_질병` | `rrf_rank_drop` | 2 | 3 | 5 |
| G_DEV_009 | `LAW_시행규칙_별표5-2다` | `related_citation_only` | 19 | 9 | 9 |
| G_DEV_014 | `GUIDE_관리지침_별표1_피부` | `not_retrieved` | - | - | - |
| G_DEV_022 | `LAW_시행규칙_별표5-2나` | `outside_top_k` | 14 | 10 | 11 |
| G_DEV_031 | `GUIDE_관리지침_별표1_기타` | `outside_top_k` | 17 | 15 | 17 |
| G_DEV_040 | `NOTICE_실증규정_제5조` | `outside_top_k` | - | 7 | 9 |
| G_DEV_043 | `GUIDE_관리지침_별표1_생리활성` | `outside_top_k` | 11 | 6 | 8 |
| G_DEV_045 | `LAW_시행규칙_별표5-2사` | `related_citation_only` | - | - | - |

## 실패 유형 해석

- `index_missing`: 정답 청크가 현재 BM25 인덱스에 없음
- `related_citation_only`: 정답 대신 골든셋의 관련 근거만 Top K에 포함
- `rrf_rank_drop`: 단일 검색 Top K에는 있으나 RRF 결합 후 순위가 내려감
- `outside_top_k`: 후보에는 있으나 Top K 밖에 위치
- `not_retrieved`: Dense와 BM25 모두 정답 청크를 후보로 찾지 못함

> 이 holdout은 반복 실행하는 고정 회귀셋이므로 블라인드 최종 성능이 아닙니다.
