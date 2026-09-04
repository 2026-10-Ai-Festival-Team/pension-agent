from src.generation.versioned_generator_prompt import load_generator_prompt


def test_v2_prompt_declared_hash_matches_and_has_the_frozen_guard_contract():
    prompt = load_generator_prompt()

    assert prompt.prompt_id == "generator_prompt_final_v2_1"
    assert prompt.declared_sha_matches
    assert prompt.runtime_transport["citation_rendering"] == "host_owned"
    assert "required_fact_completeness" in prompt.semantic_guards
    assert "answer_the_question_directly_in_the_first_sentence" in prompt.style_rules
    assert "supported_answer_requires_direct_answer_plus_evidence_derived_explanation" in prompt.style_rules
