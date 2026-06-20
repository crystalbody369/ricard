# -*- coding: utf-8 -*-
"""理カード — 誰でも自分のカードを作れるモバイルWeb（＋縁モード）。
Flask。カード画像はサーバー側でローカル生成して返す（外部送信なし）。

起動:
  python app.py
  → http://127.0.0.1:5390/
"""
import io
import os
import sys
import json
import secrets
import datetime
from functools import wraps
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from flask import (Flask, request, send_file, abort, Response, jsonify,
                   session, redirect)
from markupsafe import escape

from engine.voice import build_card
from engine.card_image import render, render_view
from engine.en import build_en
from engine.flow import build_detail
from engine.ri_consult import consult
from engine import store
from engine import auth
from engine import mailer

CONSULT_MAX_CHARS = 500   # 入力の蓋（コスト上限を固定する）
CONSULT_SIT_CHARS = 300   # 気持ち・状況欄の上限

# 課金（買い切りの回数パック）
FREE_CONSULTS = int(os.environ.get("RICARD_FREE_CONSULTS", "3"))   # 無料お試し回数
PACK_PRICE = int(os.environ.get("RICARD_PACK_PRICE", "500"))       # パック価格(円)
PACK_CREDITS = int(os.environ.get("RICARD_PACK_CREDITS", "30"))    # 1パックの回数
PACK_NAME = "理カード 相談%d回パック" % PACK_CREDITS
CONSULT_IP_DAILY = 10     # サーバー側の最終防衛：1IP/1日の相談回数（端末側3回とは別の網）


def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")   # Render はプロキシ越し
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr) or "unknown"


def _ip_over_limit(ip):
    return store.count_today("ip:" + ip) >= CONSULT_IP_DAILY   # 永続カウント


def _ip_bump(ip):
    store.bump("ip:" + ip)

app = Flask(__name__)

# 認証テーブル準備＋セッション鍵（DBに保存して再起動でも一定＝ログイン維持）
auth.init_auth()


def _secret_key():
    env = os.environ.get("RICARD_SECRET_KEY", "").strip()
    if env:
        return env
    return store.get_or_create_setting("secret_key", secrets.token_hex(32))


app.secret_key = _secret_key()
app.permanent_session_lifetime = datetime.timedelta(days=30)


def _current_user():
    """セッションのユーザーが今も有効か毎回確認（即停止・期限切れを効かせる）。"""
    u = session.get("user")
    if not u:
        return None
    st = auth.check_active(u)
    if not st["ok"]:
        session.clear()
        return None
    return {"username": u, "is_admin": st["is_admin"]}


def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not _current_user():
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "text": "ログインが必要です。"}), 401
            return redirect("/login")
        return f(*a, **kw)
    return wrap


def admin_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        u = _current_user()
        if not u or not u["is_admin"]:
            return redirect("/login")
        return f(*a, **kw)
    return wrap


def _parse(s):
    y, m, d = s.split("-")
    return (int(y), int(m), int(d))


