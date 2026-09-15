import json
import subprocess
from datetime import datetime, timedelta, timezone

# ==============================
# 設定
# ==============================

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

# 1キーワードにつき検索する動画数
RESULTS_PER_QUERY = 10


# ==============================
# 日付
# ==============================

now = datetime.now(timezone.utc)
limit_date = now - timedelta(days=DAYS)

print("================================")
print("YouTube動画収集開始")
print("対象期間:", limit_date.strftime("%Y-%m-%d"), "以降")
print("================================")


# ==============================
# 動画検索
# ==============================

videos = {}


for query in QUERIES:

    print("")
    print("--------------------------------")
    print("検索:", query)
    print("--------------------------------")

    search_command = [
        "yt-dlp",
        f"ytsearch{RESULTS_PER_QUERY}:{query}",
        "--flat-playlist",
        "--print",
        "%(id)s\t%(title)s\t%(webpage_url)s",
        "--skip-download",
        "--ignore-errors",
        "--no-warnings",
    ]

    try:

        result = subprocess.run(
            search_command,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.stderr:
            print("検索メッセージ:")
            print(result.stderr[:2000])

        search_results = []

        for line in result.stdout.splitlines():

            parts = line.split("\t")

            if len(parts) < 3:
                continue

            video_id = parts[0]
            title = parts[1]
            url = parts[2]

            if not video_id:
                continue

            search_results.append(
                (video_id, title, url)
            )

        print("検索結果:", len(search_results), "本")


        # ==============================
        # 各動画の詳細情報を取得
        # ==============================

        for video_id, search_title, url in search_results:

            # すでに取得済みならスキップ
            if video_id in videos:
                continue

            print("詳細取得:", search_title[:50])

            detail_command = [
                "yt-dlp",
                url,
                "--skip-download",
                "--no-warnings",
                "--ignore-errors",
                "--print",
                "%(id)s\t%(title)s\t%(channel)s\t%(channel_id)s\t%(upload_date)s\t%(view_count)s\t%(like_count)s\t%(comment_count)s\t%(webpage_url)s",
            ]

            try:

                detail_result = subprocess.run(
                    detail_command,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                for line in detail_result.stdout.splitlines():

                    parts = line.split("\t")

                    if len(parts) < 9:
                        continue

                    (
                        video_id2,
                        title,
                        channel,
                        channel_id,
                        upload_date,
                        view_count,
                        like_count,
                        comment_count,
                        webpage_url
                    ) = parts[:9]

                    # 投稿日が取得できなければスキップ
                    if not upload_date or len(upload_date) != 8:
                        continue

                    try:

                        upload_dt = datetime.strptime(
                            upload_date,
                            "%Y%m%d"
                        ).replace(
                            tzinfo=timezone.utc
                        )

                    except ValueError:

                        continue

                    # 7日より古い動画は除外
                    if upload_dt < limit_date:
                        continue

                    def to_int(value):

                        try:
                            return int(value)

                        except:
                            return 0

                    videos[video_id2] = {
                        "video_id": video_id2,
                        "title": title,
                        "channel": channel,
                        "channel_id": channel_id,
                        "upload_date": upload_date,
                        "view_count": to_int(view_count),
                        "like_count": to_int(like_count),
                        "comment_count": to_int(comment_count),
                        "url": webpage_url,
                    }

                    print(
                        "  → 採用:",
                        title[:60]
                    )

            except subprocess.TimeoutExpired:

                print("  → タイムアウト")

            except Exception as e:

                print(
                    "  → 詳細取得エラー:",
                    e
                )


# ==============================
# 結果整理
# ==============================

output = list(videos.values())

# 再生数順
output.sort(
    key=lambda x: x["view_count"],
    reverse=True
)


# ==============================
# 保存
# ==============================

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


# ==============================
# 結果表示
# ==============================

print("")
print("================================")
print("動画収集完了")
print("取得した動画数:", len(output))
print("================================")

for i, video in enumerate(output[:20], 1):

    print(
        f"{i}. {video['title']} "
        f"| {video['view_count']} views "
        f"| {video['channel']} "
        f"| {video['upload_date']}"
    )
