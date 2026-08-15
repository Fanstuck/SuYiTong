from types import SimpleNamespace

from jiuwenswarm.symphony.llm import extract_message_content


def test_extracts_deepseek_reasoning_content_when_content_is_empty() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    reasoning_content='{"status":"ok"}',
                )
            )
        ]
    )

    assert extract_message_content(response) == '{"status":"ok"}'
