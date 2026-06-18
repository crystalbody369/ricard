# -*- coding: utf-8 -*-
"""『今日の理』カード画像を生成する（Day 5-6）。
使い方:
  python gen_cards.py                      （サンプル：1970/1/19 → 2026/6/18）
  python gen_cards.py 1970 1 19 2026 6 18
出力: data/card_morning.png / card_sumi.png / card_night.png
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from engine.card_image import generate


def main(argv):
    if len(argv) >= 7:
        birth = (int(argv[1]), int(argv[2]), int(argv[3]))
        date = (int(argv[4]), int(argv[5]), int(argv[6]))
    else:
        birth = (1970, 1, 19)
        date = (2026, 6, 18)
        print("（サンプル：生年月日=1970/1/19、対象日=2026/6/18）")

    paths = generate(birth, date, "data")
    print("生成しました:")
    for p in paths:
        print(" -", p)


if __name__ == "__main__":
    main(sys.argv)
