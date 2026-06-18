# -*- coding: utf-8 -*-
"""「今日の理」の素材を、四柱推命の本格ロジックで一人ひとり別に組み立てる。

使う要素（すべて生年月日から決まる＝人によって違う）:
- 日主（その人の軸の天干）と、その五行・陰陽
- 命式全体の五行バランス → 身強 / 身弱
- 今日の天干が、その人にとって何の十神か（比肩〜正印の10種）
- 今日が、その人にとって追い風か / 控えめにすべきか（身強身弱との相性）
- 今日の地支と、その人の日支の関係（合・冲・刑・害）
- 今日の九星の方位

これらの組合せで、生年月日ごとに実質的に異なる読みになる。
当てる・断定する、はしない。すべてローカル計算・外部送信なし。"""

from .chart import birth_chart, day_info
from .tables import (
    GAN_ELEMENT, ZHI_ELEMENT, ELEMENTS, SHENG, KE,
    GAN_YIN_YANG, TEN_GOD_GROUP, GROUP_ROLE,
    ZHI_LIUHE, ZHI_SANHE, ZHI_CHONG, ZHI_HAI, ZHI_XING, ZHI_SELF_XING,
)


def ten_god(day_master, other_gan):
    """日主から見た、相手の天干の十神（比肩/劫財/食神/傷官/偏財/正財/偏官/正官/偏印/正印）。"""
    de = GAN_ELEMENT[day_master]
    oe = GAN_ELEMENT[other_gan]
    same_pol = GAN_YIN_YANG[day_master] == GAN_YIN_YANG[other_gan]
    if de == oe:
        return "比肩" if same_pol else "劫財"
    if SHENG.get(de) == oe:          # 我生（日主が相手を生む）
        return "食神" if same_pol else "傷官"
    if KE.get(de) == oe:             # 我剋（日主が相手を剋す）
        return "偏財" if same_pol else "正財"
    if KE.get(oe) == de:             # 剋我（相手が日主を剋す）
        return "偏官" if same_pol else "正官"
    if SHENG.get(oe) == de:          # 生我（相手が日主を生む）
        return "偏印" if same_pol else "正印"
    return "比肩"


def day_master_strength(day_master_element, element_counts):
    """命式の五行バランスから身強(strong)/身弱(weak)を簡易判定。
    支え（同じ五行＝比劫 ＋ 日主を生む五行＝印）と、
    漏らし（日主が生む/剋す ＋ 日主を剋す＝食傷財官）を比べる。"""
    dm = day_master_element
    gen_me = next(k for k, v in SHENG.items() if v == dm)   # 日主を生む五行（印）
    ctrl_me = next(k for k, v in KE.items() if v == dm)     # 日主を剋す五行（官殺）
    me_gen = SHENG[dm]                                       # 日主が生む五行（食傷）
    me_ctrl = KE[dm]                                         # 日主が剋す五行（財）
    support = element_counts.get(dm, 0) + element_counts.get(gen_me, 0)
    drain = (element_counts.get(me_gen, 0) + element_counts.get(me_ctrl, 0)
             + element_counts.get(ctrl_me, 0))
    return "strong" if support >= drain else "weak"


def _pair_in(z1, z2, pairs):
    s = {z1, z2}
    return any(s == set(p) for p in pairs)


def branch_relation(z1, z2):
    """今日の地支と、その人の日支の関係を分類する。
    clash(冲＝動く/揺れる) / harmony(合＝和む/つながる) / friction(刑害＝小さな摩擦) / calm(穏やか)。"""
    if z1 == z2:
        return "friction" if z1 in ZHI_SELF_XING else "harmony"  # 同支は基本なじむ
    if _pair_in(z1, z2, ZHI_CHONG):
        return "clash"
    if _pair_in(z1, z2, ZHI_LIUHE):
        return "harmony"
    if any(z1 in g and z2 in g for g in ZHI_SANHE):
        return "harmony"
    if _pair_in(z1, z2, ZHI_XING) or _pair_in(z1, z2, ZHI_HAI):
        return "friction"
    return "calm"


# 十神グループ → 動きの時間帯の種
_TIMING = {"食傷": "午前", "財": "午後", "官殺": "夜", "印": "日中", "比劫": "午前"}


def build_flow(birth, date):
    """birth=(年,月,日[,時]) / date=(年,月,日) → 一人ひとり別の素材を返す。"""
    bc = birth_chart(*birth)
    di = day_info(*date)

    dm = bc["day_master"]                 # 日主の天干
    dm_elem = bc["day_master_element"]
    day_zhi = bc["pillars"]["day"][1]     # その人の日支
    today_gan = di["day_gan"]
    today_zhi = di["day_zhi"]

    tg = ten_god(dm, today_gan)           # 今日の十神
    group = TEN_GOD_GROUP[tg]             # 5テーマのどれか
    role = GROUP_ROLE[group]              # support / drain
    strength = day_master_strength(dm_elem, bc["element_counts"])

    # 身強なら漏らし系(drain)が追い風、身弱なら支え系(support)が追い風
    if strength == "strong":
        favor = "favorable" if role == "drain" else "challenging"
    else:
        favor = "favorable" if role == "support" else "challenging"

    brel = branch_relation(today_zhi, day_zhi)

    # 人・日付ごとに決定的に変わる種（言い回しの選択に使う）
    base = dm + today_gan + today_zhi + day_zhi + di["date"]
    seed = sum(ord(c) for c in base)

    return {
        "date": di["date"],
        "honmei_star": bc["honmei_star"],
        "day_pillar": di["day_pillar"],
        "day_master": dm,
        "ten_god": tg,
        "group": group,
        "strength": strength,
        "favor": favor,
        "branch_rel": brel,
        "direction": di["day_direction"],
        "timing": _TIMING[group],
        "seed": seed,
        "disclaimer": ("これは娯楽・自己内省のための目安です。"
                       "断定するものではありません。方位は簡易計算の参考です。"),
    }
