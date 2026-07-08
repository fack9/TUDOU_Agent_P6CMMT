# TUDOU_Agent

## 关于TUDOU_agent

`TUDOU_Agent`是`D.potato(某李)`一定程度上模仿`claude_code`所编写的一款`windows环境`多功能agent,由于使用大量`ASCII`转义码,除了在`windows11专业版`上,其它的`windows`版本都会爆乱码,但功能不变(人话就是没特效皮肤了)

### TUDOU_agent目前功能

- `Bash`命令行
- `web sreach`网络搜索
- `web fetch`静态网页爬取
- `browserfetch`动态网页爬取
- `write`文件写入
- `read`阅读文件
- `glob`特定文件寻找
- `grep`数据寻找
- `planmode`进入计划模式,此模式下LLM只能探索项目，制定计划方案，不可修改源文件或创建，随后把计划书交给你审批(LLM用)
- `codemode`进入代码模式,此模式下LLM可执行改动类指令(优先级依然低于rootmodel指令使用前),直接开始写代码(LLM用)
- `edit`文件修改
- `taskcreate`任务创建(LLM用)
- `taskupdate`任务更新(LLM用)
- `sub-agent`多agent实例并行(LLM用)
- `enablesandbox`环境隔离沙箱
- `Retrieve`文件详情

<!-- 连接定义 -->
[headroom]:https://github.com/chopratejas/headroom
[CLI-Anything]:https://github.com/HKUDS/CLI-Anything
[taste-skills]:https://github.com/Leonxlnx/taste-skill/tree/main
[codex-skills]:https://github.com/ComposioHQ/awesome-codex-skills
[RecursiveMAS]:https://github.com/RecursiveMAS/RecursiveMAS
[RecursiveMAS2]:https://github.com/RecursiveMAS/RecursiveMAS

### TUDOU_agent使用/接入的开源项目

- <p align="left">
  <a href="https://github.com/chopratejas/headroom"><img src="https://img.shields.io/badge/headroom-blue?style=for-the-badge" alt="headroom"></a>
 </p>

- <p align="left">
  <a href="https://github.com/HKUDS/CLI-Anything"><img src="https://img.shields.io/badge/CLI_Anything-blue?style=for-the-badge" alt="CLI-Anything"></a>
 </p>

- <p align="left">
  <a href="https://github.com/Leonxlnx/taste-skill/tree/main"><img src="https://img.shields.io/badge/taste_skills-blue?style=for-the-badge" alt="taste-skills"></a>
 </p>

- <p align="left">
  <a href="https://github.com/ComposioHQ/awesome-codex-skills"><img src="https://img.shields.io/badge/awesome_codex_skills-blue?style=for-the-badge" alt="awesome-codex-skills"></a>
 </p>
<!-- 我去了啊,现在才知道有shields.io这个东西 -->
<!-- 不会写啊 -->

### TUDOU_agent功能更新&质量更新(报错修复不算在内) (V为版本号)

- 肥美的agent刚出世时候 V = `0.10.0.0`
- 更新启动`TUDOU``ASCII`艺术特效 V = `0.10.0.1`
- 输入框优化 V = `0.10.0.2`
- `Edit`内容可视化工具 V = `0.11.0.2`
- 新增给老傻子用的`importdangerskills`和`removeskills`指令 V = `0.11.1.2`
- 新增`remote`飞书远程接口 V = `0.12.1.2`
- `remote`指令新增`status`和`nocode`参数 V = `0.12.1.3`
- `thinking`提示特效优化 V = `0.12.1.4`
- 工具调用输出内容优化 V = `0.12.1.5`
- 新增给老傻子用的`set`系列指令(`set`/`MAPI`/`MURL`/`FID`/`FAS`) V = `0.12.2.5`
- 新增`rootmodel`指令 V = `0.12.3.5`
- 新增`betterui`指令 V = `0.12.4.5`
- 新增`LLM`模式`planmode` V = `0.12.5.5`
- 新增`LLM`模式`codemode` V = `0.12.6.5`
- 输入框二次优化 V = `0.12.6.6`
- `planmode`&`codemode`右边状态提示(+0.0.0.2) V = `0.12.6.8`
- 输入框3次优化 V =`0.12.6.9`
- agent整体UI质量优化 V =`1.12.6.9`
- 新增`shell`模式和其专属`downshell`命令 V =`1.12.7.9`
- 新增`memory`/`history`/`permissions`指令参数  V =`1.12.8.9`
  | 指令 | 参数|
  |--------|--------|
  |`memory`|`list/show/delete/LLM`|
  |`history`|`recent/list/show/LLM`|
  |`permissions`|`status/mode/allow/deny/remove/LLM`|
  
  (`LLM`参数是直接将指令给`LLM`让它们干活.不由agent执行)
