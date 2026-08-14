"""
curated.json + Jinja2 템플릿으로 HTML 리포트를 생성한다.

사용법:
  python scripts/generate_report.py --curated data/curated.json --out data/report.html
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--curated", default="data/curated.json")
    parser.add_argument("--template-dir", default="templates")
    parser.add_argument("--out", default="data/report.html")
    args = parser.parse_args()

    curated = json.loads(Path(args.curated).read_text(encoding="utf-8"))

    env = Environment(loader=FileSystemLoader(args.template_dir))
    template = env.get_template("report.html.j2")

    html = template.render(
        organizations=curated["organizations"],
        report_date=datetime.now().strftime("%Y-%m-%d"),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"완료: {out_path}")


if __name__ == "__main__":
    main()
