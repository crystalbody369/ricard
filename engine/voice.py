# -*- coding: utf-8 -*-
"""理の声（日本語＝ja / 繁體中文＝zh の二言語）。

言語を後から足せる形：各テーブルを {lang: {...}} で持ち、compose(m, lang) で選ぶ。
断定しない・煽らない・脅さない。外部AIは使わない（個人データは外に出ない）。"""

from .flow import build_flow

OPENING = {
    "ja": {
        "比劫": {"favorable": ["今日は、自分の足で進める日。", "今日は、迷わず一歩を踏める日。"],
                "challenging": ["今日は、抱え込まず、人に委ねる日。", "今日は、力みを抜く日。"]},
        "食傷": {"favorable": ["今日は、出して動くと流れる日。", "今日は、表に出すほど整う日。"],
                "challenging": ["今日は、出しすぎず、力を残す日。", "今日は、静かに仕舞う日。"]},
        "財": {"favorable": ["今日は、巡り合いをつかみにいける日。", "今日は、縁に手を伸ばせる日。"],
              "challenging": ["今日は、欲張らず、来たものを受ける日。", "今日は、つかむより、迎え入れる日。"]},
        "官殺": {"favorable": ["今日は、背筋を伸ばして整う日。", "今日は、筋を通すと進む日。"],
                "challenging": ["今日は、無理に押さず、静かに守る日。", "今日は、決めずに、待つ日。"]},
        "印": {"favorable": ["今日は、受け取り、満ちる日。", "今日は、頼ってよい日。"],
              "challenging": ["今日は、求めすぎず、待つ日。", "今日は、内を整える日。"]},
    },
    "zh": {
        "比劫": {"favorable": ["今天，是能靠自己向前的一天。", "今天，是能毫不猶豫踏出一步的一天。"],
                "challenging": ["今天，是不必獨自扛、可交給他人的一天。", "今天，是放下用力的一天。"]},
        "食傷": {"favorable": ["今天，動手去做就會順的一天。", "今天，越是表達出來越順的一天。"],
                "challenging": ["今天，別用盡、留些力氣的一天。", "今天，安靜收起來的一天。"]},
        "財": {"favorable": ["今天，可以主動把握緣分的一天。", "今天，能向緣分伸出手的一天。"],
              "challenging": ["今天，不貪心、接住來到面前的一天。", "今天，與其抓取、不如迎接的一天。"]},
        "官殺": {"favorable": ["今天，挺直背脊、自然調整的一天。", "今天，講道理就能前進的一天。"],
                "challenging": ["今天，不勉強推進、靜靜守住的一天。", "今天，先不決定、等待的一天。"]},
        "印": {"favorable": ["今天，接收、被填滿的一天。", "今天，可以依靠他人的一天。"],
              "challenging": ["今天，不過度索求、靜待的一天。", "今天，整理內在的一天。"]},
    },
    "en": {
        "比劫": {"favorable": ["A day you can move on your own feet.", "A day to take a step without hesitation."],
                "challenging": ["A day to not carry it all — let others share.", "A day to ease off the strain."]},
        "食傷": {"favorable": ["A day where putting it out and moving flows.", "The more you express, the more it settles."],
                "challenging": ["A day to keep some in reserve, not spend it all.", "A day to quietly put things away."]},
        "財": {"favorable": ["A day you can reach for the meetings that come.", "A day to extend your hand to a connection."],
              "challenging": ["A day to receive what comes, without grasping.", "A day to welcome rather than seize."]},
        "官殺": {"favorable": ["A day to straighten your back and settle.", "A day where order carries you forward."],
                "challenging": ["A day to quietly hold, not push.", "A day to wait without deciding."]},
        "印": {"favorable": ["A day to receive and be filled.", "A day it's alright to lean on others."],
              "challenging": ["A day to wait without asking too much.", "A day to set your inner self in order."]},
    },
}

