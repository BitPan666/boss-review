# AI 给我这个老板打分

![五档总评的示例，从 A 到 E](docs/overview.png)

![A 级成绩单，用的是示例数据](docs/rendered/A.png)

你每天给 AI 派活，其实已经在当老板了。这里按 8 个习惯给你打分：有理有据，引用你的原话，评语轻松但具体，最后出一张可以截图分享的成绩单。版式是固定的，A 到 E 各有一套主题色。

上面的图是示例数据，用来看版式，不是某个人的真实成绩。和设计师定稿的并排对照在 [`docs/compare/`](docs/compare/)。

灵感来自 Addy Osmani（参与打造 Claude Code）的[这篇文章](https://x.com/addyosmani/status/2119332146485891501)，以及 Blum（[@Blum_OG](https://x.com/Blum_OG)）的[这条帖子](https://x.com/Blum_OG/status/2119695424324010288)。

## 一句话安装

用的是 Claude Code、Codex、Cursor 这种**能自己执行命令**的 AI 的话，把下面整段复制给它，它会自己装好：

```
请从这个仓库安装 boss-review：https://github.com/BitPan666/boss-review 。把 skills/boss-review 整个文件夹（含里面的 assets）原样复制到我的用户 skill 目录，不要改文件内容。Claude Code 放到 ~/.claude/skills/boss-review ，Codex 放到 ~/.agents/skills/boss-review ，Cursor 放到 ~/.cursor/skills/boss-review 。你是哪一种，就放到对应的那个目录；分不清就三个都放一份。装好后告诉我。
```

`~` 就是你的用户主目录。Windows 上一般是 `C:\Users\你的用户名`。

装好之后，直接说「给我这个老板打个分」，或者「评估我怎么用 AI」。在 Codex 里也可以输入 `$boss-review`。

## 分工具安装

下面每一种都对照过官方说明。菜单或命令在文档里对不上的，标了「（未验证）」，没有照着猜。

### Claude 网页版或 App

官方说明：[Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)、[How to create custom skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)。

1. 打开 Settings → Capabilities，确认 **Code execution and file creation** 已经打开。新版设置里这项叫 **Create and edit files**。技能要靠它才能用。
2. Team 和 Enterprise：组织所有者要先到 Organization settings → Plugins & skills → Policy，把 **Cloud code execution and file creation** 和 **Skills** 都打开。Team 默认是开的。所有者如果关掉了「用户自己创建技能」，上传入口会消失。
3. 下载本仓库里的 [`boss-review.zip`](boss-review.zip)。压缩包第一层就是 `boss-review` 文件夹，里面有 `SKILL.md` 和 `assets`。不用自己再打包。
4. 打开 Customize → Skills，点「+」，再点「+ Create skill」，选 **Upload a skill**，上传这个 zip。
5. 在技能列表里把它打开。然后说「给我这个老板打个分」。也可以在输入框打 `/` 来找技能。

帮助中心后来有一篇说明，侧边栏的 Customize 已改名为 Plugins（[Manage plugins, skills, and connectors from one Plugins page](https://support.claude.com/en/articles/17740565-manage-plugins-skills-and-connectors-from-one-plugins-page)）。找不到 Customize 时，到 Plugins 里找技能。上传那几下仍然以上面那篇「Use skills」为准。

### Claude Code

官方说明：[Extend Claude with skills](https://code.claude.com/docs/en/skills)、[Install and manage plugins](https://code.claude.com/docs/en/plugins/install)、[Publish and distribute a plugin](https://code.claude.com/docs/en/plugins/publish)。

**复制文件夹（个人技能，所有项目都能用）**

把 `skills/boss-review` 整个文件夹放到 `~/.claude/skills/boss-review`，保证路径是 `~/.claude/skills/boss-review/SKILL.md`。新开一个会话，说「给我这个老板打个分」，或输入 `/boss-review`。

**一条命令安装（插件）**

本仓库带了 Claude Code 的插件市场清单。在终端里：

```bash
claude plugin marketplace add BitPan666/boss-review
claude plugin install boss-review@bitpan666
```

Claude Code v2.1.292 及以后，也可以合成一条：

```bash
claude plugin install boss-review --marketplace BitPan666/boss-review
```

在已经打开的会话里，v2.1.275 及以后可以输入：

```
/plugin install boss-review --marketplace BitPan666/boss-review
```

装好后技能命令是 `/boss-review:boss-review`（插件名加技能名）。直接说「给我这个老板打个分」也会触发。

### OpenAI Codex

官方说明：[Build skills](https://learn.chatgpt.com/docs/build-skills)。安装器自己的说明见 [skill-installer](https://github.com/openai/skills/blob/main/skills/.system/skill-installer/SKILL.md)。

**手动放好（和学习文档一致）**

把 `skills/boss-review` 整个文件夹放到 `~/.agents/skills/boss-review`，保证路径是 `~/.agents/skills/boss-review/SKILL.md`。Codex 会自己发现新技能；没出现就重启一次。调用时输入 `$boss-review`，或在 `/skills` 里选它。直接说「给我这个老板打个分」也可以。

**让安装器去装**

在 Codex 里说：

```
$skill-installer install https://github.com/BitPan666/boss-review/tree/main/skills/boss-review
```

两处官方说明不一致：学习文档写用户技能放在 `~/.agents/skills`，安装器自己的说明写默认装到 `~/.codex/skills`（也就是 `$CODEX_HOME/skills`）。装完如果列表里没有，就改用上面的手动复制。Cursor 的文档写它也会读取 `~/.codex/skills`，所以装到那里时，Cursor 多半也能看到。

### ChatGPT

官方说明：[Projects in ChatGPT](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)、[Creating and editing GPTs](https://help.openai.com/en/articles/8554397-creating-and-editing-gpts)、[ChatGPT Custom Instructions](https://help.openai.com/en/articles/8096356-chatgpt-custom-instructions)。

ChatGPT 网页版读不到这个仓库里的成绩单模板，所以用根目录的 [`prompt.md`](prompt.md)，全文粘贴进去。

- **项目**：侧边栏 New project 建一个项目。点项目的「•••」，选 **Project settings**，把 `prompt.md` 全文贴进项目指令。项目指令只在这个项目里生效，并且会盖过全局自定义指令。项目能用的是这个项目里的聊天和文件，不会自动去翻你在别的聊天里的记录。读不到对话时，按提示词末尾的【对话记录】贴进去。
- **自定义 GPT**：在创建页的 **Instructions** 里贴上 `prompt.md` 全文。官方已宣布自定义 GPT 将退役：受影响的 Enterprise 工作区从 2026 年 10 月 26 日起不能新建，常规退役日期是 2026 年 12 月 11 日。以帮助中心最新说明为准。
- **全局自定义指令**：Settings → Personalization，打开 Enable customization，贴进 Custom Instructions。这段提示词大约 3000 个字符。免费和 Go 的上限是 1500 个字符，放不下；Plus、Pro、Business、Enterprise、Edu 的上限是 5000 个字符，放得下。它会对所有聊天生效，一般还是放进项目更合适。

项目和自定义 GPT 能不能读到你过去所有聊天，帮助中心没有这么写。读不到就贴对话，不要指望它记得。

### Cursor

官方说明：[Agent Skills](https://cursor.com/docs/skills)、[Plugins reference](https://cursor.com/docs/reference/plugins)。

把 `skills/boss-review` 整个文件夹放到 `~/.cursor/skills/boss-review`（只在这台电脑、所有项目可用），或放到 `~/.agents/skills/boss-review`。Cursor 也会读取 `~/.claude/skills/` 和 `~/.codex/skills/`。

在 Agent 聊天里输入 `/`，搜索 `boss-review`。也可以直接说「给我这个老板打个分」。

从 GitHub 导入：官方文档写的是在 Customize 里用 **From GitHub Repository** 导入仓库，仓库里要有 `.cursor-plugin/marketplace.json`。本仓库放了这个文件，插件源写成仓库根目录 `"."`。官方示例里的源都是子目录名，没有「插件就在仓库根目录」这一例，所以这条导入路径标 **（未验证）**。稳妥的做法仍是复制文件夹。

个人技能要给云端 Agent 用，需要另外打开同步：Settings → Agents → Context and Tools → **Sync Skills for Cloud Agents**。只同步 `~/.cursor/skills/`，不同步 `~/.agents/skills/`。

### Gemini CLI

官方说明：[Extension reference](https://geminicli.com/docs/extensions/reference/)、[Agent Skills](https://geminicli.com/docs/cli/skills/)。从 GitHub 安装需要本机有 git。安装时如果询问是否信任来源，确认是这个仓库再同意。

**只装这一个技能**（默认装到 `~/.gemini/skills/boss-review`，所有项目可用）：

```bash
gemini skills install https://github.com/BitPan666/boss-review.git --path skills/boss-review
```

**整仓当扩展安装**（仓库根目录有 `gemini-extension.json`，扩展会带上 `skills/boss-review`）：

```bash
gemini extensions install https://github.com/BitPan666/boss-review
```

扩展相关的命令要在退出交互界面之后、在系统终端里跑。装完重新打开 Gemini CLI。会话里可以用 `/skills list` 确认，或 `/skills reload` 重新扫描。然后直接说「给我这个老板打个分」。

### 豆包、Kimi、DeepSeek，以及其他工具

这些聊天产品没有一份统一的官方安装步骤。最省事的做法：把 [`prompt.md`](prompt.md) 全文贴进对话框，再把几段完整对话贴在最后的【对话记录】里，然后发送。

另外查到、并且写进了官方文档的入口：

- **豆包工作**（不是普通豆包对话）：左侧「插件·技能·伙伴」→「技能」→ 右上角「+ 添加」→「上传技能」。上传的文件里要有 `SKILL.md`，开头是名称和描述。说明见[豆包工作帮助中心](https://www.doubao.com/work/docs/zh-cn/articles/081010973544-skills)。可以用本仓库的 `boss-review.zip`。普通豆包对话没查到同样的上传入口，请用粘贴。
- **Kimi Code CLI**：把文件夹放到 `~/.config/agents/skills/boss-review`（文档里的推荐用户目录；`~/.agents/skills/` 和 `~/.kimi/skills/` 也会被看到）。调用可以输入 `/skill:boss-review`。说明见[Kimi Code CLI 文档](https://moonshotai.github.io/kimi-cli/zh/customization/skills.html)。
- **Kimi 网页 / App**：功能页写了可以分享开源技能的网址来安装，Kimi Work 桌面端可以上传 zip 或 md。[页面](https://www.kimi.com/features/skills)没有写成逐步菜单，这里不补菜单路径 **（未验证）**。读不到历史就仍用 `prompt.md`。
- **DeepSeek 网页或 App**：没有查到官方的技能安装步骤 **（未验证）**。请粘贴 `prompt.md`。

## 怎么用

1. 装好或贴好提示词之后，说「给我这个老板打个分」。
2. 它如果能读到你和 AI 的历史对话，会先告诉你读了哪些、大概多少段，再打分。
3. 读不到的话，它会停下来让你贴几段完整的来回。贴得越多越准。
4. 你会先拿到一份文字成绩单（每项有原话），再拿到一张 1400×1980 的成绩单图。能跑无头浏览器就按技能里的命令截图；不能就给你填好的 HTML，保存成 `.html` 用浏览器打开再截图。完全做不了 HTML 时，按同一版式给你文字版。
5. 想和上次比，把上次的成绩单一并贴进去。

## 隐私

它只出报告，不改你的文件、设置、记忆或项目指令。对话记录只在你自己的 AI 里处理，这个仓库不收集、也不上传你的聊天。引用原话时，它会被要求避开密码、手机号和公司机密。成绩单供娱乐和自我改进，不是人事评价。
