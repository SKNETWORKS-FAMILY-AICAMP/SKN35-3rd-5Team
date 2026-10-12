"""
[00_sync_ingredients.py]
식약처 '화장품 원료성분정보' 오픈API에서 전체 성분을 받아 data/01_raw/api/에 저장하는 스크립트.

- 출처: 공공데이터포털 15111774 (이용허락범위 제한 없음)
- 필요: .env의 DATA_GO_KR_API_KEY (Encoding/Decoding 키 모두 가능)
- 다시 실행하면 최신 데이터로 덮어씁니다. 서비스 실행 중에는 이 파일만 읽고 API를 호출하지 않습니다.

실행: uv run python indexing/00_sync_ingredients.py
"""
import json
import time
import urllib.parse
from datetime import datetime

import httpx

from cosmetic_agent.common.config import DATA_DIR, settings

ENDPOINT = (
    "https://apis.data.go.kr/1471000/CsmtcsIngdCpntInfoService01/getCsmtcsIngdCpntInfoService01"
)
OUTPUT_PATH = DATA_DIR / "01_raw" / "api" / "cosmetic_ingredients.json"
PAGE_SIZE = 100

# API 필드명 → 저장 필드명
FIELD_MAP = {
    "INGR_KOR_NAME": "kor_name",
    "INGR_ENG_NAME": "eng_name",
    "CAS_NO": "cas_no",
    "ORIGIN_MAJOR_KOR_NAME": "origin_definition",
    "INGR_SYNONYM": "synonyms",
}


def _service_key() -> str:
    key = settings.DATA_GO_KR_API_KEY.strip()
    if not key:
        raise RuntimeError(".env에 DATA_GO_KR_API_KEY가 없습니다.")
    # Encoding 키(% 포함)면 풀어서 사용. httpx가 다시 인코딩한다.
    return urllib.parse.unquote(key) if "%" in key else key


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ("", "None", "null") else text


def fetch_page(client: httpx.Client, key: str, page_no: int) -> dict:
    for attempt in range(3):
        try:
            response = client.get(
                ENDPOINT,
                params={"serviceKey": key, "pageNo": page_no, "numOfRows": PAGE_SIZE, "type": "json"},
            )
            response.raise_for_status()
            return response.json()["body"]
        except (httpx.HTTPError, KeyError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def sync_ingredients() -> int:
    key = _service_key()
    records: list[dict] = []

    with httpx.Client(timeout=30) as client:
        first = fetch_page(client, key, 1)
        total = int(first["totalCount"])
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        print(f"[00_sync] 전체 {total}개, {pages}페이지")

        for page_no in range(1, pages + 1):
            body = first if page_no == 1 else fetch_page(client, key, page_no)
            for item in body.get("items") or []:
                row = {new: _clean(item.get(old)) for old, new in FIELD_MAP.items()}
                if row["synonyms"]:
                    row["synonyms"] = [s.strip() for s in row["synonyms"].split(",") if s.strip()]
                else:
                    row["synonyms"] = []
                records.append(row)
            if page_no % 20 == 0:
                print(f"  {page_no}/{pages} 페이지, {len(records)}개")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "식품의약품안전처_화장품 원료성분정보 (공공데이터포털 15111774)",
        "license": "이용허락범위 제한 없음",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "total_count": total,
        "items": records,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[00_sync] {len(records)}개 저장 → {OUTPUT_PATH.relative_to(DATA_DIR.parent)}")
    return len(records)


if __name__ == "__main__":
    sync_ingredients()
