"""
ArchAI Knowledge Base Generator — cleaner.py
Stage 0: 数据清洗

Removes navigation, ads, comments, and boilerplate from raw web text.
Keeps: title, headings, body paragraphs, image alt text.
"""

import re
from pathlib import Path


def clean_html(html: str) -> str:
    """
    Clean raw HTML to plain text suitable for architectural analysis.

    Removes: <script>, <style>, <nav>, <footer>, <header>, comments,
             common ad/related-article patterns.
    Keeps:   <h1>-<h6>, <p>, <li>, <img alt="...">, <a> text.
    """
    # Remove script and style blocks
    html = re.sub(r"<(script|style|noscript|iframe|svg)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove common noise containers
    for tag in ["nav", "footer", "header", "aside", "form"]:
        html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # Extract img alt text: <img ... alt="text" ...> → [图片: text]
    html = re.sub(
        r'<img[^>]+alt\s*=\s*["\']([^"\']+)["\'][^>]*>',
        r'[图片: \1]',
        html,
        flags=re.IGNORECASE,
    )

    # Remove remaining HTML tags but keep their text content
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</(p|div|h\d|li|tr|article|section|blockquote)>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)

    return html


def clean_text(text: str, min_line_length: int = 20) -> str:
    """
    Clean plain text: normalize whitespace, remove boilerplate lines,
    filter out navigation/social/comment patterns.

    Args:
        text: Raw text (may contain HTML remnants)
        min_line_length: Minimum characters for a line to be kept

    Returns:
        Cleaned text ready for analysis
    """
    # If contains HTML tags, clean HTML first
    if re.search(r"<\w+[^>]*>", text):
        text = clean_html(text)

    lines = text.split("\n")
    cleaned = []

    # Patterns to filter (case-insensitive)
    noise_patterns = [
        r"^(menu|navigation|search|share|subscribe|sign up|log in|login|cookie|privacy policy|terms of use)$",
        r"^(广告|导航|搜索|分享|订阅|注册|登录|隐私|条款|版权|Copyright|All Rights Reserved)$",
        r"^(related|recommended|popular|trending|you may also like|read more|watch next)",
        r"^(相关|推荐|热门|猜你喜欢|阅读更多|上一篇|下一篇)",
        r"^(comments?|leave a comment|reply|条评论|评论$|网友)",
        r"^©|^\d{4}\s",
    ]

    for line in lines:
        stripped = line.strip()

        # Skip empty
        if not stripped:
            continue

        # Skip very short lines (likely nav/button text)
        if len(stripped) < min_line_length:
            # But keep short lines that look like headings
            if not re.match(r"^[#\d.]+\s", stripped) and len(stripped) > 5:
                # Could be a short heading, keep it
                pass
            else:
                continue

        # Check noise patterns
        is_noise = False
        for pattern in noise_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                is_noise = True
                break
        if is_noise:
            continue

        # Remove repeated punctuation
        if re.match(r"^[\.\,\;\:\!\?\-_\=]{3,}$", stripped):
            continue

        cleaned.append(stripped)

    # Join with double newlines for paragraph separation
    result = "\n\n".join(cleaned)

    # Normalize whitespace: collapse 3+ newlines to 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result


def clean_file(input_path: str | Path, output_path: str | Path = "") -> str:
    """
    Read a raw file, clean it, optionally save cleaned version.

    Args:
        input_path: Path to raw text file
        output_path: Optional output path for cleaned text

    Returns:
        Cleaned text string
    """
    raw = Path(input_path).read_text(encoding="utf-8")
    cleaned = clean_text(raw)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(cleaned, encoding="utf-8")

    return cleaned


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python cleaner.py <input.txt> [output.txt]")
        sys.exit(1)

    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else ""
    result = clean_file(inp, out)
    print(f"清洗完成: {inp} → {out or '(控制台)'}")
    if out:
        orig = len(Path(inp).read_text(encoding="utf-8"))
        new = len(result)
        print(f"原始: {orig} 字符 → 清洗后: {new} 字符 ({100*new//orig if orig else 0}%)")
