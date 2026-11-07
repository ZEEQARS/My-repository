"""今日のX投稿の下書き（文章と画像）を作るスクリプト。

- 文章: GitHub Models（GitHub 付属の無料AI）で theme.txt のテーマに沿って作る
- 画像: Pillow で文字入りの画像を作る
- 出力: posts/日付.txt と posts/日付.png、Issue 本文用の issue_body.md

GitHub Actions から毎日実行される想定です。
"""

import colorsys
import datetime
import hashlib
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "posts"
THEME_FILE = ROOT / "theme.txt"
JST = datetime.timezone(datetime.timedelta(hours=9))

API_URL = "https://models.github.ai/inference/chat/completions"
MODELS = ["openai/gpt-4.1-mini", "openai/gpt-4o-mini"]
MAX_WEIGHTED_LENGTH = 280  # X の上限（日本語は1文字=2として数える）
RECENT_DAYS = 14

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
IMAGE_SIZE = (1200, 675)


def weighted_length(text: str) -> int:
    """X の数え方（半角英数字など=1、日本語など=2）で長さを数える。"""
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


def recent_posts(today: datetime.date) -> list[str]:
    """最近の投稿を読み込む（同じような内容を避けるため）。"""
    texts = []
    for path in sorted(POSTS_DIR.glob("*.txt"), reverse=True):
        if path.stem >= today.isoformat():
            continue
        texts.append(path.read_text(encoding="utf-8").strip())
        if len(texts) >= RECENT_DAYS:
            break
    return texts


def ask_ai(theme: str, today: datetime.date, recent: list[str]) -> dict:
    """GitHub Models に投稿文と画像用の短い言葉を作ってもらう。"""
    recent_block = "\n".join(f"- {t}" for t in recent) or "（まだありません）"
    prompt = textwrap.dedent(f"""\
        X（旧Twitter）に投稿する日本語の文章を1つ作ってください。

        テーマ: {theme}
        今日の日付: {today.year}年{today.month}月{today.day}日

        条件:
        - 本文は100文字以内。ハッシュタグは0〜2個まで
        - 季節や曜日に合うと良い
        - 実在の人物の名言の引用や、事実かどうか確かめられない情報は入れない
        - 下の「最近の投稿」と似た内容・言い回しは避ける

        最近の投稿:
        {recent_block}

        次の形のJSONだけを返してください:
        {{"post": "投稿の本文", "image_text": "画像に大きく入れる短い言葉（20文字以内）"}}
        """)
    token = os.environ["GITHUB_TOKEN"]
    last_error = None
    for model in MODELS:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "response_format": {"type": "json_object"},
        }).encode()
        request = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            last_error = f"{model}: {error.code} {error.read().decode(errors='replace')[:300]}"
            print(f"::warning::{last_error}")
            continue
        content = data["choices"][0]["message"]["content"].strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```")
        result = json.loads(content)
        print(f"使ったAI: {model}")
        return {"post": result["post"].strip(), "image_text": result["image_text"].strip()}
    raise RuntimeError(f"AIで文章を作れませんでした: {last_error}")


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError("日本語フォントが見つかりません")


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """画像の幅に収まるように1文字ずつ折り返す。"""
    lines, current = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        if draw.textlength(current + ch, font=font) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


def make_image(text: str, today: datetime.date, path: Path) -> None:
    """日付ごとに色の変わるグラデーション背景に、言葉を大きく入れた画像を作る。"""
    width, height = IMAGE_SIZE
    hue = int(hashlib.sha256(today.isoformat().encode()).hexdigest(), 16) % 360 / 360
    top = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.55, 0.95)]
    bottom = [int(c * 255) for c in colorsys.hsv_to_rgb((hue + 0.12) % 1, 0.75, 0.55)]

    image = Image.new("RGB", IMAGE_SIZE)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / (height - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    font_path = find_font()
    max_width = width - 200
    for size in range(96, 39, -4):
        font = ImageFont.truetype(font_path, size)
        lines = wrap_text(draw, text, font, max_width)
        line_height = int(size * 1.45)
        if len(lines) * line_height <= height - 220:
            break

    shadow = tuple(c // 2 for c in bottom)
    y = (height - len(lines) * line_height) // 2
    for line in lines:
        x = (width - draw.textlength(line, font=font)) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=shadow)
        draw.text((x, y), line, font=font, fill="white")
        y += line_height

    small = ImageFont.truetype(font_path, 30)
    date_label = f"{today.year}.{today.month:02d}.{today.day:02d}"
    draw.text((width - draw.textlength(date_label, font=small) - 50, height - 70),
              date_label, font=small, fill=(255, 255, 255))
    image.save(path)


def main() -> int:
    today = datetime.datetime.now(JST).date()
    theme = THEME_FILE.read_text(encoding="utf-8").strip()
    POSTS_DIR.mkdir(exist_ok=True)

    result = None
    for attempt in range(3):
        candidate = ask_ai(theme, today, recent_posts(today))
        length = weighted_length(candidate["post"])
        if length <= MAX_WEIGHTED_LENGTH:
            result = candidate
            break
        print(f"::warning::長すぎたので作り直します（{length}/{MAX_WEIGHTED_LENGTH}）")
    if result is None:
        print("::error::短い文章を作れませんでした")
        return 1

    text_path = POSTS_DIR / f"{today}.txt"
    image_path = POSTS_DIR / f"{today}.png"
    text_path.write_text(result["post"] + "\n", encoding="utf-8")
    make_image(result["image_text"], today, image_path)
    print(f"今日の投稿:\n{result['post']}\n画像の言葉: {result['image_text']}")

    image_url = os.environ.get("IMAGE_URL_BASE", "") + image_path.name
    issue_body = textwrap.dedent("""\
        ## 今日の投稿文
        右上のコピーボタンでコピーできます。

        ```
        {post}
        ```

        ## 画像
        長押し（パソコンなら右クリック）で保存できます。

        ![今日の画像]({image_url})

        ---
        [Xで投稿する](https://x.com/compose/post)
        投稿が終わったら、この Issue を閉じてください。
        """).format(post=result["post"], image_url=image_url)
    (ROOT / "issue_body.md").write_text(issue_body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
