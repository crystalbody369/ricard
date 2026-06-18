# -*- coding: utf-8 -*-
"""「今日の流れ」の素材を組み立てる。

ここが理カードの心臓部。出力は“素材（構造化データ）”であり、
最終的な文章（理の声）は次の工程（Day 3-4）で淡々と整える。
断定・煽りはしない。方位は簡易計算の参考。すべてローカル計算・外部送信なし。"""

from .chart import birth_chart, day_info
from .tables import GAN_ELEMENT, SHENG, KE


def _relation(me, today):
    """生まれの日主(me)から見た、今日の五行(today)との関係を返す。
    五行の生剋を、HIROさんの『理』の言葉づかいに寄せた区分にする。"""
    if me == today:
        return "比和"            # 仲間・勢い
    if SHENG.get(today) == me:    # 今日が私を生む（印）
        return "印"
    if SHENG.get(me) == today:    # 私が今日を生む（食傷）
        return "食傷"
    if KE.get(me) == today:       # 私が今日を剋す（財）
        return "財"
    if KE.get(today) == me:       # 今日が私を剋す（官殺）
        return "官殺"
    return "比和"


# 関係 → 今日の流れの「素材」。文章ではなく、方向づけと種（seed）。
TENDENCY = {
    "比和": {
        "key": "flow",
        "flow_seed": "流れに乗れる日。迷っていた一歩を、そっと踏み出してよい。",
        "en_seed": "気の合う人と進むと早い。仲間に声をかける。",
        "timing": "午前",
        "totonoe_seeds": ["勢いがある分、急ぎすぎない", "一つに絞って進む"],
    },
    "印": {
        "key": "receive",
        "flow_seed": "受け取る日。自分から押すより、来るものを受けると整う。",
        "en_seed": "人から助けや知らせが来やすい。頼ってよい。",
        "timing": "日中",
        "totonoe_seeds": ["学び・情報を取り入れる", "感謝を一つ伝える"],
    },
    "食傷": {
        "key": "express",
        "flow_seed": "出す日。考えるより、動いて形にすると流れる。",
        "en_seed": "自分から声をかけると縁が動く。",
        "timing": "午前",
        "totonoe_seeds": ["作りかけを一つ出す", "言葉にして伝える"],
    },
    "財": {
        "key": "grasp",
        "flow_seed": "縁やチャンスが向こうから来やすい日。つかむ。ただし押しすぎない。",
        "en_seed": "出会い・つながりが動く。受け止める余裕を持つ。",
        "timing": "午後",
        "totonoe_seeds": ["欲張らず一つだけ取る", "数字やお金の確認をする"],
    },
    "官殺": {
        "key": "steady",
        "flow_seed": "静かに整える日。押すと止まる。決めずに一晩おくと良い。",
        "en_seed": "無理に近づかない。距離を保つと縁が荒れない。",
        "timing": "夜",
        "totonoe_seeds": ["大きな決断は今日しない", "身の回りを片づけ整える"],
    },
}


def build_flow(birth, date):
    """birth=(年,月,日[,時]) / date=(年,月,日) から、今日の流れの素材を返す。"""
    bc = birth_chart(*birth)
    di = day_info(*date)

    me = bc["day_master_element"]          # 生まれの日主の五行
    today = di["day_element"]              # 今日の日干の五行
    rel = _relation(me, today)
    t = TENDENCY[rel]

    return {
        "date": di["date"],
        "honmei_star": bc["honmei_star"],          # 本命星（人物像の土台）
        "day_pillar": di["day_pillar"],            # 今日の干支
        "relation": rel,                           # 比和/印/食傷/財/官殺
        # ↓ 4つのカード面の「素材」。文章化は次工程で理の声に整える。
        "sections": {
            "flow": t["flow_seed"],                # 今日の流れ
            "en_hito": t["en_seed"],               # 縁・人
            "ugoki": {                             # 動き
                "direction": di["day_direction"],  # 今日の気が向く方位（簡易・参考）
                "timing": t["timing"],
            },
            "totonoe": t["totonoe_seeds"],         # 整えるヒント（種）
        },
        "chart_note": {                            # 文章化の素材（人物像の彩り）
            "day_master": bc["day_master"],
            "strong_element": bc["strong_element"],
            "weak_element": bc["weak_element"],
        },
        "disclaimer": ("これは娯楽・自己内省のための目安です。"
                       "断定するものではありません。方位は簡易計算の参考です。"),
    }
