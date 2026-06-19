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

CONSULT_MAX_CHARS = 500   # 入力の蓋（コスト上限を固定する）
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
    <button class="lang" onclick="setLang('zh')">繁體中文</button>
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
    <textarea id="cevent" maxlength="500" rows="3" data-ph="cplaceholder" oninput="qs('cchars').textContent=this.value.length" placeholder="例：道に鳥が死んでいた。朝、大きな雲を見た。古い友人に偶然会った。"></textarea>
    <div class="ccount"><span id="cchars">0</span>/500　<span id="cremain"></span></div>
    <button onclick="askConsult()" id="cbtn" data-i18n="btnconsult">理に観てもらう</button>
    <p class="note" style="text-align:left" data-i18n="consultprivacy">※入力した文章はAI（Claude）に送られ、回答を作ります。文章は保存しません。</p>
    <div id="cresult" class="detail" style="white-space:pre-wrap; line-height:1.9;"></div>
  </div>

  <p class="foot" data-i18n="foot">これは娯楽・自己内省のための目安です。当たり外れを決めるものではありません。</p>
  <p class="foot" style="margin-top:10px"><a href="/logout" style="color:var(--gold)" data-i18n="logout">ログアウト</a><!--ACCT--></p>
</div>

<script>
function qs(id){ return document.getElementById(id); }

var I18N = {
  ja: {h1:'理カード', tag:'今日を、当てずに整える。', h2today:'今日の理', gear:'⚙ 設定',
       lblbirth:'あなたの生年月日', lbltime:'生まれた時間（わかれば・任意）', lblgender:'性別（大運の計算に使用・任意）',
       optnone:'選ばない', optm:'男性', optf:'女性', btnsave:'保存して今日の理を見る',
       btnsaveimg:'画像を保存', btnshare:'シェア', btndetail:'詳細（何をもとに占ってる？）',
       h2en:'二人の縁', lblpartner:'お相手の生年月日（あなたの分は「今日の理」の設定から）',
       btnen:'二人の縁を見る', btninvite:'この縁を相手に送る',
       h2consult:'理に相談する', consultlead:'気になった出来事を書くと、理の視点で静かに観ます。当てるのではなく、整えるために。',
       cplaceholder:'例：道に鳥が死んでいた。朝、大きな雲を見た。古い友人に偶然会った。',
       btnconsult:'理に観てもらう', consultprivacy:'※入力した文章はAI（Claude）に送られ、回答を作ります。文章は保存しません。',
       remain:'残り{n}回', consultempty:'出来事を書いてください。', consultlimit:'今日の無料分（3回）は終わりました。また明日どうぞ。',
       consultwait:'理で観ています…', consultfail:'うまく言葉にできませんでした。少し時間をおいて、もう一度お試しください。',
       logout:'ログアウト',
       foot:'これは娯楽・自己内省のための目安です。当たり外れを決めるものではありません。', detailbase:'占いの土台：'},
  zh: {h1:'理卡', tag:'不為了算準，而是整理今天。', h2today:'今日之理', gear:'⚙ 設定',
       lblbirth:'你的生日', lbltime:'出生時間（若知道・可選）', lblgender:'性別（用於大運計算・可選）',
       optnone:'不選', optm:'男', optf:'女', btnsave:'儲存並看今日之理',
       btnsaveimg:'儲存圖片', btnshare:'分享', btndetail:'詳細（依據什麼占算？）',
       h2en:'兩人的緣', lblpartner:'對方的生日（你的從「今日之理」設定）',
       btnen:'看兩人的緣', btninvite:'把這段緣分傳給對方',
       h2consult:'向理諮詢', consultlead:'寫下在意的事，便以理的視角靜靜地觀照。不為算準，而是為了整理。',
       cplaceholder:'例如：路上有隻死掉的鳥。早上看到一大片雲。偶然遇見老朋友。',
       btnconsult:'請理為我觀照', consultprivacy:'※輸入的文字會送往AI（Claude）以產生回應，不會保存文字。',
       remain:'剩餘{n}次', consultempty:'請先寫下事情。', consultlimit:'今天的免費次數（3次）已用完，明天再來。',
       consultwait:'正以理觀照中…', consultfail:'這次沒能好好回應。請稍後再試一次。',
       logout:'登出',
       foot:'這是供娛樂、自我省思的參考，並非用來斷定準不準。', detailbase:'占算依據：'}
};
var LANG = (function(){ try{ return localStorage.getItem('ricard_lang') || 'ja'; }catch(e){ return 'ja'; } })();
function applyI18n(){
  var t = I18N[LANG] || I18N.ja;
  var els = document.querySelectorAll('[data-i18n]');
  for(var i=0;i<els.length;i++){ var k=els[i].getAttribute('data-i18n'); if(t[k]!==undefined) els[i].textContent = t[k]; }
  var phs = document.querySelectorAll('[data-ph]');
  for(var j=0;j<phs.length;j++){ var pk=phs[j].getAttribute('data-ph'); if(t[pk]!==undefined) phs[j].placeholder = t[pk]; }
  document.documentElement.lang = (LANG==='zh' ? 'zh-Hant' : 'ja');
  updateRemain();
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
    body: JSON.stringify({birth: qs('me').value, hour: qs('metime').value, gender: qs('gender').value})}); }catch(e){}
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

