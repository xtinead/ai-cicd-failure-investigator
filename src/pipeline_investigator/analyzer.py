
import re
from dataclasses import asdict, dataclass


@dataclass
class Finding:
    category: str
    evidence: str
    likely_cause: str
    next_steps: list[str]
    possible_remediations: list[str]
    verification_steps: list[str]


FAILURE_RULES = [
    {
        "category": "aws_iam",
        "pattern": r"AccessDenied|not authorized to perform",
        "likely_cause": (
            "The pipeline execution identity may lack a required "
            "AWS permission, or an IAM policy condition may deny access."
        ),
        "next_steps": [
            "Identify the AWS principal using aws sts get-caller-identity.",
            "Identify the denied API action and target resource.",
            "Review IAM identity policies, permission boundaries, "
            "session policies, and applicable SCPs.",
            "Inspect the corresponding CloudTrail event.",
        ],
        "possible_remediations": [
            "If a required permission is missing, update the approved "
            "least-privilege IAM policy.",
            "If a policy condition is incorrect, correct it after "
            "validating the intended access requirements.",
            "If the pipeline assumes the wrong role, correct the "
            "role configuration or trust relationship.",
        ],
        "verification_steps": [
            "Verify the pipeline is using the expected IAM principal.",
            "Confirm the required action is authorized for the "
            "intended resource.",
            "Rerun the failed operation through the approved pipeline.",
        ],
    },
    {
        "category": "terraform_state_lock",
        "pattern": r"Error acquiring the state lock",
        "likely_cause": (
            "Terraform could not acquire the state lock. "
            "Another operation may be running, or a previous "
            "operation may have left a stale lock."
        ),
        "next_steps": [
            "Check whether another Terraform operation is active.",
            "Review the lock ID and backend details.",
            "Inspect recent pipeline executions.",
            "Verify backend connectivity and permissions.",
        ],
        "possible_remediations": [
            "If another operation is active, wait for it to finish.",
            "If the lock is confirmed stale, follow the approved "
            "terraform force-unlock recovery procedure.",
            "If backend access is failing, correct the relevant "
            "network or IAM configuration.",
        ],
        "verification_steps": [
            "Confirm no conflicting Terraform operation is running.",
            "Run terraform plan and verify the backend lock works.",
            "Review the plan before approving any infrastructure changes.",
        ],
    },
    {
        "category": "kubernetes_image_pull",
        "pattern": r"ImagePullBackOff|ErrImagePull",
        "likely_cause": (
            "Kubernetes cannot retrieve the container image. "
            "Possible causes include an invalid image reference, "
            "missing registry permissions, or connectivity problems."
        ),
        "next_steps": [
            "Run kubectl describe pod <pod-name> -n <namespace>.",
            "Inspect image pull errors in the pod events.",
            "Verify the container image repository and tag or digest.",
            "Check registry credentials and network connectivity.",
        ],
        "possible_remediations": [
            "Correct the image reference if it is invalid.",
            "Restore registry access if authentication is failing.",
            "Fix DNS or network connectivity if the registry "
            "cannot be reached.",
            "Publish the missing image if the expected artifact "
            "was not built or pushed.",
        ],
        "verification_steps": [
            "Confirm the image exists in the intended registry.",
            "Verify the pod transitions to Running and Ready.",
            "Check application logs and readiness endpoints.",
        ],
    },
    {
        "category": "kubernetes_crashloop",
        "pattern": r"CrashLoopBackOff",
        "likely_cause": (
            "A container is repeatedly failing or exiting. "
            "Possible causes include application startup errors, "
            "invalid configuration, unavailable dependencies, "
            "or resource exhaustion."
        ),
        "next_steps": [
            "Run kubectl describe pod <pod-name> -n <namespace>.",
            "Run kubectl logs <pod-name> -n <namespace> --previous.",
            "Inspect the container termination reason and exit code.",
            "Check Kubernetes events and probe failures.",
            "Verify environment variables, secrets, and dependencies.",
        ],
        "possible_remediations": [
            "If configuration is invalid, correct it in Git "
            "and redeploy through the approved workflow.",
            "If OOMKilled is confirmed, investigate memory usage "
            "and adjust resource settings if justified.",
            "If an external dependency is unavailable, restore "
            "connectivity or service availability.",
            "If the application has a startup bug, fix the code "
            "and release a corrected image.",
        ],
        "verification_steps": [
            "Confirm the container starts successfully.",
            "Verify restart counts stop increasing.",
            "Check readiness and application health endpoints.",
            "Confirm the original business operation succeeds.",
        ],
    },
]



def redact(log_text: str) -> str:
    """Redact selected credential patterns from log text."""

    patterns = [
        (
            r"(?i)(authorization:\s*bearer\s+)\S+",
            r"\1[REDACTED]",
        ),
        (
            r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
            "[REDACTED_AWS_ACCESS_KEY]",
        ),
        (
            r"(?i)(password\s*[=:]\s*)[^\s]+",
            r"\1[REDACTED]",
        ),
    ]

    sanitized = log_text

    for pattern, replacement in patterns:
        sanitized = re.sub(
            pattern,
            replacement,
            sanitized,
        )

    return sanitized



def analyze(log_text: str) -> dict:
    sanitized_log = redact(log_text)
    findings = []

    for rule in FAILURE_RULES:
        match = re.search(
            rule["pattern"],
            sanitized_log,
            flags=re.IGNORECASE,
        )

        if match:
            findings.append(
                Finding(
                    category=rule["category"],
                    evidence=match.group(0),
                    likely_cause=rule["likely_cause"],
                    next_steps=rule["next_steps"],
                    possible_remediations=rule[
                        "possible_remediations"
                    ],
                    verification_steps=rule[
                        "verification_steps"
                    ],
                )
            )

    return {
        "status": (
            "findings_detected" if findings else "unknown"
        ),
        "analysis_type": "rule_based",
        "root_cause_confirmed": False,
        "findings": [
            asdict(finding) for finding in findings
        ],
    }
