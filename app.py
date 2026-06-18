# -*- coding: utf-8 -*-
"""理カード — 誰でも自分のカードを作れるモバイルWeb（＋縁モード）。
Flask。カード画像はサーバー側でローカル生成して返す（外部送信なし）。

起動:
  python app.py
  → http://127.0.0.1:5390/
"""
import io
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from flask import Flask, request, send_file, abort, Response

from engine.voice import build_card
from engine.card_image import render, render_view
from engine.en import build_en

app = Flask(__name__)


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
  input[type=date]{ width:100%; padding:12px 14px; font-size:16px; border:1px solid var(--line);
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
</style>
</head><body>
<div class="wrap">
  <h1>理カード</h1>
  <p class="tag">今日を、当てずに整える。</p>

  <div class="banner" id="banner"></div>

  <div class="card">
    <h2>今日の理</h2>
    <label>あなたの生年月日</label>
    <input type="date" id="me" min="1900-01-01" max="2025-12-31">
    <button onclick="showCard()">今日の理を見る</button>
    <div class="result">
      <img id="cardImg" alt="今日の理カード">
      <div class="row hidden" id="cardBtns">
        <button class="ghost" onclick="saveImg('cardImg','riicard_today.png')">画像を保存</button>
        <button onclick="shareImg('cardImg','riicard_today.png')">シェア</button>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>二人の縁</h2>
    <label>あなたの生年月日</label>
    <input type="date" id="enA" min="1900-01-01" max="2025-12-31">
    <label>お相手の生年月日</label>
    <input type="date" id="enB" min="1900-01-01" max="2025-12-31">
    <button onclick="showEn()">二人の縁を見る</button>
    <button class="ghost" onclick="copyInvite()">この縁の招待リンクをコピー</button>
    <div class="result">
      <img id="enImg" alt="二人の縁カード">
      <div class="row hidden" id="enBtns">
        <button class="ghost" onclick="saveImg('enImg','riicard_en.png')">画像を保存</button>
        <button onclick="shareImg('enImg','riicard_en.png')">シェア</button>
      </div>
    </div>
  </div>

  <p class="foot">これは娯楽・自己内省のための目安です。<br>当たり外れを決めるものではありません。</p>
</div>

<script>
function qs(id){ return document.getElementById(id); }

function showCard(){
  var b = qs('me').value;
  if(!b){ alert('生年月日を選んでください'); return; }
  try{ localStorage.setItem('ricard_birth', b); }catch(e){}
  var img = qs('cardImg');
  img.src = '/api/card?b=' + b + '&_=' + Date.now();
  img.style.display = 'block';
  qs('cardBtns').classList.remove('hidden');
  if(!qs('enA').value) qs('enA').value = b;
}

function showEn(){
  var a = qs('enA').value, b = qs('enB').value;
  if(!a || !b){ alert('二人の生年月日を選んでください'); return; }
  var img = qs('enImg');
  img.src = '/api/en?a=' + a + '&b=' + b + '&_=' + Date.now();
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
  var a = qs('enA').value || qs('me').value;
  if(!a){ alert('まずあなたの生年月日を選んでください'); return; }
  var link = location.origin + '/?en=' + a;
  navigator.clipboard.writeText(link).then(function(){
    alert('招待リンクをコピーしました。\\n相手に送ると、二人の縁が見られます。');
  }, function(){ prompt('このリンクを送ってください', link); });
}

// 起動時：前回の生年月日を思い出して今日のカードを自動表示／招待リンク処理
(function(){
  var p = new URLSearchParams(location.search);
  // 前回入れた生年月日を復元（端末内に保存・サーバーには送らない）
  try{
    var saved = localStorage.getItem('ricard_birth');
    if(saved){ qs('me').value = saved; showCard(); }
  }catch(e){}
  var en = p.get('en');
  if(en){
    qs('enA').value = en;
    qs('banner').textContent = 'あなたとの「縁」を見たい人がいます。あなたの生年月日を入れてください。';
    qs('banner').style.display = 'block';
    qs('enB').focus();
  } else if(qs('me').value && !qs('enA').value){
    qs('enA').value = qs('me').value;
  }
})();
</script>
</body></html>"""


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


def _png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/card")
def api_card():
    b = request.args.get("b", "")
    try:
        birth = _parse(b)
    except Exception:
        abort(400)
    today = (date.today().year, date.today().month, date.today().day)
    return _png(render(build_card(birth, today), "morning"))


@app.route("/api/en")
def api_en():
    a = request.args.get("a", "")
    b = request.args.get("b", "")
    try:
        A = _parse(a)
        B = _parse(b)
    except Exception:
        abort(400)
    return _png(render_view(build_en(A, B), "morning"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5390, debug=False)
