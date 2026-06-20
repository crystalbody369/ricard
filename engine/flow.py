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

from lunar_python import Solar

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


_GROUP_GLOSS = {
    "比劫": "自立・仲間・勢い", "食傷": "出す・表現・才能",
    "財": "つかむ・縁・お金", "官殺": "律する・責任・抑え", "印": "受け取る・学び・支え",
}
_BREL_LABEL = {
    "clash": "冲（動きやすい・変化）", "harmony": "合（和む・つながる）",
    "friction": "刑・害（小さな摩擦）", "calm": "穏やか",
}

# ── 方位（九星気学）。その日の九星の配置から「避けたい向き」を割り出す ──
_DIR_OPPOSITE = {"北": "南", "南": "北", "東": "西", "西": "東",
                 "北東": "南西", "南西": "北東", "南東": "北西", "北西": "南東"}
_HOME_DIR_BY_NUM = {1: "北", 2: "南西", 3: "東", 4: "南東", 5: "中央",
                    6: "北西", 7: "西", 8: "北東", 9: "南"}
# 十二支 → おおまかな方位（破の算出用）
_ZHI_DIR = {"子": "北", "丑": "北東", "寅": "北東", "卯": "東", "辰": "南東", "巳": "南東",
            "午": "南", "未": "南西", "申": "南西", "酉": "西", "戌": "北西", "亥": "北西"}


def _day_board(day_star_num):
    """その日の九星盤。各方位に入る星を返す（中宮＝その日の九星）。"""
    D = day_star_num
    board = {}
    for P in range(1, 10):
        star = ((P - 1 + (D - 5)) % 9) + 1
        board[_HOME_DIR_BY_NUM[P]] = star
    return board


def _dir_of_star(board, star):
    for dname, s in board.items():
        if s == star and dname != "中央":
            return dname
    return None  # 中央にある場合（その日は該当なし）


def build_direction(date, honmei_num):
    """その日の「避けたい向き（参考）」を九星の配置から割り出す。"""
    di = day_info(*date)
    board = _day_board(di["day_star_num"])
    avoid = []  # (方位, 名称)
    gohou = _dir_of_star(board, 5)             # 五黄殺＝五黄土星のある方位
    if gohou:
        avoid.append((gohou, "五黄殺"))
        anken = _DIR_OPPOSITE.get(gohou)       # 暗剣殺＝五黄の反対
        if anken:
            avoid.append((anken, "暗剣殺"))
    nippa = _DIR_OPPOSITE.get(_ZHI_DIR.get(di["day_zhi"]))  # 日破＝その日の十二支の反対
    if nippa:
        avoid.append((nippa, "日破"))
    honmei_dir = _dir_of_star(board, honmei_num)   # 本命殺＝自分の本命星のある方位
    if honmei_dir:
        avoid.append((honmei_dir, "本命殺"))
        teki = _DIR_OPPOSITE.get(honmei_dir)       # 本命的殺＝その反対
        if teki:
            avoid.append((teki, "本命的殺"))
    return {"ki_dir": di["day_direction"], "avoid": avoid}


def build_liunian(date, day_master):
    """流年＝その年の干支と、日主から見た十神（今年の運の背景）。"""
    s = Solar.fromYmdHms(int(date[0]), int(date[1]), int(date[2]), 12, 0, 0)
    ec = s.getLunar().getEightChar()
    gz = ec.getYear()
    tg = ten_god(day_master, gz[0])
    return gz, tg, TEN_GOD_GROUP[tg]


def build_yojin(dm_elem, strength):
    """用神（簡易・扶抑）。身弱なら支える五行、身強なら出す五行。"""
    gen_me = next(k for k, v in SHENG.items() if v == dm_elem)   # 日主を生む五行（印）
    if strength == "weak":
        return [gen_me, dm_elem]                 # 身弱 → 印・比で支える
    return [SHENG[dm_elem], KE[dm_elem]]         # 身強 → 食傷・財で出す