- `MCP`支持+`/mcp`指令+会话自动持久化到`SQLite`+`/history`跨`session保留`  V =`1.13.8.9`
- `config`命令结果大改,从原本的纯字符输出改为像`nano`一样的可修改子界面 V =`1.13.9.9`
- 输出模式超级大改,从死的汇总式输出改为流式输出,和个别其他的输出效果 V =`1.14.9.9`
- `context`模块逻辑+质量升级 V =`1.15.0.9`
- 命令列表新增参数显示+列表质量升级(+0.0.0.2) V =`1.15.1.1`
- agent全能性大加强,[`CLI-Anything`][CLI-Anything]工具接入`TUDOU_agent`,同时添加`buildCLI`指令用于封装目标软件的`CLI`模式 V =`1.16.1.1`
- 新增`resume`指令,用于切换到指定`ID`的会话,还可使用多种参数,`list`还可后接参数`all`,为了方便查看,在单`session`中的第一条消息会被`LLM`自动整理为会话标题 V =`1.16.2.1`
- 新增`export`指令用于导出特定`session` V =`1.16.3.1`
- 新增`TaskCreate`和`TaskUpdate`让agent把大任务拆成小步骤跟踪进度(+0.0.1.1) V =`1.16.4.2`
- 新增`TaskCreate`所生成的树状任务图 V =`1.16.4.3`
- 执行询问样式大优化,包含所有工具(+0.0.0.2) V =`1.16.4.5`
- 新增可配置的`bing_API_key`用于更好的搜索能力(默认仍是`BS4`解析,失败后使用`bing_API_key`) V =`1.16.5.5`
- 新增`BrowserFetch`用于抓取动态网页,并且添加副`LLM`内容提炼和页面原始信息`markdown`解析(+0.0.1.1) V =`1.16.6.6`
- 新增`AssistLLM`指令用于开启和关闭副`LLM`提炼网页内容 V =`1.16.7.6`
- `context`模块大升级,将[`headroom`][headroom]的上下文压缩和提炼逻辑接入`TUDOU_agent`的`context`,并允许`LLM`选择性查看原文还是压缩文 V =`1.17.6.6`
- 支持`LLM`一次性传回多指令运行 V =`1.17.6.7`
- 将命令输出从固定输出变为流式输出 V =`1.17.6.8`
- 新增`LLM`调用重试 V =`1.17.6.9`
- 添加`sub-agent`和其允许启用指令`subagent`,用于在复杂任务下主agent分解任务并委派至子agent执行 V =`1.17.7.9`
- 新增`hook`功能组件 V =`1.18.7.9`
- 添加`AskUserQuestion`环节,并升级了`task`面板的出现和清理逻辑 V =`1.18.8.9`
- 新增`Prompt Caching`用于减少调用工具的**token**损耗(如果模型不支持自动退回) V =`1.18.9.0`
- 支持可推理模型的`thinking`模式 V =`1.18.9.1`
- 新增更安全的`Workspace`隔离测试环境,用完即弃 V =`1.19.9.1`
- 新增`skills`指令和其多种参数,核心新增参数`install`需要自行去下载`Git Bash`,并且`install`仅支持下载`Github`上的`skills`(与`Github`连接需要加速器) V =`2.10.9.1`
- 新增`Low-Integrity`式沙箱,和`sandbox`系列指令 V =`2.11.9.1`
- 新增断点崩溃恢复机制,如果一个会话意外崩溃,需要重启,则可在新对话中直接输入`resume`,`resume`的新逻辑优先检查有没有`checkpoint`,随后载入并加载崩溃的会话内容 V =`2.12.0.1`
- 启动速度优化 V =`2.12.0.2`
- 新增窗口标题PID V =`2.12.0.3`
- 新增多模态图片读取功能 V =`2.12.1.3`
- 新增`skills`模型自决策调用功能 V =`2.12.2.3`
- 新增三个`LLM`用`skills`工具,`skills`热加载改为模型主动加载 V =`2.13.2.3`
- 将返回给`LLM`的调试信息从简陋的错误码改为添加完整报错,如(示例): V =`2.13.3.3`
```bash
以前的信息:
Error: Exit code 1

现在的信息:
Error: Exit code 1
     ============================================================
     7. RENDERER — source verification (no import)
     ============================================================
       ✓ render_tool_output_line has stream param
     Traceback (most recent call last):
       File "<stdin>", line 13, in <module>
     AssertionError
```
- 新增`Task`工具的合并 V =`2.13.3.4`
- 新增完整工具错误提示(给`LLM`的),如`glob`以前是返回源代码的报错,现在有内置工具的语法提示 V =`2.13.3.5`
- 将工具的流式输出进行一定处理,从原本的原始输出改为成功指令显示淡蓝色内容,错误为品红色 V =`2.12.3.6`
- 新增13个[`taste-skills`][taste-skills]旗下的`skill`包,可显著提升`LLM`的前端审美,列表如下: V =`2.13.3.6`
代码生成类:

