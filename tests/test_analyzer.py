import json

from pipeline_investigator.analyzer import redact
from pipeline_investigator.reporting import save_reports
from pipeline_investigator.analyzer import analyze

def test_redacts_aws_access_key():
    secret = "AKIA" + "A" * 16

    sanitized = redact(f"AWS_ACCESS_KEY_ID={secret}")

    assert secret not in sanitized
    assert "[REDACTED_AWS_ACCESS_KEY]" in sanitized


def test_redacts_bearer_token():
    secret = "example-secret-token"

    sanitized = redact(
        f"Authorization: Bearer {secret}"
    )

    assert secret not in sanitized
    assert "[REDACTED]" in sanitized


def test_report_generation(tmp_path):
    result = {
        "status": "findings_detected",
        "analysis_type": "rule_based",
        "root_cause_confirmed": False,
        "findings": [
            {
                "category": "aws_iam",
                "evidence": "AccessDenied",
                "likely_cause": "Missing IAM permission",
                "next_steps": [
                    "Review IAM policies",
                ],
            }
        ],
    }

    save_reports(result, str(tmp_path))

    json_path = tmp_path / "investigation.json"
    markdown_path = tmp_path / "investigation.md"

    assert json_path.exists()
    assert markdown_path.exists()

    data = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    assert data["status"] == "findings_detected"
    assert "aws_iam" in markdown_path.read_text(
        encoding="utf-8"
    )


def test_aws_iam_failure():
    log = (
        "Error: AccessDenied - "
        "not authorized to perform iam:PassRole"
    )

    result = analyze(log)

    assert result["status"] == "findings_detected"
    assert result["findings"][0]["category"] == "aws_iam"
    assert result["root_cause_confirmed"] is False


def test_terraform_state_lock():
    log = "Error acquiring the state lock"

    result = analyze(log)

    assert result["findings"][0]["category"] == (
        "terraform_state_lock"
    )


def test_kubernetes_image_pull():
    log = "Pod status: ImagePullBackOff"

    result = analyze(log)

    assert result["findings"][0]["category"] == (
        "kubernetes_image_pull"
    )


def test_unknown_failure():
    log = "Unexpected application error"

    result = analyze(log)

    assert result["status"] == "unknown"
    assert result["findings"] == []



def test_kubernetes_crashloop():
    log = "Pod status: CrashLoopBackOff"

    result = analyze(log)

    assert result["status"] == "findings_detected"
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["category"] == "kubernetes_crashloop"
    assert result["root_cause_confirmed"] is False

    assert len(finding["next_steps"]) > 0
    assert len(finding["possible_remediations"]) > 0
    assert len(finding["verification_steps"]) > 0

    assert any(
        "kubectl logs" in step
        for step in finding["next_steps"]
    )

def test_report_includes_remediation_and_verification(tmp_path):
    log = "Pod status: CrashLoopBackOff"

    result = analyze(log)

    save_reports(result, str(tmp_path))

    report_path = tmp_path / "investigation.md"

    assert report_path.exists()

    report = report_path.read_text(encoding="utf-8")

    assert "kubernetes_crashloop" in report
    assert "Recommended Diagnostic Steps" in report
    assert "Possible Remediations" in report
    assert "Verification Steps" in report
    assert "kubectl logs" in report

