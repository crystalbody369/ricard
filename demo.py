# -*- coding: utf-8 -*-
"""占術エンジンの動作確認（Day 1-2）。
生年月日と対象日を渡すと、今日の流れの“素材”をJSONで表示する。
使い方:
  python demo.py                      （サンプルで実行）
  python demo.py 1976 9 15 2026 6 18  （生年=1976/9/15、対象日=2026/6/18）
"""
import sys
import json

# Windowsのコンソール（cp950等）でも日本語/中国語を出せるようにする
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from engine import build_flow


def main(argv):
    if len(argv) >= 7:
        by, bm, bd = int(argv[1]), int(argv[2]), int(argv[3])
        dy, dm, dd = int(argv[4]), int(argv[5]), int(argv[6])
        birth = (by, bm, bd)
        date = (dy, dm, dd)
    else:
        # サンプル：生年月日 1976/9/15、対象日 2026/6/18
        birth = (1976, 9, 15)
        date = (2026, 6, 18)
        print("（サンプル実行：生年月日=1976/9/15、対象日=2026/6/18）\n")

    result = build_flow(birth, date)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 読みやすい要約も表示
    s = result["sections"]
    print("\n--- 素材の要約（このあと『理の声』で整える） ---")
    print("本命星 :", result["honmei_star"], " / 今日の干支:", result["day_pillar"],
          " / 関係:", result["relation"])
    print("今日の流れ:", s["flow"])
    print("縁・人   :", s["en_hito"])
    print("動き     :", s["ugoki"]["direction"], "／", s["ugoki"]["timing"])
    print("整える   :", " ・ ".join(s["totonoe"]))


if __name__ == "__main__":
    main(sys.argv)