| 技能名称 | 文件夹 | 大小 | 说明 |
|---|---|---|---|
| `design-taste-frontend` | taste-taste-skill | 84KB |  v2 主技能。读取需求 → 推断设计语言 → 三刻度盘控制（VARIANCE / MOTION / DENSITY）。含 Brief Inference、Design System Map、GSAP 动画骨架、Pre-Flight Check |
| `design-taste-frontend-v1` | taste-taste-skill-v1 | 20KB | v1 原版，保留给已有项目依赖 |
| `gpt-taste` | taste-gpt-tasteskill | 7KB | GPT/Codex 严格变体：更高布局方差、更强 GSAP 方向、激进反 slop |
| `image-to-code` | taste-image-to-code-skill | 34KB | 图片优先流水线：生成参考图 → 分析 → 实现前端 |
| `redesign-existing-projects` | taste-redesign-skill | 14KB | 已有项目重设计：先审计 UI → 修复布局/间距/层级/样式 |
| `high-end-visual-design` | taste-soft-skill | 10KB | 高端视觉设计：柔和对比度、宽松留白、高级字体、spring 动效 |
| `full-output-enforcement` | taste-output-skill | 2KB | 防止模型半成品输出：完整代码、禁止 placeholder 注释 |
| `minimalist-ui` | taste-minimalist-skill | 7KB | 极简 editorial 风（Notion/Linear 感）：克制调色板、清晰结构 |
| `industrial-brutalist-ui` | taste-brutalist-skill | 7KB | 工业粗野主义：瑞士字体、锐利对比、实验性布局 |
| `stitch-design-taste` | taste-stitch-skill | 11KB | Google Stitch 兼容规则，含可选 `DESIGN.md` 导出格式 |
图片生成技能类:

