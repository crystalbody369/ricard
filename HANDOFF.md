# Kizuki（気づき）— 引き継ぎ書

> **2026-06-20 リネーム**：アプリ名を「RiCard / 理カード」→ **Kizuki（気づき）** に変更（RiCardが
> カード会社・仏酒Ricardと紛らわしいため）。表示名＝日本語「気づき」／繁・简・英「Kizuki」。
> 「今日の理」「理に相談する」等の"理"概念は中身として維持。URL（ricard.onrender.com）・repo名・
> DBパス（ricard.db）は据え置き（変更はStripe webhook等に影響するため別途）。以下の旧称は読み替え。

---

## （旧）理カード（RiCard）— 引き継ぎ書

> 新セッションはこのファイルを最初に読めば現在地と残タスクが分かる。
> 最終更新: 2026-06-19

## これは何
招待制の「理」相談Webアプリ。ユーザーが「出来事＋今の状況」を書くと、
HIROの理（土台＋知識ベース1022件）でAIが **当てずに両面で** 観て返す。
無料お試し → **30回 ¥500 買い切り課金**。日本語 / 繁體中文。
方針＝当てない・断定しない・誠実（占い予言ではなく自己省察の相棒）。

## 場所・デプロイ
- コード: `C:\Users\User\RiCard\`（Flask）
- repo: `github.com/crystalbody369/ricard`（main に push → Render 自動デプロイ）
- 本番URL: `https://ricard.onrender.com`
- Render: Web Service `ricard`（id `srv-d8q0k50js32c738loiag`、Starter $7、gunicorn）
- 永続ディスク: `/var/data`（1GB）に SQLite `ricard.db`（再起動でも消えない）

## ファイル構成
- `app.py` … Flask本体。アプリHTML(PAGE)・認証/管理画面・API
  - API: `/api/card` `/api/en` `/api/detail` `/api/profile`(GET/POST)
    `/api/consult`(POST・残数/IP判定→RAG検索→成功時に消費) `/api/balance`
    `/api/checkout`(Stripe) `/api/stripe-webhook`
  - ページ: `/` `/login` `/register` `/setup`(初回管理者) `/logout` `/admin`
- `engine/ri_consult.py` … 相談AI。`_CORPUS`(ja/zh の土台)＋`consult(event,lang,kb_docs,situation)`。
  土台ルール: 性質×相談者の状況で読む／非断定・両面そっと差し出す／作話禁止
  （書いてない人物・数字を足さない）／性的・非倫理・無関係は断る／自傷は専門機関を案内。
- `engine/store.py` … SQLite層。profiles / settings / 日次総額上限 / IP回数 /
  理KB(`add_ri_doc` `search_ri_docs(query,k=4,max_chars=2500)`＝文字bigram重なりで検索 `import_ri_seed`)。
- `engine/auth.py` … 招待コード・利用者・課金。pbkdf2/5回ロック/期限/即停止、
  `register_with_code` `verify` `get_balance` `consume_consult` `add_credits`
  `reset_password` `set_enabled` `extend_days` 等。
- `engine/ri_seed.json` … 基本データ（取り込み元）。**2026-06-19にHIRO作成の構造化DBへ全面差し替え＝1098件**
  （現象別1022＋外部伝承81、重複除外）。各エントリ: title/body(理による読み→推奨対応)/tags(現象・キーワード)/
  strength(A立ち止まる・B状況で・C参考)/ptype(判断型)/cat(大分類)/note(注意点)。版は `engine/ri_seed.version`。
  旧データは `engine/ri_seed_OLD_1022.json.bak`（gitignore）。元Excel: `C:\Users\User\Downloads\理の判断データベース_外部伝承拡張版_v1.xlsx`。
  ※基本データを更新するときは Excel→変換スクリプトで ri_seed.json + version を作り直し、管理画面の「入れ替え」ボタンで反映。
- `fonts/` … Shippori Mincho / Noto Serif TC。

## Render 環境変数（HIROが設定・Claudeからは見えない）
- `ANTHROPIC_API_KEY` … 相談AI（model `claude-sonnet-4-6`、prompt caching 有効、~¥3-5/回）
- `STRIPE_SECRET_KEY` … **今は `sk_test_`（テストモード）**
- `STRIPE_WEBHOOK_SECRET` … `whsec_`（Checkout完了→credits加算）
- 任意: `RICARD_DAILY_BUDGET_JPY`(既定500) `RICARD_FREE_CONSULTS`(3)
  `RICARD_PACK_PRICE`(500) `RICARD_PACK_CREDITS`(30) `RICARD_DB_PATH` `RICARD_SECRET_KEY`

## 完了済み（動作確認済み）
- 理相談AI＋RAG（1022件を検索しk=4だけAIに渡す→件数増でもコスト一定・ステートレス）＋状況入力欄
- 知識ベース1022件取り込み済み。管理画面で追加/検索/全文/削除（追加フォーム上・一覧下）
- 招待制：紹介コードで「登録できる人数・付与日数・無料回数」を個別設定、管理者PW再設定
- 課金：無料お試し→30回¥500買い切り。Stripe Checkout＋webhook（修正済）。
  **テストカード 4242 4242 4242 4242 で購入→+30回 実証済み**。利用者残数表示・手動+30付与
- 安全：日次総額上限¥500・IP制限・永続ディスク・相談本文は保存しない・断定しない設計

## 残タスク（TODO）
1. **本番課金化**（HIROが売ると決めたら）：Stripeをテスト→本番モードへ。
   本人確認・口座登録（日本法人=栄宏ライフ）。占い系は審査されやすい→「自己省察/娯楽アプリ」で説明。
   `sk_live_` と本番webhookの `whsec_` に差し替えるだけ（作業自体は5分）。
2. **需要検証（推奨・先にやる）**：紹介コードを友人数人に配り、無料お試しで使ってもらい反応を見る。
3. 自己リセット（メールでパスワード再設定）は将来、人数が増えたら。
4. 理データの追加はHIROが随時（直すより**追加**して複数の見方を共存させる方針）。

## 開発・テストの仕方
- 編集はローカル → `git push origin main` → Render が自動で再デプロイ（4〜5分）。
- 反映前に見ると 502 や旧版が出る → Render の events で deploy が live を確認してから再読込。
- ローカル起動テスト例:
  `PYTHONIOENCODING=utf-8 RICARD_DB_PATH=./tmp.db python -c "import app; print('boot OK')"`
  test_client で `/setup`→`/admin` を叩けば管理画面HTMLも確認できる。

## 重要な制約（安全ルール）
- APIキー・パスワード・トークン等の機密はHIRO本人が扱う（Claudeは入力・閲覧しない）。
- git push 等の外部送信は毎回HIROの承認が必要。
- 理データはアプリ内に 一神会/個人名/A.Hiro/栄宏ライフ 等を**書かない**（脱識別化済み）。
- アプリ全体を常に「当てない・非断定・誠実」に保つ。
- Claude-in-Chrome は onrender.com / github.com のナビ不可（検証はWebFetch GET かHIROのスクショ）。

## 関連メモリ
- `project_app-idea-research-2026-06-18`（このアプリに至った経緯・先頭に現在地サマリ）
- `feedback_ricard-ri-add-not-replace`（理は直すより追加・状況で判断）
