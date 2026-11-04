
"""Read-only GitHub Actions API client."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.github.com"
API_VERSION = "2026-03-10"


class GitHubAPIError(Exception):
    """Raised when a GitHub API request fails."""


class GitHubActionsClient:
    def __init__(self, owner, repo, token=None):
        name_pattern = r"[A-Za-z0-9_.-]+"

        if not re.fullmatch(name_pattern, owner):
            raise ValueError("Invalid repository owner")

        if not re.fullmatch(name_pattern, repo):
            raise ValueError("Invalid repository name")

        self.owner = owner
        self.repo = repo
        self.token = token

    def _get(self, path, params=None):
        url = f"{API_URL}{path}"

        if params:
            url += "?" + urlencode(params)

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "pipeline-failure-investigator",
        }

        if self.token:
            headers["Authorization"] = (
                f"Bearer {self.token}"
            )

        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=15) as response:
                return json.load(response)

        except HTTPError as exc:
            raise GitHubAPIError(
                f"GitHub API returned HTTP {exc.code}"
            ) from exc

        except URLError as exc:
            raise GitHubAPIError(
                "Unable to connect to GitHub API"
            ) from exc

    def get_workflow_run(self, run_id):
        """Retrieve metadata for a workflow run."""

        return self._get(
            f"/repos/{self.owner}/{self.repo}"
            f"/actions/runs/{int(run_id)}"
        )

    def list_jobs(self, run_id):
        """List all jobs in the latest run attempt."""

        jobs = []
        page = 1

        while True:
            data = self._get(
                f"/repos/{self.owner}/{self.repo}"
                f"/actions/runs/{int(run_id)}/jobs",
                params={
                    "per_page": 100,
                    "page": page,
                    "filter": "latest",
                },
            )

            batch = data.get("jobs", [])
            jobs.extend(batch)

            if len(batch) < 100:
                break

            page += 1

            if page > 10:
                raise GitHubAPIError(
                    "Job pagination safety limit exceeded"
                )

        return jobs

    def get_failed_jobs(self, run_id):
        """Return jobs with a failure conclusion."""

        jobs = self.list_jobs(run_id)

        return [
            job for job in jobs
            if job.get("conclusion") == "failure"
        ]
