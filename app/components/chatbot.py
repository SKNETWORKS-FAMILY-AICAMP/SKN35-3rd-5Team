"""전체 화면과 작은 팝업이 공유하는 통합 챗봇."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

from app.components.brand import avatar_img, avatar_uri
from app.components.context import current
from app.components.generation import render_generation
from app.components.layout import clock, esc
from app.components.theme import inject_css
from app.services import backend

KST = timezone(timedelta(hours=9))
LAUNCHER_SCRIPT = Path(__file__).with_name("chat_launcher.js")


def chat_header(*, compact: bool = False) -> None:
    """메신저 상단의 대화 상대 프로필."""
    st.html(f'<div class="bw-chat-profile"><span class="bw-chat-profile-avatar">'
            f'{avatar_img(44, alt="뷰렛 토끼")}</span><div><strong>뷰렛</strong>'
            f'<span>{"광고 문구 도우미" if compact else "광고 문구를 함께 다듬는 AI 도우미"}</span></div></div>')


def state() -> dict:
    return st.session_state.setdefault("bw_chatbot_conversation", {"messages": [], "context": {}, "signature": None, "history_start": 0})


def reset() -> None:
    st.session_state.pop("bw_chatbot_conversation", None)


def _product() -> dict:
    if st.session_state.get("bw_chat_project", False):
        return current()[0]
    return {"product_id": "chat_draft", "name": "나의 화장품", "category": "일반", "owned_evidence": []}


def _sync_product() -> dict:
    product = _product()
    signature = json.dumps(product, ensure_ascii=False, sort_keys=True)
    chat = state()
    if chat["signature"] is not None and chat["signature"] != signature:
        chat["context"] = {}
        chat["history_start"] = len(chat["messages"])
        st.info("제품·실증 기준을 변경했습니다. 대화 기록은 유지하고, 이번 요청부터 새 기준을 적용합니다.")
    chat["signature"] = signature
    return product


def _review(response: dict) -> None:
    result = response["result"]
    label = {0: "사용 가능", 1: "실증 필요", 2: "수정 필요"}.get(result.get("level"), "전문가 검토 필요")
    st.markdown(f"**검토 결과 · {label}**")
    st.caption("검토한 문구")
    st.write(response["input_text"])
    if result.get("review_notes"):
        st.write(result["review_notes"])
    if result.get("suggestion"):
        st.caption("수정 제안")
        st.code(result["suggestion"], language=None)
    if result.get("next_test"):
        st.info(result["next_test"])
    with st.expander("검토 근거"):
        for citation in result.get("citations", []):
            st.write(f"{citation['source']} · {citation['article']}")
            st.caption(citation.get("content_snippet") or "")
        if not result.get("citations"):
            st.caption("반환된 근거 조항이 없습니다.")


def _response(response: dict) -> None:
    st.write(response["message"])
    if response.get("review"):
        _review(response["review"])
        st.caption("자동 검토는 법률 준수를 보장하지 않습니다.")
    if response.get("generation"):
        render_generation(response["generation"])
    if response.get("citations"):
        with st.expander("답변 근거"):
            for citation in response["citations"]:
                st.write(f"{citation['source']} · {citation['article']}")
                st.caption(citation.get("content_snippet") or "")


def _render_turn(turn: dict, *, scope: str, index: int | str, typing: bool = False) -> None:
    role = turn["role"]
    with st.container(key=f"chat_{role}_{scope}_{index}"), \
            st.chat_message(role, avatar=avatar_uri() if role == "assistant" else None):
        if role == "assistant":
            st.html('<div class="bw-chat-sender">뷰렛</div>')
        with st.container(key=f"chat_bubble_{role}_{scope}_{index}"):
            if typing:
                st.html('<div class="bw-chat-typing" role="status" aria-label="뷰렛이 답변을 작성하고 있습니다">'
                        '<span aria-hidden="true"></span><span aria-hidden="true"></span>'
                        '<span aria-hidden="true"></span></div>')
            elif role == "user":
                st.write(turn["text"])
            else:
                _response(turn["response"])
        if turn.get("at"):
            at = datetime.fromisoformat(turn["at"])
            st.html(f'<div class="bw-chat-time">{clock(at)}</div>')


def _send(message: str, product: dict, messages, *, scope: str) -> None:
    if not message.strip():
        st.warning("요청을 입력해주세요.")
        return
    chat = state()
    history = []
    for turn in chat["messages"][chat.get("history_start", 0):][-12:]:
        if turn["role"] == "user":
            history.append({"role": "user", "content": turn["text"]})
        else:
            # 실행 결과와 상태도 전달해 후속 후보 참조를 지원한다.
            history.append({"role": "assistant", "content": json.dumps(turn["response"], ensure_ascii=False)[:6000]})
    with messages:
        pending = st.empty()
    with pending.container():
        _render_turn({"role": "user", "text": message, "at": datetime.now(KST).isoformat()}, scope=scope, index="pending")
        _render_turn({"role": "assistant"}, scope=scope, index="pending", typing=True)
    try:
        response = backend.chat({"message": message, "context": chat["context"], "history": history, "product": product})
    except backend.BackendError as error:
        st.error(error.message)
        return
    finally:
        pending.empty()
    now = datetime.now(KST).isoformat()
    chat["messages"].extend([{"role": "user", "text": message, "at": now},
                             {"role": "assistant", "response": response, "at": now}])
    chat["context"] = response["context"]
    st.rerun()


def render_chat(*, compact: bool = False) -> None:
    inject_css("chat")
    product = _sync_product()
    chat = state()
    display_product = product
    if chat["context"].get("product_source") == "conversation":
        display_product = {"name": chat["context"].get("product_name") or "나의 화장품", "owned_evidence": []}
    scope = "mini" if compact else "full"
    mode = " · 데모 모드" if backend.data_mode() != "api" else ""
    st.html(f'<div class="bw-chat-context"><span class="bw-chat-context-dot"></span>'
            f'{esc(display_product["name"])} · 실증 {len(display_product.get("owned_evidence", []))}건{mode}</div>')
    messages = st.container(height=260 if compact else 350, border=False, autoscroll=True, key=f"chat_messages_{scope}")
    with messages:
        st.html(f'<div class="bw-chat-date"><span>{datetime.now(KST):%Y년 %m월 %d일}</span></div>')
        if not chat["messages"]:
            st.html(f'<div class="bw-chat-welcome"><span class="bw-chat-welcome-avatar">'
                    f'{avatar_img(38, alt="뷰렛 토끼")}</span><div><div class="bw-chat-sender">뷰렛</div>'
                    '<div class="bw-chat-welcome-bubble">안녕하세요, 뷰렛이에요 👋<br>'
                    '어떤 광고를 만들고 싶은지 말해주세요.<br>성분을 몰라도 초안부터 만들어드릴게요.</div>'
                    '<div class="bw-chat-examples"><span>이렇게 말해보세요</span>'
                    '<p>“이 광고 문구, 검토하고 고쳐줘”</p>'
                    '<p>“선크림 광고를 짧고 발랄하게 만들어줘”</p></div></div></div>')
        for index, turn in enumerate(chat["messages"]):
            _render_turn(turn, scope=scope, index=index)
    if compact:
        with st.form("chat_mini_form", clear_on_submit=True):
            entry, send = st.columns([5, 1], gap="small", vertical_alignment="center")
            with entry:
                message = st.text_input("챗봇 요청", placeholder="뷰렛에게 메시지 보내기", max_chars=5000, label_visibility="collapsed")
            with send:
                submitted = st.form_submit_button("보내기", icon=":material/arrow_upward:", width="stretch")
        if submitted:
            _send(message, product, messages, scope=scope)
    else:
        with st.container(key="chat_composer_full"):
            message = st.chat_input("뷰렛에게 메시지 보내기", max_chars=5000, key="chat_full_input")
            if message:
                _send(message, product, messages, scope=scope)
            st.html('<div class="bw-chat-composer-note">Enter로 전송 · Shift + Enter로 줄바꿈</div>')


def render_launcher(pages: dict) -> None:
    inject_css("chat")
    st.html(f'<style>.st-key-chat_launcher [data-testid="stPopoverButton"] '
            f'{{background-image:url("{avatar_uri()}");}}</style>')
    with st.container(key="chat_launcher"), \
            st.popover("통합 챗봇 열기", icon=":material/chat_bubble:", help="클릭하면 대화 · 드래그로 이동 · Alt + 방향키로 이동"), \
            st.container(key="chat_mini"):
        with st.container(key="chat_header_mini"):
            profile, expand = st.columns([4, 1], vertical_alignment="center")
            with profile:
                chat_header(compact=True)
            with expand:
                st.page_link(pages["chat"], label="전체", icon=":material/open_in_full:")
        render_chat(compact=True)
    # 저장소의 정적 스크립트만 실행하며 대화 내용은 JavaScript에 넣지 않는다.
    st.html(f"<script>{LAUNCHER_SCRIPT.read_text(encoding='utf-8')}</script>", unsafe_allow_javascript=True)
