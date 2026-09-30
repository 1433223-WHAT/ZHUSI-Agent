# 筑思 Agent

筑思 Agent 是面向建筑专业学生的建筑知识增强型学习与设计协作系统。它帮助学生理解任务、检索与解释案例、比较策略、记录设计过程，并对文档和建筑图像进行辅助分析；学生保留判断、选择、修改和最终决定。

它不是自动替学生完成设计的“AI 建筑师”，也不替代教师评图。AI 的回复、知识检索结果和视觉推测都应作为参考，由学生确认后再进入后续设计上下文。

## 当前主流程

1. 学生通过连续对话说明任务、场地、使用者与设计约束。
2. 系统区分学生已确认事实、AI 建议、知识证据与待确认内容。
3. 学生可上传 PDF、DOCX、DOC、TXT 或 Markdown；解析结果经确认后才用于后续对话。
4. 学生可上传 PNG、JPG、JPEG 或 WEBP；视觉结果分为观察、推测和未知。
5. 学生可接受、拒绝、修改或组合建议，并保留过程记录。

本机主页面：`http://127.0.0.1:8787/`

## Windows 快速启动

需要 Python 3.8 或更高版本。首次运行前：

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
```

根据需要编辑 `.env` 中的 DeepSeek、Dify 和 Qwen-VL 配置。API Key 只保存在服务端配置中，`.env` 已被 `.gitignore` 排除。

> **依赖分两级，可以只装核心那一级。**
>
> - `requirements.txt`（必装）：requests / numpy / python-docx / pypdf / Pillow，约几十 MB，一两分钟装完。
>   装完即可使用 **AI 对话、图像视觉分析、设计记忆、过程导出**。
> - `requirements-full.txt`（可选）：额外包含 `torch` 与 `transformers`，只服务于**本地向量知识检索**这一路。
>   需要时执行 `pip install -r requirements-full.txt` 并重启服务；
>   想省体积可装 CPU 版 torch：`pip install torch --index-url https://download.pytorch.org/whl/cpu`。
>
>   **不装会影响什么（如实说明）**：`/api/local_retrieve` 返回 `available: false` 后，
>   生成回答时不再注入本地检索到的**建筑判断原则与建筑思维方法**（见 `architect_chat.py` 判断层 / Skill 层注入）。
>   对话、图像分析、设计记忆、过程导出仍完全可用，但回答里不会出现基于本地知识库的案例引用与判断框架提示，
>   质量低于完整安装。

双击「启动Demo.bat」时若检测到核心依赖缺失，会自动执行 `pip install -r requirements.txt`；
自动安装失败时会给出手动执行的命令提示。

双击 `启动Demo.bat`。脚本会依次检查：

- Python 版本和运行依赖
- `.env` 与 `requirements.txt`
- 服务端口 8787 是否可用
- `/api/health` 与主页面 HTTP 状态

全部通过后会自动打开协作页面。停止时双击 `停止筑思Agent.bat`，核对显示的 PID 后输入 `Y`。

## 手动启动

在项目目录运行单一 Web 服务：

```powershell
python server.py --host 127.0.0.1 --port 8787
```

然后打开 `http://127.0.0.1:8787/`。页面、API 和案例图片都由同一个服务提供，健康检查地址为 `http://127.0.0.1:8787/api/health`。

## API Key 获取与配置（首次运行必读）

密钥只在服务端 `.env` 中读取，不会下发到浏览器，也不进入发布包。发布包内没有 `.env`，需要先复制模板：

```powershell
Copy-Item .env.example .env
```

按重要性分三档，**只配第 1 项就能正常对话**：

1. **DeepSeek（必需，负责对话与推理）**
   访问 https://platform.deepseek.com 注册并登录 → 进入「API Keys」→ 创建新密钥 →
   复制后填入 `.env` 的 `DEEPSEEK_API_KEY=sk-...`。
   是否有赠送额度、额度多少以平台当时的政策为准，请先在平台确认。

2. **阿里云百炼 DashScope（可选，负责建筑图像分析）**
   访问 https://dashscope.aliyun.com 开通服务 → 控制台创建 API Key →
   填入 `.env` 的 `DASHSCOPE_API_KEY=sk-...`。
   未配置时对话和知识检索不受影响，只有图片上传后的视觉分析会失败；界面会显示真实失败状态，不会用本地结果冒充云端已连接。

3. **Dify 知识库（可选）**
   本包已内置本地建筑知识库，不配置 Dify 也能完成知识检索。需要扩展外部知识库时再填写 `DIFY_API_KEY` 与相关 Dataset ID。

配置完成后重启服务生效。**若暂不配置任何 Key，界面仍可打开、可上传资料，但无法生成回答**——这属于预期行为，不是程序故障。

## 生成版本化发布包

