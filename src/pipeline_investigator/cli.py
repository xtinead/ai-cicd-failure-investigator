
import argparse
from pathlib import Path

from pipeline_investigator.analyzer import analyze
from pipeline_investigator.reporting import save_reports


def main():
    parser = argparse.ArgumentParser(
        description="Analyze CI/CD pipeline failure logs."
    )

    parser.add_argument(
        "--log",
        required=True,
        help="Path to a pipeline log file.",
    )

    parser.add_argument(
        "--output",
        default="reports",
        help="Directory for investigation reports.",
    )

    args = parser.parse_args()

    log_text = Path(args.log).read_text(
        encoding="utf-8"
    )

    result = analyze(log_text)

    save_reports(result, args.output)

    print(f"Investigation status: {result['status']}")
    print(f"Findings: {len(result['findings'])}")
    print(f"Reports saved to: {args.output}")


if __name__ == "__main__":
    main()