| 技能名称  | 文件夹 | 大小 | 说明 |
|---|---|---|---|
| `imagegen-frontend-web` | taste-imagegen-frontend-web | 35KB | Web 页面参考图：Hero、Landing、多段式排版，强字体/间距/反 slop |
| `imagegen-frontend-mobile` | taste-imagegen-frontend-mobile | 38KB | 移动端参考图：iOS/Android/跨平台 mockup |
| `brandkit` | taste-brandkit | 15KB | 品牌套件：Logo 方向、调色板、字体、跨品类应用 |
- `bash`等工具新增响应时前端效果 V =`2.13.3.7`
- 新增`exlpore`工具用于`LLM`大规模查看文件/目录 V =`2.13.4.7`
- `context`命令输出大改,改为`claude_code`式的输出,示例: V =`2.13.5.7`
```bash
❯ /context
⎿  Context Usage
     ⛁ ⛁ ⛁ ⛁ ⛀ ⛀ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁   deepseek-v4-pro[1m]
     ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁   268.5k/1m tokens (27%)
     ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛶ ⛶ ⛶ ⛶ ⛶
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   Estimated usage by category
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ System prompt: 6.5k tokens (0.6%)
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ System tools: 15.9k tokens (1.6%)
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ Memory files: 1.3k tokens (0.1%)
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ Skills: 618 tokens (0.1%)
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ Messages: 244.5k tokens (24.5%)
     ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝   ⛶ Free space: 698.2k (69.8%)
                                               ⛝ Autocompact buffer: 33k tokens (3.3%)

     Memory files · /memory
     ├ ~/.claude/CLAUDE.md: 612 tokens
     └ ~/.claude/projects/-mnt-c-Users-wa/memory/MEMORY.md: 715 tokens

     Skills · /skills

      Suggestions
      ℹ File reads using 78.7k tokens (8%) → save ~23.6k
        If you are re-reading files, consider referencing earlier reads. Use offset/limit for large files.
```
- 用户提问环节`AskUserQuestion`样式大改 V =`2.13.6.7`
- 优化`Anthropic`模型的缓存命中率,大约提高20%-30%不等 V =`2.13.7.7`
- `explore`样式大改,同时添加动态计数器,添加`running…`用于表示工具运行中等等样式 V =`2.13.8.7`
- 优化`write`的样式 V =`2.13.8.8`
- 优化`memory`相关提示词,大约减少%45左右的大小 V =`2.13.8.9`
- `skills`除了`taste-skills`全部替换为[`codex-skills`][codex-skills],同时引入`codex`的**渐进式三层** V =`2.14.8.9`
- `task-tree`样式大改,同样改为`claude-code`式:
```bash
旧样式:
17 ╭─────────────────────────────────────╮
18 │  ▸ Task progress (2 active) (...)|
19 │  ├─ [1] ● Fix auth bug            │
20 │  └─ [2] ○ Add logout             │
21 ╰─────────────────────────────────────╯

新样式:
26 Deploying Staging environment… (2s · ↓ 45 tokens · thought for 1s)
27   ⎿  ◼ Deploy Staging environment
28       ◻ Optimize database query performance › blocked by #1
29       ✔ Write user authentication module (3s)
```
- 整个agent的所有UI样式全部大更新,同时升级`betterui`的逻辑和效果并改名为`quiet` V =`2.15.8.9`
- `sub-agent`功能升级,完善,并优化了提示词 V =`2.15.9.0`
- 更新了输入框持久化(*ghost*)并为`Explore`添加最新内容滚动(+0.0.0.2) V =`2.15.9.2`
- `skills`管理升级,并优化了所有`system_prompt`,重点优化用户画像的制作,添加了内化`skills` V =`2.16.9.2`
- 新型`Prompt`架构,`LLM`多次生`Prompt`,`Prompt`可自进化,`LLM`会不断总结经验并更新`Prompt` V =`2.17.9.2`

### TUDOU_agent重大更新节点

