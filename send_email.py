"""
SendGrid API로 이메일을 발송한다. 두 가지 모드를 지원한다.

  notify : "리포트 생성 시작" 버튼이 담긴 알림 메일 발송 (주간 스케줄에서 호출)
  report : 완성된 HTML 리포트를 본문에 담아 발송 (파이프라인 마지막 단계에서 호출)

필요 환경변수:
  SENDGRID_API_KEY
  MAIL_FROM        (발신자, SendGrid에서 인증된 주소여야 함)
  MAIL_TO          (수신자, 콤마로 여러 명 가능)
  TRIGGER_BASE_URL (notify 모드에서 필요. 예: https://xxxx.workers.dev/trigger)
  TRIGGER_TOKEN    (notify 모드에서 필요. 서명된 1회용 토큰 - generate_trigger_token.py로 생성)

사용법:
  python scripts/send_email.py --mode notify
  python scripts/send_email.py --mode report --report-html data/report.html
"""
import argparse
import os
import sys
from pathlib import Path

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def send(subject: str, html_content: str):
    api_key = os.environ["SENDGRID_API_KEY"]
    mail_from = os.environ["MAIL_FROM"]
    mail_to = [addr.strip() for addr in os.environ["MAIL_TO"].split(",")]

    message = Mail(
        from_email=mail_from,
        to_emails=mail_to,
        subject=subject,
        html_content=html_content,
    )
    sg = SendGridAPIClient(api_key)
    resp = sg.send(message)
    print(f"발송 완료 (status={resp.status_code})")


def build_notify_html() -> str:
    trigger_url = f"{os.environ['TRIGGER_BASE_URL']}?token={os.environ['TRIGGER_TOKEN']}"
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2>📊 이번 주 SNS 트렌드 리포트가 준비됐습니다</h2>
      <p>아래 버튼을 누르면 5개 공공기관의 최신 유튜브·인스타그램 콘텐츠를 수집해
      리포트를 생성합니다. 완료되면 별도 메일로 리포트가 발송됩니다 (수 분 소요).</p>
      <p style="text-align:center; margin: 32px 0;">
        <a href="{trigger_url}"
           style="background:#1a5fb4; color:#fff; padding:14px 28px; border-radius:8px;
                  text-decoration:none; font-weight:bold; display:inline-block;">
          📊 리포트 생성 시작
        </a>
      </p>
      <p style="color:#888; font-size:12px;">이 링크는 24시간 동안만 유효합니다.</p>
    </div>
    """


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["notify", "report"], required=True)
    parser.add_argument("--report-html", default="data/report.html")
    args = parser.parse_args()

    if args.mode == "notify":
        send(
            subject="[SNS 트렌드 리포트] 이번 주 리포트를 생성해주세요",
            html_content=build_notify_html(),
        )
    else:
        html = Path(args.report_html).read_text(encoding="utf-8")
        send(subject="[SNS 트렌드 리포트] 이번 주 리포트가 도착했습니다", html_content=html)


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"ERROR: 필요한 환경변수가 없습니다: {e}", file=sys.stderr)
        sys.exit(1)
