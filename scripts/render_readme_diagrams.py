"""Build README diagrams with uncluttered routing and a signal on each edge."""
from html import escape
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / 'docs' / 'diagrams'
COLORS = {'green': '#24765e', 'blue': '#547b98', 'purple': '#89739f', 'amber': '#a78450'}
FILLS = {'green': '#edf5f0', 'blue': '#eff4f8', 'purple': '#f4f0f7', 'amber': '#faf5eb'}

class Diagram:
    def __init__(self, title, subtitle, height):
        self.height = height
        self.edges, self.cards, self.signals = [], [], []
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title description">',
            f'<title id="title">{escape(title)}</title><desc id="description">{escape(subtitle)} 각 연결선에서 신호가 화살표 방향으로 이동하며 시작 시점은 서로 다릅니다.</desc>', '<defs>']
        for name, color in COLORS.items():
            self.parts.append(f'<marker id="arrow-{name}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 4L0 8Z" fill="{color}"/></marker>')
        self.parts.append('''</defs><style>
text { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; }
.signal { stroke-dasharray: 7 107; stroke-dashoffset: 8; opacity: 0; animation: transmit 6.5s linear infinite; }
@keyframes transmit {
  0% { stroke-dashoffset: 8; opacity: 0; }
  6% { stroke-dashoffset: 0; opacity: 1; }
  78% { stroke-dashoffset: -100; opacity: 1; }
  82%, 100% { stroke-dashoffset: -100; opacity: 0; }
}
@media (prefers-reduced-motion: reduce) { .signal { animation: none; opacity: 0; } }
</style>''')
        self.parts += [f'<rect x="1" y="1" width="1198" height="{height-2}" rx="16" fill="#ffffff" stroke="#e2e8e4"/>',
            f'<text x="42" y="48" font-size="23" font-weight="700" fill="#243e34">{escape(title)}</text>',
            f'<text x="42" y="76" font-size="13" fill="#738078">{escape(subtitle)}</text>']

    def panel(self, x, y, width, height, title):
        self.parts += [f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="#fafcfb" stroke="#e4eae6"/>',
            f'<text x="{x+20}" y="{y+28}" font-size="12" font-weight="700" fill="#7a8980">{escape(title)}</text>']

    def label(self, x, y, text, color='green'):
        width = len(text) * 11 + 18
        return f'<rect x="{x-width/2}" y="{y-15}" width="{width}" height="24" rx="6" fill="#ffffff"/><text x="{x}" y="{y+1}" text-anchor="middle" font-size="12" fill="{COLORS[color]}">{escape(text)}</text>'

    def edge(self, path, color='green', phase=None, label=None, dashed=False):
        dash = ' stroke-dasharray="5 5"' if dashed else ''
        self.edges.append(f'<path d="{path}" fill="none" stroke="{COLORS[color]}" stroke-opacity="0.6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arrow-{color})"{dash}/>')
        # Each edge has one signal. Offset the loops so they do not move in unison.
        offset = (phase if phase is not None else len(self.edges) * 0.73) % 6.5
        self.signals.append(f'<path class="signal" pathLength="100" d="{path}" fill="none" stroke="{COLORS[color]}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" style="animation-delay:-{offset:.2f}s"/>')
        if label:
            self.cards.append(self.label(*label, color))

    def node(self, x, y, width, title, subtitle, color='green', height=72):
        center = x + width / 2
        self.cards += [f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10" fill="{FILLS[color]}" stroke="{COLORS[color]}" stroke-opacity="0.65"/>',
            f'<text x="{center}" y="{y+30}" text-anchor="middle" font-size="16" font-weight="700" fill="#2d4138">{escape(title)}</text>',
            f'<text x="{center}" y="{y+53}" text-anchor="middle" font-size="12" fill="#738078">{escape(subtitle)}</text>']

    def note(self, x, y, text):
        self.cards.append(f'<text x="{x}" y="{y}" font-size="12" fill="#7b867f">{escape(text)}</text>')

    def save(self, name):
        self.parts += self.edges + self.signals + self.cards
        self.parts += [f'<text x="42" y="{self.height-27}" font-size="11" fill="#87928b">실선: 주요 흐름 · 점선: 재시도 / 예외 · 이동 신호: 각 경로의 전달 방향</text>', '</svg>']
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / name).write_text('\n'.join(self.parts), encoding='utf-8')


