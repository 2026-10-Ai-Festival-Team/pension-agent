import re
from typing import Optional

from src.orchestration.product_entity_resolver import ProductEntityResolver
from src.orchestration.question_normalizer import normalize_pension_question
from dataclasses import dataclass, field


_ASCII_ACCOUNT_PATTERN = re.compile(r"(?<![A-Za-z])(?:DB|DC|IRP)(?![A-Za-z])", re.IGNORECASE)
_TAX_WORDS = ("세금", "과세", "공제", "세액", "소득세")
_ACCOUNT_ALIASES = (
    ("확정급여형", "DB"),
    ("확정기여형", "DC"),
    ("개인형 퇴직연금", "IRP"),
)
_REQUEST_FIELD_PATTERNS = (
    ("product_name", ("상품명", "펀드명")),
    ("risk_grade", (
        "위험등급", "위험 등급", "등급 표시", "몇 등급",
        "몇 단계 위험", "위험 단계", "낮은 위험", "높은 위험", "더 낮은 위험", "더 높은 위험",
    )),
    # 상품의 비용 관련 수치는 서로 대체할 수 없다. ``총보수``는 연간
    # 비율이고, ``기타비용``과 ``1,000만원 투자 시 비용 예시``는 각각
    # 별도 항목이므로 requirement 단계부터 분리한다.
    ("total_fee", ("총보수", "총 보수", "총보수ㆍ비용", "총보수·비용")),
    ("other_expenses", ("기타비용", "기타 비용")),
    ("example_cost", ("비용 예시", "투자시 비용", "투자 시 비용", "총비용 예시")),
    ("investment_target", ("투자대상", "투자 대상", "무엇에 투자", "투자 비중", "편입 비율")),
    ("investment_strategy", (
        "운용전략", "운용 전략", "투자전략", "투자 전략",
        "투자하는 전략", "어느 정도 투자", "얼마나 투자",
        "지수를 따라", "지수에 연동", "지수 추종",
    )),
    ("asset_type", ("자산유형", "자산 유형", "펀드유형", "펀드 유형")),
    ("investment_risk", ("주요 투자 위험", "투자 위험", "투자위험", "위험은 무엇", "위험이 무엇")),
    ("principal_loss_possible", (
        "원금손실", "원본손실", "원금 손실", "원금의 손실", "투자원금의 손실",
        "손실이 발생",
    )),
    ("principal_guarantee_status", ("원금보장", "원금 보장", "원리금보장", "원리금 보장")),
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
    def __init__(self, product_resolver: Optional[ProductEntityResolver] = None):
        self.product_resolver = product_resolver or ProductEntityResolver()

    def extract_entities(self, question: str) -> EntityExtraction:
        """한국어 조사·기호 결합을 허용하되 ASCII 부분문자열은 배제한다."""
        normalized = normalize_pension_question(question)
        account_hits = [match.group(0).upper() for match in _ASCII_ACCOUNT_PATTERN.finditer(normalized)]
        accounts = []
        for account in account_hits:
            if account not in accounts:
                accounts.append(account)
        for alias, account in _ACCOUNT_ALIASES:
            if alias in normalized and account not in accounts:
                accounts.append(account)
        if "연금저축" in normalized:
            accounts.append("연금저축")
        codes = [code.upper() for code in re.findall(r"KR[A-Z0-9]{10}", normalized, re.I)]
        resolved_products = self.product_resolver.resolve(normalized)
        for product in resolved_products:
            if product.code not in codes:
                codes.append(product.code)
        requested_fields = [
            field_name
            for field_name, patterns in _REQUEST_FIELD_PATTERNS
            if any(pattern in normalized for pattern in patterns)
        ]
        comparison = (
            len(accounts) >= 2
            or any(word in normalized for word in ("비교", "차이", "각각", "구별", "대조", "대비", "vs", "VS"))
            or any(symbol in normalized for symbol in ("/", "·")) and len(accounts) >= 2
        )
        return EntityExtraction(
            accounts=accounts,
            product_codes=codes,
            products=[product.canonical_name for product in resolved_products],
            tax_intent=any(word in normalized for word in _TAX_WORDS),
            comparison=comparison,
            requested_fields=requested_fields,
        )

    def analyze(self, question: str) -> QueryAnalysis:
        if not question.strip():
            raise ValueError("question must not be empty")
        raw_question = question.strip()
        normalized = normalize_pension_question(raw_question)
        extracted = self.extract_entities(normalized)
        codes = extracted.product_codes
        # Korean 조사에 붙은 DB/DC/IRP도 ``extract_entities``에서 안정적으로
        # 추출한다. Legacy ``entities``도 같은 결과를 사용해야 evidence gate가
        # ASCII word-boundary 차이로 비교축을 잃지 않는다.
        entities = extracted.accounts
        recommendation_language = any(
            word in normalized
            for word in ("추천", "적합", "가장 좋은", "골라", "찍어", "선택해", "수익률 높은")
        )
        # A request to choose the lower-risk/lower-fee item among two explicit
        # product codes is closed factual comparison, not suitability advice.
        # Keep recommendation routing for open-ended product selection.
        objective_product_comparison = (
            len(codes) >= 2
            and bool(extracted.requested_fields)
            and any(word in normalized for word in ("비교", "각각", "더 낮", "더 높", "어느", "골라"))
        )
        conditional = recommendation_language and not objective_product_comparison
        comparison = any(word in normalized for word in ("비교", "차이", "어느", "각각", "구별", "대조", "대비")) or len(entities) >= 2
        personal = any(word in normalized for word in ("현재 제", "내 계좌", "내 IRP", "개인 계좌", "제 주민", "제 잔액"))
        external_or_predictive = any(
            word in normalized
            for word in ("시장 전망", "다음 달", "향후 전망", "실시간", "현재 시장", "예측", "년 말", "연말")
        )
        intent = "unsupported_or_personal" if personal or external_or_predictive else "conditional_recommendation" if conditional else "product_explanation" if codes else "tax" if any(word in normalized for word in ("세금", "과세", "공제")) else "pension_system"
        # Keep legacy fields and decisions unchanged during P10-A. P10-B's
        # experimental router consumes ``extracted_entities`` separately.
        # Preserve the submitted wording for API/UI output.  Planner and entity
        # extraction independently use the canonical form above.
        return QueryAnalysis(raw_question, intent, codes, entities, comparison, conditional, extracted)
