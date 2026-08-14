"""
YouTube Data API v3를 이용해 설정된 채널들의 최신 영상과 통계(조회수/좋아요/댓글수)를 수집한다.

필요 환경변수:
  YOUTUBE_API_KEY

사용법:
  python scripts/collect_youtube.py --config config/channels.yaml --out data/youtube_raw.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from googleapiclient.discovery import build


def resolve_channel_id(youtube, resolve_by: str, value: str) -> str | None:
    """channel_id / username / search 세 가지 방식으로 채널 ID를 알아낸다."""
    if resolve_by == "channel_id":
        return value

    if resolve_by == "username":
        resp = youtube.channels().list(part="id", forUsername=value).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"]
        # 레거시 username이 아닐 수 있으니 search로 폴백
        print(f"  [warn] forUsername 실패: '{value}' -> search로 재시도", file=sys.stderr)
        return resolve_channel_id(youtube, "search", value)

    if resolve_by == "search":
        resp = youtube.search().list(
            part="snippet", q=value, type="channel", maxResults=1
        ).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
        return None

    raise ValueError(f"알 수 없는 resolve_by: {resolve_by}")


def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_recent_video_ids(youtube, uploads_playlist_id: str, n: int) -> list[str]:
    resp = youtube.playlistItems().list(
        part="contentDetails", playlistId=uploads_playlist_id, maxResults=n
    ).execute()
    return [item["contentDetails"]["videoId"] for item in resp.get("items", [])]


def get_video_stats(youtube, video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    resp = youtube.videos().list(
        part="snippet,statistics", id=",".join(video_ids)
    ).execute()
    out = []
    for item in resp.get("items", []):
        stats = item.get("statistics", {})
        out.append({
            "video_id": item["id"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
            "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url"),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/channels.yaml")
    parser.add_argument("--out", default="data/youtube_raw.json")
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    lookback = config["settings"]["youtube_lookback_videos"]

    youtube = build("youtube", "v3", developerKey=api_key)

    results = {}
    for org in config["organizations"]:
        name = org["name"]
        yt_cfg = org["youtube"]
        print(f"[youtube] {name} 처리 중 (resolve_by={yt_cfg['resolve_by']})...")
        try:
            channel_id = resolve_channel_id(youtube, yt_cfg["resolve_by"], yt_cfg["value"])
            if not channel_id:
                print(f"  [error] 채널을 찾을 수 없음: {yt_cfg['value']}", file=sys.stderr)
                results[org["slug"]] = {"name": name, "error": "channel_not_found", "videos": []}
                continue

            uploads_playlist_id = get_uploads_playlist_id(youtube, channel_id)
            video_ids = get_recent_video_ids(youtube, uploads_playlist_id, lookback)
            videos = get_video_stats(youtube, video_ids)

            results[org["slug"]] = {
                "name": name,
                "channel_id": channel_id,
                "videos": videos,
            }
            print(f"  -> 영상 {len(videos)}개 수집 완료")
        except Exception as e:  # noqa: BLE001
            print(f"  [error] {name}: {e}", file=sys.stderr)
            results[org["slug"]] = {"name": name, "error": str(e), "videos": []}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {out_path}")


if __name__ == "__main__":
    main()
