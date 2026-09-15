import json
from datetime import datetime, timezone

VIDEOS_FILE = "videos.json"
HISTORY_FILE = "featured_history.json"
OUTPUT_FILE = "candidates.json"


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


videos = load_json(VIDEOS_FILE, [])
history = set(load_json(HISTORY_FILE, []))

# 過去にnoteで紹介した動画を除外
videos = [
    video for video in videos
    if video.get("video_id") not in history
]


def safe_int(value):
    try:
        return int(value)
    except:
        return 0


def days_since_upload(upload_date):
    try:
        dt = datetime.strptime(
            upload_date, "%Y%m%d"
        ).replace(tzinfo=timezone.utc)

        seconds = (
            datetime.now(timezone.utc) - dt
        ).total_seconds()

        return max(seconds / 86400, 0.1)

    except:
        return 7


for video in videos:

    views = safe_int(video.get("view_count"))
    likes = safe_int(video.get("like_count"))
    comments = safe_int(video.get("comment_count"))

    days = days_since_upload(
        video.get("upload_date", "")
    )

    # 1日あたりの再生数
    views_per_day = views / days

    # 高評価率
    like_rate = likes / views if views > 0 else 0

    # コメント率
    comment_rate = comments / views if views > 0 else 0

    video["views_per_day"] = views_per_day
    video["like_rate"] = like_rate
    video["comment_rate"] = comment_rate

    # 基本スコア
    score = 0

    # 再生速度
    score += min(views_per_day / 10000, 30)

    # 高評価率
    score += min(like_rate * 1000, 25)

    # コメント率
    score += min(comment_rate * 5000, 15)

    # 再生数
    score += min(views / 100000, 15)

    video["score"] = round(score, 2)


# 総合スコア順
videos.sort(
    key=lambda x: x["score"],
    reverse=True
)

# AIに渡す候補を30本にする
candidates = videos[:30]

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        candidates,
        f,
        ensure_ascii=False,
        indent=2
    )

print("================================")
print("ランキング計算完了")
print("過去紹介済みを除外した動画:", len(videos))
print("AIに渡す候補:", len(candidates))
print("================================")

for i, video in enumerate(candidates[:10], 1):
    print(
        f"{i}. {video['title']} "
        f"| score={video['score']} "
        f"| views={video['view_count']}"
    )