def architecture():
    d = Diagram('Beaurette · 시스템 아키텍처', '요청 처리 · 공통 실행 기능 · 오프라인 데이터 준비', 850)
    d.panel(24, 104, 1152, 190, '01 / 사용자 요청 · 워크플로')
    d.edge('M200 206H252', phase=0)
    d.edge('M422 206H474', phase=1.3)
    d.edge('M644 206H696', phase=2.6)
    d.node(48, 170, 152, '사용자', '광고 문구 · 제품 자료')
    d.node(252, 170, 170, 'Streamlit', '검토 · 생성 · 챗봇 UI')
    d.node(474, 170, 170, 'FastAPI', '요청 검증 · 응답 계약')
    d.node(696, 156, 450, 'LangGraph', '통합 챗봇  /  검토 워크플로  /  생성 워크플로', height=100)
    d.panel(24, 376, 1152, 218, '02 / 워크플로에서 사용하는 공통 기능')
    # A single shared branch replaces the many-to-many graph connections.
    d.edge('M921 256V330H600V418', phase=3.9, label=(751, 321, '필요한 기능 호출'))
    d.edge('M600 330H220V418', 'blue')
    d.edge('M921 330H980V418', 'amber')
    d.node(58, 418, 324, 'Hybrid Retriever', 'Dense + BM25 · 가중 RRF', 'blue', 92)
    d.node(438, 418, 324, 'OpenAI', '판정 · 생성 · 대화', 'purple', 92)
    d.node(818, 418, 324, '규칙 · 실증 역검증', '금지 표현 · 기능성 · 시험 수치', 'amber', 92)
    d.note(76, 549, 'Qdrant Cloud + BM25 색인 사용')
    d.note(456, 549, '선택한 판정 백엔드와 작업에 따라 호출')
    d.note(836, 549, '검토·생성 결과에 같은 검증기 재사용')
    d.panel(24, 644, 1152, 138, '03 / 오프라인 데이터 준비')
    d.edge('M290 722H362', 'blue')
    d.edge('M682 722H754', 'blue')
    d.node(48, 686, 242, '규정 원문', '법령 · 고시 · 지침 · 적발 사례', 'blue')
    d.node(362, 686, 320, '청킹 · 메타데이터 · 임베딩', '조항 단위로 검색 데이터 구성', 'blue')
    d.node(754, 686, 392, 'Qdrant Cloud + BM25', '온라인 검색에서 공통으로 사용하는 색인', 'blue')
    d.save('architecture-animated.svg')


def workflow():
    d = Diagram('Beaurette · 검토 워크플로', '입력 → 근거 검색 → 교정·검증 → 결과. 예외 경로는 점선으로 구분합니다.', 870)
    d.panel(24, 104, 1152, 144, '01 / 입력 · 사전 판정')
    d.edge('M360 186H440', phase=0)
    d.edge('M740 186H820', phase=1.3)
    d.node(60, 150, 300, '입력 정규화', '문구 · 제품 · 보유 실증')
    d.node(440, 150, 300, '규칙 검사', '금지 표현 · 기능성 범위')
    d.node(820, 150, 320, '사전 판정', 'Rule / GPT · 규칙 하한')
    d.edge('M980 222V268H175V340', phase=2.6)
    d.edge('M290 388H360', 'blue', phase=3.9)
    d.edge('M590 388H660', 'blue', phase=5.2)
    d.edge('M890 388H960', label=(925, 371, '교정 불필요'))
    d.edge('M475 340V304H322V363H290', 'purple', label=(412, 295, '근거 부족 · 재검색'), dashed=True)
    d.edge('M775 340V300H1050V340', 'amber', label=(937, 292, '재검색 소진 · 판단보류'), dashed=True)
    d.node(60, 340, 230, '검색 질의 작성', '제품 맥락 · 질의 재작성', 'blue', 96)
    d.node(360, 340, 230, '하이브리드 검색', 'Dense + BM25 · RRF', 'blue', 96)
    d.node(660, 340, 230, '근거 정리 · 판정 분기', '근거 충분성 · 교정 필요성', 'blue', 96)
    d.node(960, 340, 180, '최종 결과', '판정 / 판단보류', 'green', 96)
    d.edge('M775 436V560', phase=7.8, label=(822, 503, '교정 필요'))
    d.edge('M660 608H590', phase=9.1)
    d.node(660, 560, 230, '교정 후보 제안', '실증 범위 내 표현', 'green', 96)
    d.node(360, 560, 230, '제안 문구 역검증', '금지 표현 · 실증 수치', 'purple', 96)
    d.edge('M475 656V706H775V656', 'purple', label=(628, 697, '검증 실패 · 재제안'), dashed=True)
    d.edge('M360 608H318V772H1050V436', phase=10.4, label=(930, 763, '검증 결과 확정'))
    d.note(60, 814, '재검색·재제안에는 횟수 상한을 적용합니다. 세부 노드와 분기는 아래 원본 코드를 참고하세요.')
    d.save('review-workflow-animated.svg')

if __name__ == '__main__':
    architecture()
    workflow()
    print(f'Generated diagrams: {OUTPUT}')
