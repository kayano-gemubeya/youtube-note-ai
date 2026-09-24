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
あなたはYouTube動画を発掘する編集者です。

以下の候補動画から、
「本当に視聴者に紹介する価値がある動画」だけを選んでください。

単純な再生数ランキングではありません。

最も重要なのは、

「この動画をnoteで紹介されたら、読者が実際に見てみたいと思えるか」

です。

========================================
【最重要ルール】
========================================

1. 60秒未満の動画は絶対に選ばない。

2. Shorts形式と思われる動画も選ばない。

3. 5本を無理に選ばない。

   良い動画が5本存在しない場合は、
   3本や4本など、質の高い動画だけを選んでください。

   「5本にするためだけの選出」は禁止です。

4. 動画を実際に視聴したとは考えないでください。

   与えられたタイトル、説明、再生数、
   高評価率、コメント率、登録者数、
   再生速度などから判断してください。

5. 情報が確認できない内容を推測しないでください。

6. 動画説明に書かれていない内容を
   「動画内で説明している」と断定しないでください。

========================================
【評価するポイント】
========================================

以下を総合的に評価してください。

・動画そのものの内容に価値があるか
・視聴者が知りたいと思えるテーマか
・学びや発見があるか
・面白さがありそうか
・話題性があるか
・タイトルに興味を引く要素があるか
・説明文から内容が具体的に分かるか
・再生数が投稿期間に対して伸びているか
・登録者数に対して再生数が多いか
・高評価率が高いか
・コメントが活発か
・小規模チャンネルでも伸びているか
・note記事として紹介しやすいか

ただし、

「再生数が多い」
だけでは高評価にしないでください。

逆に、

「再生数が少ない」
だけで除外もしないでください。

========================================
【避ける動画】
========================================

以下は基本的に選ばないでください。

・60秒未満
・Shorts
・ほぼ内容が分からない動画
・単純な切り抜き
・単純な転載
・同じ内容のまとめ
・広告や宣伝が中心
・商品を買わせることが主目的に見える動画
・単なる日常記録で紹介する理由が弱い動画
・内容が薄い動画
・タイトルだけが大げさな動画
・ライブ配信そのもの
・視聴者にとって紹介するメリットが弱い動画

========================================
【ジャンル】
========================================

ニュースだけに偏らないでください。

候補の中に本当に良い動画があれば、

・科学
・雑学
・テクノロジー
・ゲーム
・教育
・レビュー
・ドキュメンタリー
・料理
・歴史
・文化
・身近な疑問
・意外な発見
・面白い知識
・便利な情報

などをバランスよく選んでください。

ただし、

「ジャンルを分散させるために質の低い動画を選ぶ」

ことは禁止です。

ニュース動画は最大1本まで。

同じチャンネルから複数選ばないでください。

========================================
【特に重視する動画】
========================================

以下のような動画は積極的に評価してください。

・登録者数に対して再生数が非常に多い
・投稿から短期間で再生数が伸びている
・高評価率が高い
・コメント率が高い
・小規模チャンネルなのに大きく伸びている
・知らなかったことを知れる
・タイトルだけで内容に興味を持てる
・説明文から内容が具体的に分かる
・noteで紹介することで読者に新しい発見を与えられる

========================================
【選定の考え方】
========================================

各動画について、

「数字は良いが、内容を紹介する価値が低い」

動画と、

「数字はそこまで大きくないが、内容が非常に興味深い」

動画を区別してください。

数字だけで判断しないでください。

最終的には、

「この動画を今日のおすすめとして読者に紹介しても恥ずかしくないか」

という基準で判断してください。

========================================
【選定数】
========================================

5本です。

5本絶対に選別してください。

紹介する価値が十分にある動画だけを選んでください。

目安として、

非常に良い → 選ぶ
良い → 選ぶ
普通 → 原則選ばない
微妙 → 選ばない
情報不足 → 選ばない

としてください。

========================================
【理由】
========================================

選んだ理由は、

「再生数が多いから」

だけにしないでください。

動画の内容と数字の両方を考慮し、

なぜ読者に紹介する価値があるのかを
具体的に短く説明してください。

どちらかというと内容を重視してください。
再生回数が一桁でも、二桁でも。

ただし、動画を実際に視聴したような表現は禁止です。

========================================
【出力】
========================================

JSONだけを出力してください。

Markdownの```は使用しないでください。

必ず以下の形式にしてください。

{
  "selected": [
    {
      "candidate_number": 1,
      "reason": "選んだ理由"
    }
  ]
}

候補動画:
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
