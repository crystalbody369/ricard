# -*- coding: utf-8 -*-
"""縁（二人の相性）— 二人の四柱推命から、一組ごとに違う「縁」のカードを作る。

使う要素：二人の日主の五行関係（比和/相生/相剋）× 二人の日支の関係（合/冲/刑害/穏）
＋ 言い回しの種(seed)。良し悪しは決めず、活かし方と気をつけ方で前向きに着地する。
すべてローカル計算・外部送信なし。"""

from .chart import birth_chart
from .flow import branch_relation
from .tables import SHENG, KE

FOOTER = ("これは娯楽・二人で楽しむための目安です。"
          "相性の良し悪しを決めるものではありません。")


def _rel_category(a, b):
    if a == b:
        return "比和"
    if SHENG.get(a) == b or SHENG.get(b) == a:
        return "相生"
    if KE.get(a) == b or KE.get(b) == a:
        return "相剋"
    return "比和"


REL = {
    "比和": {
        "opening": ["似た気を持つ、安心の縁。", "同じ景色を見られる二人。"],
        "kankei": "感覚が近く、一緒にいて楽な二人。",
        "ikashi": "共通の好きを大事に。たまに新しい刺激を外から入れると、長く続く。",
        "ippo": "今日は、同じものを一緒に楽しむ。",
    },
    "相生": {
        "opening": ["支え合い、育てる縁。", "互いを伸ばし合う二人。"],
        "kankei": "一方が一方を自然に生かす関係。",
        "ikashi": "与える・受け取るを固定しすぎず、循環させると豊かになる。",
        "ippo": "今日は、相手に小さな「ありがとう」をひとつ。",
    },
    "相剋": {
        "opening": ["磨き合う、刺激の縁。", "違いが学びになる二人。"],
        "kankei": "違いが大きく、ときにぶつかるが、互いを成長させる関係。",
        "ikashi": "違いを正そうとせず、面白がる。視点が増える縁として使う。",
        "ippo": "今日は、相手の話を一つ、否定せずに最後まで聞く。",
    },
}

BRANCH_EN = {
    "harmony": {"add": "今日は波長も合いやすい。",
                "kiwotsuke": "なじむぶん、馴れ合いにならないよう、新しいことも一緒に。"},
    "clash": {"add": "今日は少し揺れやすい。",
              "kiwotsuke": "押しすぎない。勝ち負けにしない。決めごとは一晩おく。"},
    "friction": {"add": "今日は小さな行き違いに注意。",
                 "kiwotsuke": "早とちりせず、一呼吸おいて確かめる。"},
    "calm": {"add": "今日は穏やかに過ごせる。",
             "kiwotsuke": "特別なことはせず、いつも通りで十分。"},
}


def _pick(variants, seed):
    return variants[seed % len(variants)]


def build_en(birth_a, birth_b, date_str=""):
    """birth_a / birth_b = (年,月,日[,時])。縁カードの描画ビューを返す。"""
    ca = birth_chart(*birth_a)
    cb = birth_chart(*birth_b)
    rel = _rel_category(ca["day_master_element"], cb["day_master_element"])
    brel = branch_relation(ca["pillars"]["day"][1], cb["pillars"]["day"][1])

    seed = sum(ord(c) for c in (ca["day_master"] + cb["day_master"]
                                + ca["pillars"]["day"] + cb["pillars"]["day"]))
    r = REL[rel]
    b = BRANCH_EN[brel]

    return {
        "subtitle": "二 人 の 縁",
        "date": "%s ・ %s" % (ca["honmei_star"], cb["honmei_star"]),
        "opening": _pick(r["opening"], seed),
        "sections": [
            ("二人の関係", r["kankei"] + " " + b["add"]),
            ("活かし方", r["ikashi"]),
            ("気をつけること", b["kiwotsuke"]),
            ("今日の一歩", r["ippo"]),
        ],
        "closing": "縁は、つかむより、育てるもの。",
        "footer": FOOTER,
    }
