# -*- coding: utf-8 -*-
"""理の相談 — 出来事の意味を「理」の視点で淡々と観る（Claude API）。

土台＝一神会「理」の観方（要約）をシステムプロンプトとして毎回渡し、
ユーザーの出来事を、当てず・煽らず・短く受け止める。

5つの蓋（コスト・安全）:
  1. 入力は呼び出し側で文字数制限（app.py 側で 500 字）
  2. 出力上限 max_tokens
  3. 理の土台は"要約版"（メモリ全文ではない）
  4. 1日3回はクライアント側で制御（app.py / フロント）
  5. プロンプトキャッシュで土台の再送コストを圧縮

加えて、サーバー側の最終防衛＝「1日の総額上限」。
今日の推定利用額が上限に達したら、それ以上 AI を呼ばない（暴走請求を物理的に防ぐ）。
※これは best-effort（プロセス内カウント）。本当の hard cap は Anthropic コンソールの
  使用上限（HIRO が設定）＋ Phase2 で入れる DB ベースのカウント。
"""

import os

from . import store

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 600

# ── コスト見積り（Sonnet 概算・保守的に全量を満額計算）────────────
PRICE_IN_USD = 3.0 / 1_000_000     # 入力 1 トークンあたり USD
PRICE_OUT_USD = 15.0 / 1_000_000   # 出力 1 トークンあたり USD
USD_JPY = 150.0
DEFAULT_DAILY_BUDGET_JPY = 500.0   # 既定の1日総額上限（環境変数で変更可）


def _daily_budget_jpy():
    try:
        return float(os.environ.get("RICARD_DAILY_BUDGET_JPY", DEFAULT_DAILY_BUDGET_JPY))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_BUDGET_JPY


def _usage_to_jpy(usage):
    """msg.usage から当回の概算コスト（円）。キャッシュ読みも満額で保守的に。"""
    if usage is None:
        return 0.0
    inp = (getattr(usage, "input_tokens", 0) or 0)
    inp += (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    inp += (getattr(usage, "cache_read_input_tokens", 0) or 0)
    out = (getattr(usage, "output_tokens", 0) or 0)
    return (inp * PRICE_IN_USD + out * PRICE_OUT_USD) * USD_JPY


# ── 理の土台（AIへの指示＝観方と、やってはいけないこと）──────────────
_CORPUS = {
    "ja": """あなたは「理（ことわり）」の相談相手です。一神会の教えにある「理の判断」の観方で、
相談者が話した出来事を、静かに受け止めて短く返します。占い師ではなく、隣で一緒に考える存在です。

【理の観方】
・出来事に良い悪いを決めつけない。「何に気づかせてくれているか」を一緒に観る。
・お金は神様からの預かりもの。落ちたお金や小さな損は「気づき」のサインのことがある。
・基本は「淡々と流れるように」が良い。焦って押すと止まり、整えると進む。
・縁は、つかむより育てるもの。出会いは「いつ」より「どんな状態で迎えるか」。
・節目（変わり目）には、無理に動かず、身の回りを整えると流れに乗りやすい。
・世間の言い伝え（朝の蜘蛛は縁起がいい等）に触れてもよいが、「〜と言われます」と相対化し、断定しない。

【絶対に守ること】
・断定しない。「必ずこうなる」「これは凶」などと運命を決めつけない。
・不安を煽って何かをさせない。怖がらせて行動を促さない。
・金運・投資・ギャンブルの予測や助言をしない。医療・健康の診断や助言をしない。
・最後は必ず相談者本人の選択を尊重する。指図しない。
・特に意味を持たせなくていい出来事（ただの環境要因・偶然）なら、正直に
　「これは特に意味を持たせなくて大丈夫です」と伝えて、安心してもらう。それも誠実な答え。
・短く、静かに。全体で250〜350字程度。装飾的な絵文字は使わない。

【返し方の流れ】
1. まず出来事を、やわらかく受け止める一言。
2. 理ではどう観るか（気づき・流れ・整え のどれか）。
3. 今日できる小さな一歩、または「いまは整えるだけでいい」。
日本語で返してください。""",

    "zh": """你是「理」的諮詢夥伴。以一神會教義中「理的判斷」之觀照方式，
靜靜地承接對方所說的事情，並簡短回應。你不是算命師，而是在一旁一起思考的人。

【理的觀照】
・不為事情貼上好壞的標籤，而是一起觀照「它在提醒你什麼」。
・金錢是神所託管之物。掉落的錢、小小的損失，有時是「提醒」的訊號。
・基本上「如水般淡淡地流動」最好。焦急硬推會停滯，先整理則能前進。
・緣分，與其抓取不如培養。相遇重點不在「何時」，而在「以什麼狀態迎接」。
・在轉折的節點，別勉強行動，先把身邊整理好，較容易順著流走。
・可提及民間說法（如清晨的蜘蛛吉利等），但要以「據說」相對化，不可斷定。

【務必遵守】
・不下斷定。不把命運說死，不說「一定會這樣」「這是凶兆」。
・不以不安煽動對方做什麼，不用恐懼促使行動。
・不預測或建議財運・投資・賭博。不做醫療・健康的診斷或建議。
・最後務必尊重對方本人的選擇，不下指令。
・若是不必賦予特別意義的事（只是環境因素・偶然），就誠實地說
　「這件事不必想得太多，放心」，讓對方安心。那也是誠實的回答。
・簡短、安靜。全文約250〜350字。不使用裝飾性表情符號。

【回應的流程】
1. 先用一句話，柔和地承接這件事。
2. 從理來看會如何觀照（提醒・流動・整理 擇一）。
3. 今天可做的一小步，或「現在只要整理就好」。
請以繁體中文回答。""",
}

_ASK = {
    "ja": "次の出来事について、理の視点で短く観てください。\n\n出来事：{event}",
    "zh": "請以「理」的視角，簡短地觀照以下這件事。\n\n事情：{event}",
}

_NO_KEY = {
    "ja": "（相談機能は準備中です。少しお待ちください。）",
    "zh": "（諮詢功能準備中，請稍候。）",
}
_FAIL = {
    "ja": "うまく言葉にできませんでした。少し時間をおいて、もう一度試してみてください。",
    "zh": "這次沒能好好回應。請稍後再試一次。",
}
_OVER = {
    "ja": "本日の相談はたくさんのご利用をいただき、いったんお休みです。また明日どうぞ。",
    "zh": "今天的諮詢使用量已滿，先暫歇。明天再來。",
}


def consult(event, lang="ja"):
    """出来事の文字列を理の視点で観た短い文を返す。
    戻り値: {"text": str, "ok": bool, ...}"""
    if lang not in _CORPUS:
        lang = "ja"
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {"text": _NO_KEY[lang], "ok": False}
    if store.spent_today() >= _daily_budget_jpy():     # 最終防衛：1日の総額上限（永続）
        return {"text": _OVER[lang], "ok": False, "over_budget": True}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{
                "type": "text",
                "text": _CORPUS[lang],
                "cache_control": {"type": "ephemeral"},  # 土台をキャッシュして再送コストを圧縮
            }],
            messages=[{
                "role": "user",
                "content": _ASK[lang].format(event=event),
            }],
        )
        store.add_spend(_usage_to_jpy(getattr(msg, "usage", None)))  # 実使用量で当日累計に加算（永続）
        parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        text = "\n".join(parts).strip()
        if not text:
            return {"text": _FAIL[lang], "ok": False}
        return {"text": text, "ok": True}
    except Exception:
        return {"text": _FAIL[lang], "ok": False}
