"""
Cloudflare Worker가 검증할 서명된 1회용 토큰을 생성한다.
별도의 DB/KV 없이도 "위조 불가능 + 만료시간 포함" 토큰을 만들기 위해
HMAC-SHA256 서명 방식을 사용한다 (JWT의 아주 단순화된 버전).

토큰 형식: base64url(payload_json) + "." + base64url(hmac_sha256(payload_json))
payload = {"exp": <만료 unix timestamp>}

필요 환경변수:
  TRIGGER_SECRET   (Cloudflare Worker와 반드시 동일한 값을 공유해야 함 - GitHub Secrets에 저장)

사용법:
  python scripts/generate_trigger_token.py --ttl-hours 24
  -> 표준출력으로 토큰 문자열 1줄 출력 (워크플로우에서 $GITHUB_ENV로 캡처해서 사용)
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ttl-hours", type=float, default=24)
    args = parser.parse_args()

    secret = os.environ.get("TRIGGER_SECRET")
    if not secret:
        print("ERROR: TRIGGER_SECRET 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    payload = {"exp": int(time.time() + args.ttl_hours * 3600)}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    payload_b64 = b64url_encode(payload_bytes)

    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    signature_b64 = b64url_encode(signature)

    token = f"{payload_b64}.{signature_b64}"
    print(token)


if __name__ == "__main__":
    main()