def current_dayun(birth, gender_code, target_year, day_master):
    """今の大運（10年の運）。gender_code: 0=男, 1=女（lunar_python準拠）。"""
    h = birth[3] if len(birth) > 3 else 12
    s = Solar.fromYmdHms(int(birth[0]), int(birth[1]), int(birth[2]), int(h), 0, 0)
    ec = s.getLunar().getEightChar()
    yun = ec.getYun(gender_code)
    for d in yun.getDaYun():
        if d.getStartYear() <= target_year <= d.getEndYear():
            gz = d.getGanZhi()
            if not gz:                            # 起運前（幼年期）は干支なし
                return {"ganzhi": None, "age": (d.getStartAge(), d.getEndAge())}
            tg = ten_god(day_master, gz[0])
            return {"ganzhi": gz, "ten_god": tg, "group": TEN_GOD_GROUP[tg],
                    "age": (d.getStartAge(), d.getEndAge())}
    return None


_DETAIL_L = {
    "ja": {
        "methods": "四柱推命（生年月日からの命式）＋ 九星気学（方位）＋ 一神会『理』の考え方",
        "labels": {"axis": "あなたの軸（日主）", "honmei": "本命星（九星）", "strength": "体質（身強・身弱）",
                   "tgz": "今日の干支", "ttg": "今日の十神", "fit": "今日との相性", "ppl": "人との関係（地支）",
                   "avoid": "今日 控えめにしたい向き（参考）", "liunian": "今年の運（流年）",
                   "yojin": "あなたに合う五行（用神・簡易）", "dayun": "今の大運（10年の流れ）"},
        "strong": "身強（エネルギー強め）", "weak": "身弱（エネルギー控えめ）",
        "favorable": "追い風の日", "challenging": "控えめにいく日",
        "gloss": {"比劫": "自立・仲間・勢い", "食傷": "出す・表現・才能", "財": "つかむ・縁・お金",
                  "官殺": "律する・責任・抑え", "印": "受け取る・学び・支え"},
        "brel": {"clash": "冲（動きやすい・変化）", "harmony": "合（和む・つながる）",
                 "friction": "刑・害（小さな摩擦）", "calm": "穏やか"},
        "avoidnames": {"五黄殺": "五黄殺", "暗剣殺": "暗剣殺", "日破": "日破", "本命殺": "本命殺", "本命的殺": "本命的殺"},
        "none": "特になし", "dayunfmt": "%d〜%d歳：%s（%s）",
        "note": "これは当てるためのものではなく、今日を整えるための目安です。断定はしません。",
        "how": ("生年月日から四柱推命の命式（あなたの軸＝日主）を出し、"
                "今日の干支との関係＝十神「%s」で今日のテーマを、"
                "あなたの体質（身強・身弱）との相性で『追い風か控えめか』を、"
                "今日とあなたの地支の関係で人との動きを読みます。"
                "方位は、その日の九星の配置から、五黄殺・暗剣殺・日破と、"
                "あなたの本命星の位置（本命殺）から『避けたい向き』を出しています。"
                "良い向き（吉方）は流派で見方が分かれるため、定義の明確な避けたい向きだけを参考としています。"
                "挙げた向き以外は、特に気にしすぎなくて大丈夫です。"
                "さらに、今年の干支（流年）・あなたに合う五行（用神）・"
                "（性別を入れると）今の10年期（大運）も併せて見ています。"),
    },
    "zh": {
        "methods": "四柱推命（從生日推命盤）＋ 九星氣學（方位）＋ 一神會『理』的思維",
        "labels": {"axis": "你的核心（日主）", "honmei": "本命星（九星）", "strength": "體質（身強・身弱）",
                   "tgz": "今日干支", "ttg": "今日十神", "fit": "今日的相性", "ppl": "人際關係（地支）",
                   "avoid": "今天 宜避開的方位（參考）", "liunian": "今年的運（流年）",
                   "yojin": "適合你的五行（用神・簡易）", "dayun": "目前的大運（十年之流）"},
        "strong": "身強（能量偏強）", "weak": "身弱（能量偏弱）",
        "favorable": "順風的一天", "challenging": "宜收斂的一天",
        "gloss": {"比劫": "自立・夥伴・氣勢", "食傷": "表達・展現・才華", "財": "把握・緣分・金錢",
                  "官殺": "自律・責任・收斂", "印": "接收・學習・支持"},
        "brel": {"clash": "沖（容易變動）", "harmony": "合（和緩・連結）",
                 "friction": "刑・害（小摩擦）", "calm": "平穩"},
        "avoidnames": {"五黄殺": "五黃殺", "暗剣殺": "暗劍殺", "日破": "日破", "本命殺": "本命殺", "本命的殺": "本命的殺"},
        "none": "無特別", "dayunfmt": "%d〜%d歲：%s（%s）",
        "note": "這並非用來算準，而是整理今天的參考，不作斷定。",
        "how": ("從生日推出四柱命盤（你的核心＝日主），"
                "用今日干支與你的關係＝十神「%s」看今天的主題，"
                "用你的體質（身強・身弱）的相性看『順風或宜收斂』，"
                "用今日與你的地支關係看人際的動向。"
                "方位是從當日九星的配置，算出五黃殺・暗劍殺・日破，"
                "與你的本命星所在（本命殺），得出『宜避開的方位』。"
                "好的方位（吉方）各流派看法不同，故只提供定義明確的宜避開方位。"
                "上述以外的方位，不必太在意。"
                "此外也一併參看今年干支（流年）・適合你的五行（用神）・"
                "（填入性別時）目前的十年期（大運）。"),
    },
}