FLOW = {
    "ja": {
        "比劫": {"favorable": ["やりたい方へ、まっすぐ進んでよいでしょう。", "自分の判断を信じて動くと、はかどります。"],
                "challenging": ["一人で抱えず、分けると軽くなります。", "張り合わず、流れに任せると楽です。"]},
        "食傷": {"favorable": ["頭で考えるより、手を動かして形にすると流れます。", "思いついたことを、外に出してみる。"],
                "challenging": ["出しすぎると疲れます。一つに絞って。", "今日は仕上げず、寝かせてよい。"]},
        "財": {"favorable": ["来たきっかけは、受け止めてよいでしょう。ただ焦らずに。", "現実的な一手が実りやすい日です。"],
              "challenging": ["追いかけず、向こうから来るのを待つと整います。", "数字やお金は、静かに確認だけしておく。"]},
        "官殺": {"favorable": ["やるべきことを淡々と。整えるほど前に進みます。", "型を守ると、かえって自由になれる日です。"],
                "challenging": ["押すと止まりやすい日。大きな決めごとは一晩おいて。", "守りを固めるだけで、十分な日です。"]},
        "印": {"favorable": ["人や情報から、必要なものが入ってきます。素直に受け取る。", "学びや休息が、あとで効いてきます。"],
              "challenging": ["求めるより、整えて待つ。今は充電の時。", "焦らず、静けさの中にいてよい日です。"]},
    },
    "zh": {
        "比劫": {"favorable": ["朝想做的方向，直直前進就好。", "相信自己的判斷去做，會很順手。"],
                "challenging": ["別一個人扛，分擔出去會輕鬆。", "不去較勁，順著流走會比較自在。"]},
        "食傷": {"favorable": ["與其多想，不如動手做成形，會更順。", "把想到的，試著拿出來。"],
                "challenging": ["做太多會累，收斂到一件就好。", "今天不必完成，先放著也可以。"]},
        "財": {"favorable": ["來到的機會，接住就好，但別著急。", "務實的一步，今天容易有結果。"],
              "challenging": ["不追逐，等它自己過來會更順。", "數字與金錢，靜靜確認就好。"]},
        "官殺": {"favorable": ["該做的事，平淡地做。越整理越前進。", "守住規矩，今天反而更自由。"],
                "challenging": ["越推越容易停的一天。大事先擱一晚。", "今天，只要守穩就足夠。"]},
        "印": {"favorable": ["需要的，會從人或資訊進來。坦然接收。", "學習與休息，之後會發揮作用。"],
              "challenging": ["與其索求，不如整理後等待。現在是充電。", "別急，待在安靜裡也很好。"]},
    },
    "en": {
        "比劫": {"favorable": ["You may go straight toward what you want to do.", "Trust your own judgment, and it moves along."],
                "challenging": ["Don't carry it alone; sharing lightens it.", "Rather than contend, let it flow — it's easier."]},
        "食傷": {"favorable": ["Rather than think, shape it with your hands.", "Try putting what you thought of into the open."],
                "challenging": ["Putting out too much tires you. Narrow to one.", "No need to finish today; you may let it rest."]},
        "財": {"favorable": ["The chance that came, you may receive — just don't rush.", "A practical move is likely to bear fruit today."],
              "challenging": ["Rather than chase, wait for it to come.", "Money and numbers — just check them quietly."]},
        "官殺": {"favorable": ["Do what should be done, calmly. Order moves you on.", "Keeping to form, you become freer today."],
                "challenging": ["A day pushing tends to stall. Sleep on big calls.", "Just holding your ground is enough today."]},
        "印": {"favorable": ["What you need comes from people and news. Receive it.", "Learning and rest take effect later."],
              "challenging": ["Rather than seek, set things in order and wait.", "Don't rush; it's fine to stay in the quiet."]},
    },
}

EN_HITO = {
    "ja": {
        "harmony": ["人との縁が和らぐ日。素直に頼ってよい。", "つながりが心地よく動く日です。"],
        "clash": ["人間関係が動きやすい日。言葉は少なめに、丁寧に。", "揺れが出やすい日。一呼吸おいてから返す。"],
        "friction": ["小さな行き違いが出やすい日。急がず確かめて。", "細かなすれ違いに注意。早とちりをしない。"],
        "calm": ["対人は穏やか。いつも通りでいい。", "人との間は、静かに保たれます。"],
    },
    "zh": {
        "harmony": ["與人的緣分變柔和的一天，可以坦然依靠。", "關係今天舒服地流動。"],
        "clash": ["人際容易有變動的一天，話少一點、客氣些。", "容易起波動的一天，深呼吸後再回應。"],
        "friction": ["容易有小誤會的一天，別急、確認清楚。", "注意細微的擦身，別太早下結論。"],
        "calm": ["人際平穩，照平常就好。", "與人之間，今天靜靜維持著。"],
    },
    "en": {
        "harmony": ["A day bonds soften. You may lean on others honestly.", "Connections move comfortably today."],
        "clash": ["A day relationships shift. Keep words few and gentle.", "A day prone to waver. Breathe before you reply."],
        "friction": ["A day small misunderstandings arise. Don't rush; confirm.", "Watch for little crossed wires. Don't jump ahead."],
        "calm": ["With people, calm. As usual is fine.", "The space between you and others stays quiet."],
    },
}

