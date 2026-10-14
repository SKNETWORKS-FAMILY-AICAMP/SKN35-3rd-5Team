# RAG 검색 평가

- 실행일: 2026-10-14
- 평가셋: `holdout`
- 평가 문항: 16개 (`required_citation`이 있는 문항)
- Top K: 4
- Qdrant 컬렉션: `cosmetic_ad_rules_v2` (59 points)

## 검색 방식별 결과

| 검색 방식 | Hit@1 | Hit@2 | Strict Hit@4 | Evidence Coverage@4 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 37.5% | 43.8% | 43.8% | 56.2% | 0.4376 |
| BM25 | 31.2% | 37.5% | 50.0% | 93.8% | 0.4062 |
| Hybrid | 25.0% | 37.5% | 75.0% | 100.0% | 0.4369 |

## 실패 유형

| 유형 | 건수 |
| --- | ---: |
| `related_citation_only` | 4 |

## Hybrid Hit@K 실패 문항

| ID | 정답 청크 | 실패 유형 | Dense 순위 | BM25 순위 | Hybrid 순위 |
| --- | --- | --- | ---: | ---: | ---: |
| G_HOLD_007 | `LAW_시행규칙_별표5-2나` | `related_citation_only` | - | - | - |
| G_HOLD_017 | `GUIDE_관리지침_별표2_실증대상` | `related_citation_only` | 13 | 3 | 5 |
| G_HOLD_019 | `GUIDE_관리지침_별표2_효능표현` | `related_citation_only` | 10 | 15 | 14 |
| G_HOLD_021 | `LAW_시행규칙_별표5-2나` | `related_citation_only` | 7 | 20 | 19 |

## 실패 유형 해석

- `index_missing`: 정답 청크가 현재 BM25 인덱스에 없음
- `related_citation_only`: 정답 대신 골든셋의 관련 근거만 Top K에 포함
- `rrf_rank_drop`: 단일 검색 Top K에는 있으나 RRF 결합 후 순위가 내려감
- `outside_top_k`: 후보에는 있으나 Top K 밖에 위치
- `not_retrieved`: Dense와 BM25 모두 정답 청크를 후보로 찾지 못함

> 이 holdout은 반복 실행하는 고정 회귀셋이므로 블라인드 최종 성능이 아닙니다.
