#!/usr/bin/env python3
"""把 report-card.html 用无头 Chrome 截成 1400×1980 的 PNG。

只改 skills/boss-review/assets/report-card.html 顶部的 REPORT，然后：

    python3 scripts/render_report.py --html skills/boss-review/assets/report-card.html -o 报告.png

重渲五张示例并和 docs/original 并排对比：

    python3 scripts/render_report.py --samples

截图前会等文档字体加载完。机器上有「苹方 / PingFang SC」时，字形和 Peter 的定稿一致；
没有的话仍用系统黑体，版式不变。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "skills" / "boss-review" / "assets" / "report-card.html"
SAMPLES = Path(__file__).resolve().parent / "samples.json"
CHROME = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")

HALF = {"A": 200, "B": 150, "C": 100, "D": 50, "E": 25, "F": 0}
ORDER = ["交代任务", "给参考样例", "先问后做", "验收再收", "拆任务", "反馈具体", "放手程度", "把纠错变成规矩"]


def round_half_up(half_sum: int, n: int) -> int:
    return (half_sum + n) // (2 * n)


def overall_of(score: int) -> str:
    if score >= 88:
        return "A"
    if score >= 63:
        return "B"
    if score >= 45:
        return "C"
    if score >= 20:
        return "D"
    return "E"


def compute(report: dict) -> dict:
    grades = report.get("grades") or {}
    half = scored = na = 0
    worst = None
    worst_name = None
    for name in ORDER:
        g = grades.get(name)
        if g not in HALF:
            na += 1
            continue
        scored += 1
        half += HALF[g]
        s = HALF[g] / 2
        if worst is None or s < worst:
            worst = s
            worst_name = name
    avg = round_half_up(half, scored) if scored else None
    overall = "?" if na * 2 > len(ORDER) or avg is None else overall_of(avg)
    return {"avg": avg, "overall": overall, "scored": scored, "na": na, "low": worst_name}


def inject(html: str, report: dict) -> str:
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    pattern = re.compile(r"const REPORT = \{.*?\n\};", re.S)
    replaced, n = pattern.subn(f"const REPORT = {payload};", html, count=1)
    if n != 1:
        raise SystemExit("模板里没有找到 const REPORT = { ... }")
    return replaced


def screenshot(html_path: Path, png_path: Path) -> None:
    if not CHROME:
        raise SystemExit("找不到 google-chrome，无法截图")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    if png_path.exists():
        png_path.unlink()
    url = html_path.resolve().as_uri()
    profile = Path(tempfile.mkdtemp(prefix="chrome-report-"))
    cmd = [
        "timeout", "25",
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--disable-dev-shm-usage",
        f"--user-data-dir={profile}",
        "--window-size=1400,1980",
        f"--screenshot={png_path}",
        url,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(profile, ignore_errors=True)
    if not png_path.exists() or png_path.stat().st_size < 1000:
        raise SystemExit(f"截图失败：{png_path}")


def side_by_side(original: Path, rendered: Path, dest: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    a = Image.open(original).convert("RGB")
    b = Image.open(rendered).convert("RGB")
    if b.size != (1400, 1980):
        b = b.resize((1400, 1980), Image.Resampling.LANCZOS)
    gap = 24
    label_h = 48
    canvas = Image.new("RGB", (1400 * 2 + gap, 1980 + label_h), (249, 247, 241))
    canvas.paste(a, (0, label_h))
    canvas.paste(b, (1400 + gap, label_h))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((24, 12), "Peter 定稿", fill=(34, 33, 30), font=font)
    draw.text((1400 + gap + 24, 12), "模板重渲", fill=(34, 33, 30), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)


def render_html(html_path: Path, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Chrome resolves relative assets against the file location, so the
        # html has to sit next to qr.png and fonts/.
        work = Path(tmp)
        # screenshot the given file in place when it already lives in assets
        assets = TEMPLATE.parent
        if html_path.resolve().parent == assets.resolve():
            screenshot(html_path, out)
            return
        target = assets / "_render_tmp.html"
        target.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            screenshot(target, out)
        finally:
            target.unlink(missing_ok=True)
        del work


def main() -> None:
    parser = argparse.ArgumentParser(description="把老板绩效考核报告截成 1400×1980 PNG")
    parser.add_argument("--html", type=Path, help="已经填好 REPORT 的模板")
    parser.add_argument("--json", type=Path, help="一份报告 JSON，注入模板后截图")
    parser.add_argument("-o", "--output", type=Path, help="输出 PNG")
    parser.add_argument("--samples", action="store_true", help="重渲 A–E 示例并写出并排对比")
    args = parser.parse_args()

    if args.samples:
        samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
        html = TEMPLATE.read_text(encoding="utf-8")
        expected = {"A": (93, "A"), "B": (79, "B"), "C": (54, "C"), "D": (38, "D"), "E": (16, "E")}
        for key, report in samples.items():
            got = compute(report)
            want_avg, want_grade = expected[key]
            if got["avg"] != want_avg or got["overall"] != want_grade:
                raise SystemExit(f"{key} 算分不对：得到 {got} ，期望 {want_avg} {want_grade}")
            rendered = ROOT / "docs" / "rendered" / f"{key}.png"
            text = inject(html, report)
            tmp_html = TEMPLATE.parent / f"_sample_{key}.html"
            tmp_html.write_text(text, encoding="utf-8")
            try:
                screenshot(tmp_html, rendered)
            finally:
                tmp_html.unlink(missing_ok=True)
            side_by_side(ROOT / "docs" / "original" / f"{key}.png", rendered, ROOT / "docs" / "compare" / f"{key}.png")
            print(f"{key}  {got['overall']} {got['avg']}  最低 {got['low']}  -> {rendered}")
        return

    if args.json:
        report = json.loads(args.json.read_text(encoding="utf-8"))
        print(compute(report))
        html = inject(TEMPLATE.read_text(encoding="utf-8"), report)
        out = args.output or Path("报告.png")
        tmp_html = TEMPLATE.parent / "_render_once.html"
        tmp_html.write_text(html, encoding="utf-8")
        try:
            screenshot(tmp_html, out)
        finally:
            tmp_html.unlink(missing_ok=True)
        print(out)
        return

    html_path = args.html or TEMPLATE
    out = args.output or Path("报告.png")
    render_html(html_path, out)
    print(out)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr.decode("utf-8", "replace") if exc.stderr else "chrome failed\n")
        raise