PAGE = """<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>理カード</title>
<style>
  :root{ --bg:#fbf6ec; --bg2:#f3e7d0; --ink:#3a322a; --sub:#8a7b63; --gold:#b08a4e; --line:#e4d8c2; }
  *{ box-sizing:border-box; }
  body{ margin:0; background:linear-gradient(#fbf6ec,#f3e7d0); color:var(--ink);
        font-family:"Yu Mincho","YuMincho","Hiragino Mincho ProN",serif;
        -webkit-font-smoothing:antialiased; }
  .wrap{ max-width:520px; margin:0 auto; padding:28px 20px 60px; }
  h1{ font-size:30px; font-weight:500; text-align:center; letter-spacing:.3em; margin:8px 0 4px; }
  .tag{ text-align:center; color:var(--sub); font-size:14px; margin:0 0 26px; letter-spacing:.06em; }
  .card{ background:#fffdf8; border:1px solid var(--line); border-radius:16px; padding:22px 20px; margin:0 0 22px; }
  .card h2{ font-size:18px; font-weight:500; margin:0 0 14px; letter-spacing:.12em; }
  label{ display:block; font-size:13px; color:var(--sub); margin:10px 0 4px; }
  input[type=date], input[type=time], input[type=text]{ width:100%; padding:12px 14px; font-size:16px; border:1px solid var(--line);
        border-radius:10px; background:#fff; color:var(--ink); font-family:inherit; }
  button{ width:100%; margin-top:16px; padding:13px; font-size:16px; font-family:inherit;
        color:#fff; background:var(--ink); border:none; border-radius:10px; letter-spacing:.1em; cursor:pointer; }
  button.ghost{ background:transparent; color:var(--ink); border:1px solid var(--ink); }
  .row{ display:flex; gap:10px; }
  .row button{ flex:1; }
  .result{ margin-top:18px; text-align:center; }
  .result img{ width:100%; border-radius:14px; box-shadow:0 6px 24px rgba(80,60,30,.12); display:none; }
  .note{ font-size:13px; color:var(--sub); text-align:center; margin:6px 0 0; }
  .banner{ background:#fff5e0; border:1px solid #ecd9a8; color:#8a6a2a; font-size:14px;
        border-radius:10px; padding:10px 12px; margin:0 0 16px; display:none; }
  .foot{ text-align:center; color:var(--sub); font-size:12px; line-height:1.8; margin-top:30px; }
  .hidden{ display:none; }
  .detail{ display:none; text-align:left; background:#fffaf0; border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-top:12px; font-size:13px; line-height:1.8; }
  .detail table{ width:100%; border-collapse:collapse; margin:6px 0; }
  .detail td{ padding:3px 0; vertical-align:top; }
  .detail td.k{ color:var(--sub); width:46%; }
  .detail .how{ margin-top:8px; }
  .detail .note{ color:var(--sub); font-size:12px; margin-top:8px; }
  .settings{ background:#fffaf0; border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-bottom:6px; }
  select{ width:100%; padding:12px 14px; font-size:16px; border:1px solid var(--line); border-radius:10px; background:#fff; color:var(--ink); font-family:inherit; }
  textarea{ width:100%; padding:12px 14px; font-size:16px; border:1px solid var(--line); border-radius:10px; background:#fff; color:var(--ink); font-family:inherit; resize:vertical; line-height:1.7; }
  .exchip{ font-size:13px; line-height:1.5; text-align:left; padding:8px 12px; border:1px solid var(--line);
           border-radius:999px; background:#fffaf0; color:var(--ink); cursor:pointer; font-family:inherit;
           width:auto; margin:0; transition:background .15s; }
  .exchip:hover{ background:#f6edda; border-color:var(--gold); }
  .exmodal{ position:fixed; inset:0; background:rgba(40,30,15,.45); z-index:50; display:flex;
            align-items:center; justify-content:center; padding:16px; }
  .exbox{ background:#fffdf8; border:1px solid var(--line); border-radius:14px; max-width:520px; width:100%;
          max-height:85vh; overflow-y:auto; padding:22px 20px 20px; position:relative; text-align:left; }
  .exclose{ position:absolute; top:8px; right:10px; width:auto; margin:0; padding:4px 10px; font-size:22px;
            line-height:1; background:none; border:none; color:var(--sub); cursor:pointer; }
  .exfree{ font-size:12.5px; color:var(--gold); background:#fbf3df; border-radius:8px; padding:8px 10px; margin:4px 0 14px; }
  .exlbl{ font-size:12.5px; color:var(--sub); margin:14px 0 4px; font-weight:600; }
  .extext{ font-size:14px; line-height:1.85; color:var(--ink); background:#fff; border:1px solid var(--line);
           border-radius:10px; padding:11px 13px; white-space:pre-wrap; }
  .exans{ background:#fbf7ee; }
  .ccount{ font-size:12px; color:var(--sub); text-align:right; margin:6px 2px 0; }
  .ccount #cremain{ color:var(--gold); }
  .card h2{ display:flex; align-items:center; }
  .gear{ width:auto; margin-left:auto; padding:5px 12px; font-size:13px; background:transparent; color:var(--sub); border:1px solid var(--line); letter-spacing:0; }
  .langsw{ text-align:center; margin:0 0 22px; }
  .lang{ width:auto; margin:0 4px; padding:4px 14px; font-size:13px; background:transparent; color:var(--sub); border:1px solid var(--line); letter-spacing:0; }
</style>
</head><body>
<div class="wrap">
  <h1 data-i18n="h1">理カード</h1>
  <p class="tag" data-i18n="tag">今日を、当てずに整える。</p>
  <div class="langsw">
    <button class="lang" onclick="setLang('ja')">日本語</button>
    <button class="lang" onclick="setLang('zh')">繁體</button>
    <button class="lang" onclick="setLang('cn')">简体</button>
    <button class="lang" onclick="setLang('en')">English</button>
  </div>

  <div class="banner" id="banner"></div>

  <div class="card">
    <h2><span data-i18n="h2today">今日の理</span><button class="gear" onclick="toggleSettings()" data-i18n="gear">⚙ 設定</button></h2>
    <div id="settings" class="settings">
      <label data-i18n="lblbirth">あなたの生年月日</label>
      <input type="date" id="me" min="1900-01-01" max="2025-12-31">
      <label data-i18n="lbltime">生まれた時間（わかれば・任意）</label>
      <input type="time" id="metime">
      <label data-i18n="lblgender">性別（大運の計算に使用・任意）</label>
      <select id="gender"><option value="" data-i18n="optnone">選ばない</option><option value="m" data-i18n="optm">男性</option><option value="f" data-i18n="optf">女性</option></select>
      <label data-i18n="lblemail">メールアドレス（パスワード再設定に使用）</label>
      <input type="text" id="myemail" autocomplete="email" placeholder="you@example.com">
      <button onclick="saveAndShow()" data-i18n="btnsave">保存して今日の理を見る</button>
    </div>
    <div class="result">
      <img id="cardImg" alt="今日の理カード">
      <div class="row hidden" id="cardBtns">
        <button class="ghost" onclick="saveImg('cardImg','riicard_today.png')" data-i18n="btnsaveimg">画像を保存</button>
        <button onclick="shareImg('cardImg','riicard_today.png')" data-i18n="btnshare">シェア</button>
      </div>
      <button class="ghost hidden" id="detailBtn" style="margin-top:10px" onclick="showDetail()" data-i18n="btndetail">詳細（何をもとに占ってる？）</button>
      <div id="detail" class="detail"></div>
    </div>
  </div>

  <div class="card">
    <h2 data-i18n="h2en">二人の縁</h2>
    <label data-i18n="lblpartner">お相手の生年月日（あなたの分は「今日の理」の設定から）</label>
    <input type="date" id="enB" min="1900-01-01" max="2025-12-31">
    <button onclick="showEn()" data-i18n="btnen">二人の縁を見る</button>
    <button class="ghost" onclick="copyInvite()" data-i18n="btninvite">この縁を相手に送る</button>
    <div class="result">
      <img id="enImg" alt="二人の縁カード">
      <div class="row hidden" id="enBtns">
        <button class="ghost" onclick="saveImg('enImg','riicard_en.png')" data-i18n="btnsaveimg">画像を保存</button>
        <button onclick="shareImg('enImg','riicard_en.png')" data-i18n="btnshare">シェア</button>
      </div>
    </div>
  </div>

  <div class="card">
    <h2 data-i18n="h2consult">理に相談する</h2>
    <p class="note" style="text-align:left; margin:0 0 10px" data-i18n="consultlead">気になった出来事を書くと、理の視点で静かに観ます。当てるのではなく、整えるために。</p>
    <div id="cexamples" style="margin:0 0 10px">
      <p class="note" style="text-align:left;margin:0 0 6px" data-i18n="cexlead">はじめての方へ — どう書けばいい？ 見本を見る（無料・相談は消費しません）：</p>
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        <button type="button" class="exchip" onclick="showExample(0)"></button>
        <button type="button" class="exchip" onclick="showExample(1)"></button>
        <button type="button" class="exchip" onclick="showExample(2)"></button>
      </div>
    </div>
    <div id="exmodal" class="exmodal" style="display:none" onclick="if(event.target===this)closeExample()">
      <div class="exbox">
        <button type="button" class="exclose" onclick="closeExample()" aria-label="close">×</button>
        <p class="exfree" data-i18n="exfree">これは「書き方の見本」です。表示しても無料回数は減りません。</p>
        <div class="exlbl" data-i18n="exlblev">こう書きます（気になった出来事）</div>
        <div id="exev" class="extext"></div>
        <div class="exlbl" data-i18n="exlblsit">こう書きます（今の気持ち・状況）</div>
        <div id="exsit" class="extext"></div>
        <div class="exlbl" data-i18n="exlblans">こう観てもらえます（回答の一例）</div>
        <div id="exans" class="extext exans"></div>
        <button type="button" id="exuse" onclick="useExample()" data-i18n="exuse">この例を入力欄に入れて、自分で書き換える</button>
      </div>
    </div>
    <textarea id="cevent" maxlength="500" rows="3" data-ph="cplaceholder" oninput="qs('cchars').textContent=this.value.length" placeholder="例：道に鳥が死んでいた。朝、大きな雲を見た。古い友人に偶然会った。"></textarea>
    <div class="ccount"><span id="cchars">0</span>/500　<span id="cremain"></span></div>
    <label data-i18n="csitlabel" style="margin-top:10px">今の気持ち・状況・取り組んでいること（任意）</label>
    <textarea id="csituation" maxlength="300" rows="2" data-ph="csitph" placeholder="例：新しい仕事を始めたばかりで不安。いろいろ手を広げて落ち着かない。"></textarea>
    <p class="note" style="text-align:left;margin:4px 0 0" data-i18n="csithint">※気持ちや状況も書くほど、あなたに合った観方になります。</p>
    <button onclick="askConsult()" id="cbtn" data-i18n="btnconsult">理に観てもらう</button>
    <p class="note" style="text-align:left" data-i18n="consultprivacy">※入力した文章はAI（Claude）に送られ、回答を作ります。文章は保存しません。</p>
    <button class="ghost hidden" id="cbuy" onclick="buyCredits()" data-i18n="btnbuy" style="margin-top:8px">クレジットを購入（30回 ¥500）</button>
    <div id="cresult" class="detail" style="white-space:pre-wrap; line-height:1.9;"></div>
  </div>

  <p class="foot" data-i18n="foot">これは娯楽・自己内省のための目安です。当たり外れを決めるものではありません。</p>
  <p class="foot" style="margin-top:6px">運営：栄宏ライフ株式会社（Ahiro Life Co., Ltd.）</p>
  <p class="foot" style="margin-top:10px"><a href="/logout" style="color:var(--gold)" data-i18n="logout">ログアウト</a><!--ACCT--></p>
</div>

<script>
function qs(id){ return document.getElementById(id); }

var I18N = {
  ja: {h1:'理カード', tag:'今日を、当てずに整える。', h2today:'今日の理', gear:'⚙ 設定',
       lblbirth:'あなたの生年月日', lbltime:'生まれた時間（わかれば・任意）', lblgender:'性別（大運の計算に使用・任意）',
       lblemail:'メールアドレス（パスワード再設定に使用）',
       optnone:'選ばない', optm:'男性', optf:'女性', btnsave:'保存して今日の理を見る',
       btnsaveimg:'画像を保存', btnshare:'シェア', btndetail:'詳細（何をもとに占ってる？）',
       h2en:'二人の縁', lblpartner:'お相手の生年月日（あなたの分は「今日の理」の設定から）',
       btnen:'二人の縁を見る', btninvite:'この縁を相手に送る',
       h2consult:'理に相談する', consultlead:'気になった出来事を書くと、理の視点で静かに観ます。当てるのではなく、整えるために。',
       cplaceholder:'例：道に鳥が死んでいた。朝、大きな雲を見た。古い友人に偶然会った。',
       btnconsult:'理に観てもらう', consultprivacy:'※入力した文章はAI（Claude）に送られ、回答を作ります。文章は保存しません。',
       csitlabel:'今の気持ち・状況・取り組んでいること（任意）', csitph:'例：新しい仕事を始めたばかりで不安。いろいろ手を広げて落ち着かない。',
       csithint:'※気持ちや状況も書くほど、あなたに合った観方になります。', btnbuy:'クレジットを購入（30回 ¥500）',
       cexlead:'はじめての方へ — どう書けばいい？ 見本を見る（無料・相談は消費しません）：',
       exfree:'これは「書き方の見本」です。表示しても無料回数は減りません。',
       exlblev:'こう書きます（気になった出来事）', exlblsit:'こう書きます（今の気持ち・状況）',
       exlblans:'こう観てもらえます（回答の一例）', exuse:'この例を入力欄に入れて、自分で書き換える',
       paidthanks:'ご購入ありがとうございます。回数が追加されました。',
       remain:'残り{n}回', consultempty:'出来事を書いてください。', consultlimit:'今日の無料分（3回）は終わりました。また明日どうぞ。',
       consultwait:'理で観ています…', consultfail:'うまく言葉にできませんでした。少し時間をおいて、もう一度お試しください。',
       logout:'ログアウト',
       foot:'これは娯楽・自己内省のための目安です。当たり外れを決めるものではありません。', detailbase:'占いの土台：'},
  zh: {h1:'理卡', tag:'不為了算準，而是整理今天。', h2today:'今日之理', gear:'⚙ 設定',
       lblbirth:'你的生日', lbltime:'出生時間（若知道・可選）', lblgender:'性別（用於大運計算・可選）',
       lblemail:'電子郵件（用於重設密碼）',
       optnone:'不選', optm:'男', optf:'女', btnsave:'儲存並看今日之理',
       btnsaveimg:'儲存圖片', btnshare:'分享', btndetail:'詳細（依據什麼占算？）',
       h2en:'兩人的緣', lblpartner:'對方的生日（你的從「今日之理」設定）',
       btnen:'看兩人的緣', btninvite:'把這段緣分傳給對方',
       h2consult:'向理諮詢', consultlead:'寫下在意的事，便以理的視角靜靜地觀照。不為算準，而是為了整理。',
       cplaceholder:'例如：路上有隻死掉的鳥。早上看到一大片雲。偶然遇見老朋友。',
       btnconsult:'請理為我觀照', consultprivacy:'※輸入的文字會送往AI（Claude）以產生回應，不會保存文字。',
       csitlabel:'此刻的心情・處境・正在投入的事（可選）', csitph:'例如：剛開始新工作很不安，手伸得太廣靜不下來。',
       csithint:'※越是寫下心情與處境，越能得到貼近你的觀照。', btnbuy:'購買點數（30次 ¥500）',
       cexlead:'第一次使用嗎 — 該怎麼寫？ 看範例（免費・不會消耗諮詢次數）：',
       exfree:'這是「書寫範例」。開啟查看不會減少免費次數。',
       exlblev:'這樣寫（在意的事）', exlblsit:'這樣寫（此刻的心情・處境）',
       exlblans:'會這樣被觀照（回應的一例）', exuse:'把這個範例帶入輸入欄，再自行修改',
       paidthanks:'感謝您的購買，次數已增加。',
       remain:'剩餘{n}次', consultempty:'請先寫下事情。', consultlimit:'今天的免費次數（3次）已用完，明天再來。',
       consultwait:'正以理觀照中…', consultfail:'這次沒能好好回應。請稍後再試一次。',
       logout:'登出',
       foot:'這是供娛樂、自我省思的參考，並非用來斷定準不準。', detailbase:'占算依據：'},
  cn: {h1:'理卡', tag:'不为了算准，而是整理今天。', h2today:'今日之理', gear:'⚙ 设置',
       lblbirth:'你的生日', lbltime:'出生时间（若知道・可选）', lblgender:'性别（用于大运计算・可选）',
       lblemail:'电子邮箱（用于重设密码）',
       optnone:'不选', optm:'男', optf:'女', btnsave:'保存并查看今日之理',
       btnsaveimg:'保存图片', btnshare:'分享', btndetail:'详细（依据什么推算？）',
       h2en:'两人的缘', lblpartner:'对方的生日（你的在「今日之理」设置里填）',
       btnen:'看两人的缘', btninvite:'把这段缘分发给对方',
       h2consult:'向理咨询', consultlead:'写下在意的事，便以理的视角静静地观照。不为算准，而是为了整理。',
       cplaceholder:'例如：路上有只死掉的鸟。早上看到一大片云。偶然遇见老朋友。',
       btnconsult:'请理为我观照', consultprivacy:'※输入的文字会送往AI（Claude）以生成回应，不会保存文字。',
       csitlabel:'此刻的心情・处境・正在投入的事（可选）', csitph:'例如：刚开始新工作很不安，手伸得太广静不下来。',
       csithint:'※越是写下心情与处境，越能得到贴近你的观照。', btnbuy:'购买点数（30次 ¥500）',
       cexlead:'第一次使用吗 — 该怎么写？ 看范例（免费・不会消耗咨询次数）：',
       exfree:'这是「书写范例」。打开查看不会减少免费次数。',
       exlblev:'这样写（在意的事）', exlblsit:'这样写（此刻的心情・处境）',
       exlblans:'会这样被观照（回应的一例）', exuse:'把这个范例带入输入框，再自行修改',
       paidthanks:'感谢您的购买，次数已增加。',
       remain:'剩余{n}次', consultempty:'请先写下事情。', consultlimit:'今天的免费次数（3次）已用完，明天再来。',
       consultwait:'正以理观照中…', consultfail:'这次没能好好回应。请稍后再试一次。',
       logout:'登出',
       foot:'这是供娱乐、自我省思的参考，并非用来断定准不准。', detailbase:'推算依据：'},
  en: {h1:'RiCard', tag:'Settle today, not predict it.', h2today:"Today's Ri", gear:'⚙ Settings',
       lblbirth:'Your date of birth', lbltime:'Time of birth (optional)', lblgender:'Gender (for fortune-cycle calc, optional)',
       lblemail:'Email (used for password reset)',
       optnone:'Not selected', optm:'Male', optf:'Female', btnsave:"Save and see today's Ri",
       btnsaveimg:'Save image', btnshare:'Share', btndetail:'Details (what is this based on?)',
       h2en:'The bond between two', lblpartner:"The other person's birth date (yours is set in \\"Today's Ri\\")",
       btnen:'See the bond', btninvite:'Send this bond to them',
       h2consult:'Consult the Ri', consultlead:'Write down what caught your attention, and it will be observed quietly through Ri. Not to predict, but to put things in order.',
       cplaceholder:'e.g. A dead bird on the road. A big cloud this morning. Ran into an old friend.',
       btnconsult:'Ask the Ri to observe', consultprivacy:'* Your text is sent to AI (Claude) to generate a reply. It is not saved.',
       csitlabel:'Your current feelings, situation, what you are working on (optional)', csitph:'e.g. Just started a new job and feel uneasy; spreading myself too thin.',
       csithint:'* The more you write about your feelings and situation, the more it fits you.', btnbuy:'Buy credits (30 times ¥500)',
       cexlead:'New here — how should I write? See examples (free; does not use up consultations):',
       exfree:'This is a "writing example." Viewing it does not reduce your free count.',
       exlblev:'Write it like this (the event)', exlblsit:'Write it like this (your feelings / situation)',
       exlblans:'It will be observed like this (a sample reply)', exuse:'Put this example into the box and edit it yourself',
       paidthanks:'Thank you for your purchase. Your credits have been added.',
       remain:'{n} left', consultempty:'Please write the event.', consultlimit:"Today's free uses (3) are done. Please come again tomorrow.",
       consultwait:'Observing through Ri…', consultfail:"I couldn't put it into words this time. Please wait a moment and try again.",
       logout:'Log out',
       foot:'This is a guide for entertainment and self-reflection, not a judgment of right or wrong.', detailbase:'Basis of the reading: '}
};
// 相談の参考例（タップで入力欄に入る）。chip=ボタンに出す短い見出し。
var CEX = {
  ja: [
    {chip:'🛑 直前にトラブルで止まった',
     ev:'大事なメールを送ろうとした直前に、パソコンが急に固まって動かなくなりました。最初は腹が立ちましたが、再起動してもう一度メールを見直したところ、宛先を一人間違えていたことに気づきました。もしそのまま送っていたら、かなり失礼なことになっていたと思います。',
     sit:'最近、仕事を早く進めようとして少し焦っています。細かい確認を後回しにして、とにかく先に送ってしまおうという気持ちがありました。この出来事は、単なる機械トラブルとして流してよいのか、それとも理として何か見直すべきことがあるのか知りたいです。',
     ans:'焦って「先に送ろう」とする気持ちが、確かめる目を薄くしていた。そこへ強制的に止められ、もう一度見る間ができた――そんな流れに見えます。一歩早く送るより、一手確かめてから送るほうが、結局は早いことがあります。送る前に三秒だけ止まる、その小さな間を意識してみては。意味は流してもよいですが、焦りだけはそっと受け取っておいてください。'},
    {chip:'🤝 物の不調と縁が重なった',
     ev:'人と会う約束をして出かけようとしたら、家を出る直前にお気に入りの腕時計のベルトが切れました。そのあと相手から連絡が来て、急に予定を変更したいと言われました。少し嫌な気持ちになりましたが、よく考えると最近その人との関係に無理を感じていて、自分も本当は少し疲れていました。',
     sit:'相手との関係を続けた方がいいのか、少し距離を置いた方がいいのか迷っています。時計のベルトが切れたことと、予定変更が重なったので、何か意味があるのか気になっています。',
     ans:'時計は時を刻むもの、ベルトは繋ぎとめるもの。それが切れたのは「この繋がりを今のまま続けるか、一度結び直すか」を問いかける見立てとも観られます。ただ大事なのは出来事より、あなたがすでに「無理を感じ、疲れていた」と気づいていたこと。続けるか離れるかより先に、自分が何に無理しているかを書き出してみては。相手の気持ちは推測せず、まず自分の状態を。'},
    {chip:'🔁 小さなことが続いた',
     ev:'朝、家を出るときに靴ひもがほどけました。そのあとコンビニで買おうと思っていた飲み物が売り切れていました。さらに信号に何度か引っかかりました。特に大きな不安はありませんが、最近こういう小さなことにも何か意味があるのではないかと考えてしまいます。',
     sit:'今は少し神経質になっていて、何でも理の知らせではないかと思ってしまうところがあります。このような小さな出来事も全部意味を読んだ方がいいのでしょうか。それとも流してよいのでしょうか。',
     ans:'靴ひも・売り切れ・信号――それぞれは独立した、ごく普通の出来事です。「特に不安はない」と感じているのが大事なところ。感じなかった出来事に意味を探すと、消耗するだけでかえって何も見えなくなります。今は「意味を見つける力」より「意味を手放す判断」かもしれません。この三つは、流してよいと思います。'}
  ],
  zh: [
    {chip:'🛑 關鍵時刻被卡住',
     ev:'正要寄出一封重要的郵件前，電腦突然當機不動了。一開始很火大，但重開機後再檢查一次郵件，才發現有一個收件人寄錯了。如果就那樣寄出去，應該會非常失禮。',
     sit:'最近想把工作快點推進，有點焦急。把細節確認往後擺，只想著先送出去再說。想知道這件事是單純的機器故障、可以流過去，還是以理來看有什麼該重新檢視的。',
     ans:'「先送出去再說」的焦急，讓你確認的眼神變淡了；就在這時被硬生生擋下，多出了重看一次的空檔——看起來是這樣的流動。與其早一步送出，先確認一手，反而常常更快。寄出前停個三秒，試著留下那一點小小的空檔。意義可以流過去，但那份焦急，請輕輕收下。'},
    {chip:'🤝 物的不順與緣分重疊',
     ev:'和人約好要見面、正準備出門時，出門前心愛的手錶錶帶斷了。之後對方傳來訊息，說想臨時改約。當下有點不舒服，但仔細想想，最近對這段關係感到勉強，自己其實也有些累了。',
     sit:'在猶豫該繼續這段關係，還是稍微保持距離。錶帶斷掉和臨時改約剛好重疊，想知道是否有什麼意義。',
     ans:'錶刻劃時間，錶帶繫住東西。它斷了，也可以看成在問「要就這樣繼續，還是重新繫過」。但更重要的不是事件本身，而是你已經察覺到自己「感到勉強、也累了」。在決定繼續或離開之前，先把自己究竟在勉強什麼寫下來。別去猜對方的心情，先看自己的狀態。'},
    {chip:'🔁 小事接連發生',
     ev:'早上出門時鞋帶鬆開了。之後想在便利商店買的飲料剛好賣完。接著又連續遇到好幾個紅燈。並沒有特別不安，只是最近會忍不住想，這些小事是不是有什麼意義。',
     sit:'現在有點神經質，什麼都會想說是不是理的提示。像這樣的小事，是全部都要讀出意義比較好，還是可以流過去呢？',
     ans:'鞋帶・賣完・紅燈——各自都是獨立又平常的事。你說「沒有特別不安」，這點很重要。對沒有感覺的事去找意義，只會消耗自己、反而更看不清。現在，比起「找出意義」，或許更需要「放下意義」。這三件，流過去就好。'}
  ],
  cn: [
    {chip:'🛑 关键时刻被卡住',
     ev:'正要寄出一封重要的邮件前，电脑突然死机不动了。一开始很火大，但重开机后再检查一次邮件，才发现有一个收件人寄错了。如果就那样寄出去，应该会非常失礼。',
     sit:'最近想把工作快点推进，有点焦急。把细节确认往后摆，只想着先送出去再说。想知道这件事是单纯的机器故障、可以流过去，还是以理来看有什么该重新检视的。',
     ans:'「先送出去再说」的焦急，让你确认的眼神变淡了；就在这时被硬生生挡下，多出了重看一次的空档——看起来是这样的流动。与其早一步送出，先确认一手，反而常常更快。寄出前停个三秒，试着留下那一点小小的空档。意义可以流过去，但那份焦急，请轻轻收下。'},
    {chip:'🤝 物的不顺与缘分重叠',
     ev:'和人约好要见面、正准备出门时，出门前心爱的手表表带断了。之后对方传来讯息，说想临时改约。当下有点不舒服，但仔细想想，最近对这段关系感到勉强，自己其实也有些累了。',
     sit:'在犹豫该继续这段关系，还是稍微保持距离。表带断掉和临时改约刚好重叠，想知道是否有什么意义。',
     ans:'表刻划时间，表带系住东西。它断了，也可以看成在问「要就这样继续，还是重新系过」。但更重要的不是事件本身，而是你已经察觉到自己「感到勉强、也累了」。在决定继续或离开之前，先把自己究竟在勉强什么写下来。别去猜对方的心情，先看自己的状态。'},
    {chip:'🔁 小事接连发生',
     ev:'早上出门时鞋带松开了。之后想在便利商店买的饮料刚好卖完。接着又连续遇到好几个红灯。并没有特别不安，只是最近会忍不住想，这些小事是不是有什么意义。',
     sit:'现在有点神经质，什么都会想说是不是理的提示。像这样的小事，是全部都要读出意义比较好，还是可以流过去呢？',
     ans:'鞋带・卖完・红灯——各自都是独立又平常的事。你说「没有特别不安」，这点很重要。对没有感觉的事去找意义，只会消耗自己、反而更看不清。现在，比起「找出意义」，或许更需要「放下意义」。这三件，流过去就好。'}
  ],
  en: [
    {chip:'🛑 Stopped right before sending',
     ev:'Just before I sent an important email, my computer suddenly froze. At first I was annoyed, but after restarting and checking the email again, I noticed I had one wrong recipient. If I had sent it as is, it would have been quite rude.',
     sit:"I've been rushing to get work done quickly, putting off careful checks, just wanting to send things first. I'd like to know whether this is just a machine glitch to let go of, or something to review through Ri.",
     ans:'The urge to "just send it first" had thinned your checking eye. Right then you were forcibly stopped, and a moment to look again opened up — that is how the flow seems. Rather than sending a step early, checking one move first is often faster in the end. Try to keep that small pause, just three seconds before sending. You may let the meaning go, but do gently take in the haste itself.'},
    {chip:'🤝 A thing broke as a bond wavered',
     ev:"As I was leaving to meet someone, the band of my favorite watch broke right before I left. Then they messaged me, suddenly wanting to change our plans. I felt a little put off, but thinking about it, I have been feeling strained in this relationship lately, and honestly I was a bit tired too.",
     sit:"I'm unsure whether to keep this relationship going or put some distance between us. The watch band breaking and the change of plans overlapped, so I wonder if it means something.",
     ans:'A watch marks time; a band holds things together. Its breaking can be seen as asking, "continue this bond as is, or re-tie it once?" But what matters more than the event is that you had already noticed you felt strained and tired. Before deciding to continue or part, try writing down what exactly you are straining at. Do not guess the other person\\'s feelings; first look at your own state.'},
    {chip:'🔁 Small things kept happening',
     ev:'My shoelace came undone as I left in the morning. Then the drink I wanted at the convenience store was sold out. And I hit several red lights. Nothing felt especially worrying, but lately I keep wondering if such small things have some meaning.',
     sit:"I'm a little on edge right now, tending to think everything might be a sign from Ri. Should I read meaning into every small thing like this, or is it fine to let them go?",
     ans:'Shoelace, sold-out, red lights — each is an independent, perfectly ordinary event. The important part is that you feel nothing especially worrying. Searching for meaning in things you did not feel only wears you out and clouds your sight. Right now, more than "the power to find meaning," you may need "the judgment to let meaning go." These three, I think you can let pass.'}
  ]
};
var EX_CUR = 0;
function renderExamples(){
  var ex = CEX[LANG] || CEX.ja;
  var btns = document.querySelectorAll('.exchip');
  for(var i=0;i<btns.length;i++){ if(ex[i]) btns[i].textContent = ex[i].chip; }
}
function showExample(i){
  var ex = (CEX[LANG] || CEX.ja)[i]; if(!ex) return;
  EX_CUR = i;
  qs('exev').textContent = ex.ev;
  qs('exsit').textContent = ex.sit;
  qs('exans').textContent = ex.ans;
  qs('exmodal').style.display = 'flex';
}
function closeExample(){ qs('exmodal').style.display = 'none'; }
function useExample(){
  // 見本を入力欄に入れるだけ（送信しない＝この時点では無料回数は減らない）
  var ex = (CEX[LANG] || CEX.ja)[EX_CUR]; if(!ex) return;
  qs('cevent').value = ex.ev; qs('csituation').value = ex.sit;
  qs('cchars').textContent = ex.ev.length;
  closeExample();
  qs('cevent').focus();
  qs('cevent').scrollIntoView({behavior:'smooth', block:'center'});
}
var LANG = (function(){ try{ return localStorage.getItem('ricard_lang') || 'ja'; }catch(e){ return 'ja'; } })();
function applyI18n(){
  var t = I18N[LANG] || I18N.ja;
  var els = document.querySelectorAll('[data-i18n]');
  for(var i=0;i<els.length;i++){ var k=els[i].getAttribute('data-i18n'); if(t[k]!==undefined) els[i].textContent = t[k]; }
  var phs = document.querySelectorAll('[data-ph]');
  for(var j=0;j<phs.length;j++){ var pk=phs[j].getAttribute('data-ph'); if(t[pk]!==undefined) phs[j].placeholder = t[pk]; }
  document.documentElement.lang = ({zh:'zh-Hant', cn:'zh-Hans', en:'en'}[LANG] || 'ja');
  renderExamples();
  refreshBalance();
}
function setLang(l){
  LANG = l; try{ localStorage.setItem('ricard_lang', l); }catch(e){}
  applyI18n();
  if(qs('cardImg').style.display==='block') showCard();
  if(qs('detail').style.display==='block'){ qs('detail').style.display='none'; showDetail(); }
  if(qs('enImg').style.display==='block') showEn();
}

function localToday(){
  var d = new Date();
  return d.getFullYear() + '-' + ('0'+(d.getMonth()+1)).slice(-2) + '-' + ('0'+d.getDate()).slice(-2);
}
function toggleSettings(){ var s=qs('settings'); s.style.display=(s.style.display==='none')?'block':'none'; }
function saveProfile(){
  // 生年月日はアカウント（サーバー）に保存。ログインで自動復元される。
  try{ fetch('/api/profile', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({birth: qs('me').value, hour: qs('metime').value, gender: qs('gender').value,
                          email: (qs('myemail')?qs('myemail').value:'')})}); }catch(e){}
}
function saveAndShow(){
  if(!qs('me').value){ alert('生年月日を選んでください'); qs('me').focus(); return; }
  saveProfile(); showCard(); qs('settings').style.display='none';
}
function showCard(){
  try{
    var b = qs('me').value;
    if(!b){ alert('生年月日を選んでください'); qs('me').focus(); return; }
    var t = qs('metime').value;  // "HH:MM" または ""
    var url = '/api/card?b=' + b + '&d=' + localToday() + '&lang=' + LANG;
    if(t){ url += '&h=' + parseInt(t.split(':')[0], 10); }
    var img = qs('cardImg');
    img.style.opacity = '0.35';                 // 押すたびに一瞬光って「更新された」と分かる
    img.onload = function(){
      img.style.opacity = '1';
      img.scrollIntoView({behavior:'smooth', block:'center'});  // 必ずカードまで移動
    };
    img.onerror = function(){
      img.style.opacity = '1';
      alert('カードの生成に失敗しました。もう一度お試しください。');
    };
    img.src = url + '&_=' + Date.now();
    img.style.display = 'block';
    qs('cardBtns').classList.remove('hidden');
    qs('detailBtn').classList.remove('hidden');
  }catch(err){
    alert('エラー: ' + (err && err.message ? err.message : err));
  }
}

function showEn(){
  var a = qs('me').value, b = qs('enB').value;
  if(!a){ alert('先に「設定」であなたの生年月日を入れてください'); toggleSettings(); return; }
  if(!b){ alert('お相手の生年月日を選んでください'); return; }
  var img = qs('enImg');
  img.style.opacity = '0.35';
  img.onload = function(){ img.style.opacity='1'; img.scrollIntoView({behavior:'smooth', block:'center'}); };
  img.onerror = function(){ img.style.opacity='1'; alert('縁カードの生成に失敗しました。'); };
  img.src = '/api/en?a=' + a + '&b=' + b + '&lang=' + LANG + '&_=' + Date.now();
  img.style.display = 'block';
  qs('enBtns').classList.remove('hidden');
}

function saveImg(id, name){
  var a = document.createElement('a');
  a.href = qs(id).src; a.download = name; a.click();
}

async function shareImg(id, name){
  var src = qs(id).src;
  try{
    var r = await fetch(src); var blob = await r.blob();
    var file = new File([blob], name, {type:'image/png'});
    if(navigator.canShare && navigator.canShare({files:[file]})){
      await navigator.share({files:[file], text:'今日の理'});
      return;
    }
  }catch(e){}
  saveImg(id, name);
}

function copyInvite(){
  var a = qs('me').value;
  if(!a){ alert('先に「設定」であなたの生年月日を入れてください'); toggleSettings(); return; }
  var link = location.origin + '/?en=' + a;
  // スマホ：OSの共有メニュー（LINE・メール等）を開く
  if(navigator.share){
    navigator.share({ title:'理カード', text:'二人の縁、見てみない？', url: link }).catch(function(){});
    return;
  }
  // PC等：クリップボードにコピー
  if(navigator.clipboard){
    navigator.clipboard.writeText(link).then(function(){
      alert('招待リンクをコピーしました。LINEやメールで相手に送ってください。');
    }, function(){ prompt('このリンクを送ってください', link); });
  } else {
    prompt('このリンクを送ってください', link);
  }
}

// ── 理に相談する（無料お試し＋購入クレジット・サーバーで管理）──────────────
function renderBalance(b){
  var el = qs('cremain'); if(!el || !b) return;
  var t = I18N[LANG] || I18N.ja;
  if(b.unlimited){ el.textContent = '∞'; if(qs('cbuy')) qs('cbuy').classList.add('hidden'); return; }
  el.textContent = (t.remain || '残り{n}回').replace('{n}', b.total);
  if(qs('cbuy')) qs('cbuy').classList.toggle('hidden', b.total > 0);
}
function refreshBalance(){
  fetch('/api/balance').then(function(r){ return r.json(); }).then(renderBalance).catch(function(){});
}
async function askConsult(){
  var t = I18N[LANG] || I18N.ja;
  var ev = qs('cevent').value.trim();
  if(!ev){ alert(t.consultempty); return; }
  var sit = qs('csituation') ? qs('csituation').value.trim() : '';
  var btn = qs('cbtn'), res = qs('cresult'), old = btn.textContent;
  btn.disabled = true; btn.textContent = t.consultwait;
  res.style.display = 'block'; res.textContent = t.consultwait;
  try{
    var r = await fetch('/api/consult', {method:'POST', headers:{'Content-Type':'application/json'},
                        body: JSON.stringify({event: ev, situation: sit, lang: LANG})});
    var j = await r.json();
    res.textContent = j.text || t.consultfail;
    if(j.balance) renderBalance(j.balance);
    if(j.need_purchase && qs('cbuy')) qs('cbuy').classList.remove('hidden');
  }catch(e){ res.textContent = t.consultfail; }
  btn.disabled = false; btn.textContent = old;
  res.scrollIntoView({behavior:'smooth', block:'center'});
}
async function buyCredits(){
  try{
    var r = await fetch('/api/checkout', {method:'POST'});
    var j = await r.json();
    if(j.ok && j.url){ window.location = j.url; }
    else { alert(j.text || '準備中です'); }
  }catch(e){ alert('準備中です'); }
}

function renderDetail(j){
  var html = '<div>' + ((I18N[LANG]||I18N.ja).detailbase) + j.methods + '</div><table>';
  for(var i=0;i<j.rows.length;i++){ html += '<tr><td class="k">'+j.rows[i][0]+'</td><td>'+j.rows[i][1]+'</td></tr>'; }
  html += '</table><div class="how">'+j.how+'</div><div class="note">'+j.note+'</div>';
  return html;
}
function showDetail(){
  var b = qs('me').value; if(!b){ alert('先に生年月日を入れてください'); return; }
  var el = qs('detail');
  if(el.style.display === 'block'){ el.style.display='none'; return; }
  var t = qs('metime').value, g = qs('gender').value;
  var url = '/api/detail?b=' + b + '&d=' + localToday() + '&lang=' + LANG;
  if(t){ url += '&h=' + parseInt(t.split(':')[0], 10); }
  if(g){ url += '&g=' + g; }
  fetch(url).then(function(r){ return r.json(); }).then(function(j){
    el.innerHTML = renderDetail(j);
    el.style.display = 'block';
    el.scrollIntoView({behavior:'smooth', block:'center'});
  }).catch(function(){ alert('詳細の取得に失敗しました。'); });
}

// 起動時：前回の生年月日を思い出して今日のカードを自動表示／招待リンク処理
(function(){
  applyI18n();
  var p = new URLSearchParams(location.search);
  var en = p.get('en');
  if(en){
    qs('enB').value = en;
    qs('banner').textContent = 'あなたとの「縁」を見たい人からの招待です。あなたの生年月日は「設定」から入れてください。';
    qs('banner').style.display = 'block';
  }
  if(p.get('paid') === '1'){
    var tt = I18N[LANG] || I18N.ja;
    qs('banner').textContent = tt.paidthanks || 'ご購入ありがとうございます。';
    qs('banner').style.display = 'block';
  }
  // 生年月日はアカウントから復元（新規登録者はまっさら）
  fetch('/api/profile').then(function(r){ return r.json(); }).then(function(j){
    if(j && j.email && qs('myemail')){ qs('myemail').value = j.email; }
    if(j && j.birth){
      qs('me').value = j.birth;
      if(j.hour){ qs('metime').value = j.hour; }
      if(j.gender){ qs('gender').value = j.gender; }
      qs('settings').style.display = 'none';
      showCard();
    } else {
      qs('settings').style.display = 'block';   // 新規＝まっさら、設定を開いて入力を促す
    }
  }).catch(function(){ qs('settings').style.display = 'block'; });
})();
</script>
</body></html>"""


