import re
from dataclasses import dataclass, field


_ASCII_ACCOUNT_PATTERN = re.compile(r"(?<![A-Za-z])(?:DB|DC|IRP)(?![A-Za-z])", re.IGNORECASE)
_TAX_WORDS = ("세금", "과세", "공제", "세액", "소득세")
_REQUEST_FIELD_PATTERNS = (
    ("product_name", ("상품명", "펀드명")),
    ("risk_grade", ("위험등급", "위험 등급")),
    ("fee", ("판매수수료", "총보수", "보수ㆍ비용", "보수·비용")),
    ("investment_target", ("투자대상", "투자 대상", "무엇에 투자")),
    ("investment_strategy", ("운용전략", "운용 전략", "투자전략", "투자 전략")),
    ("effective_date", ("기준일", "작성기준일", "작성 기준일")),
)


@dataclass(frozen=True)
class EntityExtraction:
    """Routing 실험용 결정적 entity view; 기존 Agent decision에는 아직 연결하지 않는다."""

    accounts: list[str]
    product_codes: list[str]
    products: list[str]
    tax_intent: bool
    comparison: bool
    requested_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QueryAnalysis:
    question: str
    intent: str
    product_codes: list[str]
    entities: list[str]
    requires_comparison: bool
    requires_user_conditions: bool
    extracted_entities: EntityExtraction = field(
        default_factory=lambda: EntityExtraction([], [], [], False, False)
    )


class QueryAnalyzer:
    def extract_entities(self, question: str) -> EntityExtraction:
        """한국어 조사·기호 결합을 허용하되 ASCII 부분문자열은 배제한다."""
        normalized = question.strip()
        account_hits = [match.group(0).upper() for match in _ASCII_ACCOUNT_PATTERN.finditer(normalized)]
        accounts = []
        for account in account_hits:
            if account not in accounts:
                accounts.append(account)
        if "연금저축" in normalized:
            accounts.append("연금저축")
        codes = [code.upper() for code in re.findall(r"KR[A-Z0-9]{10}", normalized, re.I)]
        requested_fields = [
            field_name
            for field_name, patterns in _REQUEST_FIELD_PATTERNS
            if any(pattern in normalized for pattern in patterns)
        ]
        comparison = (
            len(accounts) >= 2
            or any(word in normalized for word in ("비교", "차이", "각각", "어느", "vs", "VS"))
            or any(symbol in normalized for symbol in ("/", "·")) and len(accounts) >= 2
        )
        return EntityExtraction(
            accounts=accounts,
            product_codes=codes,
            products=[],
            tax_intent=any(word in normalized for word in _TAX_WORDS),
            comparison=comparison,
            requested_fields=requested_fields,
        )

    def analyze(self, question: str) -> QueryAnalysis:
        if not question.strip():
            raise ValueError("question must not be empty")
        normalized = question.strip()
        codes = [code.upper() for code in re.findall(r"KR[A-Z0-9]{10}", normalized, re.I)]
        entities = [item for item in ("DB", "DC", "IRP") if re.search(rf"\b{item}\b", normalized, re.I)]
        conditional = any(word in normalized for word in ("추천", "어떤 상품", "적합"))
        comparison = any(word in normalized for word in ("비교", "차이", "어느", "각각")) or len(entities) >= 2
        personal = any(word in normalized for word in ("현재 제", "내 계좌", "내 IRP", "개인 계좌"))
        intent = "unsupported_or_personal" if personal else "conditional_recommendation" if conditional else "product_explanation" if codes else "tax" if any(word in normalized for word in ("세금", "과세", "공제")) else "pension_system"
        # Keep legacy fields and decisions unchanged during P10-A. P10-B's
        # experimental router consumes ``extracted_entities`` separately.
        return QueryAnalysis(normalized, intent, codes, entities, comparison, conditional, self.extract_entities(normalized))
