# -*- coding: utf-8 -*-
"""整った『今日の理』カードを表示し、禁止表現チェックを通す（Day 3-4）。
使い方:
  python demo_card.py                      （サンプル：1970/1/19 → 2026/6/18）
  python demo_card.py 1970 1 19 2026 6 18
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from engine import build_card, render_text, check_text


def main(argv):
    if len(argv) >= 7:
        birth = (int(argv[1]), int(argv[2]), int(argv[3]))
        date = (int(argv[4]), int(argv[5]), int(argv[6]))
    else:
        birth = (1970, 1, 19)
        date = (2026, 6, 18)
        print("（サンプル：生年月日=1970/1/19、対象日=2026/6/18）\n")

    card = build_card(birth, date)
    text = render_text(card)
    print(text)

    print("\n" + "=" * 40)
    # 自己点検：このカードに禁止表現が無いか
    hits = check_text(text)
    print("[禁止表現チェック]", "OK（クリーン）" if not hits else hits)

    # 14日連続で回しても全部クリーンか（型が崩れないことの確認）
    all_clean = all(
        not check_text(render_text(build_card(birth, (2026, 6, d))))
        for d in range(18, 31)
    )
    print("[6/18〜6/30 連続チェック] 全日クリーン:", all_clean)

    # 検知テスト：わざと悪い文を入れて、ちゃんと弾けるか
    bad = "今すぐ買わないと絶対に不幸になります。必ず大儲け。"
    print("[検知テスト] 悪い例 →", check_text(bad))


if __name__ == "__main__":
    main(sys.argv)
