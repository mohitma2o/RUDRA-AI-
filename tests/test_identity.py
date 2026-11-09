from rudra.identity import (
    check_creator_query,
    creator_response_language,
)


def test_creator_questions_return_deterministic_language_matched_replies():
    cases = (
        (
            "Who made you?",
            "en",
            "I was created and developed by Mohit Mattoo.",
        ),
        (
            "Who is your creator?",
            "en",
            "I was created and developed by Mohit Mattoo.",
        ),
        (
            "Tumhe kisne banaya hai?",
            "hi",
            "Mujhe Mohit Mattoo ne banaya hai.",
        ),
        (
            "Tuhanu kine banaya?",
            "pa",
            "Mainu Mohit Mattoo ne banaya hai.",
        ),
        (
            "ਤੁਹਾਨੂੰ ਕਿਸਨੇ ਬਣਾਇਆ?",
            "pa",
            "ਮੈਨੂੰ Mohit Mattoo ਨੇ ਬਣਾਇਆ ਹੈ।",
        ),
        (
            "तुम्हें किसने बनाया है?",
            "hi",
            "Mujhe Mohit Mattoo ne banaya hai.",
        ),
    )

    for prompt, expected_language, expected_reply in cases:
        matched, reply = check_creator_query(prompt)
        assert matched, repr(prompt)
        assert expected_reply in reply
        assert creator_response_language(prompt) == expected_language


def test_unrelated_questions_do_not_trigger_creator_response():
    for prompt in (
        "Who made this song?",
        "Tell me about Mohit Mattoo.",
        "What is a creator?",
        "",
    ):
        assert check_creator_query(prompt) == (False, "")


def test_legacy_agent_answers_creator_question_before_calling_models():
    from rudra.agent import agent_response

    response = agent_response(
        "Who created you?",
        llm_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("Creator questions should bypass the model.")
        ),
        tool_call_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("Creator questions should bypass tool calling.")
        ),
    )

    assert "Mohit Mattoo" in response


def test_legacy_query_llm_answers_creator_question_before_provider_selection(monkeypatch):
    from rudra import llm

    monkeypatch.setattr(
        llm,
        "get_llm_backend",
        lambda: (_ for _ in ()).throw(
            AssertionError("Creator questions should bypass provider selection.")
        ),
    )

    assert "Mohit Mattoo" in llm.query_llm("Who is your creator?")
