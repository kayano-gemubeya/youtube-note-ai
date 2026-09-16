import json
import os
import re
import requests
from datetime import datetime, timedelta, timezone

# ==========================================
# 設定
# ==========================================

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
RESULTS_PER_QUERY = 25

# ==========================================
# APIキー
# ==========================================

API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "YOUTUBE_API_KEYがGitHub Secretsにありません"
    )

BASE_URL = "https://www.googleapis.com/youtube/v3"

# ==========================================
# 日本語判定
# ==========================================

def has_japanese(text):
    """
    タイトル・説明などに日本語文字が含まれているか確認
    """

    if not text:
        return False

    # ひらがな
    if re.search(r"[\u3040-\u309F]", text):
        return True

    # カタカナ
    if re.search(r"[\u30A0-\u30FF]", text):
        return True

    # 日本語の漢字が含まれる場合
    # 中国語だけの文章をなるべく除外するため、
    # ひらがな・カタカナを優先する
    return False


# ==========================================
# 日付
# ==========================================

now = datetime.now(timezone.utc)

published_after = now - timedelta(days=DAYS)

published_after_text = published_after.strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

print("================================")
print("YouTube Data API 動画収集開始")
print("対象期間:", published_after_text, "以降")
print("================================")


# ==========================================
# 動画保存場所
# ==========================================

videos = {}


# ==========================================
# YouTube検索
# ==========================================