@app.route("/sample")
def sample():
    # ログイン後の相談画面のサンプル（公開・ログイン不要）。
    # 実アプリのページ(PAGE)そのものを表示し、サンプル用の動作だけ差し込む。
    html = PAGE.replace("<!--ACCT-->", "").replace("</body>", SAMPLE_INJECT + "</body>")
    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.route("/")
def index():
    u = _current_user()
    if not u:
        # 未ログインの人には公開ページ（サービス説明・料金）を見せる。
        # ＝Stripe審査の「販売内容を確認できる・パスワードで保護されていない」要件を満たす。
        return _shell("ようこそ", LANDING_BODY)
    acct = ('  ・  <a href="/admin" style="color:var(--gold)">管理者画面</a>'
            if (u and u["is_admin"]) else "")
    resp = Response(PAGE.replace("<!--ACCT-->", acct), mimetype="text/html")
    # 常に最新ページを配る（古いキャッシュで新機能が動かないのを防ぐ）
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


def _png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


def _server_today():
    return (date.today().year, date.today().month, date.today().day)


@app.route("/api/card")
@login_required
def api_card():
    b = request.args.get("b", "")
    d = request.args.get("d", "")   # 閲覧者の端末ローカル日付（その人の"今日"）
    h = request.args.get("h", "")   # 生まれた時間（任意・0〜23時）
    lang = request.args.get("lang", "ja")
    lang = {"cn": "zh", "en": "ja"}.get(lang, lang)   # カード画像はja/zhのみ→簡体は繁体、英語は日本語で表示
    lang = lang if lang in ("ja", "zh") else "ja"
    try:
        birth = _parse(b)
        if h != "":
            birth = birth + (int(h),)   # (年,月,日,時)
    except Exception:
        abort(400)
    try:
        target = _parse(d) if d else _server_today()
    except Exception:
        target = _server_today()
    return _png(render(build_card(birth, target, lang), "morning", lang))


