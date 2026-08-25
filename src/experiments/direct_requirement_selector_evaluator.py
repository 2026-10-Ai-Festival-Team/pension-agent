"""Evaluation and frozen-baseline adapters for P39 direct selection."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from src.experiments.query_understanding import RequirementBuilder
from src.orchestration.query_analyzer import QueryAnalyzer


_LEGACY_SLOT_MAP = {
    "db_operation": "DB.operation_party",
    "dc_operation": "DC.operation_party",
    "db_benefit": "DB.benefit_determination",
    "dc_benefit": "DC.benefit_determination",
    "db_dc_operation_party": ("DB.operation_party", "DC.operation_party"),
    "db_dc_benefit_determination": ("DB.benefit_determination", "DC.benefit_determination"),
    "dc_employer_contribution": "DC.employer_contribution",
    "db_dc_contribution_structure": "DC.employer_contribution",
    "education_frequency": "retirement_pension.participant_education.frequency",
    "education_outsourcing": "retirement_pension.participant_education.outsourcing",
    "pension_savings_only_deduction_limit": "pension_savings.tax_credit.limit",
    "pension_savings_irp_combined_deduction_limit": "pension_savings_IRP.tax_credit.combined_limit",
    "general_account_tax_timing": "general_account.investment_income.tax_timing",
    "pension_account_tax_deferral": ("pension_account.investment_income.tax_timing", "pension_account.investment_income.not_tax_exempt"),
    "foreign_etf_general_account_tax": "foreign_ETF.general_account.tax_timing",
    "foreign_etf_pension_account_tax": "foreign_ETF.pension_account.tax_timing",
    "pension_savings_withdrawal_scope": "pension_savings.early_withdrawal.allowed_reasons",
    "irp_withdrawal_legal_grounds_comparison": "IRP.early_withdrawal.allowed_reasons",
    "account_withdrawal_tax_treatment": ("pension_savings.withdrawal.tax_treatment", "IRP.withdrawal.tax_treatment"),
    "isa_transfer_deadline": "ISA.transfer.deadline",
    "isa_transfer_additional_tax_credit": "ISA.transfer.additional_tax_credit",
    "in_kind_transfer_meaning": "retirement_pension.in_kind_transfer.definition",
    "db_dc_in_kind_transfer_application": "retirement_pension.in_kind_transfer.DB_DC.application_route",
    "irp_in_kind_transfer_application": "retirement_pension.in_kind_transfer.IRP.application_route",
    "retirement_etf_direct_trade": "retirement_pension.ETF.direct_trade_scope",
    "retirement_etf_leverage_inverse_restriction": "retirement_pension.ETF.leverage_inverse_restriction",
    "retirement_income_transfer_tax_deferral": "retirement_income.IRP_transfer.tax_timing",
    "retirement_income_annuity_tax_timing": "retirement_income.IRP_transfer.tax_timing",
}
_PRODUCT_SLOT_MAP = {
    "risk_grade": "product.risk_grade.current",
    "risk_grade_changeability": "product.risk_grade.change_possibility",
    "investment_strategy": "product.tracking_index",
    "investment_target": "product.equity_allocation_limit",
    "total_fee": "product.total_fee",
    "example_cost": "product.period_cost",
}


def legacy_planner_requirements(question: str) -> tuple[str, ...]:
    """Project the existing production Planner into P39's common vocabulary.

    This is a reporting adapter, never a change to the legacy plan or its
    retrieval behavior.  Unmapped legacy slots are deliberately omitted rather
    than guessed into a P39 requirement.
    """
    plan = RequirementBuilder().build(QueryAnalyzer().analyze(question))
    selected: set[str] = set()
    for slot in plan.case.slots:
        mapped = _LEGACY_SLOT_MAP.get(slot.key)
        if mapped is None and ":" in slot.key:
            _, field = slot.key.split(":", 1)
            mapped = _PRODUCT_SLOT_MAP.get(field)
        if isinstance(mapped, str):
            selected.add(mapped)
        elif mapped:
            selected.update(mapped)
    return tuple(sorted(selected))


def v21_plan_requirements(plan: dict) -> tuple[str, ...]:
    """Project frozen P38-7B semantic-plan output into P39 vocabulary.

    This provides an honest comparison baseline; it does not rerun HCX or
    repair missing atoms from the raw question.
    """
    subjects, fields = set(plan.get("subjects", [])), set(plan.get("fields", []))
    qualifiers = set(plan.get("essential_qualifiers", []))
    selected: set[str] = set()
    if "operation_party" in fields:
        if "account:DB" in subjects:
            selected.add("DB.operation_party")
        if "account:DC" in subjects:
            selected.add("DC.operation_party")
    if "benefit_determination" in fields:
        if "account:DB" in subjects:
            selected.add("DB.benefit_determination")
        if "account:DC" in subjects:
            selected.add("DC.benefit_determination")
    if "contribution_structure" in fields and "account:DC" in subjects:
        selected.add("DC.employer_contribution")
    if "education_frequency" in fields:
        selected.add("retirement_pension.participant_education.frequency")
    if "education_outsourcing" in fields:
        selected.add("retirement_pension.participant_education.outsourcing")
    if "tax_credit_limit" in fields:
        if {"account:pension_savings", "account:IRP"} <= subjects:
            selected.update(("pension_savings.tax_credit.limit", "pension_savings_IRP.tax_credit.combined_limit"))
        if "account:ISA" in subjects:
            selected.add("ISA.transfer.additional_tax_credit")
    if "tax_timing" in fields:
        if "product:foreign_etf" in subjects:
            if "account:general" in subjects:
                selected.add("foreign_ETF.general_account.tax_timing")
            if "account:pension" in subjects:
                selected.add("foreign_ETF.pension_account.tax_timing")
        elif {"account:general", "account:pension"} <= subjects:
            selected.update(("general_account.investment_income.tax_timing", "pension_account.investment_income.tax_timing"))
            if "not_tax_exempt" in qualifiers:
                selected.add("pension_account.investment_income.not_tax_exempt")
        elif "account:IRP" in subjects and "event:retirement_benefit" in subjects:
            selected.add("retirement_income.IRP_transfer.tax_timing")
    if "withdrawal_reason" in fields:
        if "account:DC" in subjects:
            selected.add("DC.early_withdrawal.allowed_reasons")
        if "account:pension_savings" in subjects:
            selected.add("pension_savings.early_withdrawal.allowed_reasons")
        if "account:IRP" in subjects:
            selected.add("IRP.early_withdrawal.allowed_reasons")
    if "required_document" in fields and "account:DC" in subjects:
        selected.add("DC.early_withdrawal.required_documents")
    if "tax_treatment" in fields:
        if "account:pension_savings" in subjects:
            selected.add("pension_savings.withdrawal.tax_treatment")
        if "account:IRP" in subjects:
            selected.add("IRP.withdrawal.tax_treatment")
    if "transfer_deadline" in fields and "account:ISA" in subjects:
        selected.add("ISA.transfer.deadline")
    if "transfer_definition" in fields:
        selected.add("retirement_pension.in_kind_transfer.definition")
    if "application_route" in fields:
        if {"account:DB", "account:DC"} & subjects:
            selected.add("retirement_pension.in_kind_transfer.DB_DC.application_route")
        if "account:IRP" in subjects:
            selected.add("retirement_pension.in_kind_transfer.IRP.application_route")
    if "etf_direct_trade" in fields:
        selected.add("retirement_pension.ETF.direct_trade_scope")
    if "leverage_inverse_restriction" in fields:
        selected.add("retirement_pension.ETF.leverage_inverse_restriction")
    if "risk_grade" in fields:
        if "historical" in qualifiers:
            selected.add("product.risk_grade.historical")
        if "historical" not in qualifiers or "current" in qualifiers:
            selected.add("product.risk_grade.current")
    if "risk_grade_changeability" in fields:
        selected.add("product.risk_grade.change_possibility")
    if "tracking_index" in fields:
        selected.add("product.tracking_index")
    if "equity_allocation_limit" in fields:
        selected.add("product.equity_allocation_limit")
    if "total_fee" in fields:
        selected.add("product.total_fee")
    if "cost_example" in fields:
        selected.add("product.period_cost")
    if "partial_withdrawal_condition" in fields:
        selected.add("pension_account.partial_withdrawal.condition")
    if "account_closure_condition" in fields:
        selected.add("pension_account.account_closure.condition")
    if "partial_withdrawal_tax" in fields:
        selected.add("pension_account.partial_withdrawal.tax_treatment")
    if "account_closure_tax" in fields:
        selected.add("pension_account.account_closure.tax_treatment")
    return tuple(sorted(selected))


def score_requirement_predictions(rows: list[dict], predictions: dict[str, tuple[str, ...]], runtime: dict | None = None) -> dict:
    """Score direct multi-label requirements with per-question audit details."""
    total_tp = total_fp = total_fn = exact = multi_matched = multi_gold = 0
    details = []
    for row in rows:
        # P39-1 projects P38 rows by ``source_question_id``; fresh P39-2+
        # manifests own their stable ``id``.  Supporting both is essential so
        # a completed live run cannot fail during final scoring.
        qid = row["source_question_id"] if "source_question_id" in row else row["id"]
        gold = set(row["selected_requirements"])
        predicted = set(predictions.get(qid, ()))
        tp, extra, missing = gold & predicted, predicted - gold, gold - predicted
        total_tp += len(tp)
        total_fp += len(extra)
        total_fn += len(missing)
        exact += int(predicted == gold)
        if len(gold) > 1:
            multi_gold += len(gold)
            multi_matched += len(tp)
        details.append({
            "source_question_id": qid,
            "question": row["question"],
            "gold_requirements": sorted(gold),
            "predicted_requirements": sorted(predicted),
            "matched_requirements": sorted(tp),
            "unsupported_extra_requirements": sorted(extra),
            "false_missing_requirements": sorted(missing),
            "requirement_exact": predicted == gold,
            "multi_requirement_recall": round(len(tp) / len(gold), 4) if len(gold) > 1 else None,
        })
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    return {
        "question_count": len(rows),
        "requirement_precision": round(precision, 4),
        "requirement_recall": round(recall, 4),
        "requirement_exact": {"exact": exact, "total": len(rows), "accuracy": round(exact / len(rows), 4) if rows else 0.0},
        "multi_requirement_recall": {"matched": multi_matched, "gold": multi_gold, "recall": round(multi_matched / multi_gold, 4) if multi_gold else 1.0},
        "unsupported_extra_requirement_count": total_fp,
        "false_missing_requirement_count": total_fn,
        "details": details,
        "runtime": runtime or {},
    }


def score_scope_errors(
    rows: list[dict],
    predictions: dict[str, tuple[str, ...]],
    product_codes: dict[str, tuple[str, ...]],
) -> dict:
    """Report subject/account/product scope errors independently of aggregate F1."""
    details, errors = [], 0
    for row in rows:
        qid = row["id"]
        missing_scope = sorted(set(row.get("scope_requirements", ())) - set(predictions.get(qid, ())))
        expected_codes = tuple(row.get("expected_product_codes", ()))
        actual_codes = tuple(product_codes.get(qid, ()))
        product_scope_error = bool(expected_codes) and actual_codes != expected_codes
        scope_error = bool(missing_scope) or product_scope_error
        errors += int(scope_error)
        details.append({
            "id": qid,
            "missing_scope_requirements": missing_scope,
            "expected_product_codes": list(expected_codes),
            "resolved_product_codes": list(actual_codes),
            "product_scope_error": product_scope_error,
            "scope_error": scope_error,
        })
    return {"scope_error_count": errors, "total": len(rows), "details": details}


def frozen_v21_predictions(path: Path) -> dict[str, tuple[str, ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["source_question_id"]: v21_plan_requirements(item["plan"]) for item in data["planner_outputs"]}
