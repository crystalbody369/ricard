# -*- coding: utf-8 -*-
"""『今日の理』カードを縦3:4の美しい画像にする（Pillow・完全ローカル）。
背景はプログラムで上品に描く（外部AI画像生成なし＝即・無料・データ非送信）。
游明朝で静かな明朝の佇まい。SNSのストーリーズにそのまま貼れる縦型。"""

import os
from PIL import Image, ImageDraw, ImageFont

from .voice import build_card

# 同梱フォント（Shippori明朝・OFL）。Windows/Linux どちらでも動く＝本番(Render)でもOK。
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
F_SERIF = os.path.join(FONT_DIR, "ShipporiMincho-Regular.ttf")
F_SERIF_DB = os.path.join(FONT_DIR, "ShipporiMincho-Bold.ttf")
F_TC = os.path.join(FONT_DIR, "NotoSerifTC.ttf")  # 繁體中文用（OFL）

W, H = 1080, 1440
MARGIN = 110
CONTENT_W = W - MARGIN * 2

# 3つの世界観
STYLES = {
    "morning": {  # 朝の光（暖かいクリーム）
        "bg_top": (251, 246, 236), "bg_bottom": (242, 229, 205),
        "text": (58, 50, 42), "label": (150, 124, 88), "accent": (178, 138, 78),
        "closing": (120, 104, 80), "footer": (158, 146, 124), "motif": None,
    },
    "sumi": {  # 墨と余白（静かな白）
        "bg_top": (247, 246, 242), "bg_bottom": (235, 233, 226),
        "text": (43, 43, 40), "label": (124, 120, 110), "accent": (60, 76, 92),
        "closing": (92, 90, 84), "footer": (158, 156, 146), "motif": "enso",
    },
    "night": {  # 夜（深い藍）
        "bg_top": (26, 32, 46), "bg_bottom": (44, 54, 74),
        "text": (238, 231, 215), "label": (156, 165, 183), "accent": (201, 168, 103),
        "closing": (203, 196, 178), "footer": (120, 128, 146), "motif": "moon",
    },
}


def _font(path, size):
    return ImageFont.truetype(path, size)


def _vgrad(top, bottom):
    img = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


def _motif(img, kind, style):
    """うっすらとした意匠（円相／月と星）。主張しすぎない。"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if kind == "enso":  # 円相（手描き風の薄い円）
        r = 330
        cx, cy = W // 2, 660
        col = (180, 176, 164, 60)
        od.arc([cx - r, cy - r, cx + r, cy + r], start=20, end=340, fill=col, width=14)
    elif kind == "moon":  # 月と星
        od.ellipse([W - 320, 150, W - 160, 310], fill=(230, 224, 206, 28))
        for (x, y, s) in [(180, 230, 3), (300, 180, 2), (240, 360, 2),
                          (W - 420, 420, 2), (160, 520, 2), (W - 240, 560, 3)]:
            od.ellipse([x - s, y - s, x + s, y + s], fill=(235, 230, 215, 120))
    img.alpha_composite(overlay)
    return img


def _wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) <= maxw:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def _center_block(draw, y, text, font, fill, maxw, leading):
    for line in _wrap(draw, text, font, maxw):
        w = draw.textlength(line, font=font)
        draw.text(((W - w) / 2, y), line, font=font, fill=fill)
        y += int(font.size * leading)
    return y


def _left_block(draw, x, y, text, font, fill, maxw, leading):
    for line in _wrap(draw, text, font, maxw):
        draw.text((x, y), line, font=font, fill=fill)
        y += int(font.size * leading)
    return y


def render_view(view, style_name="morning", lang="ja"):
    st = STYLES[style_name]
    base = _vgrad(st["bg_top"], st["bg_bottom"]).convert("RGBA")
    if st["motif"]:
        base = _motif(base, st["motif"], st)
    draw = ImageDraw.Draw(base)

    serif = F_TC if lang == "zh" else F_SERIF
    serif_db = F_TC if lang == "zh" else F_SERIF_DB
    f_title = _font(serif, 30)
    f_date = _font(serif, 26)
    f_open = _font(serif_db, 60)
    f_label = _font(serif_db, 27)
    f_body = _font(serif, 37)
    f_close = _font(serif, 38)
    f_foot = _font(serif, 20)
    f_mark = _font(serif, 25)

    # 見出し「今日の理」＋日付
    y = 96
    t = view.get("subtitle", "今 日 の 理")
    w = draw.textlength(t, font=f_title)
    draw.text(((W - w) / 2, y), t, font=f_title, fill=st["label"])
    y += 46
    w = draw.textlength(view["date"], font=f_date)
    draw.text(((W - w) / 2, y), view["date"], font=f_date, fill=st["label"])
    y += 44
    draw.line([(W / 2 - 36, y), (W / 2 + 36, y)], fill=st["accent"], width=2)
    y += 70

    # 一言（フック）
    y = _center_block(draw, y, view["opening"].rstrip("。"), f_open, st["text"], CONTENT_W, 1.3)
    y += 56

    # セクション（ビューから）
    sections = view["sections"]
    for label, text in sections:
        draw.text((MARGIN, y), label, font=f_label, fill=st["accent"])
        y += 42
        y = _left_block(draw, MARGIN, y, text, f_body, st["text"], CONTENT_W, 1.5)
        y += 34

    # 結び
    y += 14
    y = _center_block(draw, y, view["closing"], f_close, st["closing"], CONTENT_W, 1.4)

    # フッター（注記：句点ごとに改行して末尾の孤立を防ぐ）＋ブランド
    foot = [s + "。" for s in view["footer"].split("。") if s.strip()]
    fy = H - 64 - 28 * len(foot)
    for line in foot:
        w = draw.textlength(line, font=f_foot)
        draw.text(((W - w) / 2, fy), line, font=f_foot, fill=st["footer"])
        fy += 28
    mark = view.get("mark", "気 づ き")
    w = draw.textlength(mark, font=f_mark)
    draw.text(((W - w) / 2, H - 56), mark, font=f_mark, fill=st["label"])

    return base.convert("RGB")


_DAILY_L = {
    "ja": {"subtitle": "今 日 の 理", "mark": "Kizuki",
           "labels": ["流れ", "縁・人", "動き", "整える"]},
    "zh": {"subtitle": "今 日 之 理", "mark": "Kizuki",
           "labels": ["流動", "緣分", "行動", "整理"]},
}


def daily_view(card, lang="ja"):
    """個人の『今日の理』カードを描画用ビューに変換（lang で言語切替）。"""
    L = _DAILY_L.get(lang, _DAILY_L["ja"])
    return {
        "subtitle": L["subtitle"],
        "date": card["date"],
        "opening": card["opening"],
        "sections": [
            (L["labels"][0], card["flow"]),
            (L["labels"][1], card["en_hito"]),
            (L["labels"][2], card["ugoki"]),
            (L["labels"][3], card["totonoe"]),
        ],
        "closing": card["closing"],
        "mark": L["mark"],
        "footer": card["footer"],
    }


def render(card, style_name="morning", lang="ja"):
    """個人カードを描画（互換ラッパー）。"""
    return render_view(daily_view(card, lang), style_name, lang)


def generate(birth, date, outdir, styles=None):
    """3:4カードを各スタイルで生成し、保存先パスのリストを返す。"""
    card = build_card(birth, date)
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for name in (styles or list(STYLES.keys())):
        img = render(card, name)
        p = os.path.join(outdir, "card_%s.png" % name)
        img.save(p)
        paths.append(p)
    return paths
