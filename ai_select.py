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

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    videos = json.load(f)

print("================================")
print("AI選定開始")
print("候補動画:", len(videos))
print("================================")

if not videos:
    raise RuntimeError("候補動画が0本です")


# ==========================================
# AIに渡すデータを作る
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


# ==========================================
# Geminiへの指示
# ==========================================

prompt = """
あなたはYouTube動画を発掘する編集者です。

以下の候補動画30本から、
noteで紹介する価値がある動画を5本選んでください。

単純な再生数ランキングにはしないでください。

以下を総合的に判断してください。

・直近で勢いがあるか
・高評価率が高いか
・コメントが活発か
・登録者数に対して再生数が多いか
・小規模チャンネルなのに伸びているか
・視聴者にとって知りたい内容か
・ためになる内容か
・面白い内容か
・話題性があるか
・noteの記事として紹介しやすいか
・同じジャンルばかりになっていないか

重要なルール：

ニュース動画は最大1本までにしてください。

5本すべてをニュース系にしないでください。

できるだけ、

・科学
・雑学
・テクノロジー
・ゲーム
・教育
・面白い動画
・レビュー
・ドキュメンタリー
・意外な発見
・知られていない面白い動画

など、ジャンルを分散してください。

ただし、ニュース以外に本当に良い動画がない場合は、
無理にジャンルを分散する必要はありません。

また、

「登録者数が少ないのに再生数が多い」
「高評価率が高い」
「投稿直後なのに急速に再生されている」

ような動画を積極的に発掘してください。

再生数が少ないことだけを理由に除外しないでください。

以下のような動画は優先度を下げてください。

・単なるライブ配信
・内容がほとんど分からない動画
・同じ内容のまとめ動画
・広告目的が強い動画

最終的に5本選んでください。

回答はJSONだけにしてください。

Markdownの```は付けないでください。

必ず次の形式で回答してください。

{
  "selected": [
    {
      "candidate_number": 1,
      "reason": "選んだ理由を短く"
    }
  ]
}

候補動画:
""" + "\n".join(video_text)


# ==========================================
# Gemini Interactions API
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

print("Geminiに候補を送信中...")

try:

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120
    )

except requests.RequestException as e:

    print("Gemini API通信エラー:")
    print(e)

    raise RuntimeError(
        "Gemini APIとの通信に失敗しました"
    )


# ==========================================
# APIエラー確認
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
# Geminiの回答テキストを取得
#
# Gemini 3.6 Flash / Interactions API
#
# steps
#   ↓
# model_output
#   ↓
# content
#   ↓
# text
# ==========================================

text = None

steps = data.get("steps", [])

for step in steps:

    if step.get("type") != "model_output":
        continue

    content = step.get("content", [])

    if not isinstance(content, list):
        continue

    for item in content:

        if not isinstance(item, dict):
            continue

        if item.get("type") == "text":

            candidate_text = item.get("text")

            if candidate_text:
                text = candidate_text
                break

    if text:
        break


# ==========================================
# 念のため outputs 形式にも対応
# ==========================================

if not text:

    outputs = data.get("outputs", [])

    if isinstance(outputs, list):

        for output in outputs:

            if not isinstance(output, dict):
                continue

            if output.get("type") != "model_output":
                continue

            content = output.get("content", [])

            if not isinstance(content, list):
                continue

            for item in content:

                if not isinstance(item, dict):
                    continue

                if item.get("type") == "text":

                    candidate_text = item.get("text")

                    if candidate_text:
                        text = candidate_text
                        break

            if text:
                break


# ==========================================
# テキスト取得失敗
# ==========================================

if not text:

    print("")
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
# JSONとして解析
# ==========================================

cleaned_text = text.strip()


# Markdownの```json が付いていた場合
if cleaned_text.startswith("```json"):

    cleaned_text = cleaned_text[7:].strip()

elif cleaned_text.startswith("```"):

    cleaned_text = cleaned_text[3:].strip()


if cleaned_text.endswith("```"):

    cleaned_text = cleaned_text[:-3].strip()


try:

    result = json.loads(cleaned_text)

except json.JSONDecodeError:

    print("")
    print("Geminiの回答:")
    print(cleaned_text)

    raise RuntimeError(
        "Geminiの回答をJSONとして読み取れませんでした"
    )


# ==========================================
# selected確認
# ==========================================

if not isinstance(result, dict):

    raise RuntimeError(
        "Geminiの回答がJSONオブジェクトではありません"
    )


selected_items = result.get("selected", [])


if not isinstance(selected_items, list):

    raise RuntimeError(
        "Geminiの回答に selected がありません"
    )


# ==========================================
# 選ばれた動画を取得
# ==========================================

selected = []

used_numbers = set()

for item in selected_items:

    if not isinstance(item, dict):
        continue

    number = item.get("candidate_number")

    if not isinstance(number, int):
        continue

    if number < 1 or number > len(videos):
        continue

    # 同じ動画が重複した場合は除外
    if number in used_numbers:
        continue

    used_numbers.add(number)

    video = videos[number - 1].copy()

    video["ai_reason"] = item.get(
        "reason",
        ""
    )

    selected.append(video)


# ==========================================
# 最大5本
# ==========================================

selected = selected[:5]


if not selected:

    print("")
    print("Geminiの回答:")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    raise RuntimeError(
        "AIが動画を1本も選択しませんでした"
    )


# ==========================================
# selected.jsonに保存
# ==========================================

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


# ==========================================
# 結果表示
# ==========================================

print("")
print("================================")
print("AI選定完了")
print("選ばれた動画:", len(selected))
print("================================")

for i, video in enumerate(selected, 1):

    print(
        f"{i}. {video.get('title', '')}"
    )

    print(
        f"   チャンネル: {video.get('channel', '')}"
    )

    print(
        f"   理由: {video.get('ai_reason', '')}"
    )

print("")
print("selected.json を作成しました")
