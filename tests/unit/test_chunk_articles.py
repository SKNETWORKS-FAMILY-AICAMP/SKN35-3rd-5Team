import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "indexing" / "03_chunk_articles.py"
SPEC = importlib.util.spec_from_file_location("chunk_articles", MODULE_PATH)
chunk_articles = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(chunk_articles)


def test_chunk_by_articles_preserves_article_boundaries():
    chunks = chunk_articles.chunk_by_articles(
        "제1조(목적) 첫 번째 내용이다.\n제2조의2(범위) 두 번째 내용이다.",
        "테스트법",
    )
    assert [chunk["article"] for chunk in chunks] == ["제1조(목적)", "제2조의2(범위)"]
    assert chunks[0]["source"] == "테스트법"


def test_chunk_law_xml_adds_legal_metadata(tmp_path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <법령><기본정보><법령명_한글>화장품법</법령명_한글><법종구분>법률</법종구분>
    <시행일자>20260101</시행일자></기본정보><조문><조문단위><조문번호>13</조문번호>
    <조문여부>조문</조문여부><조문제목>부당한 표시ㆍ광고</조문제목>
    <조문시행일자>20260101</조문시행일자><조문내용>제13조(부당한 표시ㆍ광고)</조문내용>
    <항><항번호>①</항번호><항내용>① 의약품으로 오인하게 해서는 안 된다.</항내용></항>
    </조문단위></조문></법령>"""
    path = tmp_path / "law.xml"
    path.write_text(xml, encoding="utf-8")

    chunks = chunk_articles.chunk_law_xml(path)

    assert len(chunks) == 1
    assert chunks[0]["article"] == "제13조"
    assert chunks[0]["authority"] == 1
    assert chunks[0]["effective_date"] == "2026-01-01"
    assert "의약품으로 오인" in chunks[0]["content"]


def test_validate_chunks_rejects_duplicate_ids():
    chunk = {
        "id": "DUPLICATE",
        "content": "내용",
        "source": "출처",
        "article": "제1조",
        "document_type": "법령",
        "authority": 1,
        "product_scope": "공통",
        "effective_date": "2026-01-01",
        "source_file": "law.xml",
        "part": 1,
    }
    try:
        chunk_articles.validate_chunks([chunk, chunk.copy()], 1200)
    except ValueError as error:
        assert "중복" in str(error)
    else:
        raise AssertionError("중복 ID를 허용하면 안 됩니다.")
