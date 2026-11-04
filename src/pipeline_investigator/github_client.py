
"""Read-only GitHub Actions API client."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


API_URL = "https://api.github.com"
API_VERSION = "2026-03-10"


class GitHubAPIError(Exception):
    """Raised when a GitHub API request fails."""


MAX_LOG_BYTES = 1024 * 1024  # 1 MiB for the prototype

# GitHub Actions logs are delivered through temporary URLs.
# This allowlist must be reviewed if GitHub changes its hosts.
ALLOWED_LOG_HOSTS = {
    "results-receiver.actions.githubusercontent.com",
    "pipelines.actions.githubusercontent.com",
    "productionresultssa0.blob.core.windows.net",
}


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self, request, fp, code, msg, headers, newurl
    ):
        return None



def validate_download_url(url):
    parsed = urlsplit(url)

    if parsed.scheme != "https":
        raise GitHubAPIError(
            "Log download must use HTTPS"
        )

    if parsed.username or parsed.password or parsed.port:
        raise GitHubAPIError(
            "Unexpected URL credentials or port"
        )

    hostname = parsed.hostname or ""

    allowed_exact_hosts = {
        "results-receiver.actions.githubusercontent.com",
        "pipelines.actions.githubusercontent.com",
    }

    allowed_azure_storage = re.fullmatch(
        r"productionresultssa[0-9]+\.blob\.core\.windows\.net",
        hostname,
    )

    if (
        hostname not in allowed_exact_hosts
        and not allowed_azure_storage
    ):
        raise GitHubAPIError(
            "Unapproved log download host"
        )

    return url



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


    def download_job_logs(self, job_id):
        """Download bounded plain-text logs for one job."""

        job_id = int(job_id)
        if job_id <= 0:
            raise ValueError("Job ID must be positive")

        api_url = (
            f"{API_URL}/repos/{self.owner}/{self.repo}"
            f"/actions/jobs/{job_id}/logs"
        )

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "pipeline-failure-investigator",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        opener = build_opener(NoRedirectHandler())

        try:
            request = Request(api_url, headers=headers)

            try:
                with opener.open(request, timeout=15):
                    raise GitHubAPIError(
                        "Expected a GitHub log redirect"
                    )
            except HTTPError as exc:
                if exc.code != 302:
                    raise GitHubAPIError(
                        f"GitHub log API returned HTTP {exc.code}"
                    ) from exc

                download_url = exc.headers.get("Location")

            if not download_url:
                raise GitHubAPIError(
                    "GitHub did not provide a download URL"
                )

            validate_download_url(download_url)

            # Never forward the GitHub token to the
            # temporary storage URL.
            download_request = Request(
                download_url,
                headers={
                    "User-Agent": "pipeline-failure-investigator"
                },
            )

            with opener.open(
                download_request, timeout=15
            ) as response:
                if response.status != 200:
                    raise GitHubAPIError(
                        "Unexpected log download response"
                    )

                content = response.read(MAX_LOG_BYTES + 1)

            if len(content) > MAX_LOG_BYTES:
                raise GitHubAPIError(
                    "Job logs exceed the configured size limit"
                )

            return content.decode(
                "utf-8", errors="replace"
            )

        except GitHubAPIError:
            raise
        except (HTTPError, URLError, TimeoutError) as exc:
            raise GitHubAPIError(
                "Unable to download GitHub job logs"
            ) from exc
