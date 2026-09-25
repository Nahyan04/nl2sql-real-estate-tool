from app.core.prompt_builder import build_system_prompt, build_user_prompt, MAX_PROMPT_CHARS


def test_source_semantics_and_unsupported_contract():
    prompt = build_system_prompt()
    assert 'active_value_aed is not annual rent' in prompt
    assert 'Sales municipality is unknown' in prompt
    assert '<unsupported>' in prompt
    assert 'community_id' not in prompt


def test_budget_preserves_question_and_feedback():
    prompt = build_user_prompt('question', 'x'*50000, feedback='retry detail')
    assert len(prompt) + len(build_system_prompt()) <= MAX_PROMPT_CHARS
    assert 'question' in prompt and 'retry detail' in prompt