def build_detail(birth, date, gender=None, lang="ja"):
    """このカードが『何をもとに出ているか』を分かりやすく返す（誠実さの開示用・二言語）。"""
    L = _DETAIL_L.get(lang, _DETAIL_L["ja"])
    lb = L["labels"]
    m = build_flow(birth, date)
    bc = birth_chart(*birth)
    dm = m["day_master"]
    dm_elem = bc["day_master_element"]
    honmei = (m["honmei_star"].replace("緑", "綠").replace("黒", "黑")
              if lang == "zh" else m["honmei_star"])
    strength = L["strong"] if m["strength"] == "strong" else L["weak"]
    favor = L["favorable"] if m["favor"] == "favorable" else L["challenging"]
    rows = [
        [lb["axis"], "%s（%s）" % (dm, dm_elem)],
        [lb["honmei"], honmei],
        [lb["strength"], strength],
        [lb["tgz"], m["day_pillar"]],
        [lb["ttg"], "%s（%s）" % (m["ten_god"], L["gloss"][m["group"]])],
        [lb["fit"], favor],
        [lb["ppl"], L["brel"][m["branch_rel"]]],
    ]
    dinfo = build_direction(date, bc["honmei_star_num"])
    grouped, order = {}, []
    for d, lbl in dinfo["avoid"]:
        if d not in grouped:
            grouped[d] = []
            order.append(d)
        grouped[d].append(L["avoidnames"].get(lbl, lbl))
    avoid_str = "・".join("%s（%s）" % (d, "・".join(grouped[d])) for d in order) or L["none"]
    rows.append([lb["avoid"], avoid_str])
    ly_gz, _ly_tg, ly_grp = build_liunian(date, dm)
    rows.append([lb["liunian"], "%s（%s）" % (ly_gz, L["gloss"][ly_grp])])
    yojin = build_yojin(dm_elem, m["strength"])
    rows.append([lb["yojin"], "・".join(yojin)])
    if gender in ("m", "f"):
        du = current_dayun(birth, 0 if gender == "m" else 1, int(date[0]), dm)
        if du and du.get("ganzhi"):
            rows.append([lb["dayun"], L["dayunfmt"] % (du["age"][0], du["age"][1],
                                                       du["ganzhi"], L["gloss"][du["group"]])])
    return {"methods": L["methods"], "rows": rows, "how": L["how"] % m["ten_god"], "note": L["note"]}
