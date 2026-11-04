
import pytest

from pipeline_investigator.github_client import (
    GitHubActionsClient,
    GitHubAPIError,
)


from pipeline_investigator.github_client import (
    validate_download_url,
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

def test_rejects_unapproved_log_host():
    with pytest.raises(GitHubAPIError):
        validate_download_url(
            "https://example.com/secret-log"
        )


def test_rejects_insecure_log_url():
    with pytest.raises(GitHubAPIError):
        validate_download_url(
            "http://productionresultssa0.blob.core.windows.net/log"
        )

def test_accepts_valid_log_url():
    # This should not raise an exception
    validate_download_url(
        "https://productionresultssa0.blob.core.windows.net/log"
    )


def test_accepts_observed_github_storage_host():
    url = (
        "https://productionresultssa10.blob.core.windows.net/"
        "example-log"
    )

    assert validate_download_url(url) == url

def test_accepts_github_actions_hosts():
    for host in [
        "results-receiver.actions.githubusercontent.com",
        "pipelines.actions.githubusercontent.com",
    ]:
        url = f"https://{host}/example-log"
        assert validate_download_url(url) == url

def test_rejects_url_with_credentials_or_port():
    with pytest.raises(GitHubAPIError):
        validate_download_url(
            "https://user:pass@results-receiver.actions.githubusercontent.com:443/log"
        )
    with pytest.raises(GitHubAPIError):
        validate_download_url(
            "https://results-receiver.actions.githubusercontent.com:443/log"
        )
def test_rejects_non_https_url():
    with pytest.raises(GitHubAPIError):
        validate_download_url(
            "ftp://results-receiver.actions.githubusercontent.com/log"
        )
