# -*- coding: utf-8 -*-
"""縁（二人の相性）— 日本語＝ja / 繁體中文＝zh の二言語。
良し悪しは決めず、活かし方と気をつけ方で前向きに着地する。すべてローカル計算・外部送信なし。"""

from .chart import birth_chart
from .flow import branch_relation
from .tables import SHENG, KE


def _rel_category(a, b):
    if a == b:
        return "比和"
    if SHENG.get(a) == b or SHENG.get(b) == a:
        return "相生"
    if KE.get(a) == b or KE.get(b) == a:
        return "相剋"
    return "比和"


REL = {
    "ja": {
        "比和": {"opening": ["似た気を持つ、安心の縁。", "同じ景色を見られる二人。"],
                "kankei": "感覚が近く、一緒にいて楽な二人。",
                "ikashi": "共通の好きを大事に。たまに新しい刺激を外から入れると、長く続く。",
                "ippo": "今日は、同じものを一緒に楽しむ。"},
        "相生": {"opening": ["支え合い、育てる縁。", "互いを伸ばし合う二人。"],
                "kankei": "一方が一方を自然に生かす関係。",
                "ikashi": "与える・受け取るを固定しすぎず、循環させると豊かになる。",
                "ippo": "今日は、相手に小さな「ありがとう」をひとつ。"},
        "相剋": {"opening": ["磨き合う、刺激の縁。", "違いが学びになる二人。"],
                "kankei": "違いが大きく、ときにぶつかるが、互いを成長させる関係。",
                "ikashi": "違いを正そうとせず、面白がる。視点が増える縁として使う。",
                "ippo": "今日は、相手の話を一つ、否定せずに最後まで聞く。"},
    },
    "zh": {
        "比和": {"opening": ["氣質相近、令人安心的緣分。", "能看見同一片風景的兩人。"],
                "kankei": "感覺相近、在一起很自在的兩人。",
                "ikashi": "珍惜共同的喜好。偶爾從外面加點新刺激，能走得更久。",
                "ippo": "今天，一起享受同一件事。"},
        "相生": {"opening": ["互相扶持、彼此滋養的緣分。", "能讓對方成長的兩人。"],
                "kankei": "一方自然地成就另一方的關係。",
                "ikashi": "別把給予與接受固定，讓它循環會更豐盛。",
                "ippo": "今天，對對方說一聲小小的「謝謝」。"},
        "相剋": {"opening": ["互相磨練、帶來刺激的緣分。", "差異能成為學習的兩人。"],
                "kankei": "差異大、有時會碰撞，但能讓彼此成長的關係。",
                "ikashi": "別想糾正差異，把它當作有趣，當成增加視角的緣分。",
                "ippo": "今天，把對方的一段話，不否定地聽到最後。"},
    },
}

BRANCH_EN = {
    "ja": {
        "harmony": {"add": "今日は波長も合いやすい。", "kiwotsuke": "なじむぶん、馴れ合いにならないよう、新しいことも一緒に。"},
        "clash": {"add": "今日は少し揺れやすい。", "kiwotsuke": "押しすぎない。勝ち負けにしない。決めごとは一晩おく。"},
        "friction": {"add": "今日は小さな行き違いに注意。", "kiwotsuke": "早とちりせず、一呼吸おいて確かめる。"},
        "calm": {"add": "今日は穏やかに過ごせる。", "kiwotsuke": "特別なことはせず、いつも通りで十分。"},
    },
    "zh": {
        "harmony": {"add": "今天頻率也容易合拍。", "kiwotsuke": "正因合拍，別流於隨便，也一起做點新的事。"},
        "clash": {"add": "今天稍微容易起波動。", "kiwotsuke": "別硬推、別分勝負，要決定的事先擱一晚。"},
        "friction": {"add": "今天注意小誤會。", "kiwotsuke": "別太早下定論，深呼吸後確認。"},
        "calm": {"add": "今天能平穩度過。", "kiwotsuke": "不必特別做什麼，照平常就足夠。"},
    },
}

# 言語別ラベル
_L = {
    "ja": {"subtitle": "二 人 の 縁", "sep": " ・ ",
           "labels": ["二人の関係", "活かし方", "気をつけること", "今日の一歩"],
           "closing": "縁は、つかむより、育てるもの。", "mark": "理 カ ー ド",
           "footer": "これは娯楽・二人で楽しむための目安です。相性の良し悪しを決めるものではありません。"},
    "zh": {"subtitle": "兩 人 的 緣", "sep": " ・ ",
           "labels": ["兩人關係", "相處之道", "留意之處", "今日一步"],
           "closing": "緣分，與其抓取，不如培養。", "mark": "理 卡",
           "footer": "這是供娛樂、兩人同樂的參考，並非用來斷定合不合。"},
}


def _star(name, lang):
    return name.replace("緑", "綠").replace("黒", "黑") if lang == "zh" else name


def _pick(variants, seed):
    return variants[seed % len(variants)]


def build_en(birth_a, birth_b, lang="ja"):
    """birth_a / birth_b = (年,月,日[,時])。縁カードの描画ビュー（lang で言語切替）。"""
    if lang not in REL:
        lang = "ja"
    ca = birth_chart(*birth_a)
    cb = birth_chart(*birth_b)
    rel = _rel_category(ca["day_master_element"], cb["day_master_element"])
    brel = branch_relation(ca["pillars"]["day"][1], cb["pillars"]["day"][1])
    seed = sum(ord(c) for c in (ca["day_master"] + cb["day_master"]
                                + ca["pillars"]["day"] + cb["pillars"]["day"]))
    r = REL[lang][rel]
    b = BRANCH_EN[lang][brel]
    L = _L[lang]
    return {
        "subtitle": L["subtitle"],
        "date": "%s%s%s" % (_star(ca["honmei_star"], lang), L["sep"], _star(cb["honmei_star"], lang)),
        "opening": _pick(r["opening"], seed),
        "sections": [
            (L["labels"][0], r["kankei"] + " " + b["add"]),
            (L["labels"][1], r["ikashi"]),
            (L["labels"][2], b["kiwotsuke"]),
            (L["labels"][3], r["ippo"]),
        ],
        "closing": L["closing"],
        "mark": L["mark"],
        "footer": L["footer"],
    }
