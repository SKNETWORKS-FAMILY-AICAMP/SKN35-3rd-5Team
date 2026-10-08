"""
[01_download_regulations.py]
법령, 식약처 고시, 지침, 보도자료를 수집하여 data/01_raw/에 저장하는 스크립트.
"""
from pathlib import Path


def download_official_documents(output_dir: Path) -> list[Path]:
    """공식 법령 및 식약처 지침 문서를 다운로드/배치합니다.

    Args:
        output_dir: 저장 대상 디렉토리 (data/01_raw)

    Returns:
        수집된 원본 파일 경로 리스트
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[01_download] 문서를 수집하여 {output_dir} 에 저장합니다.")
    
    # TODO (팀원 구현 영역):
    # 1. 국가법령정보센터 또는 식약처 오픈API/크롤러 연동
    # 2. 또는 수동 다운로드된 PDF 파일 검증 로직 작성
    return list(output_dir.glob("*.*"))


if __name__ == "__main__":
    download_official_documents(Path("data/01_raw"))