for query in QUERIES:

    print("")
    print("--------------------------------")
    print("検索:", query)
    print("--------------------------------")

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after_text,
        "maxResults": RESULTS_PER_QUERY,
        "regionCode": "JP",
        "relevanceLanguage": "ja",
        "key": API_KEY,
    }

    try:

        response = requests.get(
            f"{BASE_URL}/search",
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        items = data.get("items", [])

        print(
            "検索結果:",
            len(items),
            "本"
        )

        for item in items:

            video_id = item["id"]["videoId"]

            snippet = item["snippet"]

            title = snippet.get(
                "title",
                ""
            )

            description = snippet.get(
                "description",
                ""
            )

            # ==================================
            # 日本語タイトル判定
            # ==================================

            if not has_japanese(title):

                print(
                    "日本語タイトルではないため除外:",
                    title[:60]
                )

                continue

            # ==================================
            # 同じ動画の重複を自動排除
            # ==================================

            videos[video_id] = {

                "video_id": video_id,

                "title": title,

                "channel": snippet.get(
                    "channelTitle",
                    ""
                ),

                "channel_id": snippet.get(
                    "channelId",
                    ""
                ),

                "upload_date": snippet.get(
                    "publishedAt",
                    ""
                ),

                "description": description,

                "language": "ja",

                "url": (
                    "https://www.youtube.com/watch?v="
                    + video_id
                ),
            }

    except Exception as e:

        print(
            "検索エラー:",
            e
        )


# ==========================================
# 動画詳細情報
# ==========================================

print("")
print("================================")
print("動画詳細情報を取得中")
print("動画数:", len(videos))
print("================================")

video_ids = list(videos.keys())


for start in range(
    0,
    len(video_ids),
    50
):

    batch = video_ids[
        start:start + 50
    ]

    params = {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(batch),
        "key": API_KEY,
    }

    try:

        response = requests.get(
            f"{BASE_URL}/videos",
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        for item in data.get(
            "items",
            []
        ):

            video_id = item["id"]

            if video_id not in videos:
                continue

            statistics = item.get(
                "statistics",
                {}
            )

            snippet = item.get(
                "snippet",
                {}
            )

            # ==================================
            # YouTube側の言語情報
            # ==================================

            default_language = snippet.get(
                "defaultLanguage",
                ""
            )

            default_audio_language = snippet.get(
                "defaultAudioLanguage",
                ""
            )

            videos[video_id][
                "default_language"
            ] = default_language

            videos[video_id][
                "default_audio_language"
            ] = default_audio_language

            # ==================================
            # 音声言語が明確に日本語以外なら除外
            # ==================================

            if default_audio_language:

                if not default_audio_language.lower().startswith("ja"):

                    print(
                        "日本語音声ではないため除外:",
                        videos[video_id]["title"],
                        "| 音声言語:",
                        default_audio_language
                    )

                    del videos[video_id]

                    continue

            # ==================================
            # 再生数など
            # ==================================

            videos[video_id][
                "view_count"
            ] = int(
                statistics.get(
                    "viewCount",
                    0
                )
            )

            videos[video_id][
                "like_count"
            ] = int(
                statistics.get(
                    "likeCount",
                    0
                )
            )

            videos[video_id][
                "comment_count"
            ] = int(
                statistics.get(
                    "commentCount",
                    0
                )
            )

            videos[video_id][
                "duration"
            ] = item.get(
                "contentDetails",
                {}
            ).get(
                "duration",
                ""
            )

            videos[video_id][
                "category_id"
            ] = snippet.get(
                "categoryId",
                ""
            )

    except Exception as e:

        print(
            "動画詳細取得エラー:",
            e
        )


# ==========================================
# チャンネル情報
# ==========================================

print("")
print("================================")
print("チャンネル情報を取得中")
print("================================")

channel_ids = list(
    set(
        video["channel_id"]
        for video in videos.values()
        if video.get("channel_id")
    )
)

channel_subscribers = {}


for start in range(
    0,
    len(channel_ids),
    50
):

    batch = channel_ids[
        start:start + 50
    ]

    params = {
        "part": "statistics",
        "id": ",".join(batch),
        "key": API_KEY,
    }

    try:

        response = requests.get(
            f"{BASE_URL}/channels",
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        for item in data.get(
            "items",
            []
        ):

            statistics = item.get(
                "statistics",
                {}
            )

            subscriber_count = statistics.get(
                "subscriberCount"
            )

            if subscriber_count is not None:

                channel_subscribers[
                    item["id"]
                ] = int(
                    subscriber_count
                )

    except Exception as e:

        print(
            "チャンネル情報取得エラー:",
            e
        )


# ==========================================
# データ計算
# ==========================================

output = []


for video in videos.values():

    if "view_count" not in video:
        continue

    subscribers = channel_subscribers.get(
        video["channel_id"],
        0
    )

    video[
        "subscriber_count"
    ] = subscribers

    views = video[
        "view_count"
    ]

    likes = video[
        "like_count"
    ]

    comments = video[
        "comment_count"
    ]

    # ==================================
    # 高評価率・コメント率
    # ==================================

    if views > 0:

        video[
            "like_rate"
        ] = likes / views

        video[
            "comment_rate"
        ] = comments / views

    else:

        video[
            "like_rate"
        ] = 0

        video[
            "comment_rate"
        ] = 0


    # ==================================
    # 投稿からの経過時間
    # ==================================

    try:

        upload_dt = datetime.fromisoformat(
            video[
                "upload_date"
            ].replace(
                "Z",
                "+00:00"
            )
        )

        hours = max(
            (
                now - upload_dt
            ).total_seconds() / 3600,
            0.1
        )

        video[
            "hours_since_upload"
        ] = hours

        video[
            "views_per_hour"
        ] = views / hours

    except Exception:

        video[
            "hours_since_upload"
        ] = 999

        video[
            "views_per_hour"
        ] = 0


    output.append(video)


# ==========================================
# 最終重複チェック
# ==========================================

unique_videos = {}

for video in output:

    video_id = video.get(
        "video_id"
    )

    if not video_id:
        continue

    unique_videos[
        video_id
    ] = video


output = list(
    unique_videos.values()
)


# ==========================================
# ランキング
# ==========================================

output.sort(
    key=lambda x: x[
        "views_per_hour"
    ],
    reverse=True
)


# ==========================================
# JSON保存
# ==========================================

with open(
    "videos.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2
    )


# ==========================================
# 結果表示
# ==========================================

print("")
print("================================")
print("動画収集完了")
print("取得した動画数:", len(output))
print("================================")

for i, video in enumerate(
    output[:20],
    1
):

    print(
        f"{i}. "
        f"{video['title'][:50]} "
        f"| 再生 "
        f"{video['view_count']:,} "
        f"| 高評価率 "
        f"{video['like_rate']:.2%} "
        f"| 1時間再生 "
        f"{video['views_per_hour']:,.0f} "
        f"| 登録者 "
        f"{video['subscriber_count']:,} "
        f"| 音声言語 "
        f"{video.get('default_audio_language', '不明')}"
    )