发布包使用明确白名单，只收集运行所需文件，不复制 `.env`、密钥、日志、测试、缓存或历史对话输出：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_web_release.ps1
```

命令会在 `releases/<时间戳>/` 生成独立版本和 `manifest.sha256` 校验清单。发布包不包含真实 `.env`；部署时需从 `.env.example` 另行创建，不能提交到 GitHub。

## 固定公网地址（方案 2）

公网方案采用 **Cloudflare Named Tunnel**。固定域名始终转发到本机 `127.0.0.1:8787`，因此更新代码或发布版本时网址不变，也无需开放路由器端口。

前置条件：

- 一个已接入 Cloudflare 的域名；
- 本机安装并登录 `cloudflared`；
- 已创建 Named Tunnel，并把 `deploy/cloudflared-config.example.yml` 复制到本机私有配置目录后填写 Tunnel UUID、凭据路径和域名。

配置完成后，先启动筑思服务并确认本机健康检查通过，再启动固定 Tunnel：

```powershell
cloudflared tunnel run <你的-Tunnel-名称>
```

建议测试阶段通过 Cloudflare Access 限制访问者。Tunnel 凭据 JSON、`.env` 和 API Key 都只保存在部署机器上，不进入仓库或发布包。临时 Quick Tunnel 地址不能当作校赛固定入口。

持续更新时保持 Tunnel 运行，只需在本机完成测试、生成新版本并重启筑思服务；固定域名不会改变。上线后仍需抽查 `/api/health`、主页面和一次真实模型对话。若新版本验证失败，应继续运行上一版本，不要让失败版本替换当前服务。

## 关键文件

- `demo/collaborator.html`：当前对话式协作主界面
- `server.py`：本地 HTTP API 与模型、知识库适配入口
- `architect_chat.py`：协作对话编排
- `conversation_state.py`：学生事实、设计状态和过程记录
- `document_parser.py`：文档解析
- `image_analyzer.py`：建筑图像分析框架
- `tests/`：单元测试、边界测试和端到端测试脚本
- `docs/`：`ArchAI人机协同验证记录.md` 是整体人机协同验证记录；
  `learning-01…33` 逐条记录了开发中发现的边界问题（如场地纠正、图像状态、跨层级触发）及其修正过程，
  可用来对照查看这些约束为什么存在。

> 关于 `tests/`：其中部分端到端脚本会调用真实模型 API，**运行前请确认额度**。
> 正常使用和评审不需要运行它们，它们只是工程规范性的证明。

## 环境自检（可选）：`_smoke_test.py` 是干什么的

简单说：**它是用来回答「我这套环境到底装对了没有」的检查脚本**，不是项目运行必需的文件。

什么时候需要它：

- 第一次配好 `.env` 并启动服务后，想确认是不是真能问答；
- 有人反馈「跑不起来」时，用它快速定位断在哪一环。

跑出来四项全绿就不用再管；平时正常使用不需要它。

怎么用（两个命令行窗口）：

```bat
:: 第一个窗口：先启动服务
启动Demo.bat
:: 或：python server.py --host 127.0.0.1 --port 8787

:: 第二个窗口：服务起来后，在本目录执行
python _smoke_test.py
```

它依次检查四项，每项打印「通过 / 失败 / 跳过」：

| 项 | 检查什么 | 不通过意味着什么 |
|---|---|---|
| `[1] 健康检查` | 服务有没有活着 | 服务没启动；这一项不过会直接退出 |
| `[2] 本地知识库检索` | 内置知识库能否检索 | 未装 torch 时显示「跳过」，属正常 |
| `[3] 核心对话问答` | 问一句真问题，AI 有没有回答 | Key 无效 / 余额不足 / 网络不通 |
| `[4] 带资料上下文` | 上传任务书后 AI 会不会用上 | 同上，或文档解析链路有问题 |

脚本只依赖 `requests`（核心依赖已包含），不需要额外安装。第 `[3][4]` 项会真实调用一次大模型，
消耗极少量额度（每次约几千 token），跑一次就见效，不是本地模拟。
脚本内置的《补园记》示例问题仅用于验证链路，不会写入你的项目数据。

## 真实限制

- Qwen-VL 的真实图像调用只有在有效 `DASHSCOPE_API_KEY` 和网络可用时才能验证；本地代码与模拟流程通过不代表云端鉴权成功。
- DOCX 内嵌图片和 PDF 页面图像尚未进入视觉分析流程。
- 扫描型 PDF 尚无 OCR；系统会提示需要 OCR。
- 旧版 `.doc` 解析依赖本机 Microsoft Word 和 `pywin32`。
- 浏览器状态目前保存在 `localStorage`，不是正式数据库，也不适合多人协作或跨设备同步。
- 外部模型或知识库失败时，界面应显示真实失败状态；本地回退结果不等于外部服务已连接。
