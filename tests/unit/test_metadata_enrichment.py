import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "indexing" / "metadata_enrichment.py"
SPEC = importlib.util.spec_from_file_location("metadata_enrichment", MODULE_PATH)
metadata_enrichment = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(metadata_enrichment)


def test_enrichment_adds_searchable_regulatory_metadata_without_changing_content():
    chunk = {
        "id": "NOTICE_실증규정_제3조",
        "source": "화장품 표시·광고 실증에 관한 규정",
        "article": "제3조",
        "section_title": "실증자료",
        "document_type": "고시",
        "authority": 2,
        "content": "광고 주장은 객관적이고 과학적인 시험 자료와 직접 관련되어야 한다.",
    }

    enriched = metadata_enrichment.enrich_chunk_metadata(chunk)

    assert enriched["content"] == chunk["content"]
    assert enriched["legal_force"] == "고시"
    assert enriched["evidence_requirement"] == "필수"
    assert "실증 필요" in enriched["claim_categories"]
    assert enriched["search_keywords"]


def test_search_text_contains_metadata_and_original_source_text():
    chunk = {
        "id": "GUIDE_관리지침_별표1_질병",
        "source": "화장품 표시광고 관리지침",
        "article": "별표1",
        "section_title": "질병 관련 표현",
        "authority": 3,
        "content": "화장품을 의약품으로 인식하게 할 우려가 있는 표현을 설명한다.",
    }

    search_text = metadata_enrichment.build_search_text(chunk)

    assert "문서효력 행정지침" in search_text
    assert "주장유형 의약품 오인" in search_text
    assert chunk["content"] in search_text
