"""화장품 법령·지침·행정사례를 검색용 JSONL 청크로 변환한다.

법령 XML은 조문/별표의 법적 경계를 보존하고, 지침과 사례 TXT는 제목 및
문단 경계를 우선한다. 모든 청크는 BM25와 벡터 저장소가 공유할 안정적인
``id``와 공통 메타데이터를 가진다.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable


DEFAULT_MAX_CHARS = 1_200
DEFAULT_OVERLAP_CHARS = 120

PAGE_MARKER_RE = re.compile(r"<!--\s*page\s+\d+\s*-->|^\s*-\s*\d+\s*-\s*$", re.MULTILINE | re.IGNORECASE)
SPACE_RE = re.compile(r"[ \t\u00a0]+")
BLANK_RE = re.compile(r"\n{3,}")
ARTICLE_RE = re.compile(r"(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*\([^\n)]+\))?)")
GUIDE_HEADING_RE = re.compile(
    r"^(?:[IVX]+\.\s+.+|\[별표\s*\d*\].*|□\s*화장품법.+|붙\s*임(?:\s*\d+)?\s+.+)$"
)


def _text(element: ET.Element | None, tag: str) -> str:
    if element is None:
        return ""
    child = element.find(tag)
    return _clean_text("".join(child.itertext())) if child is not None else ""


def _clean_text(text: str) -> str:
    """PDF 변환 흔적과 불필요한 공백을 제거하되 문단 경계는 유지한다."""
    # NFKC는 법령에서 사용하는 한글 아래아점(ㆍ)을 다른 자모로 바꾸므로 NFC를 쓴다.
    text = unicodedata.normalize("NFC", text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = PAGE_MARKER_RE.sub("", text)
    lines = [SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        if not line:
            if cleaned and cleaned[-1]:
                cleaned.append("")
            continue
        cleaned.append(line)
    return BLANK_RE.sub("\n\n", "\n".join(cleaned)).strip()


def _compact(text: str) -> str:
    """법령 XML 안에서 줄바꿈된 한 문장을 검색 친화적으로 정규화한다."""
    return re.sub(r"\s+", " ", _clean_text(text)).strip()


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "_", value).strip("_")
    return value[:60] or "UNKNOWN"


def _format_date(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return ""


def _authority_for_law_type(law_type: str) -> int:
    return 2 if "고시" in law_type else 1


def _document_type_for_law(law_type: str) -> str:
    return "고시" if "고시" in law_type else "법령"


DOCUMENT_ID_NAMES = {
    "화장품법": "화장품법",
    "화장품법 시행규칙": "시행규칙",
    "화장품 표시·광고 실증에 관한 규정": "실증규정",
    "화장품 표시ㆍ광고 실증에 관한 규정": "실증규정",
    "화장품 표시·광고 관리 지침": "관리지침",
}


def _canonical_id(prefix: str, source: str, location: str, part: int = 1) -> str:
    """골든셋 채점 규칙인 ``종류_문서_위치`` 형식의 ID를 만든다."""
    document = DOCUMENT_ID_NAMES.get(source, _slug(source))
    normalized_location = re.sub(r"[^0-9A-Za-z가-힣-]+", "_", location).strip("_")
    base = f"{prefix}_{document}_{normalized_location}"
    return base if part == 1 else f"{base}_part{part}"


def _legacy_ids(prefix: str, source: str, location: str, part: int = 1) -> list[str]:
    """이전 생성본 및 초기 골든셋 ID와 전환 기간 동안 호환한다."""
    document = DOCUMENT_ID_NAMES.get(source, _slug(source))
    location_star = re.sub(r"\s+", "", location)
    suffix = "" if part == 1 else f"*part{part}"
    aliases = [f"{prefix}*{document}*{location_star}{suffix}"]
    if prefix == "LAW" and document == "시행규칙" and location == "별표5-2가":
        aliases.append("LAW_COSMETIC_RULE_별표5_2가")
    return aliases


def _is_searchable_body(body: str) -> bool:
    """삭제 조문 및 제목만 있는 조각처럼 검색 가치가 없는 본문을 제외한다."""
    compact = re.sub(r"\s+", " ", body).strip()
    if not compact:
        return False
    if len(compact) < 150 and re.search(r"(?:^|\s)삭제(?:\s|<|$)", compact):
        return False
    return True


def _split_long_text(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int = 0,
) -> list[str]:
    """문단/문장 경계를 우선해 긴 텍스트를 분할한다."""
    text = _clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) == 1:
        paragraphs = [
            p.strip()
            for p in re.split(
                r"(?<=[.!?。])\s+|(?<=다\.)\s+|(?=^[①-⑳]|^\d+[.)]\s)",
                text,
                flags=re.MULTILINE,
            )
            if p.strip()
        ]
    if len(paragraphs) == 1:
        paragraphs = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    result: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                result.append(current.strip())
                current = ""
            for start in range(0, len(paragraph), max_chars):
                result.append(paragraph[start : start + max_chars].strip())
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            result.append(current.strip())
            overlap = current[-overlap_chars:].strip() if overlap_chars else ""
            current = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph
    if current:
        result.append(current.strip())
    return [part for part in result if part]


def _element_lines(element: ET.Element) -> list[str]:
    """조문 요소를 문서 순서대로 읽되 중첩 태그의 중복 텍스트를 제거한다."""
    tags = {"조문내용", "항내용", "호내용", "목내용"}
    lines: list[str] = []
    for node in element.iter():
        if node.tag in tags:
            value = _compact("".join(node.itertext()))
            if value and (not lines or value != lines[-1]):
                lines.append(value)
    return lines


def _article_reference(article: ET.Element) -> str:
    number = _text(article, "조문번호")
    branch = _text(article, "조문가지번호")
    if not number:
        content = _text(article, "조문내용")
        match = ARTICLE_RE.search(content)
        return match.group(1).replace(" ", "") if match else "조문"
    return f"제{number}조" + (f"의{branch}" if branch and branch != "0" else "")


def _split_advertising_appendix(body: str) -> list[tuple[str, str]]:
    """시행규칙 별표5를 1항과 광고 준수사항 2가~2카로 분리한다."""
    second = re.search(r"(?m)^\s*2\.\s*화장품\s*표시[ㆍ·]광고\s*시\s*준수사항", body)
    if not second:
        return [("별표5", body)]

    sections: list[tuple[str, str]] = []
    first = body[: second.start()].strip()
    if first:
        sections.append(("별표5-1", first))

    compliance = body[second.start():]
    item_matches = list(re.finditer(r"(?m)^\s*([가-카])\.\s+", compliance))
    for index, match in enumerate(item_matches):
        end = item_matches[index + 1].start() if index + 1 < len(item_matches) else len(compliance)
        item = compliance[match.start():end].strip()
        sections.append((f"별표5-2{match.group(1)}", item))
    return sections


def _law_chunk(
    *,
    source: str,
    section: str,
    title: str,
    content: str,
    law_type: str,
    effective_date: str,
    source_file: str,
    part: int,
) -> dict[str, Any]:
    prefix = "NOTICE" if "고시" in law_type else "LAW"
    scope = "기능성" if "기능성화장품" in source else "공통"
    return {
        "id": _canonical_id(prefix, source, section, part),
        "legacy_ids": _legacy_ids(prefix, source, section, part),
        "content": content,
        "source": source,
        "article": section,
        "section_title": title,
        "document_type": _document_type_for_law(law_type),
        "authority": _authority_for_law_type(law_type),
        "product_scope": scope,
        "effective_date": effective_date,
        "source_file": source_file,
        "part": part,
    }


def chunk_law_xml(path: Path, max_chars: int = DEFAULT_MAX_CHARS) -> list[dict[str, Any]]:
    """국가법령정보센터 XML을 조문 및 별표 구조로 청킹한다."""
    root = ET.parse(path).getroot()
    is_admin_rule = root.tag == "AdmRulService"
    info = root.find("행정규칙기본정보" if is_admin_rule else "기본정보")
    source = _text(info, "행정규칙명" if is_admin_rule else "법령명_한글") or path.stem.replace("_", " ")
    law_type = _text(info, "행정규칙종류" if is_admin_rule else "법종구분")
    law_type = law_type or ("고시" if "규정" in source else "법령")
    effective_date = _format_date(_text(info, "시행일자"))
    chunks: list[dict[str, Any]] = []

    if is_admin_rule:
        # 행정규칙 XML은 각 조문이 루트의 반복 <조문내용> CDATA로 제공된다.
        for article in root.findall("./조문내용"):
            body = _clean_text("".join(article.itertext()))
            match = ARTICLE_RE.search(body)
            if not match or not _is_searchable_body(body):
                continue  # 장/절 제목은 다음 조문 헤더의 검색 문맥만 흐리므로 제외한다.
            reference = re.sub(r"\s+", "", match.group(1).split("(", 1)[0])
            title_match = re.match(r"제\s*\d+\s*조(?:\s*의\s*\d+)?\s*\(([^)]+)\)", body)
            title = title_match.group(1).strip() if title_match else ""
            header = f"[{source} {reference}" + (f" {title}" if title else "") + "]"
            available = max(200, max_chars - len(header) - 1)
            for index, part in enumerate(_split_long_text(body, max_chars=available), 1):
                content = f"{header}\n{part}"
                chunks.append(
                    _law_chunk(
                        source=source,
                        section=reference,
                        title=title,
                        content=content,
                        law_type=law_type,
                        effective_date=effective_date,
                        source_file=path.name,
                        part=index,
                    )
                )
    else:
        for article in root.findall("./조문/조문단위"):
            if _text(article, "조문여부") not in {"", "조문"}:
                continue
            reference = _article_reference(article)
            title = _text(article, "조문제목")
            lines = _element_lines(article)
            if not lines:
                continue
            header = f"[{source} {reference}" + (f" {title}" if title else "") + "]"
            body = "\n".join(lines)
            if not _is_searchable_body(body):
                continue
            available = max(200, max_chars - len(header) - 1)
            parts = _split_long_text(body, max_chars=available)
            for index, part in enumerate(parts, 1):
                content = f"{header}\n{part}"
                chunks.append(
                    _law_chunk(
                        source=source,
                        section=reference,
                        title=title,
                        content=content,
                        law_type=law_type,
                        effective_date=_format_date(_text(article, "조문시행일자")) or effective_date,
                        source_file=path.name,
                        part=index,
                    )
                )

    for annex in root.findall("./별표/별표단위"):
        number = _text(annex, "별표번호").lstrip("0") or "0"
        branch = _text(annex, "별표가지번호").lstrip("0")
        annex_kind = _text(annex, "별표구분") or "별표"
        section = annex_kind + (f" {number}" if number != "0" else "") + (f"의{branch}" if branch else "")
        title = _text(annex, "별표제목")
        body = _text(annex, "별표내용")
        if not _is_searchable_body(body):
            continue
        structured_sections = (
            _split_advertising_appendix(body)
            if source == "화장품법 시행규칙" and annex_kind == "별표" and number == "5" and not branch
            else [(re.sub(r"\s+", "", section), body)]
        )
        for location, section_body in structured_sections:
            header = f"[{source} {location}" + (f" {title}" if title else "") + "]"
            available = max(200, max_chars - len(header) - 1)
            for index, part in enumerate(_split_long_text(section_body, max_chars=available), 1):
                content = f"{header}\n{part}"
                chunks.append(
                    _law_chunk(
                        source=source,
                        section=location,
                        title=title,
                        content=content,
                        law_type=law_type,
                        effective_date=effective_date,
                        source_file=path.name,
                        part=index,
                    )
                )
    return chunks


def _sectionize_text(text: str, heading_re: re.Pattern[str]) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    heading = "서문"
    buffer: list[str] = []
    for line in _clean_text(text).splitlines():
        if heading_re.match(line.strip()):
            if any(item.strip() for item in buffer):
                sections.append((heading, buffer))
            heading = line.strip()
            buffer = []
        else:
            buffer.append(line)
    if any(item.strip() for item in buffer):
        sections.append((heading, buffer))
    return [(title, _clean_text("\n".join(lines))) for title, lines in sections]


def _slice_marked_sections(
    text: str,
    specifications: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """라벨과 시작 패턴 목록을 사용해 표 형태 TXT의 의미 구간을 자른다."""
    starts: list[tuple[int, str]] = []
    for label, pattern in specifications:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            starts.append((match.start(), label))
    starts.sort()
    sections: list[tuple[str, str]] = []
    for index, (start, label) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        sections.append((label, text[start:end].strip()))
    return sections


def _guide_chunk(
    *,
    source: str,
    location: str,
    body: str,
    effective_date: str,
    source_file: str,
    max_chars: int,
) -> list[dict[str, Any]]:
    header = f"[{source} > {location}]"
    available = max(200, max_chars - len(header) - 1)
    chunks: list[dict[str, Any]] = []
    for index, part in enumerate(
        _split_long_text(body, max_chars=available, overlap_chars=DEFAULT_OVERLAP_CHARS), 1
    ):
        content = f"{header}\n{part}"
        chunks.append({
            "id": _canonical_id("GUIDE", source, location, index),
            "legacy_ids": _legacy_ids("GUIDE", source, location, index),
            "content": content,
            "source": source,
            "article": location,
            "section_title": location,
            "document_type": "지침",
            "authority": 3,
            "product_scope": "공통",
            "effective_date": effective_date,
            "source_file": source_file,
            "part": index,
        })
    return chunks


def chunk_guide_text(path: Path, max_chars: int = DEFAULT_MAX_CHARS) -> list[dict[str, Any]]:
    """표시·광고 관리지침 TXT를 장/별표 단위로 청킹한다."""
    text = _clean_text(path.read_text(encoding="utf-8"))
    source = "화장품 표시·광고 관리 지침"
    date_match = re.search(r"(20\d{2})[.\-]\s*(\d{1,2})[.\-]\s*(\d{1,2})", text)
    effective_date = "-".join(
        [date_match.group(1), date_match.group(2).zfill(2), date_match.group(3).zfill(2)]
    ) if date_match else ""
    chunks: list[dict[str, Any]] = []
    appendix_one = re.search(r"(?m)^\[별표\s*1\]", text)
    appendix_two = re.search(r"(?m)^\[별표\s*2\]", text)
    preamble = text[: appendix_one.start()] if appendix_one else text
    for heading, body in _sectionize_text(preamble, GUIDE_HEADING_RE):
        if heading == "서문" and "I. 목적" not in body:
            # 표지, 제·개정 점검표 및 목차는 검색 근거로 사용하지 않는다.
            continue
        if len(re.sub(r"\s+", " ", body).strip()) < 30:
            continue
        chunks.extend(_guide_chunk(
            source=source,
            location=heading,
            body=body,
            effective_date=effective_date,
            source_file=path.name,
            max_chars=max_chars,
        ))

    if appendix_one and appendix_two:
        appendix_one_text = text[appendix_one.end():appendix_two.start()]
        category_specs = [
            ("별표1_질병", r"질병을\s*진단[·ㆍ]?\s*\n?치료"),
            ("별표1_피부", r"피부\s*관련\s*표현"),
            ("별표1_모발", r"모발\s*관련\s*표현"),
            ("별표1_생리활성", r"생리활성\s*관련"),
            ("별표1_신체개선", r"신체\s*개선\s*표현"),
            ("별표1_기능성", r"기능성\s*관련\s*표현"),
            ("별표1_지정공인", r"특정인\s*또는\s*\n?기관의\s*지정"),
            ("별표1_범위이탈", r"화장품의\s*범위를\s*\n?벗어나는\s*광고"),
            ("별표1_인체유래", r"인체\s*유래\s*성분"),
            ("별표1_사용방법", r"사실과\s*\n?다르거나\s*\n?소비자가"),
            ("별표1_기타", r"그\s*밖의\s*기타\s*\n?표현"),
        ]
        for location, body in _slice_marked_sections(appendix_one_text, category_specs):
            chunks.extend(_guide_chunk(
                source=source,
                location=location,
                body=body,
                effective_date=effective_date,
                source_file=path.name,
                max_chars=max_chars,
            ))

        appendix_two_text = text[appendix_two.end():]
        footer = re.search(r"(?m)^\*\s*본\s*민원인\s*안내서", appendix_two_text)
        if footer:
            appendix_two_text = appendix_two_text[:footer.start()]
        second = re.search(r"(?m)^\s*2\.\s*효능[·ㆍ]효과[·ㆍ]품질", appendix_two_text)
        if second:
            appendix_two_sections = [
                ("별표2_실증대상", appendix_two_text[:second.start()].strip()),
                ("별표2_효능표현", appendix_two_text[second.start():].strip()),
            ]
        else:
            appendix_two_sections = [("별표2_실증대상", appendix_two_text)]
        for location, body in appendix_two_sections:
            chunks.extend(_guide_chunk(
                source=source,
                location=location,
                body=body,
                effective_date=effective_date,
                source_file=path.name,
                max_chars=max_chars,
            ))
    return chunks


def _case_title(text: str, path: Path) -> str:
    for line in _clean_text(text).splitlines():
        line = line.lstrip("# ").strip()
        if 12 <= len(line) <= 200 and not line.startswith(("출처:", "이용 조건:")):
            if "보도자료" not in line and not re.fullmatch(r"\d{4}[.\-].*", line):
                return line
    fallback = re.sub(r"^case_\d{4}-\d{2}-\d{2}_", "", path.stem)
    return fallback.replace("_", " ")


def chunk_case_text(path: Path, max_chars: int = DEFAULT_MAX_CHARS) -> list[dict[str, Any]]:
    """행정처분/적발 보도자료를 사례 단위의 문단 청크로 변환한다."""
    raw = path.read_text(encoding="utf-8")
    text = _clean_text(raw)
    title = _case_title(text, path)
    date_match = re.search(r"(20\d{2})[-._ ](\d{2})[-._ ](\d{2})", path.name)
    effective_date = "-".join(date_match.groups()) if date_match else ""
    topic = re.sub(r"^case_\d{4}-\d{2}-\d{2}_", "", path.stem).replace("_", "")
    # 웹페이지 복사 과정에서 붙은 스크립트/저작권 안내는 검색 노이즈라 제거한다.
    text = re.split(r"//\s*0\)\s*\{|저작권정책 담당자안내", text, maxsplit=1)[0].strip()
    header = f"[행정처분·부당광고 사례 > {title}]"
    available = max(200, max_chars - len(header) - 1)
    chunks: list[dict[str, Any]] = []
    for index, part in enumerate(
        _split_long_text(text, max_chars=available, overlap_chars=DEFAULT_OVERLAP_CHARS), 1
    ):
        content = f"{header}\n{part}"
        base_id = f"CASE_{effective_date or '날짜미상'}_{topic}"
        chunk_id = base_id if index == 1 else f"{base_id}_part{index}"
        chunks.append({
            "id": chunk_id,
            "legacy_ids": [f"CASE*{effective_date or '날짜미상'}*{topic}" + ("" if index == 1 else f"*part{index}")],
            "content": content,
            "source": "식품의약품안전처 부당광고 적발 사례",
            "article": title,
            "section_title": title,
            "document_type": "사례",
            "authority": 4,
            "product_scope": "공통",
            "effective_date": effective_date,
            "source_file": path.name,
            "part": index,
        })
    return chunks


def chunk_by_articles(text: str, doc_name: str) -> list[dict[str, Any]]:
    """일반 텍스트 법령을 제N조 경계로 나누는 하위 호환 함수."""
    cleaned = _clean_text(text)
    matches = list(ARTICLE_RE.finditer(cleaned))
    if not matches:
        return [{"article": "전문", "content": cleaned, "source": doc_name}] if cleaned else []
    chunks: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        chunks.append({
            "article": match.group(1).replace(" ", ""),
            "content": _clean_text(cleaned[match.start():end]),
            "source": doc_name,
        })
    return chunks


def chunk_raw_documents(raw_dir: Path, max_chars: int = DEFAULT_MAX_CHARS) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted((raw_dir / "law").glob("*.xml")):
        chunks.extend(chunk_law_xml(path, max_chars=max_chars))
    for path in sorted((raw_dir / "guide").glob("*.txt")):
        chunks.extend(chunk_guide_text(path, max_chars=max_chars))
    for path in sorted((raw_dir / "cases").glob("*.txt")):
        chunks.extend(chunk_case_text(path, max_chars=max_chars))
    return chunks


def validate_chunks(chunks: Iterable[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    chunks = list(chunks)
    required = {
        "id", "content", "source", "article", "document_type", "authority",
        "product_scope", "effective_date", "source_file", "part",
    }
    ids: set[str] = set()
    for chunk in chunks:
        missing = required - chunk.keys()
        if missing:
            raise ValueError(f"필수 메타데이터 누락: {sorted(missing)}")
        if not chunk["content"].strip():
            raise ValueError(f"빈 청크: {chunk['id']}")
        if len(chunk["content"]) > max_chars + 100:
            raise ValueError(f"청크 길이 초과({len(chunk['content'])}): {chunk['id']}")
        if chunk["id"] in ids:
            raise ValueError(f"중복 청크 ID: {chunk['id']}")
        ids.add(chunk["id"])
    return chunks


def write_jsonl(chunks: Iterable[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="법령·지침·사례 구조 청킹")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/01_raw"))
    parser.add_argument("--output", type=Path, default=Path("data/02_processed/chunks.jsonl"))
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    args = parser.parse_args()

    chunks = validate_chunks(chunk_raw_documents(args.raw_dir, args.max_chars), args.max_chars)
    write_jsonl(chunks, args.output)
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk["document_type"]] = counts.get(chunk["document_type"], 0) + 1
    print(f"[03_chunk] {len(chunks)}개 청크 생성: {args.output}")
    print("[03_chunk] 유형별:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
