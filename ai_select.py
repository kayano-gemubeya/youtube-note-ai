import json
import os
import re
import requests

INPUT_FILE = "candidates.json"
OUTPUT_FILE = "selected.json"

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY が設定されていません")


# ==========================================
# 動画の長さを秒に変換
# YouTube APIの ISO 8601形式
#
# 例:
# PT13S      → 13秒
# PT59S      → 59秒
# PT1M       → 60秒
# PT5M30S    → 330秒
# PT1H10M    → 4200秒
# ==========================================

def duration_to_seconds(duration):

    if not duration:
        return 0

    match = re.match(
        r"^PT"
        r"(?:(\d+)H)?"
        r"(?:(\d+)M)?"
        r"(?:(\d+)S)?$",
        duration
    )

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


# ==========================================
# 動画を読み込む
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

    raise RuntimeError(
        "candidates.json に動画がありません"
    )


# ==========================================
# ① 60秒未満の動画を除外
# ==========================================

filtered_videos = []

short_count = 0
duplicate_count = 0

seen_video_ids = set()


for video in videos:

    video_id = video.get(
        "video_id",
        ""
    )

    # --------------------------------------
    # 重複チェック
    # --------------------------------------

    if video_id:

        if video_id in seen_video_ids:

            duplicate_count += 1
            continue

        seen_video_ids.add(video_id)


    # --------------------------------------
    # 動画時間
    # --------------------------------------

    duration = video.get(
        "duration",
        ""
    )

    duration_seconds = duration_to_seconds(
        duration
    )

    video[
        "duration_seconds"
    ] = duration_seconds


    # --------------------------------------
    # 60秒未満なら除外
    # --------------------------------------

    if duration_seconds < 60:

        short_count += 1

        print(
            "60秒未満のため除外:",
            video.get("title", "")[:80],
            f"({duration_seconds}秒)"
        )

        continue


    filtered_videos.append(video)


print("")
print("================================")
print("事前フィルタリング完了")
print("重複除外:", duplicate_count)
print("60秒未満除外:", short_count)
print("AI審査対象:", len(filtered_videos))
print("================================")


if not filtered_videos:

    raise RuntimeError(
        "60秒以上の候補動画がありません"
    )


# ==========================================
# AIに渡すデータ
# ==========================================

video_text = []


for i, video in enumerate(
    filtered_videos,
    1
):

    duration_seconds = video.get(
        "duration_seconds",
        0
    )

    video_text.append(
        f"""
候補{i}

タイトル:
{video.get("title", "")}

チャンネル:
{video.get("channel", "")}

動画時間:
{duration_seconds}秒

登録者数:
{video.get("subscriber_count", 0)}

再生数:
{video.get("view_count", 0)}

高評価率:
{video.get("like_rate", 0):.2%}

コメント率:
{video.get("comment_rate", 0):.2%}

1時間あたり再生数:
{video.get("views_per_hour", 0):.0f}

投稿からの経過時間:
{video.get("hours_since_upload", 0):.1f}時間

AI選定用スコア:
{video.get("score", 0)}

動画説明:
{video.get("description", "")[:2000]}

音声言語:
{video.get("default_audio_language", "")}

動画URL:
{video.get("url", "")}
"""
    )


# ==========================================
# Geminiへの指示
# ==========================================

