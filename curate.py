"""
youtube_raw.json / instagram_raw.json을 읽어 조회수/좋아요 기준으로 상위 N개를 큐레이션한다.

사용법:
  python scripts/curate.py --config config/channels.yaml \
      --youtube data/youtube_raw.json --instagram data/instagram_raw.json \
      --out data/curated.json
"""
import argparse
import json
from pathlib import Path

import yaml


def curate_youtube(entry: dict, top_n: int) -> dict:
    videos = entry.get("videos", [])
    ranked = sorted(videos, key=lambda v: v["view_count"], reverse=True)[:top_n]
    return {
        "name": entry["name"],
        "status": "ok" if "error" not in entry else "failed",
        "error": entry.get("error"),
        "top_videos": ranked,
    }


def curate_instagram(entry: dict, top_n: int) -> dict:
    posts = entry.get("posts", [])
    # 좋아요 수가 대부분 None(비로그인 미노출)이므로, 있으면 정렬에 쓰고 없으면 최신순 그대로 사용
    has_likes = any(p.get("like_count") is not None for p in posts)
    if has_likes:
        ranked = sorted(posts, key=lambda p: (p.get("like_count") or 0), reverse=True)[:top_n]
        ranking_note = "좋아요 수 기준 정렬"
    else:
        ranked = posts[:top_n]
        ranking_note = "좋아요 수 미확보 - 최신 게시순"

    return {
        "name": entry["name"],
        "status": entry.get("status", "unknown"),
        "error": entry.get("error"),
        "ranking_note": ranking_note,
        "top_posts": ranked,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/channels.yaml")
    parser.add_argument("--youtube", default="data/youtube_raw.json")
    parser.add_argument("--instagram", default="data/instagram_raw.json")
    parser.add_argument("--out", default="data/curated.json")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    yt_top_n = config["settings"]["youtube_top_n"]
    ig_top_n = config["settings"]["instagram_top_n"]

    youtube_raw = json.loads(Path(args.youtube).read_text(encoding="utf-8"))
    instagram_raw = json.loads(Path(args.instagram).read_text(encoding="utf-8"))

    curated = {"organizations": []}
    for org in config["organizations"]:
        slug = org["slug"]
        yt_entry = youtube_raw.get(slug, {"name": org["name"], "videos": []})
        ig_entry = instagram_raw.get(slug, {"name": org["name"], "posts": []})

        curated["organizations"].append({
            "name": org["name"],
            "youtube": curate_youtube(yt_entry, yt_top_n),
            "instagram": curate_instagram(ig_entry, ig_top_n),
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {out_path}")


if __name__ == "__main__":
    main()
