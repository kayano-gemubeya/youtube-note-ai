import json
import os
import requests

INPUT_FILE = "selected.json"
OUTPUT_FILE = "article.md"

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY が設定されていません")


# ==========================================
# AIが選んだ動画を読み込む
# ==========================================

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    videos = json.load(f)

print("================================")
print("note記事生成開始")
print("対象動画:", len(videos))
print("================================")

if not videos:
    raise RuntimeError("selected.json に動画がありません")


# ==========================================
# 動画情報をAIに渡す
# ==========================================

video_text = []

for i, video in enumerate(videos, 1):

    video_text.append(
        f"""
動画{i}

タイトル:
{video.get("title", "")}

チャンネル:
{video.get("channel", "")}

登録者数:
{video.get("subscriber_count", 0)}

再生数:
{video.get("view_count", 0)}

高評価率:
{video.get("like_rate", 0):.2%}

コメント率:
{video.get("comment_rate", 0):.2%}

1日あたり再生数:
{video.get("views_per_day", 0):.0f}

AI選定理由:
{video.get("ai_reason", "")}

動画説明:
{video.get("description", "")[:1500]}

URL:
{video.get("url", "")}
"""
    )


# ==========================================
# Geminiへの指示
# ==========================================

prompt = """
あなたはYouTube動画を紹介するnote記事の編集者です。

以下のYouTube動画5本をもとに、
読者が「この動画を見てみたい」と思えるような
日本語のnote記事を作成してください。

重要：

・動画の情報を勝手に作らない
・動画を実際に視聴したような表現をしない
・与えられたタイトル、説明、数字、AI選定理由をもとに記事を書く
・誇張しすぎない
・ニュースだけの記事にしない
・5本それぞれを分かりやすく紹介する
・読みやすい日本語にする
・中学生でも読みやすい文章にする
・広告のような文章にしすぎない
・「絶対見るべき」など断定的な表現を多用しない

記事の構成は以下にしてください。

# 今日の注目YouTube 5選

最初に、
「今日はYouTubeで見つけた注目動画を5本紹介します」
という趣旨の短い導入を書いてください。

その後、

## 1. 動画タイトル

チャンネル名、動画の内容、
注目した理由などを分かりやすく紹介してください。

最後に、

▶ 動画を見る：
動画URL

と書いてください。

同じ形式で5本紹介してください。

最後に、

## まとめ

という見出しを作り、
5本を簡単に振り返ってください。

重要：

Markdown形式で出力してください。

コードブロックは使わないでください。

記事本文だけを出力してください。
余計な説明は付けないでください。

以下が今回紹介する動画です。

""" + "\n".join(video_text)


# ==========================================
# Gemini API
# ==========================================

url = "https://generativelanguage.googleapis.com/v1beta/interactions"

payload = {
    "model": "gemini-3.6-flash",
    "input": prompt
}

headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": API_KEY
}

print("Geminiに記事生成を依頼中...")


response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=180
)


# ==========================================
# APIエラー
# ==========================================

if response.status_code != 200:

    print("Gemini APIエラー:", response.status_code)
    print(response.text[:5000])

    raise RuntimeError(
        "Gemini APIの呼び出しに失敗しました"
    )


data = response.json()

print("Gemini APIから正常に回答を受信しました")


# ==========================================
# Geminiのテキスト回答を取得
#
# Interactions APIでは
#
# steps
#   ↓
# model_output
#   ↓
# content
#   ↓
# text
#
# という構造になっている
# ==========================================

steps = data.get("steps", [])

text = None

for step in steps:

    if step.get("type") == "model_output":

        content = step.get("content", [])

        for item in content:

            if item.get("type") == "text":

                text = item.get("text")

                break

        if text:
            break


# ==========================================
# 回答が取得できなかった場合
# ==========================================

if not text:

    print("Geminiから取得したデータ:")

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )
    )

    raise RuntimeError(
        "Geminiのテキスト回答を取得できませんでした"
    )


print("Geminiのテキスト回答を取得しました")


# ==========================================
# 記事を保存
# ==========================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(text.strip())


# ==========================================
# 完了
# ==========================================

print("")
print("================================")
print("note記事生成完了")
print("================================")

print("")
print(text)

print("")
print("article.md を作成しました")
