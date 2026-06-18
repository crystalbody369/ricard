# -*- coding: utf-8 -*-
"""理の声 — 「今日の流れ」の素材を、淡々とした文章に整える。

方針:
- 断定しない・煽らない・脅さない。「淡々と流れる／押すと止まる／整えると進む」。
- 外部AIは使わず、すべてローカルの型で組み立てる（個人データは外に出ない）。
- 同じ関係でも日によって少し言い回しが変わる（日付で決定的に選ぶ＝再現可能）。
"""

from .flow import build_flow

# 関係（比和/印/食傷/財/官殺）ごとの文章パーツ。各リストから日付で1つ選ぶ。
VOICE = {
    "比和": {
        "opening": ["今日は、流れに乗れる日。", "今日は、追い風の日。"],
        "flow": [
            "迷っていた一歩は、そっと踏み出してよいでしょう。力まなくても進みます。",
            "考えすぎず、流れにまかせると前に進みます。",
        ],
        "en_hito": ["気の合う人と動くと早い日。仲間に一声かけてみる。"],
        "totonoe": ["勢いがある分、欲張らず一つに絞ると整います。"],
        "closing": ["急がず、しかし止まらず。"],
    },
    "印": {
        "opening": ["今日は、受け取る日。"],
        "flow": [
            "自分から押すより、来るものを受け取るほうが整います。",
            "今日は、まわりの力を借りてよい日です。",
        ],
        "en_hito": ["人から助けや知らせが届きやすい日。素直に頼ってよいでしょう。"],
        "totonoe": ["学びや情報を一つ取り入れる。感謝を、ひとつ言葉にする。"],
        "closing": ["受け取ることも、進むことのうち。"],
    },
    "食傷": {
        "opening": ["今日は、出す日。"],
        "flow": [
            "頭で考えるより、手を動かして形にすると流れます。",
            "ためていたものを、少し外に出すとよい日です。",
        ],
        "en_hito": ["自分から声をかけると、縁が静かに動きます。"],
        "totonoe": ["作りかけを一つ、外に出してみる。"],
        "closing": ["出すことで、巡りはじめる。"],
    },
    "財": {
        "opening": ["今日は、巡り合う日。"],
        "flow": [
            "縁やきっかけが、向こうから来やすい日。来たものは受け止める。ただ、押しすぎないように。",
            "向こうから動きが来やすい日。焦って掴まず、迎え入れるくらいで。",
        ],
        "en_hito": ["出会い・つながりが動きます。掴もうと焦らず、受け止める余裕を持って。"],
        "totonoe": ["欲張らず、一つだけ取る。数字やお金は、静かに確認しておく。"],
        "closing": ["つかむより、迎え入れる。"],
    },
    "官殺": {
        "opening": ["今日は、静かに整える日。"],
        "flow": [
            "押すと止まりやすい日。大きな決めごとは、一晩おいてからでよいでしょう。",
            "急がないほうが、かえって早く進む日です。",
        ],
        "en_hito": ["無理に近づかず、少し距離を保つと、縁は荒れません。"],
        "totonoe": ["身のまわりを片づけて整える。決断は、今日はしない。"],
        "closing": ["止まって見えるのは、整えている時間。"],
    },
}


def _pick(variants, date_str):
    """日付から決定的に1つ選ぶ（毎日少し変わるが、同じ日なら同じ結果）。"""
    n = sum(int(c) for c in date_str if c.isdigit())
    return variants[n % len(variants)]


def compose(material):
    """flow.build_flow の素材 → 整った『今日の理』カードのテキスト構造。"""
    rel = material["relation"]
    v = VOICE[rel]
    date = material["date"]
    ug = material["sections"]["ugoki"]
    ugoki = "もし動くなら、%sに。今日は%sの方が、少し気が通ります。" % (
        ug["timing"], ug["direction"])

    return {
        "date": date,
        "honmei_star": material["honmei_star"],
        "relation": rel,
        "opening": _pick(v["opening"], date),
        "flow": _pick(v["flow"], date),
        "en_hito": _pick(v["en_hito"], date),
        "ugoki": ugoki,
        "totonoe": _pick(v["totonoe"], date),
        "closing": _pick(v["closing"], date),
        "footer": material["disclaimer"],
    }


def render_text(card):
    """投稿・プレビュー用のプレーンテキスト。"""
    lines = [
        "｜今日の理｜　%s" % card["date"],
        "",
        card["opening"],
        "",
        "◦ 流れ　… %s" % card["flow"],
        "◦ 縁・人 … %s" % card["en_hito"],
        "◦ 動き　… %s" % card["ugoki"],
        "◦ 整える … %s" % card["totonoe"],
        "",
        card["closing"],
        "",
        "（%s）" % card["footer"],
    ]
    return "\n".join(lines)


def build_card(birth, date):
    """生年月日・対象日 → 整った『今日の理』カード。"""
    return compose(build_flow(birth, date))
