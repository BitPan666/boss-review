#!/usr/bin/env python3
"""把 report-card.html 用无头 Chrome 截成 1400×1980 的 PNG。

只改 skills/boss-review/assets/report-card.html 顶部的 REPORT，然后：

    python3 scripts/render_report.py --html skills/boss-review/assets/report-card.html -o 报告.png

从一份 JSON 注入模板再截图：

    python3 scripts/render_report.py --json report.json -o 报告.png

重渲五张示例并和 docs/original 并排对比：

    python3 scripts/render_report.py --samples

依赖：本机的 Google Chrome（/usr/bin/google-chrome 或 PATH 里的 google-chrome），
以及 Python 包 playwright（`pip install playwright`）。截图由 Playwright 驱动这个
系统 Chrome，不必再执行 `playwright install`。`--samples` 的并排对比还需要 Pillow。
Chrome 自带的 `--screenshot` 在部分 Linux 上会一直挂到超时，所以这里不走那条路径。

超时默认 30 秒，可以用 `--timeout 60` 加长。脚本出错会把页面错误打出来并以非 0 退出，
不会留下一张写着默认分数的图。

截图前会等文档字体加载完。机器上有「苹方 / PingFang SC」时，字形和 Peter 的定稿一致；
没有的话仍用系统黑体，版式不变。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "skills" / "boss-review" / "assets" / "report-card.html"
SAMPLES = Path(__file__).resolve().parent / "samples.json"
CHROME = (
    os.environ.get("CHROME")
    or ("/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None)
    or shutil.which("google-chrome")
    or shutil.which("google-chrome-stable")
    or shutil.which("chromium")
    or shutil.which("chromium-browser")
)

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


def normalize_grade(value, item: str):
    if value is None:
        return None
    if not isinstance(value, str):
        raise SystemExit(f"「{item}」的等级必须是 A–F 或 null，得到 {value!r}")
    grade = value.strip().upper()
    if grade not in HALF:
        raise SystemExit(f"「{item}」的等级 {value!r} 无法识别，只能是 A–F 或 null")
    return grade


def compute(report: dict) -> dict:
    grades = report.get("grades") or {}
    half = scored = na = 0
    worst = None
    worst_name = None
    seen = []
    for name in ORDER:
        g = normalize_grade(grades.get(name), name)
        if g is None:
            na += 1
            continue
        scored += 1
        seen.append(g)
        half += HALF[g]
        s = HALF[g] / 2
        if worst is None or s < worst:
            worst = s
            worst_name = name
    if seen and all(g == seen[0] for g in seen):
        worst_name = None
    avg = round_half_up(half, scored) if scored else None
    overall = "?" if na * 2 > len(ORDER) or avg is None else overall_of(avg)
    return {"avg": avg, "overall": overall, "scored": scored, "na": na, "low": worst_name}


def js_payload(report: dict) -> str:
    """JSON that is safe to drop inside a <script> element.

    `<` becomes \\u003c so a value like `</script>` cannot close the tag or run.
    The page then reads the object as data and writes it with textContent.
    """
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    return (
        payload.replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def inject(html: str, report: dict) -> str:
    payload = js_payload(report)
    pattern = re.compile(r"const REPORT = \{.*?\n\};", re.S)
    replaced, n = pattern.subn(lambda _m: f"const REPORT = {payload};", html, count=1)
    if n != 1:
        raise SystemExit("模板里没有找到 const REPORT = { ... }")
    return replaced


def png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def screenshot(html_path: Path, png_path: Path, timeout_s: float = 30) -> None:
    if not CHROME or not Path(CHROME).exists():
        raise SystemExit("找不到 Google Chrome（期望 /usr/bin/google-chrome），无法截图")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "截图需要 Python 包 playwright，用的是系统里的 Chrome，不必 playwright install。\n"
            "安装：pip install playwright\n"
            f"导入失败：{exc}"
        ) from exc

    png_path.parent.mkdir(parents=True, exist_ok=True)
    if png_path.exists():
        png_path.unlink()
    html_text = html_path.read_text(encoding="utf-8")
    lowered = html_text.lower()
    # A raw </script> inside the report data would execute if it were in a
    # script element. The template keeps the data in a textarea and allows
    # exactly two script tags; anything else is rejected before Chrome runs.
    if lowered.count("</script>") != 2 or lowered.count("<script") != 2:
        raise SystemExit("页面脚本出错：HTML 里有未转义的 </script>，拒绝截图")
    timeout_ms = max(1, int(timeout_s * 1000))
    errors: list[str] = []
    console: list[str] = []
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    executable_path=CHROME,
                    args=[
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--hide-scrollbars",
                        "--force-device-scale-factor=1",
                        "--disable-dev-shm-usage",
                    ],
                )
            except Exception as exc:
                raise SystemExit(f"Chrome 启动失败：{exc}") from exc
            try:
                page = browser.new_page(
                    viewport={"width": 1400, "height": 1980},
                    device_scale_factor=1,
                )
                page.set_default_timeout(timeout_ms)
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.on(
                    "console",
                    lambda msg: console.append(f"[{msg.type}] {msg.text}")
                    if msg.type in ("error", "warning")
                    else None,
                )
                page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=timeout_ms)
                page.evaluate("() => document.fonts.ready")
                state = page.evaluate(
                    """() => ({
                      rendered: document.body.dataset.rendered || "",
                      error: document.body.dataset.renderError || ""
                    })"""
                )
                if state["error"] or errors or state["rendered"] != "ok":
                    detail = state["error"] or "\n".join(errors) or "脚本没有跑完，页面没有完成渲染"
                    extra = "\n".join(console)
                    tail = f"\n控制台：\n{extra}" if extra else ""
                    raise SystemExit(f"页面脚本出错：{detail}{tail}")
                page.screenshot(path=str(png_path), full_page=False, timeout=timeout_ms)
            finally:
                browser.close()
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"Chrome 截图失败：{exc}") from exc
    if not png_path.exists() or png_path.stat().st_size < 1000:
        raise SystemExit(f"截图失败：{png_path}（Chrome 没有写出图片）")
    size = png_size(png_path)
    if size != (1400, 1980):
        raise SystemExit(f"截图尺寸是 {size}，期望 1400×1980：{png_path}")


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


def render_html(html_path: Path, out: Path, timeout_s: float) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Chrome resolves relative assets against the file location, so the
        # html has to sit next to qr.png and fonts/.
        work = Path(tmp)
        # screenshot the given file in place when it already lives in assets
        assets = TEMPLATE.parent
        if html_path.resolve().parent == assets.resolve():
            screenshot(html_path, out, timeout_s)
            return
        target = assets / "_render_tmp.html"
        target.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            screenshot(target, out, timeout_s)
        finally:
            target.unlink(missing_ok=True)
        del work


def main() -> None:
    parser = argparse.ArgumentParser(description="把老板绩效考核报告截成 1400×1980 PNG")
    parser.add_argument("--html", type=Path, help="已经填好 REPORT 的模板")
    parser.add_argument("--json", type=Path, help="一份报告 JSON，注入模板后截图")
    parser.add_argument("-o", "--output", type=Path, help="输出 PNG")
    parser.add_argument("--samples", action="store_true", help="重渲 A–E 示例并写出并排对比")
    parser.add_argument("--timeout", type=float, default=30, help="截图超时，单位秒，默认 30")
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
                screenshot(tmp_html, rendered, args.timeout)
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
            screenshot(tmp_html, out, args.timeout)
        finally:
            tmp_html.unlink(missing_ok=True)
        print(out)
        return

    html_path = args.html or TEMPLATE
    out = args.output or Path("报告.png")
    render_html(html_path, out, args.timeout)
    print(out)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr.decode("utf-8", "replace") if exc.stderr else "chrome failed\n")
        raise