TOTONOE = {
    "ja": {
        "比劫": {"favorable": ["やると決めた一つを、今日進める。"], "challenging": ["人に一つ、お願いしてみる。"]},
        "食傷": {"favorable": ["作りかけを一つ、外に出す。"], "challenging": ["手を止めて、休む時間を取る。"]},
        "財": {"favorable": ["欲張らず、一つだけ取る。"], "challenging": ["お金と数字を、静かに見直す。"]},
        "官殺": {"favorable": ["身のまわりを整え、段取りを一つ決める。"], "challenging": ["大きな決断は、今日はしない。"]},
        "印": {"favorable": ["学びや情報を一つ、取り入れる。"], "challenging": ["感謝を、ひとつ言葉にする。"]},
    },
    "zh": {
        "比劫": {"favorable": ["把決定要做的那一件，今天推進。"], "challenging": ["試著拜託別人一件事。"]},
        "食傷": {"favorable": ["把做到一半的，拿一個出來。"], "challenging": ["停下手，留點休息的時間。"]},
        "財": {"favorable": ["不貪心，只取一個。"], "challenging": ["靜靜地重看金錢與數字。"]},
        "官殺": {"favorable": ["整理周遭，定下一個步驟。"], "challenging": ["重大的決定，今天先不做。"]},
        "印": {"favorable": ["吸收一個學習或資訊。"], "challenging": ["把一份感謝，說出口。"]},
    },
    "en": {
        "比劫": {"favorable": ["Move the one thing you decided on, today."], "challenging": ["Try asking one person for one thing."]},
        "食傷": {"favorable": ["Put out one of the things you've half-made."], "challenging": ["Stop your hands and take time to rest."]},
        "財": {"favorable": ["Don't be greedy; take just one."], "challenging": ["Quietly review your money and numbers."]},
        "官殺": {"favorable": ["Tidy your surroundings and decide one step."], "challenging": ["Don't make big decisions today."]},
        "印": {"favorable": ["Take in one piece of learning or news."], "challenging": ["Put one gratitude into words."]},
    },
}

CLOSING = {
    "ja": {
        "比劫": ["急がず、しかし止まらず。"], "食傷": ["出すことで、巡りはじめる。"],
        "財": ["つかむより、迎え入れる。"], "官殺": ["止まって見えるのは、整えている時間。"],
        "印": ["受け取ることも、進むことのうち。"],
    },
    "zh": {
        "比劫": ["不急，但也不停。"], "食傷": ["因為釋出，才開始流轉。"],
        "財": ["與其抓取，不如迎接。"], "官殺": ["看似停下，其實是在整理的時間。"],
        "印": ["接收，也是前進的一種。"],
    },
    "en": {
        "比劫": ["Don't hurry, but don't stop."], "食傷": ["By putting out, the flow begins."],
        "財": ["Rather than grasp, welcome."], "官殺": ["What looks stopped is time spent ordering."],
        "印": ["Receiving, too, is part of moving forward."],
    },
}

_TIMING_ZH = {"午前": "上午", "午後": "下午", "夜": "夜晚", "日中": "白天"}
_TIMING_EN = {"午前": "morning", "午後": "afternoon", "夜": "evening", "日中": "daytime"}
_FOOTER = {
    "ja": "これは娯楽・自己内省のための目安です。断定するものではありません。方位は簡易計算の参考です。",
    "zh": "這是供娛樂、自我省思的參考，並非斷定。方位為簡易計算的參考。",
    "en": "This is a guide for entertainment and self-reflection, not a judgment. Directions are a rough reference.",
}


def _pick(variants, seed):
    return variants[seed % len(variants)]


def compose(m, lang="ja"):
    """build_flow の素材 → 整った『今日の理』カード（lang で言語切替）。"""
    if lang not in OPENING:
        lang = "ja"
    g, fav, brel, seed = m["group"], m["favor"], m["branch_rel"], m["seed"]
    if lang == "zh":
        prefix = "別急，" if brel == "clash" else ""
        ugoki = "%s若要行動，%s較沉穩。" % (prefix, _TIMING_ZH[m["timing"]])
    elif lang == "en":
        prefix = "Don't rush — " if brel == "clash" else ""
        ugoki = "%sIf you move, the %s is calmer." % (prefix, _TIMING_EN[m["timing"]])
    else:
        prefix = "急がず、" if brel == "clash" else ""
        ugoki = "%sもし動くなら、%sが落ち着きます。" % (prefix, m["timing"])
    return {
        "date": m["date"],
        "honmei_star": m["honmei_star"],
        "ten_god": m["ten_god"],
        "opening": _pick(OPENING[lang][g][fav], seed),
        "flow": _pick(FLOW[lang][g][fav], seed + 1),
        "en_hito": _pick(EN_HITO[lang][brel], seed + 2),
        "ugoki": ugoki,
        "totonoe": _pick(TOTONOE[lang][g][fav], seed + 3),
        "closing": _pick(CLOSING[lang][g], seed + 4),
        "footer": _FOOTER[lang],
    }


def render_text(card):
    """投稿・プレビュー用のプレーンテキスト（ローカル確認用）。"""
    lines = [
        "｜今日の理｜　%s" % card["date"], "",
        card["opening"], "",
        "◦ 流れ　… %s" % card["flow"],
        "◦ 縁・人 … %s" % card["en_hito"],
        "◦ 動き　… %s" % card["ugoki"],
        "◦ 整える … %s" % card["totonoe"], "",
        card["closing"], "",
        "（%s）" % card["footer"],
    ]
    return "\n".join(lines)


def build_card(birth, date, lang="ja"):
    """生年月日・対象日 → 一人ひとり別の『今日の理』カード（lang で言語切替）。"""
    return compose(build_flow(birth, date), lang)
