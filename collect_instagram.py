"""
Playwright로 Instagram 공개 프로필 페이지에 접속해 최신 게시물을 '최선을 다해(best-effort)' 스냅샷 수집한다.

*** 중요 - 이 스크립트의 한계 ***
- Instagram은 비로그인 접근을 자주 차단하거나 로그인을 요구합니다.
- 좋아요/조회수 등 정량 지표는 비로그인 상태에서 노출되지 않는 경우가 많아,
  실패 시 게시물 URL과 캡션 일부만 확보하고 지표는 null로 남습니다.
- DOM 구조가 수시로 바뀌므로 셀렉터가 깨질 수 있습니다. 실패해도 파이프라인 전체가
  죽지 않도록 채널 단위로 예외 처리하고, 실패 채널은 리포트에 "확인 실패"로 표시합니다.
- 운영 전환 시에는 Rival IQ, Meltwater 등 정식 라이선스 소셜 리스닝 도구로의 교체를 권장합니다.

필요 패키지: playwright (playwright install chromium 필요)

사용법:
  python scripts/collect_instagram.py --config config/channels.yaml --out data/instagram_raw.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def collect_profile_posts(page, url: str, lookback: int) -> list[dict]:
    """공개 프로필 페이지에서 최신 게시물 링크 + 캡션 일부를 최선을 다해 추출한다."""
    page.goto(url, wait_until="networkidle", timeout=20000)

    # 로그인 유도 팝업이 뜨면 닫기 시도 (셀렉터는 IG 구조 변경 시 깨질 수 있음)
    try:
        page.get_by_role("button", name="나중에 하기").click(timeout=3000)
    except PWTimeout:
        pass

    # 로그인 페이지로 리다이렉트됐는지 확인
    if "accounts/login" in page.url:
        raise RuntimeError("로그인 페이지로 리다이렉트됨 - 비로그인 접근 차단")

    # 게시물 링크 수집 (프로필 그리드의 <a href="/p/..."> 패턴)
    page.wait_for_selector("main a[href*='/p/']", timeout=10000)
    anchors = page.query_selector_all("main a[href*='/p/']")

    posts = []
    seen = set()
    for a in anchors:
        href = a.get_attribute("href")
        if not href or href in seen:
            continue
        seen.add(href)
        full_url = f"https://www.instagram.com{href}"

        # 썸네일 alt 텍스트에 캡션 일부가 담기는 경우가 많음 (완전하지 않음)
        img = a.query_selector("img")
        alt_text = img.get_attribute("alt") if img else None

        posts.append({
            "url": full_url,
            "caption_snippet": alt_text,
            "like_count": None,   # 비로그인 상태에서 통상 미노출
            "view_count": None,   # 비로그인 상태에서 통상 미노출
        })
        if len(posts) >= lookback:
            break

    return posts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/channels.yaml")
    parser.add_argument("--out", default="data/instagram_raw.json")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    lookback = config["settings"]["instagram_lookback_posts"]

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
        page = context.new_page()

        for org in config["organizations"]:
            name = org["name"]
            url = org["instagram"]["url"]
            print(f"[instagram] {name} 처리 중...")
            try:
                posts = collect_profile_posts(page, url, lookback)
                results[org["slug"]] = {"name": name, "url": url, "posts": posts, "status": "ok"}
                print(f"  -> 게시물 {len(posts)}개 수집 완료")
            except Exception as e:  # noqa: BLE001
                print(f"  [warn] {name} 수집 실패: {e}", file=sys.stderr)
                results[org["slug"]] = {
                    "name": name, "url": url, "posts": [],
                    "status": "failed", "error": str(e),
                }
            time.sleep(2)  # 과도한 연속 요청 방지

        browser.close()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {out_path}")


if __name__ == "__main__":
    main()