@app.route("/api/en")
@login_required
def api_en():
    a = request.args.get("a", "")
    b = request.args.get("b", "")
    lang = request.args.get("lang", "ja")
    lang = {"cn": "zh", "en": "ja"}.get(lang, lang)   # カード画像はja/zhのみ→簡体は繁体、英語は日本語で表示
    lang = lang if lang in ("ja", "zh") else "ja"
    try:
        A = _parse(a)
        B = _parse(b)
    except Exception:
        abort(400)
    return _png(render_view(build_en(A, B, lang), "morning", lang))


@app.route("/api/detail")
@login_required
def api_detail():
    b = request.args.get("b", "")
    d = request.args.get("d", "")
    h = request.args.get("h", "")
    g = request.args.get("g", "")
    lang = request.args.get("lang", "ja")
    lang = {"cn": "zh", "en": "ja"}.get(lang, lang)   # カード画像はja/zhのみ→簡体は繁体、英語は日本語で表示
    lang = lang if lang in ("ja", "zh") else "ja"
    try:
        birth = _parse(b)
        if h != "":
            birth = birth + (int(h),)
    except Exception:
        abort(400)
    try:
        target = _parse(d) if d else _server_today()
    except Exception:
        target = _server_today()
    return jsonify(build_detail(birth, target, g if g in ("m", "f") else None, lang))


