"""외부 모델 없이 사용하는 광고 텍스트 문장 분리."""
import re

# 마침표는 공백/끝 앞에서만 분리하여 42.5% 같은 소수를 보존합니다.
# 느낌표/물음표는 붙여 쓴 문장도 분리합니다. 닫는 따옴표는 앞 문장에 포함합니다.
_BOUNDARY = re.compile(r'''[!?]+[”’"']*|\.+[”’"']*(?=\s|$)|\n+''')
MAX_SENTENCES = 100


def split_sentences(text: str) -> list[str]:
    sentences = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        sentence = text[start:match.end()].strip()
        if sentence:
            sentences.append(sentence)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences
