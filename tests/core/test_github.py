import pytest

from taken.core.github import normalize_source, parse_source


@pytest.mark.parametrize(
    ("raw", "expected_owner", "expected_repo", "expected_skill"),
    [
        ("vercel-labs/agent-skills", "vercel-labs", "agent-skills", None),
        ("vercel-labs/agent-skills/react-best-practices", "vercel-labs", "agent-skills", "react-best-practices"),
        ("https://github.com/vercel-labs/agent-skills", "vercel-labs", "agent-skills", None),
        ("https://github.com/vercel-labs/agent-skills/tree/main", "vercel-labs", "agent-skills", None),
        ("npx skills add vercel-labs/agent-skills", "vercel-labs", "agent-skills", None),
        (
            "npx skills add vercel-labs/agent-skills/react-best-practices",
            "vercel-labs",
            "agent-skills",
            "react-best-practices",
        ),
    ],
)
def test_normalize_and_parse__all_source_formats__correct_owner_repo_skill(
    raw: str,
    expected_owner: str,
    expected_repo: str,
    expected_skill: str | None,
) -> None:
    # Act
    owner, repo, skill = parse_source(normalize_source(raw))

    # Assert
    assert owner == expected_owner
    assert repo == expected_repo
    assert skill == expected_skill