- `remote`飞书接口支持 V = `0.12.1.2`
- agent整体UI质量优化 V =`1.12.6.9`
- `MCP`协议支持 V =`1.13.8.9`
- `CLI-Anything`工具接入`TUDOU_agent`并添加`buildCLI`指令 V =`1.16.1.1`
- 使用`headroom`的上下文压缩和提炼逻辑作为`context`模块的更新 V =`1.17.6.6`
- 自研新型`Prompt`自进化架构 V =`2.17.9.2`

### TUDOU_agent组件&配置文件

- `skills`文件,库文件夹为`builtin_skills`中
- `memory`创建,以支持大模型跨会话记忆(有时候你得主动和他说记忆会话,他才会保存记忆)
- 根目录下的`config.yaml`文件为大模型配置文件和`config`文件夹
- 根目录下的`hooks`文件夹中的`yaml`文件可以配置全局`hook`脚本配置和项目级配置
- `Workspace`隔离,隔离环境不影响实际,用完即弃
- `Low-Integrity`式`sandbox`,可由`LLM`或手动指令进入,环境完全隔离,不影响实际环境,用完即弃
- `hook`自定义条件触发脚本

### 如何配置模型

- 1.前往任意大模型网页(如果你还没有`API_key`),找到API平台服务(`TUDOU`这边默认是`deepseek-v4-pro`)
- 2.根据网页指示创建一个API_key(注意,大部分API平台只在创建时给你,必需复制,后续API_key无法复制),随后前往keys充值(建议不常用就先充50,反正token也差不多)
- 3.打开`config.yaml`文件,国内大模型就在`openai_compat`一栏中填写你的`api_key`和`base_url`(或者是用`setmapi`和`setmurl`指令来设置)(`base_url`你得自己去查看网页给的接口文档,`TUDOU`这边默认是`deepseek`的`https://api.deepseek.com/v1`)

### 如何配置远程连接(选填,不填只导致remote指令不可用)

