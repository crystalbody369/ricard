# -*- coding: utf-8 -*-
"""縁（二人の相性）— 2つの生年月日から、淡々とした「縁」のカードを作る。

当てる・断定する・優劣をつける、はしない。
どんな関係も「活かし方」と「気をつけること」を前向きに示して着地する。
すべてローカル計算・外部送信なし。"""

from .chart import birth_chart
from .tables import SHENG, KE

FOOTER = ("これは娯楽・二人で楽しむための目安です。"
          "相性の良し悪しを決めるものではありません。")


def _category(a, b):
    """二人の日主五行の関係を、比和／相生／相剋に分ける。"""
    if a == b:
        return "比和"
    if SHENG.get(a) == b or SHENG.get(b) == a:
        return "相生"
    if KE.get(a) == b or KE.get(b) == a:
        return "相剋"
    return "比和"


EN = {
    "比和": {
        "opening": "似た気を持つ、安心の縁。",
        "kankei": "感覚が近く、一緒にいて楽な二人。同じ景色を見られる。",
        "ikashi": "共通の好きを大事に。ときどき外から新しい刺激を入れると、もっと長く続く。",
        "kiwotsuke": "似ているぶん、馴れ合いになりやすい。たまに新しいことを一緒に。",
        "ippo": "今日は、同じものを一緒に楽しむ。",
    },
    "相生": {
        "opening": "支え合い、育てる縁。",
        "kankei": "一方が一方を自然に生かす関係。一緒にいると伸びていく。",
        "ikashi": "与える側・受け取る側を固定しすぎず、循環させると豊かになる。",
        "kiwotsuke": "尽くしすぎ・頼りすぎに気をつける。お互いの間（ま）を残す。",
        "ippo": "今日は、相手に小さな「ありがとう」をひとつ。",
    },
    "相剋": {
        "opening": "磨き合う、刺激の縁。",
        "kankei": "違いが大きく、ときにぶつかる。でも、互いを成長させる関係。",
        "ikashi": "違いを正そうとせず、面白がる。視点が増える縁として使う。",
        "kiwotsuke": "押しすぎない。勝ち負けにしない。一晩おくと収まる。",
        "ippo": "今日は、相手の話を一つ、否定せずに最後まで聞く。",
    },
}


def build_en(birth_a, birth_b, date_str=""):
    """birth_a / birth_b = (年,月,日[,時])。縁カードの描画ビューを返す。"""
    ca = birth_chart(*birth_a)
    cb = birth_chart(*birth_b)
    cat = _category(ca["day_master_element"], cb["day_master_element"])
    e = EN[cat]

    return {
        "subtitle": "二 人 の 縁",
        "date": date_str or "%s ・ %s" % (ca["honmei_star"], cb["honmei_star"]),
        "opening": e["opening"],
        "sections": [
            ("二人の関係", e["kankei"]),
            ("活かし方", e["ikashi"]),
            ("気をつけること", e["kiwotsuke"]),
            ("今日の一歩", e["ippo"]),
        ],
        "closing": "縁は、つかむより、育てるもの。",
        "footer": FOOTER,
    }
