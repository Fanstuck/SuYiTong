from pathlib import Path

from syt_platform.services.academic_search import AcademicSearchService


def test_openalex_key_is_sent_as_bearer_header(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENALEX_API_KEY=fixture-openalex-token\n", encoding="utf-8")

    service = AcademicSearchService(env_path)

    assert service._openalex_headers() == {
        "Authorization": "Bearer fixture-openalex-token"
    }
