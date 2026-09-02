# 筑思 Agent

筑思 Agent 是面向建筑专业学生的建筑知识增强型学习与设计协作系统。它帮助学生理解任务、检索与解释案例、比较策略、记录设计过程，并对文档和建筑图像进行辅助分析；学生保留判断、选择、修改和最终决定。

它不是自动替学生完成设计的“AI 建筑师”，也不替代教师评图。AI 的回复、知识检索结果和视觉推测都应作为参考，由学生确认后再进入后续设计上下文。

## 当前主流程

1. 学生通过连续对话说明任务、场地、使用者与设计约束。
2. 系统区分学生已确认事实、AI 建议、知识证据与待确认内容。
3. 学生可上传 PDF、DOCX、DOC、TXT 或 Markdown；解析结果经确认后才用于后续对话。
4. 学生可上传 PNG、JPG、JPEG 或 WEBP；视觉结果分为观察、推测和未知。
5. 学生可接受、拒绝、修改或组合建议，并保留过程记录。

主页面：`http://127.0.0.1:8000/demo/collaborator.html`

## Windows 快速启动

需要 Python 3.8 或更高版本。首次运行前：

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
```

根据需要编辑 `.env` 中的 DeepSeek、Dify 和 Qwen-VL 配置。API Key 只保存在服务端配置中，`.env` 已被 `.gitignore` 排除。

双击 `启动Demo.bat`。脚本会依次检查：

- Python 版本和运行依赖
- `.env` 与 `requirements.txt`
- 后端端口 8787 和前端端口 8000
- 后端 `/api/health` 与主页面 HTTP 状态

全部通过后会自动打开协作页面。停止时双击 `停止筑思Agent.bat`，核对显示的 PID 后输入 `Y`。

## 手动启动

在项目目录运行后端：

```powershell
python server.py --port 8787
```

另开终端运行前端：

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

然后打开 `http://127.0.0.1:8000/demo/collaborator.html`。后端健康检查地址为 `http://127.0.0.1:8787/api/health`。

## 关键文件

- `demo/collaborator.html`：当前对话式协作主界面
- `server.py`：本地 HTTP API 与模型、知识库适配入口
- `architect_chat.py`：协作对话编排
- `conversation_state.py`：学生事实、设计状态和过程记录
- `document_parser.py`：文档解析
- `image_analyzer.py`：建筑图像分析框架
- `tests/`：单元测试、边界测试和端到端测试脚本

## 真实限制

- Qwen-VL 的真实图像调用只有在有效 `DASHSCOPE_API_KEY` 和网络可用时才能验证；本地代码与模拟流程通过不代表云端鉴权成功。
- DOCX 内嵌图片和 PDF 页面图像尚未进入视觉分析流程。
- 扫描型 PDF 尚无 OCR；系统会提示需要 OCR。
- 旧版 `.doc` 解析依赖本机 Microsoft Word 和 `pywin32`。
- 浏览器状态目前保存在 `localStorage`，不是正式数据库，也不适合多人协作或跨设备同步。
- 外部模型或知识库失败时，界面应显示真实失败状态；本地回退结果不等于外部服务已连接。
