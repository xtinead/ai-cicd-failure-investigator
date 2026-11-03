
import json
from pathlib import Path


def save_reports(result: dict, output_dir: str) -> None:
    """Generate JSON and Markdown investigation reports."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    json_path = directory / "investigation.json"
    markdown_path = directory / "investigation.md"

    # Generate machine-readable JSON report
    json_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    # Generate human-readable Markdown report
    lines = [
        "# CI/CD Pipeline Investigation",
        "",
        f"**Status:** {result['status']}",
        f"**Analysis type:** {result['analysis_type']}",
        f"**Root cause confirmed:** {result['root_cause_confirmed']}",
        "",
    ]

    # Handle unknown or unrecognized failures
    if not result["findings"]:
        lines.extend([
            "## Investigation Result",
            "",
            "No recognized failure signature was detected.",
            "Manual investigation is required.",
            "",
        ])

    # Generate a detailed report for each detected failure
    for finding in result["findings"]:

        lines.extend([
            f"## {finding['category']}",
            "",
            "### Detected Evidence",
            "",
            f"`{finding['evidence']}`",
            "",
            "### Likely Cause",
            "",
            finding["likely_cause"],
            "",
            "### Recommended Diagnostic Steps",
            "",
        ])

        # Steps to investigate the failure
        for step in finding.get("next_steps", []):
            lines.append(f"- {step}")

        # Potential fixes based on investigation results
        remediations = finding.get(
            "possible_remediations", []
        )

        if remediations:
            lines.extend([
                "",
                "### Possible Remediations",
                "",
            ])

            for remediation in remediations:
                lines.append(f"- {remediation}")

        # Steps to verify the issue is resolved
        verification = finding.get(
            "verification_steps", []
        )

        if verification:
            lines.extend([
                "",
                "### Verification Steps",
                "",
            ])

            for step in verification:
                lines.append(f"- {step}")

        # Separate findings for readability
        lines.append("")

    # Write Markdown report
    markdown_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
