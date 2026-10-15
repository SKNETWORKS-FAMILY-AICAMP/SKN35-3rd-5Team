"""Generate self-contained, animated SVG diagrams for the repository README.

Run: python scripts/render_readme_diagrams.py
No external fonts, scripts, images, or Python dependencies are required.
"""

from html import escape
from pathlib import Path


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "diagrams"
COLORS = {"green": "#198368", "blue": "#44789a", "purple": "#8560b4", "amber": "#b78030"}
FILLS = {"green": "#eaf5ef", "blue": "#ecf3f8", "purple": "#f1edf9", "amber": "#fbf3e5"}


class Diagram:
    def __init__(self, title, subtitle, height):
        self.height = height
        self.parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title description">
<title id="title">{escape(title)}</title>
<desc id="description">{escape(subtitle)} 연결선의 빛이 화살표 방향으로 이동합니다.</desc>
<defs>
  <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#dbe5e4" stroke-width="0.6" opacity="0.5"/></pattern>
''']
        for name, color in COLORS.items():
            self.parts.append(f'<marker id="arrow-{name}" markerWidth="12" markerHeight="12" refX="11" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L12 6L0 12Z" fill="{color}"/></marker>')
        self.parts.append('''</defs>
<style>
  text { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif; }
  .flow { stroke-dasharray: 16 56; animation: travel 2.6s linear infinite; }
  @keyframes travel { from { stroke-dashoffset: 72; } to { stroke-dashoffset: 0; } }
  @media (prefers-reduced-motion: reduce) { .flow { animation: none; opacity: 0; } }
