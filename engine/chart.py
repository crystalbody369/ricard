# -*- coding: utf-8 -*-
"""命式（八字＋九星＋五行バランス）と、対象日の干支・九星を計算する。
lunar_python（純Python・コンパイル不要）を利用。すべてローカル計算・外部送信なし。"""

from lunar_python import Solar

from .tables import (
    GAN_ELEMENT, ZHI_ELEMENT, ELEMENTS,
    NINE_STAR_JP, NINE_STAR_ELEMENT, NINE_STAR_DIRECTION, KANJI_NUM,
)


def _star_num(nine_star_obj):
    """lunar_python の NineStar から 1〜9 の番号を取り出す。
    文字列表現（例「六白金开阳」）の先頭の漢数字から判定する。"""
    s = str(nine_star_obj)
    for ch in s:
        if ch in KANJI_NUM:
            return KANJI_NUM[ch]
    # 念のためのフォールバック
    try:
        return int(nine_star_obj.getNumber()) + 1
    except Exception:
        return 5


def _count_elements(pillars):
    """干支の各柱から五行をカウント（天干＋地支の本気）。"""
    counts = {e: 0 for e in ELEMENTS}
    for gz in pillars.values():
        gan, zhi = gz[0], gz[1]
        counts[GAN_ELEMENT[gan]] += 1
        counts[ZHI_ELEMENT[zhi]] += 1
    return counts


def birth_chart(year, month, day, hour=None):
    """生年月日（任意で時刻）から命式を作る。

    返り値の例:
      {
        "pillars": {"year": "丙辰", "month": "丁酉", "day": "庚午", "time": "辛巳"},
        "day_master": "庚",
        "day_master_element": "金",
        "element_counts": {"木":1, "火":2, ...},
        "strong_element": "金",
        "weak_element": "木",
        "honmei_star_num": 6,
        "honmei_star": "六白金星",
        "honmei_star_element": "金",
      }
    """
    h = hour if hour is not None else 12
    solar = Solar.fromYmdHms(int(year), int(month), int(day), int(h), 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    pillars = {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
    }
    if hour is not None:
        pillars["time"] = ec.getTime()

    counts = _count_elements(pillars)
    day_master = pillars["day"][0]

    strong = max(counts, key=lambda e: counts[e])
    weak = min(counts, key=lambda e: counts[e])

    honmei_num = _star_num(lunar.getYearNineStar())

    return {
        "pillars": pillars,
        "day_master": day_master,
        "day_master_element": GAN_ELEMENT[day_master],
        "element_counts": counts,
        "strong_element": strong,
        "weak_element": weak,
        "honmei_star_num": honmei_num,
        "honmei_star": NINE_STAR_JP[honmei_num],
        "honmei_star_element": NINE_STAR_ELEMENT[honmei_num],
    }


def day_info(year, month, day):
    """対象日の干支・五行・九星・方位を返す。"""
    solar = Solar.fromYmdHms(int(year), int(month), int(day), 12, 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    day_pillar = ec.getDay()
    day_gan, day_zhi = day_pillar[0], day_pillar[1]
    star_num = _star_num(lunar.getDayNineStar())

    return {
        "date": "%04d-%02d-%02d" % (int(year), int(month), int(day)),
        "day_pillar": day_pillar,
        "day_gan": day_gan,
        "day_zhi": day_zhi,
        "day_element": GAN_ELEMENT[day_gan],
        "day_star_num": star_num,
        "day_star": NINE_STAR_JP[star_num],
        "day_direction": NINE_STAR_DIRECTION[star_num],
    }
