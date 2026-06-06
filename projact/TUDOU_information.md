# TUDOU_Agent
## 关于TUDOU_agent
`TUDOU_Agent`是`D.potato(某李)`一定程度上模仿`claude_code`所编写的一款`windows环境`多功能agent,由于使用大量`ASCII`转义码,除了在`windows11专业版`上,其它的`windows`版本都会爆乱码,但功能不变(人话就是没特效皮肤了)

### TUDOU_agent目前功能
- `Bash`命令行
- `web sreach`网络搜索
- `web fetch`静态网页爬取
- `browserfetch`动态网页爬取
- `write`文件写入
- `read`支持大模型(默认为大语言模型(`LLM`) )阅读文件
- `glob`特定文件寻找
- `grep`特定文件内部特定数据寻找
- `planmode`进入计划模式,此模式下LLM只能探索项目，制定计划方案，不可修改源文件或创建，随后把计划书交给你审批(LLM用)
- `codemode`进入代码模式,此模式下LLM可执行改动类指令(优先级依然低于rootmodel指令使用前),直接开始写代码(LLM用)
- `edit`源文件可视化
- `taskcreate`任务创建(LLM用)
- `taskupdate`任务更新(LLM用)

<!-- 连接定义 -->
[headroom]:https://github.com/chopratejas/headroom
[CLI-Anything]:https://github.com/HKUDS/CLI-Anything
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
- `context压缩`模块逻辑+质量升级 V =`1.15.0.9`
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
- `context压缩`模块大升级,将[`headroom`][headroom]的上下文压缩和提炼逻辑接入`TUDOU_agent`的`context压缩`,并允许`LLM`选择性查看原文还是压缩文 V =`1.17.6.6`
- 支持`LLM`一次性传回多指令运行 V =`1.17.6.7`
- 将命令输出从固定输出变为流式输出 V =`1.17.6.8`

### TUDOU_agent重大更新节点
- `remote`飞书接口支持 V = `0.12.1.2`
- agent整体UI质量优化 V =`1.12.6.9`
- `MCP`协议支持 V =`1.13.8.9`
- `CLI-Anything`工具接入`TUDOU_agent`并添加`buildCLI`指令 V =`1.16.1.1`
- 使用`headroom`的上下文压缩和提炼逻辑作为`context压缩`模块的更新 V =`1.17.6.6`

### TUDOU_agent组件&配置文件
- `skills`文件,库文件夹为`builtin_skills`中
- `memory`创建,以支持大模型跨会话记忆(有时候你得主动和他说记忆会话,他才会保存记忆)
- 根目录下的`config.yaml`文件为大模型配置文件和`config`文件夹

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
- 个别`LLM`你问他哪家公司的模型,如`deepseek`,他可能回答你是`Anthropic`的`claude`,底层原因是这些`LLM`他们本身知识库和训练集中没有告诉他们是谁,而`TUDOU_agent`中的预提示词一部分是从`claude_code`里扒出来,`LLM`看提示词推测他就是`Anthropic`的模型(2025年后各公司产出的大模型大部分都有这个问题,他们的知识库和训练集中基本都多多少少有`claude_code`的提示词)
- 如果你发给他 `<thinking>`他可能会回复你一些很无厘头的回复,这是因为个别`LLM`如`deepseek`他们在训练的时候有一组固定的问题和答案,他们之中直接可以用`<thinking>`来触发回答
- 如果`LLM`运行的指令是`Linux`(`Ubuntu`)的,并且是解析文件字节,他可能会报错:
```python
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
```python
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


### ??
- 如何成为一名`标准`的`神人`?
- 此`TUDOU_agent`版本:`TUDOU_agent_N4HBEST_1.17.6.7_version`

