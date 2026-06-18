# 理カードを世界に公開する手順

HIROさんの定番ルート＝**GitHub → Render（有料）**。これで誰でも開ける公開URLが出る。
（外部公開・git push はHIROさんの承認・操作が必要。僕はその直前まで準備する。）

## A. 僕が準備済み（ローカル・外部送信なし）
- `requirements.txt` … 必要ライブラリ（gunicorn 追加）
- `Procfile` … 起動コマンド `gunicorn app:app --bind 0.0.0.0:$PORT`
- `runtime.txt` … Python 3.12（Renderが安定対応）
- `.gitignore` … 生成画像やキャッシュを除外

## B. GitHubに上げる（git push はHIROさん承認）
1. `git init && git add . && git commit -m "理カード MVP"`（ローカル＝OK）
2. GitHubで空のリポジトリを作る（HIROさん）
3. `git remote add origin <URL>` → `git push -u origin main`
   ← **この push が「外部に出る」操作。HIROさんが実行/承認**

## C. Renderでデプロイ（HIROさんのアカウント・操作）
1. Render → New → **Web Service** → 上のGitHubリポを接続
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. プラン選択（有料推奨。無料は無アクセス時に寝て初回が遅い）→ Create
5. 数分で公開URL（例 `https://ricard.onrender.com`）が出る

## D. 公開後
- 公開URLをSNSでシェア／友人10〜20人に配って「頼まず投稿するか」を見る
- 当たりの兆しが出たら独自ドメイン・スケール（＝お金の問題＝良い問題）

## メモ（正直に）
- **コスト**: Render有料は月数ドル〜。バズったら増える（良い問題）。
- **プライバシー**: 現状アプリは生年月日を計算に使うだけで**保存しない**（DB・ログなし）。
- 繁体字をフル対応するなら、フォントを游明朝→Noto Serif CJKに差し替え。
