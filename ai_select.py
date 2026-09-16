import json
import os
import requests

INPUT_FILE = "candidates.json"
OUTPUT_FILE = "selected.json"

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY が設定されていません")


# ==========================================
# 候補動画を読み込む
# ==========================================

with open(
    INPUT_FILE,
    "r",
    encoding="utf-8"
) as f:
    videos = json.load(f)


print("================================")
print("AI選定開始")
print("候補動画:", len(videos))
print("================================")


if not videos:
    raise RuntimeError("候補動画が0本です")


# ==========================================
# AIに渡すデータを整理
# ==========================================

video_text = []

for i, video in enumerate(videos, 1):

    video_text.append(
        f"""
候補{i}
タイトル: {video.get("title", "")}
チャンネル: {video.get("channel", "")}
登録者数: {video.get("subscriber_count", 0)}
再生数: {video.get("view_count", 0)}
高評価率: {video.get("like_rate", 0):.2%}
コメント率: {video.get("comment_rate", 0):.2%}
1日あたり再生数: {video.get("views_per_day", 0):.0f}
スコア: {video.get("score", 0)}
説明:
{video.get("description", "")[:1000]}
"""
    )


prompt = """
あなたはYouTube動画を発掘する編集者です。

以下の候補動画から、noteで紹介する価値がある動画を5本選んでください。

単純な再生数ランキングにはしないでください。

以下を総合的に判断してください。

・直近で勢いがあるか
・高評価率が高いか
・コメントが活発か
・チャンネル登録者数に対して再生数が多いか
・小規模チャンネルなのに伸びているか
・視聴者にとって「知りたい」「見たい」と思える内容か
・ためになる内容か
・面白い内容か
・話題性があるか
・noteの記事として紹介しやすいか
・同じような動画ばかりにならないか

ニュースだけに偏らないようにしてください。

また、以下のような動画は基本的に優先度を下げてください。

・単なるライブ配信
・内容がほとんど分からない動画
・同じ内容のまとめ動画
・極端に広告的な動画
・タイトルだけでは価値が判断しにくい動画

重要:
「再生数が少ないからダメ」とは判断しないでください。

登録者数が少ないのに再生数が伸びている動画や、
高評価率が非常に高い動画など、
「これから伸びそう」「知られていないけど面白い」
という動画も積極的に候補にしてください。

出力は必ずJSONだけにしてください。

形式:

{
  "selected": [
    {
      "candidate_number": 1,
      "reason": "選んだ理由を短く"
    }
  ]
}

必ず5本選んでください。

候補動画:
""" + "\n".join(video_text)


# ==========================================
# Gemini API
# ==========================================

url = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-2.5-flash:generateContent"
)

payload = {
    "contents": [
        {
            "parts": [
                {
                    "text": prompt
                }
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0.3,
        "responseMimeType": "application/json"
    }
}

headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": API_KEY
}


print("Geminiに候補を送信中...")


response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=120
)


if response.status_code != 200:

    print(
        "Gemini APIエラー:",
        response.status_code
    )

    print(
        response.text[:3000]
    )

    raise RuntimeError(
        "Gemini APIの呼び出しに失敗しました"
    )


data = response.json()


# ==========================================
# Geminiの回答を取得
# ==========================================

try:

    text = data[
        "candidates"
    ][0][
        "content"
    ][
        "parts"
    ][0][
        "text"
    ]

except Exception:

    print("Geminiの回答を取得できませんでした")
    print(json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ))

    raise


result = json.loads(text)


# ==========================================
# 実際の動画情報を付ける
# ==========================================

selected = []

for item in result.get(
    "selected",
    []
):

    number = item.get(
        "candidate_number"
    )

    if not isinstance(
        number,
        int
    ):
        continue

    if number < 1 or number > len(videos):
        continue

    video = videos[
        number - 1
    ].copy()

    video[
        "ai_reason"
    ] = item.get(
        "reason",
        ""
    )

    selected.append(video)


# ==========================================
# 5本保存
# ==========================================

selected = selected[:5]


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        selected,
        f,
        ensure_ascii=False,
        indent=2
    )


print("")
print("================================")
print("AI選定完了")
print("選ばれた動画:", len(selected))
print("================================")


for i, video in enumerate(
    selected,
    1
):

    print(
        f"{i}. {video.get('title', '')}"
    )

    print(
        f"   理由: {video.get('ai_reason', '')}"
    )