@app.route("/api/profile", methods=["GET", "POST"])
@login_required
def api_profile():
    u = _current_user()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        store.save_profile(u["username"], (d.get("birth") or "").strip(),
                           (d.get("hour") or "").strip(), (d.get("gender") or "").strip())
        if "email" in d:    # 本人のメール（パスワード再設定用）も更新
            auth.set_email(u["username"], (d.get("email") or "").strip())
        return jsonify({"ok": True})
    prof = store.get_profile(u["username"])
    prof["email"] = auth.get_email(u["username"])
    return jsonify(prof)


@app.route("/api/consult", methods=["POST"])
@login_required
def api_consult():
    data = request.get_json(silent=True) or {}
    event = (data.get("event") or "").strip()
    lang = data.get("lang", "ja")
    lang = lang if lang in ("ja", "zh", "cn", "en") else "ja"   # 相談は4言語
    if not event:
        return jsonify({"ok": False, "text": ""}), 400
    if len(event) > CONSULT_MAX_CHARS:      # 入力の蓋（長文を物理的に拒否）
        event = event[:CONSULT_MAX_CHARS]
    situation = (data.get("situation") or "").strip()[:CONSULT_SIT_CHARS]
    u = _current_user()
    bal = auth.get_balance(u["username"], FREE_CONSULTS)
    if not bal["unlimited"] and bal["total"] <= 0:    # 残数なし＝購入へ
        msg = ("無料のお試し分が終わりました。続けるには、下のボタンからクレジットをご購入ください。"
               if lang == "ja" else "免費試用次數已用完。請從下方按鈕購買點數以繼續。")
        return jsonify({"ok": False, "need_purchase": True, "text": msg, "balance": bal}), 200
    ip = _client_ip()
    if _ip_over_limit(ip):                   # サーバー側IP制限（端末カウントのすり抜け対策）
        msg = "今日のご利用が多いため、いったんお休みです。また明日どうぞ。" if lang == "ja" \
              else "今天使用量較多，先暫歇，明天再來。"
        return jsonify({"ok": False, "text": msg}), 429
    kb = store.search_ri_docs((event + " " + situation).strip())   # 出来事＋状況で関連検索
    result = consult(event, lang, kb_docs=kb, situation=situation)
    if result.get("ok"):
        _ip_bump(ip)                         # 成功時のみカウント
        auth.consume_consult(u["username"], FREE_CONSULTS)   # 成功時のみ1回消費
        result["balance"] = auth.get_balance(u["username"], FREE_CONSULTS)
    return jsonify(result)


@app.route("/api/balance")
@login_required
def api_balance():
    u = _current_user()
    b = auth.get_balance(u["username"], FREE_CONSULTS)
    b["pack_price"] = PACK_PRICE
    b["pack_credits"] = PACK_CREDITS
    return jsonify(b)


@app.route("/api/checkout", methods=["POST"])
@login_required
def api_checkout():
    u = _current_user()
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        return jsonify({"ok": False, "text": "購入機能は現在準備中です。"})
    try:
        import stripe
        stripe.api_key = key
        base = request.url_root.rstrip("/")
        sess = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "unit_amount": PACK_PRICE,
                    "product_data": {"name": PACK_NAME},
                },
                "quantity": 1,
            }],
            metadata={"username": u["username"], "credits": str(PACK_CREDITS)},
            success_url=base + "/?paid=1",
            cancel_url=base + "/?paid=0",
        )
        return jsonify({"ok": True, "url": sess.url})
    except Exception:
        return jsonify({"ok": False, "text": "決済の開始に失敗しました。少し時間をおいてお試しください。"})


@app.route("/api/stripe-webhook", methods=["POST"])
def stripe_webhook():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        return ("", 200)
    import stripe
    stripe.api_key = key
    wh = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        if wh:
            event = stripe.Webhook.construct_event(payload, sig, wh)
        else:
            event = json.loads(payload.decode("utf-8"))
    except Exception:
        return ("bad signature", 400)
    try:
        etype = event["type"]                       # StripeObjectも辞書もインデックスでOK
    except Exception:
        etype = None
    if etype == "checkout.session.completed":
        try:
            meta = event["data"]["object"]["metadata"] or {}
            uname = meta["username"]
            n = int(meta["credits"])
        except Exception:
            uname, n = None, 0
        if uname and n > 0:
            auth.add_credits(uname, n)
    return ("", 200)


