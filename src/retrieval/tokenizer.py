import re, unicodedata
from typing import List, Protocol
from kiwipiepy import Kiwi
TOKEN_PATTERN = re.compile(r"KR[A-Z0-9]{10}|[A-Za-z]+(?:[-_/][A-Za-z0-9]+)*|\d+(?:[.,]\d+)*(?:%|원|만원|억원|년|개월|일)?|[가-힣]+", re.I)
class SearchTokenizer(Protocol):
    name: str
    def tokenize(self, text: str) -> List[str]: ...
class SimpleKoreanTokenizer:
    name = "simple-ko-v1"
    def tokenize(self, text: str) -> List[str]:
        tokens = [item.lower() for item in TOKEN_PATTERN.findall(unicodedata.normalize("NFC", text))]
        for token in list(tokens):
            if re.fullmatch(r"[가-힣]+", token):
                tokens.extend(token[index:index + 2] for index in range(len(token) - 1))
        return list(dict.fromkeys(tokens))
class KiwiKoreanTokenizer:
    name = "kiwi-ko-v1"; allowed = ("NN", "VV", "VA", "SL", "SN", "SH")
    def __init__(self):
        self.kiwi = Kiwi()
        for word in ["퇴직연금", "연금저축", "개인형IRP", "세액공제", "중도인출", "디폴트옵션"]: self.kiwi.add_user_word(word, "NNP")
    def tokenize(self, text: str) -> List[str]:
        exact = [item.lower() for item in TOKEN_PATTERN.findall(text)]
        morphs = [item.form.lower() for item in self.kiwi.tokenize(text) if item.tag.startswith(self.allowed)]
        return list(dict.fromkeys(exact + morphs))
