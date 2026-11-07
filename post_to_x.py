"""posts.txt から今日の投稿を1件選んで X に投稿するスクリプト。

GitHub Actions から毎日1回実行される想定です。
環境変数 DRY_RUN に値が入っているときは、投稿せずに内容を表示するだけです。
"""

import datetime
import os
import sys
from pathlib import Path

POSTS_FILE = Path(__file__).parent / "posts.txt"
SEPARATOR = "---"
COMMENT_PREFIX = "//"
MAX_WEIGHTED_LENGTH = 280  # 無料・通常アカウントの上限（日本語は1文字=2として数える）
JST = datetime.timezone(datetime.timedelta(hours=9))

SECRET_NAMES = [
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
]


def load_posts(path: Path) -> list[str]:
    """`---` だけの行で区切られた投稿を読み込む。`//` で始まる行は無視する。"""
    posts: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == SEPARATOR:
            posts.append("\n".join(current).strip())
            current = []
        elif not line.lstrip().startswith(COMMENT_PREFIX):
            current.append(line)
    posts.append("\n".join(current).strip())
    return [p for p in posts if p]


def weighted_length(text: str) -> int:
    """X の文字数の数え方（半角英数字など=1、日本語など=2）で長さを数える。"""
    total = 0
    for ch in text:
        code = ord(ch)
        if (
            code <= 0x10FF
            or 0x2000 <= code <= 0x200D
            or 0x2010 <= code <= 0x201F
            or 0x2032 <= code <= 0x2037
        ):
            total += 1
        else:
            total += 2
    return total


def pick_today(posts: list[str], today: datetime.date) -> str:
    """日付をもとに、毎日1件ずつ順番に投稿を選ぶ（最後まで行ったら最初に戻る）。"""
    return posts[today.toordinal() % len(posts)]


def main() -> int:
    posts = load_posts(POSTS_FILE)
    if not posts:
        print("::warning::posts.txt に投稿がありません。投稿を書いてください。")
        return 0

    today = datetime.datetime.now(JST).date()
    text = pick_today(posts, today)
    length = weighted_length(text)

    print(f"今日の日付（日本時間）: {today}")
    print(f"投稿の数: {len(posts)}")
    print(f"今日の投稿（{length}/{MAX_WEIGHTED_LENGTH}）:\n{text}")

    if length > MAX_WEIGHTED_LENGTH:
        print(
            f"::error::投稿が長すぎます（{length}/{MAX_WEIGHTED_LENGTH}）。"
            "日本語は1文字を2として数えるので、だいたい140文字までにしてください。"
        )
        return 1

    if os.environ.get("DRY_RUN"):
        print("テスト実行なので、X には投稿していません。")
        return 0

    missing = [name for name in SECRET_NAMES if not os.environ.get(name)]
    if missing:
        print(
            "::warning::X の API キーが設定されていないため、投稿をスキップしました。"
            f"GitHub の Secrets に次を登録してください: {', '.join(missing)}"
        )
        return 0

    import tweepy

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    response = client.create_tweet(text=text)
    print(f"投稿しました: https://x.com/i/web/status/{response.data['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
