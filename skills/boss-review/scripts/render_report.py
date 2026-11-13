#!/usr/bin/env python3
"""Render report data to an A4 PNG or a portable, offline HTML file."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parent.parent
TEMPLATE = SKILL / "assets" / "report-card.html"
SAMPLES = ROOT / "scripts" / "samples.json"
CHROME = (
    os.environ.get("CHROME")
    or ("/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None)
    or shutil.which("google-chrome")
    or shutil.which("google-chrome-stable")
    or shutil.which("chromium")
    or shutil.which("chromium-browser")
    or next((str(path) for path in (
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ) if path.is_file()), None)
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
    if not isinstance(report, dict):
        raise SystemExit("报告必须是 JSON 对象")
    grades = report.get("grades")
    if grades is None:
        grades = {}
    if not isinstance(grades, dict):
        raise SystemExit("grades 必须是 JSON 对象")
    if unknown := grades.keys() - set(ORDER):
        raise SystemExit(f"未知评分维度：{', '.join(sorted(unknown))}")
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
    """Escape delimiters before the browser parses the textarea as HTML."""
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    return (
        payload.replace("&", "\\u0026").replace("<", "\\u003c")
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


def offline_html(report: dict) -> str:
    html = inject(TEMPLATE.read_text(encoding="utf-8"), report)
    for name, mime in (("qr.png", "image/png"), ("fonts/Inter-ExtraBold.woff2", "font/woff2")):
        encoded = base64.b64encode((TEMPLATE.parent / name).read_bytes()).decode("ascii")
        html = html.replace(f'"{name}"', f'"data:{mime};base64,{encoded}"', 1)
    return html


def report_from_html(path: Path) -> dict:
    # Import data only. Always render with the installed template, even for
    # legacy --html inputs that contain additional scripts.
    html = path.read_text(encoding="utf-8")
    marker = re.search(r"const REPORT = (?=\{)", html)
    if marker is None:
        raise SystemExit("HTML 中没有找到 const REPORT = { ... }")
    try:
        report, end = json.JSONDecoder().raw_decode(html, marker.end())
    except ValueError as exc:
        raise SystemExit(f"REPORT 必须是合法 JSON：{exc}") from exc
    if not html[end:].lstrip().startswith(";"):
        raise SystemExit("REPORT JSON 后必须以分号结束")
    return report


def png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def screenshot(html_path: Path, png_path: Path, timeout_s: float = 30) -> None:
    if not CHROME or not Path(CHROME).exists():
        raise SystemExit("找不到 Chrome 或 Chromium。可用 CHROME 指定浏览器路径，或用 --html-output 导出 HTML")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "截图需要 Python 包 playwright，用的是系统里的 Chrome，不必 playwright install。\n"
            "安装：pip install playwright\n"
            f"导入失败：{exc}"
        ) from exc

    png_path.parent.mkdir(parents=True, exist_ok=True)
    timeout_ms = max(1, int(timeout_s * 1000))
    browser_args = ["--disable-gpu", "--hide-scrollbars", "--disable-crash-reporter"]
    if os.environ.get("BOSS_REVIEW_SINGLE_PROCESS") == "1":
        browser_args += ["--no-zygote", "--single-process"]
    errors: list[str] = []
    console: list[str] = []
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    executable_path=CHROME,
                    timeout=timeout_ms,
                    args=browser_args,
                )
            except Exception as exc:
                raise SystemExit(f"Chrome 启动失败：{exc}") from exc
            try:
                page = browser.new_page(
                    viewport={"width": 1400, "height": 1980},
                    device_scale_factor=1,
                )
                page.set_default_timeout(timeout_ms)
                page.route(re.compile(r"^https?://"), lambda route: route.abort())
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.on(
                    "console",
                    lambda msg: console.append(f"[{msg.type}] {msg.text}")
                    if msg.type in ("error", "warning")
                    else None,
                )
                page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=timeout_ms)
                page.wait_for_function("document.fonts.status === 'loaded'", timeout=timeout_ms)
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


def render_png(html: str, out: Path, timeout_s: float) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    # Isolate each run and publish only after successful screenshot validation.
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        work = Path(tmp)
        source = work / "report.html"
        source.write_text(html, encoding="utf-8")
        staged = work / "report.png"
        screenshot(source, staged, timeout_s)
        staged.replace(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="把老板绩效考核报告导出为 1400×1980 PNG 或离线 HTML")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--html", type=Path, help="从旧 HTML 读取 REPORT JSON，按已安装模板重渲")
    inputs.add_argument("--json", type=Path, help="报告 JSON")
    inputs.add_argument("--samples", action="store_true", help="在源码仓库重渲 A–E 示例")
    parser.add_argument("-o", "--output", type=Path, help="输出 PNG，默认 报告.png")
    parser.add_argument("--html-output", type=Path, help="输出单文件 HTML，未指定 -o 时跳过 PNG")
    parser.add_argument("--timeout", type=float, default=30, help="浏览器各步骤超时，单位秒")
    args = parser.parse_args()

    if args.samples:
        if not SAMPLES.is_file():
            parser.error("--samples 需要源码仓库的 scripts/samples.json")
        samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
        expected = {"A": 93, "B": 79, "C": 54, "D": 38, "E": 16}
        for key, report in samples.items():
            got = compute(report)
            if (got["avg"], got["overall"]) != (expected[key], key):
                raise SystemExit(f"{key} 算分不对：{got}")
            rendered = ROOT / "docs" / "rendered" / f"{key}.png"
            render_png(offline_html(report), rendered, args.timeout)
            side_by_side(ROOT / "docs" / "original" / f"{key}.png", rendered,
                         ROOT / "docs" / "compare" / f"{key}.png")
            print(f"{key}  {got['avg']}  最低 {got['low']}  -> {rendered}")
        return

    try:
        report = (json.loads(args.json.read_text(encoding="utf-8")) if args.json
                  else report_from_html(args.html))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"无法读取报告数据：{exc}") from exc
    score = compute(report)
    html = offline_html(report)
    print(json.dumps(score, ensure_ascii=False))
    if args.html_output:
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(html, encoding="utf-8")
        print(args.html_output)
    if args.output or not args.html_output:
        out = args.output or Path("报告.png")
        render_png(html, out, args.timeout)
        print(out)


if __name__ == "__main__":
    main()