prompt = """
あなたは「YouTubeの面白くて価値のある動画を発掘する編集者」です。

あなたの仕事は、
再生数ランキングを作ることではありません。

読者に本当に紹介する価値がある動画を、
候補の中から厳しく審査して選ぶことです。

今回の候補動画は、
すでに60秒以上の動画だけに絞っています。

ただし、
60秒以上だから良い動画とは限りません。

タイトルや説明だけを見て、
「面白そうだから」という理由だけで選ばないでください。

与えられた情報から、
その動画が実際に読者に紹介する価値があるかを慎重に判断してください。


========================================
最重要ルール
========================================

「再生数が多い = 良い動画」
ではありません。

「再生数が少ない = 悪い動画」
でもありません。

特に、

・小規模チャンネルなのに伸びている
・投稿してから短期間なのに反応が強い
・タイトルだけでは目立たないが内容に価値がありそう
・知られていない面白いテーマ
・専門的だが分かりやすそう
・視聴者が新しい発見を得られそう

な動画は積極的に評価してください。

一方、

・数字だけが強い
・内容が薄そう
・単なる釣りタイトル
・ニュースを読み上げるだけ
・他の動画の内容をまとめただけ
・広告や宣伝が中心
・ライブ配信そのもの
・何を扱っているのか説明からほとんど分からない
・短時間で中身が薄そう
・似たような動画が大量にある

ものは評価を下げてください。


========================================
評価基準
========================================

各候補について、頭の中で以下を評価してください。

【1 内容の価値】
視聴者が見たあとに、
新しい知識、発見、楽しさなどを得られそうか。

【2 面白さ】
テーマそのものに興味を持てるか。
「ちょっと見てみたい」と思える内容か。

【3 独自性】
他の動画でも簡単に見られるような内容ではなく、
その動画ならではの魅力がありそうか。

【4 情報量・内容の充実度】
タイトルや説明から、
しっかりした内容が含まれていると判断できるか。

【5 話題性】
現在見る意味があるか。
ただしニュース性だけを過大評価しないこと。

【6 視聴者への実用性】
知識、レビュー、解説など、
視聴者の役に立つ要素があるか。

【7 noteで紹介する価値】
記事で紹介したときに、
読者が「この動画ちょっと見てみよう」と思えるか。

【8 チャンネル規模に対する伸び】
登録者数と比較して再生数や反応が強いか。

ただし、
数字は「内容の良さ」より下位の判断材料です。


========================================
特に重要
========================================

以下のような動画は、
数字が良くても慎重にしてください。

・10～数分程度でも内容が極端に薄そうな動画
・タイトルだけが大げさな動画
・単なるニュース読み上げ
・単なる切り抜き
・単なるランキング
・単なるまとめ
・広告色が強い商品紹介
・同じ内容を大量投稿しているような動画
・説明文から内容がほとんど分からない動画

「再生数が伸びている」という理由だけでは、
選出しないでください。


========================================
ニュースについて
========================================

ニュース・時事系は最大1本まで。

ニュースが5本あっても、
最大1本しか選ばないでください。

ニュース以外に価値のある動画を優先してください。


========================================
ジャンルについて
========================================

可能なら、

・科学
・雑学
・テクノロジー
・ゲーム
・教育
・レビュー
・ドキュメンタリー
・歴史
・意外な発見
・実用情報
・エンタメ

などからバランスよく選んでください。

ただし、
「ジャンルを分散するためだけに微妙な動画を選ぶ」
ことは禁止です。

良い動画が少ない場合は、
5本未満でも構いません。


========================================
重要な判断
========================================

「この動画、本当に読者に紹介したいか？」

という視点で最終判断してください。

微妙な動画しかない場合、
無理に5本選ばないでください。

特に、
「5本埋めるためだけの選出」は禁止です。


========================================
最終選出
========================================

候補をすべて比較したうえで、
本当に価値がある動画を最大5本選んでください。

目安として、
「noteの記事で紹介しても読者に納得してもらえそう」
な動画を選んでください。


========================================
出力形式
========================================

JSONだけを出力してください。

Markdownの```は絶対に付けないでください。

以下の形式です。

{
  "selected": [
    {
      "candidate_number": 1,
      "reason": "この動画を選んだ具体的な理由"
    }
  ]
}

candidate_numberは、
必ず候補番号をそのまま使用してください。

同じ候補を2回選ばないでください。

最大5本です。

候補:
""" + "\n".join(video_text)


# ==========================================
# Gemini API
# ==========================================

url = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/interactions"
)

payload = {
    "model": "gemini-3.6-flash",
    "input": prompt
}

headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": API_KEY
}


print("")
print("Geminiに候補を送信中...")


try:

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=180
    )

except requests.RequestException as e:

    print("Gemini API通信エラー:")
    print(e)

    raise RuntimeError(
        "Gemini APIとの通信に失敗しました"
    )


# ==========================================
# APIエラー
# ==========================================

if response.status_code != 200:

    print(
        "Gemini APIエラー:",
        response.status_code
    )

    print(
        response.text[:5000]
    )

    raise RuntimeError(
        "Gemini APIの呼び出しに失敗しました"
    )


data = response.json()

print(
    "Gemini APIから正常に回答を受信しました"
)


# ==========================================
# Gemini回答を取得
# ==========================================

text = None


# ------------------------------------------
# Interactions APIのsteps
# ------------------------------------------

steps = data.get(
    "steps",
    []
)