// ── 理に相談する（無料は1日3回・端末内でカウント）──────────────
var CFREE = 3;
function consultCount(){
  var today = localToday(), n = 0;
  try{
    if(localStorage.getItem('ricard_consult_date') === today){ n = parseInt(localStorage.getItem('ricard_consult_count')||'0',10)||0; }
    else { localStorage.setItem('ricard_consult_date', today); localStorage.setItem('ricard_consult_count','0'); }
  }catch(e){}
  return n;
}
function consultRemain(){ return Math.max(0, CFREE - consultCount()); }
function updateRemain(){
  var el = qs('cremain'); if(!el) return;
  var t = I18N[LANG] || I18N.ja;
  el.textContent = (t.remain || '残り{n}回').replace('{n}', consultRemain());
}
function bumpConsult(){
  var today = localToday(), n = consultCount() + 1;
  try{ localStorage.setItem('ricard_consult_date', today); localStorage.setItem('ricard_consult_count', String(n)); }catch(e){}
  updateRemain();
}
async function askConsult(){
  var t = I18N[LANG] || I18N.ja;
  var ev = qs('cevent').value.trim();
  if(!ev){ alert(t.consultempty); return; }
  if(consultRemain() <= 0){ alert(t.consultlimit); return; }
  var btn = qs('cbtn'), res = qs('cresult'), old = btn.textContent;
  btn.disabled = true; btn.textContent = t.consultwait;
  res.style.display = 'block'; res.textContent = t.consultwait;
  try{
    var r = await fetch('/api/consult', {method:'POST', headers:{'Content-Type':'application/json'},
                        body: JSON.stringify({event: ev, lang: LANG})});
    var j = await r.json();
    res.textContent = j.text || t.consultfail;
    if(j.ok){ bumpConsult(); }
  }catch(e){ res.textContent = t.consultfail; }
  btn.disabled = false; btn.textContent = old;
  res.scrollIntoView({behavior:'smooth', block:'center'});
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
  // 生年月日はアカウントから復元（新規登録者はまっさら）
  fetch('/api/profile').then(function(r){ return r.json(); }).then(function(j){
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


@app.route("/")
@login_required
def index():
    u = _current_user()
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
        return jsonify({"ok": True})
    return jsonify(store.get_profile(u["username"]))


@app.route("/api/consult", methods=["POST"])
@login_required
def api_consult():
    data = request.get_json(silent=True) or {}
    event = (data.get("event") or "").strip()
    lang = data.get("lang", "ja")
    lang = lang if lang in ("ja", "zh") else "ja"
    if not event:
        return jsonify({"ok": False, "text": ""}), 400
    if len(event) > CONSULT_MAX_CHARS:      # 入力の蓋（長文を物理的に拒否）
        event = event[:CONSULT_MAX_CHARS]
    ip = _client_ip()
    if _ip_over_limit(ip):                   # サーバー側IP制限（端末カウントのすり抜け対策）
        msg = "今日のご利用が多いため、いったんお休みです。また明日どうぞ。" if lang == "ja" \
              else "今天使用量較多，先暫歇，明天再來。"
        return jsonify({"ok": False, "text": msg}), 429
    result = consult(event, lang)
    if result.get("ok"):
        _ip_bump(ip)                         # 成功時のみカウント
    return jsonify(result)


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

LOGIN_BODY = """<h1>理カード</h1><p class="tag">今日を、当てずに整える。</p>
<div class="card"><h2>ログイン</h2>{err}
<form method="post">
<label>ユーザー名</label><input type="text" name="username" autocomplete="username">
<label>パスワード</label><input type="password" name="password" autocomplete="current-password">
<button class="full" type="submit">ログイン</button></form>
<p class="lnk">紹介コードをお持ちの方は <a href="/register">こちらで登録</a></p></div>"""

REGISTER_BODY = """<h1>理カード</h1><p class="tag">紹介コードで登録</p>
<div class="card"><h2>新規登録</h2>{err}
<form method="post">
<label>紹介コード</label><input type="text" name="code">
<label>ユーザー名</label><input type="text" name="username" autocomplete="username">
<label>パスワード（6文字以上）</label><input type="password" name="password" autocomplete="new-password">
<button class="full" type="submit">登録して始める</button></form>
<p class="lnk">すでに登録済みの方は <a href="/login">ログイン</a></p></div>"""


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
                                    request.form.get("password", ""))
            session.permanent = True
            session["user"] = uname
            return redirect("/")
        except Exception as e:
            err = str(e)
    eb = ('<div class="err">%s</div>' % escape(err)) if err else ""
    return _shell("新規登録", REGISTER_BODY.format(err=eb))


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
                    max_uses=int(request.form.get("max_uses") or 0),
                    grant_days=(int(request.form["grant_days"]) if request.form.get("grant_days") else None),
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
            elif a == "user_delete":
                auth.delete_user(request.form.get("username", ""))
                msg = "利用者を削除しました。"
            elif a == "ri_save":
                store.set_setting("ri_extra", request.form.get("ri_extra", ""))
                msg = "理の追記を保存しました。"
        except Exception as e:
            msg = "エラー: " + str(e)

    # 紹介コード表
    crows = ""
    for c in auth.list_codes():
        uses = ("%d / %s" % (c["used_count"], "∞" if not c["max_uses"] else c["max_uses"]))
        gd = ("%d日" % c["grant_days"]) if c["grant_days"] is not None else "無期限"
        to = "off" if c["enabled"] else "on"
        crows += ("<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>付与%s</td>"
                  "<td><form method='post' style='display:inline'><input type='hidden' name='action' value='code_toggle'>"
                  "<input type='hidden' name='code' value='%s'><input type='hidden' name='to' value='%s'>"
                  "<button class='mini ghost'>%s</button></form>"
                  "<form method='post' style='display:inline' onsubmit=\"return confirm('削除しますか？')\">"
                  "<input type='hidden' name='action' value='code_delete'><input type='hidden' name='code' value='%s'>"
                  "<button class='mini ghost'>削除</button></form></td></tr>") % (
            escape(c["code"]), escape(c["状態"]), uses, gd,
            escape(c["code"]), to, ("停止" if c["enabled"] else "再開"), escape(c["code"]))

    # 利用者表
    urows = ""
    for u in auth.list_users():
        to = "off" if u["enabled"] else "on"
        admin_tag = " 👑" if u["is_admin"] else ""
        acts = ""
        if not u["is_admin"]:
            acts = ("<form method='post' style='display:inline'><input type='hidden' name='action' value='user_toggle'>"
                    "<input type='hidden' name='username' value='%s'><input type='hidden' name='to' value='%s'>"
                    "<button class='mini ghost'>%s</button></form>"
                    "<form method='post' style='display:inline'><input type='hidden' name='action' value='user_extend'>"
                    "<input type='hidden' name='username' value='%s'><button class='mini ghost'>+30日</button></form>"
                    "<form method='post' style='display:inline' onsubmit=\"return confirm('削除しますか？')\">"
                    "<input type='hidden' name='action' value='user_delete'><input type='hidden' name='username' value='%s'>"
                    "<button class='mini ghost'>削除</button></form>") % (
                escape(u["username"]), to, ("停止" if u["enabled"] else "再開"),
                escape(u["username"]), escape(u["username"]))
        urows += "<tr><td><b>%s</b>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(u["username"]), admin_tag, escape(u["状態"]), escape(str(u["expires_on"])), acts)

    ri_extra = escape(store.get_setting("ri_extra", "") or "")
    spent = store.spent_today()
    me = _current_user()
    mb = ('<div class="ok">%s</div>' % escape(msg)) if msg else ""

    body = """<h1>管理者画面</h1><p class="tag">理カード・オーナー専用（{user}）</p>
{msg}
<div class="card"><div class="top"><h2>今日の利用額</h2><a class="btn ghost mini" href="/">アプリへ</a></div>
<p class="note">本日のAI利用：約 ¥{spent} / 上限の蓋つき。<a href="/logout">ログアウト</a></p></div>

<div class="card"><h2>紹介コード</h2>
<table><tr><th>コード</th><th>状態</th><th>使用</th><th>付与期限</th><th></th></tr>{crows}</table>
<form method="post" style="margin-top:14px;border-top:1px solid var(--line);padding-top:12px">
<input type="hidden" name="action" value="code_create">
<label>新しいコード（例：RICARD2026）</label><input type="text" name="code">
<div class="row"><div style="flex:1"><label>使用上限（0=無制限）</label><input type="number" name="max_uses" value="0"></div>
<div style="flex:1"><label>付与する利用日数（空=無期限）</label><input type="number" name="grant_days" placeholder="空=無期限"></div></div>
<label>メモ（任意）</label><input type="text" name="note">
<button type="submit">コードを発行</button></form></div>

<div class="card"><h2>利用者</h2>
<table><tr><th>ユーザー</th><th>状態</th><th>期限</th><th></th></tr>{urows}</table></div>

<div class="card"><h2>理の追記（あなただけの理）</h2>
<p class="note">ここに書いた理を、AIが相談で大切にします。※名前・団体名は書かないでください（普遍的な原則のみ）。</p>
<form method="post"><input type="hidden" name="action" value="ri_save">
<textarea name="ri_extra" rows="10" placeholder="例：急いては事を仕損じる。焦りは好転の前ぶれのこともある…">{ri_extra}</textarea>
<button type="submit">理を保存</button></form></div>""".format(
        user=escape(me["username"]), msg=mb, spent=int(spent),
        crows=crows or "<tr><td colspan='5' class='note'>まだありません</td></tr>",
        urows=urows, ri_extra=ri_extra)
    return _shell("管理者", body)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5390, debug=False)