</style>
''')
        self.parts.extend([
            f'<rect x="1" y="1" width="1198" height="{height-2}" rx="18" fill="#f7faf9" stroke="#dfe8e4"/>',
            f'<rect x="1" y="1" width="1198" height="{height-2}" rx="18" fill="url(#grid)"/>',
            f'<text x="36" y="44" font-size="22" font-weight="700" fill="#203c34">{escape(title)}</text>',
            f'<text x="36" y="70" font-size="13" fill="#6d7e77">{escape(subtitle)}</text>',
        ])

    def lane(self, x, width, title):
        self.parts.append(f'<rect x="{x}" y="98" width="{width}" height="{self.height-165}" rx="12" fill="#ffffff" fill-opacity="0.48" stroke="#d6e1dc" stroke-dasharray="5 6"/>')
        self.parts.append(f'<text x="{x+width/2}" y="125" text-anchor="middle" font-size="12" font-weight="700" fill="#82948a">{escape(title)}</text>')

    def edge(self, path, color="green", delay=0, label=None):
        stroke = COLORS[color]
        self.parts.append(f'<path d="{path}" fill="none" stroke="{stroke}" stroke-opacity="0.55" stroke-width="3.5" stroke-linejoin="round" marker-end="url(#arrow-{color})"/>')
        self.parts.append(f'<path class="flow" d="{path}" fill="none" stroke="{stroke}" stroke-opacity="0.18" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" style="animation-delay:-{delay}s"/>')
        self.parts.append(f'<path class="flow" d="{path}" fill="none" stroke="{stroke}" stroke-opacity="1" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round" style="animation-delay:-{delay}s"/>')
        if label:
            x, y, text = label
            width = len(text) * 12 + 16
            self.parts.append(f'<rect x="{x-width/2}" y="{y-14}" width="{width}" height="22" rx="5" fill="#f7faf9"/>')
            self.parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-size="12" fill="{stroke}">{escape(text)}</text>')

    def node(self, x, y, width, title, subtitle, color="green", height=72):
        center = x + width / 2
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10" fill="{FILLS[color]}" stroke="{COLORS[color]}" stroke-width="1.4"/>')
        self.parts.append(f'<text x="{center}" y="{y+30}" text-anchor="middle" font-size="15" font-weight="700" fill="#263e36">{escape(title)}</text>')
        self.parts.append(f'<text x="{center}" y="{y+52}" text-anchor="middle" font-size="11" fill="#6a7d74">{escape(subtitle)}</text>')

    def save(self, filename):
        y = self.height - 31
        self.parts.append(f'<path d="M38 {y-4}H82" stroke="#198368" stroke-width="3.5" marker-end="url(#arrow-green)"/><text x="94" y="{y}" font-size="11" fill="#6d7e77">화살표 방향으로 이동하는 강조선 · 데이터 / 처리 흐름</text>')
        self.parts.append('</svg>')
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / filename).write_text("\n".join(self.parts), encoding="utf-8")


def architecture():
    d = Diagram("Beaurette · 시스템 아키텍처", "사용자 요청 → 대화·검토·생성 → 근거 검색·모델 호출·역검증", 790)
    for x, width, title in [(24, 154, "01 / 사용자"), (198, 166, "02 / 서비스"), (390, 236, "03 / LangGraph"), (654, 520, "04 / 검색 · 모델 · 검증")]:
        d.lane(x, width, title)
    # Requests and orchestration. Draw all connectors before the cards.
    d.edge("M101 242V300", delay=0.1)
    d.edge("M162 336H210", delay=0.5)
    d.edge("M352 336H378V196H410", delay=0.9)
    d.edge("M352 336H410", delay=1.3)
    d.edge("M352 336H378V476H410", delay=1.7)
    d.edge("M507 232V300", delay=0.4)
    d.edge("M507 232H634V476H604", delay=1.2)
    # All three graphs use retrieval and the model.
    d.edge("M604 196H636V190H680", "blue", 0.3)
    d.edge("M604 336H642V204H680", "blue", 1.1)
    d.edge("M604 476H648V218H680", "blue", 1.9)
    d.edge("M604 196H630V342H680", "purple", 0.6)
    d.edge("M604 336H680", "purple", 1.4)
    d.edge("M604 476H630V356H680", "purple", 2.2)
    d.edge("M604 336H622V488H680", "amber", 1.0)
    d.edge("M604 476H622V508H680", "amber", 1.8)
    d.edge("M878 196H954V175H976", "blue", 0.7)
    d.edge("M878 211H936V282H976", "blue", 1.5)
    # Offline ingestion shares the same two search stores.
    d.edge("M162 602H210", "blue", 0.4)
    d.edge("M352 602H938V182H976", "blue", 1.2)
    d.edge("M352 614H954V290H976", "blue", 2.0)
    d.node(40, 170, 122, "사용자", "문구 · 제품 · 보유 실증")
    d.node(40, 300, 122, "Streamlit", "검토 · 생성 · 챗봇 UI")
    d.node(210, 300, 142, "FastAPI", "요청 검증 · 결과 계약")
    d.node(410, 160, 194, "통합 챗봇", "자연어 의도 · 대화 맥락")
    d.node(410, 300, 194, "검토 워크플로", "규칙 판정 · 교정 · 검증")
    d.node(410, 440, 194, "생성 워크플로", "후보 생성 · 검증 · 재작성")
    d.node(680, 160, 198, "Hybrid Retriever", "Dense + BM25 · 가중 RRF", "blue")
    d.node(976, 140, 178, "Qdrant Cloud", "Dense · 조항 벡터", "blue")
    d.node(976, 250, 178, "BM25", "Sparse · 로컬 색인", "blue")
    d.node(680, 310, 198, "OpenAI", "판정 · 생성 · 대화", "purple")
    d.node(680, 460, 198, "규칙 · 실증 역검증", "금지 표현 · 기능성 · 수치", "amber")
    d.node(40, 570, 122, "규정 원문", "법령 · 고시 · 지침 · 사례", "blue")
    d.node(210, 570, 142, "오프라인 인덱싱", "청킹 · 메타데이터 · 임베딩", "blue")
    d.save("architecture-animated.svg")


def workflow():
    d = Diagram("Beaurette · 검토 워크플로", "주 처리 흐름은 초록색 · 재시도는 보라색 · 보류 경로는 황색", 850)
    for x, width, title in [(24, 270, "01 / 입력 · 사전 판정"), (320, 410, "02 / 검색 · 근거 확인"), (756, 418, "03 / 교정 · 검증 · 결과")]:
        d.lane(x, width, title)
    d.edge("M159 232V286", delay=0)
    d.edge("M159 358V412", delay=0.6)
    d.edge("M260 448H305V196H350", delay=1.2)
    d.edge("M455 232V286", delay=1.8)
    d.edge("M455 358V412", delay=2.4)
    d.edge("M560 448H598V196H560", "purple", 0.6, (610, 260, "재검색"))
    d.edge("M560 448H610V688H910", "amber", 1.4, (715, 674, "재시도 소진 · 판단보류"))
    d.edge("M455 484V566", delay=0.8, label=(455, 533, "근거 충분"))
    d.edge("M560 602H674V216H800", delay=1.4, label=(704, 410, "교정 필요"))
    d.edge("M560 602H660V716H910", delay=2.0, label=(752, 704, "교정 불필요"))
    d.edge("M935 252V336", delay=2.0)
    d.edge("M1070 372H1126V216H1070", "purple", 1.1, (1120, 294, "재제안"))
    d.edge("M935 408V652", delay=2.6, label=(1002, 539, "검증 결과 확정"))
    d.node(58, 160, 202, "입력 정규화", "문구 · 제품 · 보유 실증")
    d.node(58, 286, 202, "규칙 검사", "금지 표현 · 기능성 범위")
    d.node(58, 412, 202, "사전 판정", "Rule / GPT · 규칙 하한")
    d.node(350, 160, 210, "검색 질의 작성", "질의 재작성 · 재시도 제한", "blue")
    d.node(350, 286, 210, "하이브리드 검색", "Dense + BM25 · RRF", "blue")
    d.node(350, 412, 210, "근거 충분성 확인", "재검색 / 진행 / 판단보류", "blue")
    d.node(350, 566, 210, "근거 정리 · 판정 분기", "조항 연결 · 교정 필요 여부", "blue")
    d.node(800, 180, 270, "실증 범위 내 후보 제안", "보유 근거로 표현 상한 계산")
    d.node(800, 336, 270, "제안 문구 역검증", "금지 표현 · 기능성 · 실증 수치", "purple")
    d.node(910, 652, 244, "최종 결과", "판정 · 근거 · 제안 / 판단보류", "amber")
    d.save("review-workflow-animated.svg")


if __name__ == "__main__":
    architecture()
    workflow()
    print(f"Generated README diagrams in {OUTPUT}")