for step in steps:

    if not isinstance(step, dict):
        continue

    if step.get("type") != "model_output":
        continue

    content = step.get(
        "content",
        []
    )

    if not isinstance(content, list):
        continue

    for item in content:

        if not isinstance(item, dict):
            continue

        if item.get("type") != "text":
            continue

        candidate_text = item.get(
            "text"
        )

        if candidate_text:

            text = candidate_text
            break

    if text:
        break


# ------------------------------------------
# outputs形式にも対応
# ------------------------------------------

if not text:

    outputs = data.get(
        "outputs",
        []
    )

    if isinstance(outputs, list):

        for output in outputs:

            if not isinstance(
                output,
                dict
            ):
                continue

            if output.get(
                "type"
            ) != "model_output":
                continue

            content = output.get(
                "content",
                []
            )

            if not isinstance(
                content,
                list
            ):
                continue

            for item in content:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                if item.get(
                    "type"
                ) != "text":
                    continue

                candidate_text = item.get(
                    "text"
                )

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
    print(
        "Geminiから取得したデータ:"
    )

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


print(
    "Geminiのテキスト回答を取得しました"
)


# ==========================================
# JSON解析
# ==========================================

cleaned_text = text.strip()


# Markdownコードブロック除去

if cleaned_text.startswith(
    "```json"
):

    cleaned_text = cleaned_text[
        7:
    ].strip()

elif cleaned_text.startswith(
    "```"
):

    cleaned_text = cleaned_text[
        3:
    ].strip()


if cleaned_text.endswith(
    "```"
):

    cleaned_text = cleaned_text[
        :-3
    ].strip()


try:

    result = json.loads(
        cleaned_text
    )

except json.JSONDecodeError:

    print("")
    print(
        "Geminiの回答:"
    )

    print(
        cleaned_text
    )

    raise RuntimeError(
        "Geminiの回答をJSONとして読み取れませんでした"
    )


# ==========================================
# selected確認
# ==========================================

if not isinstance(
    result,
    dict
):

    raise RuntimeError(
        "Geminiの回答がJSONオブジェクトではありません"
    )


selected_items = result.get(
    "selected",
    []
)


if not isinstance(
    selected_items,
    list
):

    raise RuntimeError(
        "Geminiの回答にselectedがありません"
    )


# ==========================================
# 選択された動画を取得
# ==========================================

selected = []

used_numbers = set()


for item in selected_items:

    if not isinstance(
        item,
        dict
    ):
        continue

    number = item.get(
        "candidate_number"
    )

    if not isinstance(
        number,
        int
    ):
        continue

    if (
        number < 1
        or number > len(filtered_videos)
    ):
        continue

    # 重複防止

    if number in used_numbers:
        continue

    used_numbers.add(
        number
    )

    video = filtered_videos[
        number - 1
    ].copy()

    video[
        "ai_reason"
    ] = item.get(
        "reason",
        ""
    )

    selected.append(
        video
    )


# ==========================================
# 最大5本
# ==========================================

selected = selected[:5]


# ==========================================
# 選出0本
# ==========================================

if not selected:

    print("")
    print(
        "Geminiの回答:"
    )

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
# 最終安全チェック
# ==========================================

final_selected = []

final_ids = set()


for video in selected:

    video_id = video.get(
        "video_id"
    )

    if video_id in final_ids:
        continue

    duration_seconds = video.get(
        "duration_seconds",
        0
    )

    # 万一AIが60秒未満を選んでも除外

    if duration_seconds < 60:
        continue

    final_ids.add(
        video_id
    )

    final_selected.append(
        video
    )


selected = final_selected[:5]


if not selected:

    raise RuntimeError(
        "最終チェック後に選択動画が0本になりました"
    )


# ==========================================
# selected.json保存
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
print("================================")

print(
    "AI審査対象:",
    len(filtered_videos)
)

print(
    "最終選出:",
    len(selected)
)

print("")


for i, video in enumerate(
    selected,
    1
):

    print(
        f"{i}. "
        f"{video.get('title', '')}"
    )

    print(
        f"   チャンネル: "
        f"{video.get('channel', '')}"
    )

    print(
        f"   動画時間: "
        f"{video.get('duration_seconds', 0)}秒"
    )

    print(
        f"   理由: "
        f"{video.get('ai_reason', '')}"
    )

    print("")


print(
    "selected.json を作成しました"
)
