# My-repository：Xの投稿の下書きを毎日作る

毎晩20時ごろ（日本時間）に、**投稿文と画像を自動で作って**、GitHub の Issue でお知らせします。
最後の投稿だけ、自分で X に貼り付けて行います。**すべて無料**です。

## 毎日やること

1. 通知が来たら Issue を開く
2. 投稿文をコピーし、画像を保存する
3. X に貼り付けて投稿する

スマホに通知を受け取るには、GitHub アプリを入れてログインしてください。

## 変えたいとき

- **投稿のテーマ**: `theme.txt` を書き換える
- **時刻**: `.github/workflows/daily-post.yml` の `cron` を書き換える（日本時間から9時間引いた時刻で書く）
- **止める**: Actions タブ →「毎日の投稿の下書きを作る」→ 右上の「…」→ Disable workflow
- **今すぐ作る**: Actions タブ →「毎日の投稿の下書きを作る」→ Run workflow

## しくみ

| ファイル | 役割 |
| --- | --- |
| `theme.txt` | 投稿のテーマ |
| `make_post.py` | 文章（GitHub Models の無料AI）と画像を作る |
| `.github/workflows/daily-post.yml` | 毎日自動で動かし、Issue を作る |
| `posts/` | 作った文章と画像がたまっていく |
