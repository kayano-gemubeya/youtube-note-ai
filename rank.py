import json
from datetime import datetime, timezone

VIDEOS_FILE = "videos.json"
HISTORY_FILE = "featured_history.json"
OUTPUT_FILE = "candidates.json"


def load_json(filename, default):

    try:

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except FileNotFoundError:

        return default

    except json.JSONDecodeError:

        return default


def safe_int(value):

    try:
        return int(value)

    except (ValueError, TypeError):

        return 0


def days_since_upload(upload_date):

    try:

        # YouTube Data API形式
        # 例: 2026-09-15T03:21:00Z

        if "T" in upload_date:

            dt = datetime.fromisoformat(
                upload_date.replace(
                    "Z",
                    "+00:00"
                )
            )

        # 古い形式にも対応
        else:

            dt = datetime.strptime(
                upload_date,
                "%Y%m%d"
            ).replace(
                tzinfo=timezone.utc
            )

        seconds = (
            datetime.now(timezone.utc) - dt
        ).total_seconds()

        return max(
            seconds / 86400,
            0.1
        )

    except Exception:

        return 7


# ==========================================
# データ読み込み
# ==========================================

videos = load_json(
    VIDEOS_FILE,
    []
)

history = set(
    load_json(
        HISTORY_FILE,
        []
    )
)

print("================================")
print("ランキング計算開始")
print("取得動画:", len(videos))
print("過去紹介済み:", len(history))
print("================================")


# ==========================================
# 過去に紹介した動画を除外
# ==========================================

videos = [
    video
    for video in videos
    if video.get("video_id") not in history
]

print(
    "重複除外後:",
    len(videos)
)


# ==========================================
# スコア計算
# ==========================================

for video in videos:

    views = safe_int(
        video.get(
            "view_count",
            0
        )
    )

    likes = safe_int(
        video.get(
            "like_count",
            0
        )
    )

    comments = safe_int(
        video.get(
            "comment_count",
            0
        )
    )

    subscribers = safe_int(
        video.get(
            "subscriber_count",
            0
        )
    )

    days = days_since_upload(
        video.get(
            "upload_date",
            ""
        )
    )

    # ======================================
    # 各指標
    # ======================================

    # 1日あたり再生数
    views_per_day = (
        views / days
        if days > 0
        else 0
    )

    # 高評価率
    like_rate = (
        likes / views
        if views > 0
        else 0
    )

    # コメント率
    comment_rate = (
        comments / views
        if views > 0
        else 0
    )

    video[
        "views_per_day"
    ] = views_per_day

    video[
        "like_rate"
    ] = like_rate

    video[
        "comment_rate"
    ] = comment_rate


    # ======================================
    # 総合スコア
    # ======================================

    score = 0


    # 急上昇度
    score += min(
        views_per_day / 10000,
        30
    )


    # 高評価率
    score += min(
        like_rate * 1000,
        25
    )


    # コメント率
    score += min(
        comment_rate * 5000,
        15
    )


    # 総再生数
    score += min(
        views / 100000,
        15
    )


    # 小規模チャンネルからの発掘
    # 登録者が少ないチャンネルほど少し加点
    if subscribers > 0:

        views_per_subscriber = (
            views / subscribers
        )

        discovery_score = min(
            views_per_subscriber * 5,
            15
        )

        score += discovery_score


    video[
        "score"
    ] = round(
        score,
        2
    )


# ==========================================
# スコア順
# ==========================================

videos.sort(
    key=lambda x: x.get(
        "score",
        0
    ),
    reverse=True
)


# ==========================================
# AIに渡す候補
# ==========================================

candidates = videos[:30]


# ==========================================
# 保存
# ==========================================

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


# ==========================================
# 結果表示
# ==========================================

print("")
print("================================")
print("ランキング計算完了")
print("重複除外後:", len(videos))
print("AIに渡す候補:", len(candidates))
print("================================")

for i, video in enumerate(
    candidates[:10],
    1
):

    print(
        f"{i}. "
        f"{video.get('title', '')[:50]} "
        f"| score={video.get('score', 0)} "
        f"| views={video.get('view_count', 0):,} "
        f"| likes={video.get('like_count', 0):,} "
        f"| subscribers={video.get('subscriber_count', 0):,}"
    )
