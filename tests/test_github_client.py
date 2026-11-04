
import pytest

from pipeline_investigator.github_client import (
    GitHubActionsClient,
    GitHubAPIError,
)


def test_client_configuration():
    client = GitHubActionsClient(
        owner="xtinead",
        repo="ai-cicd-failure-investigator",
    )

    assert client.owner == "xtinead"
    assert client.repo == "ai-cicd-failure-investigator"


def test_rejects_invalid_repository_name():
    with pytest.raises(ValueError):
        GitHubActionsClient(
            owner="xtinead",
            repo="../another-repository",
        )


def test_get_workflow_run(monkeypatch):
    client = GitHubActionsClient(
        owner="xtinead",
        repo="ai-cicd-failure-investigator",
    )

    def fake_get(path, params=None):
        assert path.endswith("/actions/runs/123")
        return {
            "id": 123,
            "conclusion": "failure",
        }

    monkeypatch.setattr(client, "_get", fake_get)

    result = client.get_workflow_run(123)

    assert result["id"] == 123
    assert result["conclusion"] == "failure"


def test_get_failed_jobs(monkeypatch):
    client = GitHubActionsClient(
        owner="xtinead",
        repo="ai-cicd-failure-investigator",
    )

    fake_jobs = [
        {
            "id": 101,
            "name": "build",
            "conclusion": "success",
        },
        {
            "id": 102,
            "name": "deploy",
            "conclusion": "failure",
        },
        {
            "id": 103,
            "name": "test",
            "conclusion": "success",
        },
    ]

    monkeypatch.setattr(
        client,
        "list_jobs",
        lambda run_id: fake_jobs,
    )

    failed_jobs = client.get_failed_jobs(123)

    assert len(failed_jobs) == 1
    assert failed_jobs[0]["name"] == "deploy"


def test_pagination(monkeypatch):
    client = GitHubActionsClient(
        owner="xtinead",
        repo="ai-cicd-failure-investigator",
    )

    pages_requested = []

    def fake_get(path, params=None):
        page = params["page"]
        pages_requested.append(page)

        if page == 1:
            return {
                "jobs": [
                    {"id": i, "conclusion": "success"}
                    for i in range(100)
                ]
            }

        return {
            "jobs": [
                {"id": 100, "conclusion": "failure"}
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)

    jobs = client.list_jobs(123)

    assert len(jobs) == 101
    assert pages_requested == [1, 2]