- 1.前往`飞书`官网，并注册账号(https://open.feishu.cn/?lang=zh-CN)
- 2.前往`https://open.feishu.cn/?lang=zh-CN`,点击`CLI`下方的`立即体验`
- 3.点击右上角的`开发者后台`,点`创建企业自建应用`,填报创建信息
- 4.在左边列表中找到`添加应用能力`,选择`机器人`
- 5.点击`权限管理`,找到`批量导入/导出权限`,选择`导入`,随后删除它给你的默认JSON信息，黏贴一下内容:
```json
{
  "scopes": {
    "tenant": [
      "application:application:self_manage",
      "application:bot.menu:write",
      "cardkit:card:read",
      "cardkit:card:write",
      "contact:contact.base:readonly",
      "docs:document.comment:create",
      "docs:document.comment:delete",
      "docs:document.comment:read",
      "docs:document.comment:update",
      "docs:document.comment:write_only",
      "docx:document.block:convert",
      "docx:document:create",
      "docx:document:readonly",
      "docx:document:write_only",
      "drive:drive.metadata:readonly",
      "im:chat.members:bot_access",
      "im:chat.members:read",
      "im:chat:read",
      "im:chat:readonly",
      "im:chat:update",
      "im:message.group_at_msg.include_bot:readonly",
      "im:message.group_at_msg:readonly",
      "im:message.p2p_msg:readonly",
      "im:message.pins:read",
      "im:message.pins:write_only",
      "im:message.reactions:read",
      "im:message.reactions:write_only",
      "im:message:readonly",
      "im:message:send_as_bot",
      "im:message:send_multi_users",
      "im:message:send_sys_msg",
      "im:message:update",
      "im:resource"
    ],
    "user": [
      "offline_access"
    ]
  }
}
```

完成后点击`下一步,确认新增权限`,然后点`申请开通`
- 6.点`事件与回调`,点`订阅方式`,选择`长连接`,然后保存,点`添加事件`,在搜索栏中黏贴`im.message.receive_v1`随后勾选，点`添加`
- 7.点`版本管理与发布`,点`创建版本`,把信息填好，点`保存`
- 8.回到`凭证与基础信息`,复制你的`App ID`和你的`App Secret`至`remote`栏位下`feishu`下的`app_id`和`app_secret`(或者是直接使用`setfas`和`setfid`指令设置)
- 9.打开你的手机，下载`飞书`,完成各种验证,随后在搜索栏搜索你保存的实例名称，找到他就可以对话了(记得一定先在agent上运行/remote start )

### 个别提示词回复错误说明&命令行错误

- 个别`LLM`你问他哪家公司的模型,如`deepseek`,他可能回答你是`Anthropic`的`claude`,底层原因是这些`LLM`他们本身知识库和训练集中没有告诉他们是谁,而`TUDOU_agent`中的预提示词一部分是从`claude_code`里扒出来,`LLM`看提示词推测他就是`Anthropic`的模型(2025年后各公司产出的大模型大部分都有这个问题,他们的知识库和训练集中基本都多多少少有`claude_code`的东西)
- 如果你发给他 `<thinking>`他可能会回复你一些很无厘头的回复,这是因为个别`LLM`如`deepseek`他们在训练的时候有一组固定的问题和答案,他们之中直接可以用`<thinking>`来触发回答
- 如果`LLM`运行的指令是`Linux`(`Ubuntu`)的,并且是解析文件字节,他可能会报错:
```bash
报错信息:
Exception in thread Thread-95 (_readerthread):
Traceback (most recent call last):
  File "threading.py", line 1075, in _bootstrap_inner
  File "threading.py", line 1012, in run
  File "subprocess.py", line 1599, in _readerthread
UnicodeDecodeError: 'gbk' codec can't decode byte 0xae in position 11: illegal multibyte sequence
```
这是正常现象,不影响整体运行,原因是`TUDOU_agent`是用`PyInstaller`打包的`Windows`应用程序,`subprocess.Popen`调用的是`GBK`解码,当`subprocess.Popen`执行`Linux`命令时,如果命令的目标文件含有`UTF-8`的特殊字节(合法字节),如`0xae`是一个`GBK`中的非法多字节序列,但却是`UTF-8`的合法字节,`GBK`就会直接报错上面的示例信息,人话:`subprocess`用`GBK`去解码`UTF-8`输出，遇到`GBK`不认识的字节就炸了
- 如果你在`shell`模式中运行需要检测终端环境是否符合要求的文件,他将会报错,如你在shell模式下再次运行`TUDOU_agent`他会报错:
```bash
Error: D:\Program Files\Python312\Lib\site-packages\lark_oapi\ws\pb\google\__init__.py:2: UserWarning: pkg_resources is
deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated
for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  __import__('pkg_resources').declare_namespace(__name__)
Traceback (most recent call last):
  File "C:\Users\wa\Desktop\TUDOU_area\TUDOU_claude_projact\TUDOU_agent\projact\main.py", line 51, in <module>
    main()
  File "C:\Users\wa\Desktop\TUDOU_area\TUDOU_claude_projact\TUDOU_agent\projact\main.py", line 45, in main
    cli = TUDOU_CLI(cli_overrides if cli_overrides else None)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\wa\Desktop\TUDOU_area\TUDOU_claude_projact\TUDOU_agent\projact\cli.py", line 83, in __init__
    self.input_handler = InputHandler(history_file=paths.get('user_history_file'), get_plan_state=lambda:
self._plan_state.get('active', False), get_code_mode=lambda: self._code_mode, get_shell_mode=lambda: self._shell_active)
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\wa\Desktop\TUDOU_area\TUDOU_claude_projact\TUDOU_agent\projact\ui\input_handler.py", line 174, in
__init__
    self.session = _SepPromptSession(history=history, auto_suggest=AutoSuggestFromHistory(), completer=SlashCompleter(),
style=PROMPT_STYLE, multiline=False, get_plan_state=get_plan_state, get_code_mode=get_code_mode,
get_shell_mode=get_shell_mode)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
^^^^^^^^
  File "C:\Users\wa\Desktop\TUDOU_area\TUDOU_claude_projact\TUDOU_agent\projact\ui\input_handler.py", line 57, in
__init__
    super().__init__(*args, **kwargs)
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\shortcuts\prompt.py", line 476, in __init__
    self.app = self._create_application(editing_mode, erase_when_done)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\wa\Desktop\TUDOU_area\TUDOU_claude_projact\TUDOU_agent\projact\ui\input_handler.py", line 60, in
_create_application
    app = super()._create_application(*args, **kwargs)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\shortcuts\prompt.py", line 727, in
_create_application
    application: Application[_T] = Application(
                                   ^^^^^^^^^^^^
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\application\application.py", line 267, in __init__
    self.output = output or session.output
                            ^^^^^^^^^^^^^^
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\application\current.py", line 67, in output
    self._output = create_output()
                   ^^^^^^^^^^^^^^^
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\output\defaults.py", line 91, in create_output
    return Win32Output(stdout, default_color_depth=color_depth_from_env)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\output\win32.py", line 115, in __init__
    info = self.get_win32_screen_buffer_info()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Program Files\Python312\Lib\site-packages\prompt_toolkit\output\win32.py", line 219, in
get_win32_screen_buffer_info
    raise NoConsoleScreenBufferError
prompt_toolkit.output.win32.NoConsoleScreenBufferError: No Windows console found. Are you running cmd.exe?
```
原因是`shell`模式里通过`subprocess.run(..., shell=True)`启动了`main.py`而源代码子进程的`stdout/stderr`是管道（`capture_output=True`），不是真正的`Windows`控制台,启动时`main`创建`TUDOU_CLI()`→创建`InputHandler()`→ 创建`prompt_toolkit.PromptSession`→`PromptSession`初始化时调用`create_output()`检测当前环境→`Windows`上检测到`stdout`不是真正的控制台→抛出
```bash
NoConsoleScreenBufferError: "No Windows console found. 
Are you running cmd.exe?"
```
人话:进程需要一个真实的终端才能工作，管道不行。你在`shell`模式里跑一个同样依赖的程序，子进程拿不到真正的控制台句柄，直接挂了。
- 千万不要作死让`LLM`或者在`shell`模式中执行`wsl`这类运行于`windows`的控制台,他们的输出并不会被传回`TUDOU_agent`而是后台运行(你让`LLM`运行它会报错超时,但实际它运行了),而这时,你按什么键`TUDOU_agent`都不会显示,因为此时你的输入优先级在`wsl`的界面,虽不显示但你输入的内容`enter`后仍会生效,如果是`wsl`你可以输入`exit`来退出这种状态,其他的就不知道了

### TUDOU_agent目前研究

- Agent在面对长任务时，自发输出的一种高信息密度编码，对于我们人类来说完全不可读，信息密度约为英语的2-4倍左右,可大量节省token
  现`Github`上已有项目将此工程化,但目前仍未通用化，目前仅针对`Qwen/Llama/Gemma`,并且由于`TUDOU_agent`目前仅`API`,而不是本地模型,此项目可能无法接入(`API`仅能传输正常文本和图像等数据，而隐藏状态向量不能表示为文本，否则会变成乱码,反而使模型更加难以理解甚至崩溃,并且这个项目是针对小模型的)
- 以下是官网上的流程图:

- <img src="https://recursivemas.github.io/static/images/figures/RecursiveLearning.png" alt="RecursiveMAS" width="900" height="700">

- 仓库:[***`RecursiveMAS`***][RecursiveMAS]
- 官方地址:[***`RecursiveMAS`***][RecursiveMAS2]

### ???

- ***何意味啊,咕咕嘎嘎....***
- 此`TUDOU_agent`版本:`TUDOU_agent_VMSSUBN_2.15.9.0_version`