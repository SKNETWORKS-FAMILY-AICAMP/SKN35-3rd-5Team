"""배포 서버처럼 BM25 파일이 없을 때 시작 시 자동 생성되는지 (색인 스크립트의 같은 폴더 import 포함)."""


def test_bm25_index_is_built_when_missing(tmp_path, monkeypatch):
    from cosmetic_agent import service

    target = tmp_path / "bm25_index.pkl"
    monkeypatch.setattr(service.settings, "BM25_INDEX_PATH", target)
    service._ensure_bm25_index()
    assert target.exists() and target.stat().st_size > 0
