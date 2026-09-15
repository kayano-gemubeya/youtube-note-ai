import json
import subprocess
from datetime import datetime, timedelta, timezone

# 検索するキーワード
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

# 直近何日間の動画を対象にするか
DAYS = 7

# 1キーワードあたりの検索数
RESULTS_PER_QUERY = 20

# 現在時刻
now = datetime.now(timezone.utc)

# 7日前
limit_date = now - timedelta(days=DAYS)

# 動画を保存する辞書
videos = {}

for query in QUERIES:

    print("")
    print("================================")
    print("検索:", query)
    print("================================")

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

        # エラー内容をログに表示
        if result.stderr:
            print("===== yt-dlp メッセージ =====")
            print(result.stderr)
            print("=============================")

        # 検索結果を処理
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

            # 投稿日がない場合はスキップ
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

            # 数値に変換
            def to_int(value):

                try:
                    return int(value)

                except:
                    return 0

            video = {
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

            # 同じ動画は1回だけ保存
            videos[video_id] = video

    except subprocess.TimeoutExpired:

        print("検索がタイムアウトしました:", query)

    except Exception as e:

        print("エラーが発生しました:", e)


# リストに変換
output = list(videos.values())

# 再生数の多い順
output.sort(
    key=lambda x: x["view_count"],
    reverse=True
)

# JSONとして保存
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


print("")
print("================================")
print("動画収集完了")
print("取得した動画数:", len(output))
print("================================")

# 上位10本を表示
for i, video in enumerate(output[:10], 1):

    print(
        f"{i}. {video['title']} "
        f"| {video['view_count']} views "
        f"| {video['channel']}"
    )
