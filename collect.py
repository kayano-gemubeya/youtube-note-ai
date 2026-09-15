import json
import subprocess
from datetime import datetime, timedelta, timezone

# 検索するジャンル・キーワード
QUERIES = [
    "ニュース",
    "科学",
    "雑学",
    "テクノロジー",
    "ゲーム",
    "解説",
    "教育",
    "面白い",
    "レビュー",
    "ドキュメンタリー",
]

DAYS = 7
RESULTS_PER_QUERY = 20

now = datetime.now(timezone.utc)
limit_date = now - timedelta(days=DAYS)

videos = {}

for query in QUERIES:
    print(f"検索中: {query}")

    command = [
        "yt-dlp",
        f"ytsearchdate{RESULTS_PER_QUERY}:{query}",
        "--flat-playlist",
        "--print",
        "%(id)s\t%(title)s\t%(channel)s\t%(channel_id)s\t%(upload_date)s\t%(view_count)s\t%(like_count)s\t%(comment_count)s\t%(webpage_url)s",
        "--skip-download",
        "--ignore-errors",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120
        )
        print("===== yt-dlp 標準エラー =====")
print(result.stderr)
print("==============================")

        for line in result.stdout.splitlines():
            parts = line.split("\t")

            if len(parts) < 9:
                continue

            (
                video_id,
                title,
                channel,
                channel_id,
                upload_date,
                view_count,
                like_count,
                comment_count,
                url
            ) = parts[:9]

            if not upload_date or len(upload_date) != 8:
                continue

            try:
                upload_dt = datetime.strptime(
                    upload_date, "%Y%m%d"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if upload_dt < limit_date:
                continue

            def to_int(value):
                try:
                    return int(value)
                except:
                    return 0

            videos[video_id] = {
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "channel_id": channel_id,
                "upload_date": upload_date,
                "view_count": to_int(view_count),
                "like_count": to_int(like_count),
                "comment_count": to_int(comment_count),
                "url": url,
            }

    except Exception as e:
        print(f"エラー: {e}")

output = list(videos.values())

# 再生数の多い順
output.sort(
    key=lambda x: x["view_count"],
    reverse=True
)

with open("videos.json", "w", encoding="utf-8") as f:
    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2
    )

print(f"\n取得した動画数: {len(output)}")
print("videos.json を作成しました。")
