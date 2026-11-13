# AI 给我这个老板打分

![五档总评的示例，从 A 到 E](docs/overview.png)

<a href="docs/rendered/A.png"><img src="docs/rendered/A.png" width="340" alt="A 级成绩单，用的是示例数据"></a>

你每天给 AI 派活，其实已经在当老板了。这里按 8 个习惯给你打分：有理有据，引用你的原话，评语轻松但具体，最后出一张可以截图分享的成绩单。版式是固定的，A 到 E 各有一套主题色。

上面的图是示例数据，用来看版式，不是某个人的真实成绩。和设计师定稿的并排对照在 [`docs/compare/`](docs/compare/)。

灵感来自 Addy Osmani（参与打造 Claude Code）的[这篇文章](https://x.com/addyosmani/status/2119332146485891501)，以及 Blum（[@Blum_OG](https://x.com/Blum_OG)）的[这条帖子](https://x.com/Blum_OG/status/2119695424324010288)。

## 一句话安装

用的是 Claude Code、Codex、Cursor 这种**能自己执行命令**的 AI 的话，把下面整段复制给它，它会自己装好：

```
请从这个仓库安装 boss-review：https://github.com/BitPan666/boss-review 。把 skills/boss-review 整个文件夹（含里面的 assets 和 scripts）原样复制到我的用户 skill 目录，不要改文件内容。Claude Code 放到 ~/.claude/skills/boss-review ，Codex 放到 ~/.agents/skills/boss-review ，Cursor 放到 ~/.cursor/skills/boss-review 。你是哪一种，就放到对应的那个目录；分不清就先确认当前工具。装好后告诉我。
```

`~` 就是你的用户主目录。Windows 上一般是 `C:\Users\你的用户名`。

装好之后，直接说「给我这个老板打个分」，或者「评估我怎么用 AI」。在 Codex 里也可以输入 `$boss-review`。

在普通聊天窗口里使用时，把 [`prompt.md`](prompt.md) 和几段对话贴进去。需要手动安装或上传 Skill 时，见[分工具安装指南](docs/install.md)。

## 怎么用

1. 安装后说「给我这个老板打个分」。默认按消息时间评估当前平台近 30 天的对话。Codex 和 Claude Code 可用随 Skill 安装的脚本读取本机记录。其他平台以当前可访问的记录为准；读不到时可以贴几段完整对话。
2. 报告会说明实际使用的时间范围和对话数。八项维度分别评估，证据不足的项不计分；总评为 A–E，证据不足过半显示「?」。
3. 报告给出脱敏的文字证据和一张固定版式的 A4 PNG。PNG 需要 Python 3.10+、Python Playwright 和 Chrome/Chromium；浏览器或脚本不可用时交文字版。
4. 想和上次比，可以把上次的成绩单一并贴进去。

### 在源码仓库验证出图

```bash
python3 -m unittest discover -s tests -v
python3 scripts/render_report.py --samples
```

第一条用合成数据，不需要浏览器。第二条需要 Playwright、Chrome/Chromium 和 Pillow，并生成五张对照图。可用 `CHROME` 指定浏览器路径，包括 Playwright 安装的 `chrome-headless-shell`。受限环境若无法启动多进程，使用该无头浏览器验证时可设置 `BOSS_REVIEW_SINGLE_PROCESS=1`。安装包中的出图脚本支持 `--json report.json -o report.png`；开发时需要检查模板，可使用 `--html-output report.html`。

## 隐私

只有在发起评分时才读取所选来源。采集和出图脚本无需联网，分析仍由你使用的 AI 服务处理。图片只放分数和评语，原话证据只出现在文字版并做脱敏。分享前请确认报告里没有你不想公开的信息。
