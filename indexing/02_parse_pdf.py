"""
[02_parse_pdf.py]
data/01_raw/ 내의 PDF/HWP 문서를 정제된 텍스트 및 마크다운으로 변환하는 스크립트.
"""
from pathlib import Path


def parse_pdf_documents(raw_dir: Path, output_dir: Path) -> dict[str, str]:
    """PDF 파일들을 파싱하여 텍스트 데이터 딕셔너리로 반환 및 임시 저장합니다.

    Args:
        raw_dir: data/01_raw 경로
        output_dir: 중간 텍스트 저장 경로

    Returns:
        {파일명: 텍스트내용} 딕셔너리
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[02_parse] {raw_dir} 내 문서를 파싱합니다.")

    parsed_docs: dict[str, str] = {}
    # TODO (팀원 구현 영역):
    # PyPDFLoader, pdfplumber, pypdf 등을 이용해 표(Table)와 텍스트 추출
    return parsed_docs


if __name__ == "__main__":
    parse_pdf_documents(Path("data/01_raw"), Path("data/02_processed/parsed_text"))