def _shell(title, body):
    return Response("""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + title + """・理カード</title><style>
 :root{ --bg:#fbf6ec; --bg2:#f3e7d0; --ink:#3a322a; --sub:#8a7b63; --gold:#b08a4e; --line:#e4d8c2; }
 *{box-sizing:border-box;} body{margin:0;background:linear-gradient(#fbf6ec,#f3e7d0);color:var(--ink);
  font-family:"Yu Mincho","Hiragino Mincho ProN",serif;-webkit-font-smoothing:antialiased;}
 .wrap{max-width:640px;margin:0 auto;padding:30px 20px 70px;}
 h1{font-size:26px;font-weight:500;letter-spacing:.2em;text-align:center;margin:6px 0 4px;}
 .tag{text-align:center;color:var(--sub);font-size:13px;margin:0 0 24px;}
 .card{background:#fffdf8;border:1px solid var(--line);border-radius:14px;padding:20px 18px;margin:0 0 18px;}
 h2{font-size:17px;font-weight:500;letter-spacing:.08em;margin:0 0 12px;}
 label{display:block;font-size:13px;color:var(--sub);margin:10px 0 4px;}
 input[type=text],input[type=password],input[type=number],textarea{width:100%;padding:11px 13px;font-size:16px;
  border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink);font-family:inherit;}
 textarea{resize:vertical;line-height:1.7;}
 .pw{position:relative;display:block;}
 .pw>input{padding-right:48px;}
 .eye{position:absolute;right:6px;top:50%;transform:translateY(-50%);margin:0;padding:4px 8px;background:transparent;color:var(--sub);border:none;font-size:20px;cursor:pointer;line-height:1;}
 button,.btn{display:inline-block;margin-top:14px;padding:11px 16px;font-size:15px;font-family:inherit;color:#fff;
  background:var(--ink);border:none;border-radius:9px;letter-spacing:.06em;cursor:pointer;text-decoration:none;}
 button.full{width:100%;}
 .mini{padding:5px 10px;font-size:12px;margin:2px;}
 .ghost{background:transparent;color:var(--ink);border:1px solid var(--ink);}
 .err{background:#fbe9e7;border:1px solid #e0b4ab;color:#a04434;font-size:14px;border-radius:9px;padding:10px 12px;margin:0 0 14px;}
 .ok{background:#eaf5e9;border:1px solid #b6d8b0;color:#3a7a34;font-size:14px;border-radius:9px;padding:10px 12px;margin:0 0 14px;}
 .lnk{text-align:center;font-size:13px;margin-top:14px;}
 a{color:var(--gold);}
 table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0;}
 th,td{padding:6px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle;}
 th{color:var(--sub);font-weight:500;}
 #kbtable th{position:sticky;top:0;background:#fffdf8;z-index:1;}
 .row{display:flex;gap:8px;flex-wrap:wrap;}
 .note{font-size:12px;color:var(--sub);margin:6px 0;}
 .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
</style></head><body><div class="wrap">""" + body + """
<script>
(function(){var ps=document.querySelectorAll('input[type=password]');
for(var i=0;i<ps.length;i++){(function(inp){
 var w=document.createElement('span');w.className='pw';
 inp.parentNode.insertBefore(w,inp);w.appendChild(inp);
 var b=document.createElement('button');b.type='button';b.className='eye';b.textContent='👁';
 b.onclick=function(){if(inp.type==='password'){inp.type='text';b.textContent='🙈';}
  else{inp.type='password';b.textContent='👁';}};
 w.appendChild(b);})(ps[i]);}})();
window.filterList=function(inpId,tableId,countId){
 var inp=document.getElementById(inpId); if(!inp) return;
 var q=inp.value.trim();
 var rows=document.querySelectorAll('#'+tableId+' tr'); var n=0;
 for(var k=0;k<rows.length;k++){
  if(!rows[k].hasAttribute('data-s')) continue;
  var s=rows[k].getAttribute('data-s');
  var show=(!q)||(s.indexOf(q)>=0);
  rows[k].style.display=show?'':'none';
  if(show) n++;
 }
 var c=document.getElementById(countId); if(c) c.textContent=n;
};
window.filterKB=function(){window.filterList('kbsearch','kbtable','kbcount');};
window.toggleFull=function(td){
 var s=td.querySelector('.snip'), f=td.querySelector('.full');
 if(!f) return;
 var open=(f.style.display==='none');
 f.style.display=open?'block':'none';
 if(s) s.style.display=open?'none':'block';
};
(function(){
 var boxes=document.querySelectorAll('.scrollbox'); if(!boxes.length) return;
 for(var i=0;i<boxes.length;i++){(function(box){
  box.addEventListener('mouseenter',function(){box.setAttribute('data-over','1');});
  box.addEventListener('mouseleave',function(){box.removeAttribute('data-over');});
 })(boxes[i]);}
 document.addEventListener('keydown',function(e){
  var tag=(e.target.tagName||'').toLowerCase();
  if(tag==='input'||tag==='textarea') return;
  var box=null, all=document.querySelectorAll('.scrollbox');
  for(var i=0;i<all.length;i++){
   if(all[i].getAttribute('data-over')==='1'||document.activeElement===all[i]){box=all[i];break;}
  }
  if(!box) return;
  var step=44;
  if(e.key==='ArrowDown'){box.scrollTop+=step;e.preventDefault();}
  else if(e.key==='ArrowUp'){box.scrollTop-=step;e.preventDefault();}
  else if(e.key==='PageDown'||e.key===' '){box.scrollTop+=box.clientHeight*0.9;e.preventDefault();}
  else if(e.key==='PageUp'){box.scrollTop-=box.clientHeight*0.9;e.preventDefault();}
  else if(e.key==='Home'){box.scrollTop=0;e.preventDefault();}
  else if(e.key==='End'){box.scrollTop=box.scrollHeight;e.preventDefault();}
 });
})();
</script>
</div></body></html>""",
                    mimetype="text/html")


SETUP_BODY = """<h1>理カード</h1><p class="tag">最初の管理者を作成します</p>
<div class="card"><h2>管理者アカウント作成</h2>{err}
<form method="post">
<label>ユーザー名</label><input type="text" name="username" autocomplete="username">
<label>パスワード（6文字以上）</label><input type="password" name="password" autocomplete="new-password">
<button class="full" type="submit">管理者を作成</button></form>
<p class="note">この画面は最初の1回だけ表示されます。</p></div>"""


# ログインしていない人に見せる公開ページ（サービス説明・料金・規約）。
LANDING_BODY = """<h1>理カード</h1><p class="tag">今日を、当てずに整える。</p>

<div class="card"><h2>理カードとは</h2>
<p>気になった出来事を書くと、「理（ことわり）」の視点で静かに観る、相談のためのアプリです。
当てる占いではありません。出来事の良し悪しを決めつけず、「いま何に気づき、何を整えるとよいか」を一緒に観ます。
日本語・繁體中文・简体中文・English に対応しています。</p></div>

<div class="card"><h2>できること</h2>
<p>・気になった出来事と、いまの気持ち・状況を書く<br>
・理の視点での観方が返ってきます（断定せず、流してよい時は「流してよい」とお伝えします）<br>
・生年月日から「今日の理」も見られます</p></div>

<div class="card"><h2>サービスの一例（こんなふうに観ます）</h2>
<p class="note" style="margin-bottom:8px">実際にアプリで返ってくる回答の一例です。<a href="/sample">▶ ログイン後の画面イメージを見る</a></p>
<div style="font-size:14px;line-height:1.85;background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px">
<b>相談した出来事：</b><br>
「大事なメールを送ろうとした直前に、パソコンが急に固まりました。再起動して見直したら、宛先を一人間違えていたことに気づきました。」<br><br>
<b>いまの状況：</b><br>
「仕事を早く進めようと焦っていて、確認を後回しにしていました。」<br><br>
<b>理の観方（回答例）：</b><br>
<span style="color:var(--sub)">焦って「先に送ろう」とする気持ちが、確かめる目を薄くしていた。そこへ強制的に止められ、もう一度見る間ができた――そんな流れに見えます。一歩早く送るより、一手確かめてから送るほうが、結局は早いことがあります。送る前に三秒だけ止まる、その小さな間を意識してみては。意味は流してもよいですが、焦りだけはそっと受け取っておいてください。</span>
</div></div>

<div class="card"><h2>料金・購入で得られるもの</h2>
<p>まずは<b>無料でお試し</b>いただけます。続けて使いたい方は：</p>
<p style="font-size:18px;margin:8px 0"><b>相談30回ぶん ＝ ¥500</b>（税込）</p>
<p>・購入すると、アプリ内で<b>相談を30回</b>利用できる回数が付与されます。<br>
・<b>買い切り</b>（1回きりのお支払い）。自動更新・サブスクではありません。<br>
・お支払いは Stripe（クレジットカード）で安全に処理されます。</p>
<p class="note">デジタルサービスの性質上、付与後の返金は原則としてお受けできません。不具合等があればお問い合わせください。</p></div>

<div class="card"><h2>プライバシー</h2>
<p>相談で入力した文章は<b>保存しません</b>。その場で観るために使うだけです。</p></div>

<div class="card"><h2>ご利用にあたって</h2>
<p class="note">本サービスは娯楽・自己内省のための目安です。占いの当たり外れを保証するものではありません。
医療・投資・法律などの専門的な助言ではありません。重要な判断はご自身で、必要に応じて専門家にご相談ください。</p></div>

<div class="card"><h2>はじめる</h2>
<p>現在は<b>招待制</b>です。紹介コードをお持ちの方はご登録いただけます。</p>
<a class="btn" href="/login">ログイン</a>　<a class="btn ghost" href="/register">紹介コードで登録</a></div>

<div class="card"><h2>特定商取引法に基づく表記</h2>
<table>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">販売事業者</td><td>栄宏ライフ株式会社（Ahiro Life Co., Ltd.）</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">運営統括責任者</td><td>請求があれば遅滞なく開示します</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">所在地</td><td>請求があれば遅滞なく開示します</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">電話番号</td><td>請求があれば遅滞なく開示します（お問い合わせはメールでお願いします）</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">お問い合わせ</td><td><a href="mailto:ahiro@ahiro.page">ahiro@ahiro.page</a></td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">販売価格</td><td>相談30回パック ¥500（税込）</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">商品代金以外の費用</td><td>なし（通信にかかる費用はお客様のご負担となります）</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">支払方法</td><td>クレジットカード（Stripe）</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">支払時期</td><td>購入手続きの完了時にお支払いが確定します</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">提供時期</td><td>決済完了後ただちに、アプリ内へ相談回数を付与します</td></tr>
<tr><td style="color:var(--sub);white-space:nowrap;vertical-align:top">返品・キャンセル</td><td>デジタルサービスの性質上、付与後の返金・キャンセルはお受けできません。不具合等はお問い合わせください。</td></tr>
</table></div>"""


# /sample 用：実アプリのページ(PAGE)そのものに差し込むスクリプト。
# 相談は実例の回答を表示（実API・課金なし）、今日の理/縁は登録後の案内にする。
SAMPLE_INJECT = """<script>
(function(){
 function q(id){return document.getElementById(id);}
 var EV='大事なメールを送ろうとした直前に、パソコンが急に固まって動かなくなりました。最初は腹が立ちましたが、再起動してもう一度メールを見直したところ、宛先を一人間違えていたことに気づきました。もしそのまま送っていたら、かなり失礼なことになっていたと思います。';
 var SIT='最近、仕事を早く進めようとして少し焦っています。細かい確認を後回しにして、とにかく先に送ってしまおうという気持ちがありました。';
 var ANS='焦って「先に送ろう」とする気持ちが、確かめる目を薄くしていた。そこへ強制的に止められ、もう一度見る間ができた――そんな流れに見えます。一歩早く送るより、一手確かめてから送るほうが、結局は早いことがあります。送る前に三秒だけ止まる、その小さな間を意識してみては。意味は流してもよいですが、焦りだけはそっと受け取っておいてください。';
 var bn=document.querySelector('.banner');
 if(bn){bn.style.display='block'; bn.innerHTML='🔎 これは<b>サンプル画面</b>です（ログイン後の実際の画面）。「理に相談する」は実例の回答を表示します。実際のご利用には登録が必要です。';}
 if(q('cevent')){q('cevent').value=EV; if(q('cchars'))q('cchars').textContent=EV.length;}
 if(q('csituation'))q('csituation').value=SIT;
 window.refreshBalance=function(){};
 setTimeout(function(){var cr=q('cremain'); if(cr)cr.textContent='登録後にご利用いただけます'; if(q('cbuy'))q('cbuy').classList.add('hidden');},350);
 window.askConsult=function(){var res=q('cresult'); if(!res)return; res.style.display='block'; res.textContent=ANS; res.scrollIntoView({behavior:'smooth',block:'center'});};
 window.buyCredits=function(){alert('サンプル画面です。ご購入は登録・ログイン後にご利用いただけます。');};
 window.showCard=function(){alert('サンプル画面です。「今日の理」は登録・ログイン後にご利用いただけます。');};
 window.showEn=function(){alert('サンプル画面です。「二人の縁」は登録・ログイン後にご利用いただけます。');};
})();
</script>"""

LOGIN_BODY = """<h1>理カード</h1><p class="tag">今日を、当てずに整える。</p>
<div class="card"><h2>ログイン</h2>{err}
<form method="post">
<label>ユーザー名</label><input type="text" name="username" autocomplete="username">
<label>パスワード</label><input type="password" name="password" autocomplete="current-password">
<button class="full" type="submit">ログイン</button></form>
<p class="lnk"><a href="/forgot">パスワードをお忘れですか？</a></p>
<p class="lnk">紹介コードをお持ちの方は <a href="/register">こちらで登録</a></p></div>"""

REGISTER_BODY = """<h1>理カード</h1><p class="tag">紹介コードで登録</p>
<div class="card"><h2>新規登録</h2>{err}
<form method="post">
<label>紹介コード</label><input type="text" name="code">
<label>ユーザー名</label><input type="text" name="username" autocomplete="username">
<label>メールアドレス（パスワード再設定に使います）</label><input type="text" name="email" autocomplete="email">
<label>パスワード（6文字以上）</label><input type="password" name="password" autocomplete="new-password">
<button class="full" type="submit">登録して始める</button></form>
<p class="lnk">すでに登録済みの方は <a href="/login">ログイン</a></p></div>"""

FORGOT_BODY = """<h1>理カード</h1><p class="tag">パスワードの再設定</p>
<div class="card"><h2>パスワードをお忘れの方</h2>{err}{msg}
<p class="note" style="text-align:left">ご登録のメールアドレスを入力してください。再設定用のリンクをお送りします。</p>
<form method="post">
<label>メールアドレス</label><input type="text" name="email" autocomplete="email">
<button class="full" type="submit">再設定リンクを送る</button></form>
<p class="lnk"><a href="/login">ログインに戻る</a></p></div>"""

RESET_BODY = """<h1>理カード</h1><p class="tag">新しいパスワードの設定</p>
<div class="card"><h2>新しいパスワード</h2>{err}
<form method="post">
<input type="hidden" name="token" value="{token}">
<label>新しいパスワード（6文字以上）</label><input type="password" name="password" autocomplete="new-password">
<button class="full" type="submit">パスワードを設定する</button></form></div>"""


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if auth.count_users() > 0:
        return redirect("/login")
    err = ""
    if request.method == "POST":
        try:
            auth.add_user(request.form.get("username", ""),
                          request.form.get("password", ""), is_admin=True)
            session.permanent = True
            session["user"] = (request.form.get("username", "") or "").strip()
            return redirect("/admin")
        except Exception as e:
            err = str(e)
    eb = ('<div class="err">%s</div>' % escape(err)) if err else ""
    return _shell("初期設定", SETUP_BODY.format(err=eb))


@app.route("/login", methods=["GET", "POST"])
def login():
    if auth.count_users() == 0:
        return redirect("/setup")
    err = ""
    if request.method == "POST":
        uname = (request.form.get("username", "") or "").strip()
        r = auth.verify(uname, request.form.get("password", ""))
        if r["ok"]:
            session.permanent = True
            session["user"] = uname
            return redirect("/admin" if r["is_admin"] else "/")
        err = r["reason"]
    eb = ('<div class="err">%s</div>' % escape(err)) if err else ""
    return _shell("ログイン", LOGIN_BODY.format(err=eb))


@app.route("/register", methods=["GET", "POST"])
def register():
    err = ""
    if request.method == "POST":
        try:
            uname = (request.form.get("username", "") or "").strip()
            auth.register_with_code(request.form.get("code", ""), uname,
                                    request.form.get("password", ""),
                                    request.form.get("email", ""))
            session.permanent = True
            session["user"] = uname
            return redirect("/")
        except Exception as e:
            err = str(e)
    eb = ('<div class="err">%s</div>' % escape(err)) if err else ""
    return _shell("新規登録", REGISTER_BODY.format(err=eb))


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    err, msg = "", ""
    if request.method == "POST":
        email = (request.form.get("email", "") or "").strip()
        res = auth.create_reset_token(email)
        if res and mailer.mail_configured():
            uname, raw = res
            link = request.url_root.rstrip("/") + "/reset?token=" + raw
            body = ("理カード：パスワード再設定のご案内\n\n"
                    "下のリンクから新しいパスワードを設定してください（60分間有効）。\n"
                    + link + "\n\n"
                    "※このメールに心当たりがない場合は、破棄してください。\n"
                    "理カード（栄宏ライフ株式会社）")
            mailer.send_email(email, "理カード パスワード再設定", body)
        # 存在の有無は伏せて、常に同じ案内（攻撃対策）。未設定時は手動連絡へ誘導。
        if mailer.mail_configured():
            msg = ('<div class="ok">ご登録があれば、再設定リンクをメールでお送りしました。'
                   '数分待っても届かない場合は迷惑メールもご確認ください。</div>')
        else:
            msg = ('<div class="ok">現在メール送信の準備中です。お手数ですが '
                   '<a href="mailto:ahiro@ahiro.page">ahiro@ahiro.page</a> までご連絡ください。</div>')
    eb = ('<div class="err">%s</div>' % escape(err)) if err else ""
    return _shell("パスワード再設定", FORGOT_BODY.format(err=eb, msg=msg))


@app.route("/reset", methods=["GET", "POST"])
def reset():
    err = ""
    token = (request.values.get("token", "") or "").strip()
    if request.method == "POST":
        uname = auth.consume_reset_token(token, request.form.get("password", ""))
        if uname:
            return _shell("完了", '<h1>理カード</h1><p class="tag">設定が完了しました</p>'
                          '<div class="card"><div class="ok">新しいパスワードを設定しました。</div>'
                          '<p class="lnk"><a href="/login">ログインへ</a></p></div>')
        err = "リンクが無効か、期限切れです（60分で失効）。パスワードは6文字以上にしてください。お手数ですが、もう一度お試しください。"
    eb = ('<div class="err">%s</div>' % escape(err)) if err else ""
    return _shell("新しいパスワード", RESET_BODY.format(err=eb, token=escape(token)))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    msg = ""
    if request.method == "POST":
        a = request.form.get("action", "")
        try:
            if a == "code_create":
                auth.create_code(
                    request.form.get("code", ""),
                    max_uses=max(0, int(request.form.get("max_uses") or 0)),
                    grant_days=(max(1, int(request.form["grant_days"])) if request.form.get("grant_days") else None),
                    grant_free=(max(0, int(request.form["grant_free"])) if request.form.get("grant_free") else None),
                    note=request.form.get("note", ""))
                msg = "紹介コードを作成しました。"
            elif a == "code_toggle":
                auth.set_code_enabled(request.form.get("code", ""),
                                      request.form.get("to") == "on")
                msg = "コードの状態を変更しました。"
            elif a == "code_delete":
                auth.delete_code(request.form.get("code", ""))
                msg = "コードを削除しました。"
            elif a == "user_toggle":
                auth.set_enabled(request.form.get("username", ""),
                                 request.form.get("to") == "on")
                msg = "利用者の状態を変更しました。"
            elif a == "user_extend":
                auth.extend_days(request.form.get("username", ""), 30)
                msg = "利用期限を30日延長しました。"
            elif a == "user_grant":
                auth.add_credits(request.form.get("username", ""), PACK_CREDITS)
                msg = "%d回ぶんのクレジットを付与しました。" % PACK_CREDITS
            elif a == "user_resetpw":
                uname = request.form.get("username", "")
                np = auth.reset_password(uname)
                msg = "%s さんのパスワードを再設定しました。新しい仮パスワード：%s （本人に伝えてください）" % (uname, np)
            elif a == "user_delete":
                auth.delete_user(request.form.get("username", ""))
                msg = "利用者を削除しました。"
            elif a == "ri_save":
                store.set_setting("ri_extra", request.form.get("ri_extra", ""))
                msg = "理の追記を保存しました。"
            elif a == "ridoc_add":
                store.add_ri_doc(request.form.get("doc_title", ""),
                                 request.form.get("doc_body", ""))
                msg = "理を知識ベースに追加しました。"
            elif a == "ridoc_delete":
                store.delete_ri_doc(request.form.get("doc_id", ""))
                msg = "理を知識ベースから削除しました。"
            elif a == "ri_import":
                n = store.import_ri_seed()
                msg = "同梱の理データを %d 件取り込みました。" % n
            elif a == "ri_replace":
                n = store.replace_ri_seed()
                msg = "知識ベースを最新の基本データ（%d件）に入れ替えました。" % n
        except Exception as e:
            msg = "エラー: " + str(e)

    # 紹介コード表
    crows = ""
    ccount = 0
    for c in auth.list_codes():
        ccount += 1
        uses = ("%d / %s" % (c["used_count"], "∞" if not c["max_uses"] else c["max_uses"]))
        gd = ("%d日" % c["grant_days"]) if c["grant_days"] is not None else "無期限"
        gf = ("無料%d回" % c["grant_free"]) if c.get("grant_free") is not None else "無料既定"
        gd = gd + "・" + gf
        to = "off" if c["enabled"] else "on"
        srch_c = escape(c["code"] + " " + c["状態"] + " " + gd)
        crows += ("<tr data-s=\"%s\"><td><b>%s</b></td><td>%s</td><td>%s</td><td>付与%s</td>"
                  "<td><form method='post' style='display:inline'><input type='hidden' name='action' value='code_toggle'>"
                  "<input type='hidden' name='code' value='%s'><input type='hidden' name='to' value='%s'>"
                  "<button class='mini ghost'>%s</button></form>"
                  "<form method='post' style='display:inline' onsubmit=\"return confirm('削除しますか？')\">"
                  "<input type='hidden' name='action' value='code_delete'><input type='hidden' name='code' value='%s'>"
                  "<button class='mini ghost'>削除</button></form></td></tr>") % (
            srch_c, escape(c["code"]), escape(c["状態"]), uses, gd,
            escape(c["code"]), to, ("停止" if c["enabled"] else "再開"), escape(c["code"]))

    # 利用者表
    urows = ""
    ucount = 0
    for u in auth.list_users():
        ucount += 1
        to = "off" if u["enabled"] else "on"
        admin_tag = " 👑" if u["is_admin"] else ""
        if u["is_admin"]:
            bal_txt = "∞"
        else:
            quota = u["free_quota"] if u["free_quota"] is not None else FREE_CONSULTS
            free_rem = max(0, quota - u["free_used"])
            bal_txt = "残%d（無料%d/%d・購入%d）" % (free_rem + u["credits"], free_rem, quota, u["credits"])
        acts = ""
        if not u["is_admin"]:
            acts = ("<form method='post' style='display:inline'><input type='hidden' name='action' value='user_toggle'>"
                    "<input type='hidden' name='username' value='%s'><input type='hidden' name='to' value='%s'>"
                    "<button class='mini ghost'>%s</button></form>"
                    "<form method='post' style='display:inline'><input type='hidden' name='action' value='user_grant'>"
                    "<input type='hidden' name='username' value='%s'><button class='mini ghost'>+%d回</button></form>"
                    "<form method='post' style='display:inline'><input type='hidden' name='action' value='user_extend'>"
                    "<input type='hidden' name='username' value='%s'><button class='mini ghost'>+30日</button></form>"
                    "<form method='post' style='display:inline' onsubmit=\"return confirm('パスワードを再設定しますか？')\">"
                    "<input type='hidden' name='action' value='user_resetpw'><input type='hidden' name='username' value='%s'>"
                    "<button class='mini ghost'>PW再設定</button></form>"
                    "<form method='post' style='display:inline' onsubmit=\"return confirm('削除しますか？')\">"
                    "<input type='hidden' name='action' value='user_delete'><input type='hidden' name='username' value='%s'>"
                    "<button class='mini ghost'>削除</button></form>") % (
                escape(u["username"]), to, ("停止" if u["enabled"] else "再開"),
                escape(u["username"]), PACK_CREDITS,
                escape(u["username"]), escape(u["username"]), escape(u["username"]))
        email_line = ("<br><span class='note' style='font-size:11px'>%s</span>" % escape(u["email"])) if u.get("email") else ""
        srch_u = escape(u["username"] + " " + u.get("email", "") + " " + u["状態"] + " " + bal_txt + " " + str(u["expires_on"]))
        urows += "<tr data-s=\"%s\"><td><b>%s</b>%s%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            srch_u, escape(u["username"]), admin_tag, email_line, escape(u["状態"]), escape(str(u["expires_on"])),
            escape(bal_txt), acts)

    ri_extra = escape(store.get_setting("ri_extra", "") or "")
    spent = store.spent_today()
    me = _current_user()
    mb = ('<div class="ok">%s</div>' % escape(msg)) if msg else ""

    # 理の知識ベース一覧
    dcount = store.count_ri_docs()
    drows = ""
    for d in store.list_ri_docs():
        snip = (d["body"][:44] + "…") if len(d["body"]) > 44 else d["body"]
        st = (d.get("strength") or "").strip()
        badge = ("<span style='font-size:11px;color:var(--gold)'>[%s]</span> " % escape(st)) if st else ""
        meta = ""
        if d.get("cat") or d.get("ptype") or d.get("tags"):
            meta = ("<div class='note' style='font-size:12px;margin-top:6px'>分類：%s／型：%s／タグ：%s</div>"
                    % (escape(d.get("cat", "")), escape(d.get("ptype", "")), escape(d.get("tags", ""))))
        drows += ("<tr data-s=\"%s\"><td onclick=\"toggleFull(this)\" style=\"cursor:pointer\">%s<b>%s</b><br>"
                  "<span class='note snip'>%s</span>"
                  "<div class='full' style='display:none;font-size:13px;line-height:1.9;margin-top:6px;color:var(--ink)'>%s%s</div></td>"
                  "<td>%s</td>"
                  "<td><form method='post' style='display:inline' onsubmit=\"return confirm('削除しますか？')\">"
                  "<input type='hidden' name='action' value='ridoc_delete'>"
                  "<input type='hidden' name='doc_id' value='%s'>"
                  "<button class='mini ghost'>削除</button></form></td></tr>") % (
            escape(d["title"] + d["body"] + " " + d.get("tags", "")), badge, escape(d["title"]), escape(snip),
            escape(d["body"]).replace("\n", "<br>"), meta, d["created_at"], d["id"])
    drows = drows or "<tr><td colspan='3' class='note'>まだありません</td></tr>"

    # 取り込み／差し替えブロック。基本データの新版があれば「入れ替え」、無ければ状態表示。
    seed_total = store.seed_count()
    if not store.seed_is_current():
        import_block = (
            '<div class="card" style="margin:0 0 12px;border:1px solid var(--gold);background:#fbf7ee">'
            '<b>基本データの新しい版があります（%d件）。</b>'
            '<p class="note" style="margin:6px 0">これに入れ替えると、いまの知識ベースは<b>全て消えて</b>新版に置き換わります'
            '（あなたが手で足した理も消えます）。これを今後の判断材料の土台にします。</p>'
            '<form method="post" style="display:inline" onsubmit="return confirm(\'知識ベースを全消去して最新版に入れ替えます。よろしいですか？\')">'
            '<input type="hidden" name="action" value="ri_replace">'
            '<button type="submit">最新の基本データ（%d件）に入れ替える</button></form>'
            '<form method="post" style="display:inline;margin-left:8px"><input type="hidden" name="action" value="ri_import">'
            '<button type="submit" class="ghost">消さずに足りない分だけ追加</button></form></div>' % (seed_total, seed_total))
    else:
        import_block = ('<div class="ok" style="margin:0 0 12px">✓ 基本データ（%d件・最新版）を取り込み済みです。'
                        '私が新しい版を用意したときだけ、ここに入れ替えボタンが出ます。</div>' % seed_total)

    body = """<h1>管理者画面</h1><p class="tag">理カード・オーナー専用（{user}）</p>
{msg}
<div class="card"><div class="top"><h2>今日の利用額</h2><a class="btn ghost mini" href="/">アプリへ</a></div>
<p class="note">本日のAI利用：約 ¥{spent}（概算）/ 上限の蓋つき。</p>
<p class="note"><a href="https://console.anthropic.com/settings/usage" target="_blank" rel="noopener" style="color:var(--gold)">▶ 実際のAPI利用額を確認（Anthropicコンソール）</a></p>
<p class="note"><a href="https://dashboard.stripe.com/" target="_blank" rel="noopener" style="color:var(--gold)">▶ 売上を確認（Stripeダッシュボード）</a> ・ <a href="/logout">ログアウト</a></p></div>

<div class="card"><h2>紹介コード</h2>
<input type="text" id="codesearch" oninput="filterList('codesearch','codetable','codecount')" placeholder="コードを検索（TEST / RICARD / 有効 など）">
<div class="note" style="margin:2px">表示中 <span id="codecount">{ccount}</span> 件。枠内にマウスを合わせると↑↓キーでも動きます。</div>
<div id="codebox" class="scrollbox" tabindex="0" style="max-height:300px; overflow-y:auto; border:1px solid var(--line); border-radius:8px; padding:0 10px; outline:none;">
<table id="codetable"><tr><th>コード</th><th>状態</th><th>登録人数</th><th>付与・無料</th><th></th></tr>{crows}</table>
</div>
<form method="post" style="margin-top:14px;border-top:1px solid var(--line);padding-top:12px">
<input type="hidden" name="action" value="code_create">
<label>新しいコード（例：RICARD2026）</label><input type="text" name="code">
<div class="row"><div style="flex:1"><label>登録できる人数（0=無制限）</label><input type="number" name="max_uses" value="0" min="0" step="1"></div>
<div style="flex:1"><label>付与する利用日数（空=無期限）</label><input type="number" name="grant_days" min="1" step="1" placeholder="空=無期限"></div></div>
<label>無料お試し回数（空＝既定の3回）</label><input type="number" name="grant_free" min="0" step="1" placeholder="空=既定3">
<label>メモ（任意）</label><input type="text" name="note">
<button type="submit">コードを発行</button></form></div>

<div class="card"><h2>利用者</h2>
<input type="text" id="usersearch" oninput="filterList('usersearch','usertable','usercount')" placeholder="利用者を検索（名前 / 有効 / 停止 など）">
<div class="note" style="margin:2px">表示中 <span id="usercount">{ucount}</span> 件。枠内にマウスを合わせると↑↓キー・PageUp/Down でも動きます。</div>
<div id="userbox" class="scrollbox" tabindex="0" style="max-height:380px; overflow-y:auto; border:1px solid var(--line); border-radius:8px; padding:0 10px; outline:none;">
<table id="usertable"><tr><th>ユーザー</th><th>状態</th><th>期限</th><th>残数</th><th></th></tr>{urows}</table>
</div></div>

<div class="card"><h2>理の追記（AIに教える理）</h2>
<p class="note">ここに書いた理を、AIが<b>全ユーザーの相談</b>で参考にして答えます。※名前・団体名は書かないでください（普遍的な原則のみ）。長いほど1回のコストが上がるので、要点を絞るのがおすすめです。</p>
<form method="post"><input type="hidden" name="action" value="ri_save">
<textarea name="ri_extra" id="ri_extra" rows="10" maxlength="5000" oninput="document.getElementById('richars').textContent=this.value.length" placeholder="例：急いては事を仕損じる。焦りは好転の前ぶれのこともある…">{ri_extra}</textarea>
<div class="note" style="text-align:right"><span id="richars">0</span> / 5000 字</div>
<button type="submit">理を保存</button></form>
<script>document.getElementById('richars').textContent=document.getElementById('ri_extra').value.length;</script></div>

<div class="card"><h2>理の知識ベース（{dcount}件）</h2>
<p class="note">講話・事例・原則を1件ずつ追加。相談ごとにAIが<b>関係するものだけ自動で探して</b>使います。何件でも貯められます（大量OK）。※名前・団体名は書かないでください。</p>
{import_block}
<form method="post"><input type="hidden" name="action" value="ridoc_add">
<label>タイトル（例：落ちたお金の理）</label><input type="text" name="doc_title">
<label>本文（理の内容・原則・事例）</label>
<textarea name="doc_body" rows="6" maxlength="20000" placeholder="例：お金は神様からの預かりもの。落ちた小銭は気づきのサイン。急がず、まず身の回りを整える…"></textarea>
<button type="submit">この理を知識ベースに追加</button></form>
<div class="note" style="margin-top:18px;border-top:1px solid var(--line);padding-top:12px">▼ 登録済みの理（一覧・検索）— 表示中 <span id="kbcount">{dcount}</span> 件</div>
<input type="text" id="kbsearch" oninput="filterKB()" placeholder="理を検索（お金 / 縁 / 焦り / 言葉 など）">
<div class="note" style="margin:2px">行をクリックすると全文が開きます。枠内にマウスを合わせると↑↓キー・PageUp/Down でも動きます。</div>
<div id="kbbox" class="scrollbox" tabindex="0" style="max-height:380px; overflow-y:auto; border:1px solid var(--line); border-radius:8px; padding:0 10px; outline:none;">
<table id="kbtable"><tr><th>理（タイトル／抜粋）</th><th>追加日</th><th></th></tr>{drows}</table>
</div></div>""".format(
        user=escape(me["username"]), msg=mb, spent=int(spent),
        crows=crows or "<tr><td colspan='5' class='note'>まだありません</td></tr>",
        urows=urows, ri_extra=ri_extra, dcount=dcount, drows=drows,
        ccount=ccount, ucount=ucount,
        import_block=import_block)
    return _shell("管理者", body)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5390, debug=False)
