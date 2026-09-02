# 筑思 Agent 固定 Tunnel 网页发布实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 在当前会话逐任务实现。用户禁止创建子任务或调用其他聊天，因此不得使用 subagent-driven-development。步骤使用复选框跟踪进度。

**目标：** 将当前 8000/8787 双端口 Demo 改为由 `server.py:8787` 提供页面、图片和 API 的同源网页，并生成不含密钥和历史数据的版本化发布包，为固定 Cloudflare Named Tunnel 提供单一入口。

**架构：** 保留现有 `BaseHTTPRequestHandler` 和业务 API，在同一 Handler 内增加受限静态文件路由；前端改用同源相对 URL；启动器收束为单进程。发布脚本按显式清单生成候选版本，验证通过后才更新 `current` 指针。

**技术栈：** Python 3、`http.server`、HTML/JavaScript、PowerShell、Windows batch、`unittest`、Playwright、Cloudflare Tunnel。

---

## 文件结构

- 创建：`tests/test_web_release.py`——单端口静态路由、路径安全、同源前端和发布包契约。
- 创建：`tools/build_web_release.ps1`——按允许清单复制发布文件并生成校验清单。
- 创建：`deploy/cloudflared-config.example.yml`——固定 Tunnel 单入口配置示例，不包含 token 或真实域名。
- 修改：`server.py`——安全提供 `demo/`、`images/` 和根入口。
- 修改：`demo/collaborator.html`——使用同源 API 和图片路径。
- 修改：`启动Demo.bat`——只启动 8787，并验证健康接口和主页面。
- 修改：`停止筑思Agent.bat`——只定位 8787 的项目 Python 进程。
- 修改：`tests/test_windows_launchers.py`——更新为单端口启动契约。
- 修改：`tests/e2e_collaborator.py`——主页面地址改为 8787，继续拦截业务 API。
- 修改：`README.md`——记录本机、固定 Tunnel、发布和真实限制。

## 任务 1：锁定单端口失败行为

**文件：**
- 创建：`tests/test_web_release.py`
- 读取：`server.py:291-314`
- 读取：`demo/collaborator.html:400-479`

- [ ] **步骤 1：编写失败测试**

测试使用临时 `ThreadingHTTPServer(("127.0.0.1", 0), ArchAIHandler)`，断言：

```python
def test_root_serves_collaborator_html(self):
    response = requests.get(self.base_url + "/", timeout=3)
    self.assertEqual(200, response.status_code)
    self.assertIn("筑思", response.text)
    self.assertIn("text/html", response.headers["Content-Type"])

def test_demo_and_image_assets_are_served(self):
    html = requests.get(self.base_url + "/demo/collaborator.html", timeout=3)
    image = requests.get(self.base_url + "/images/安藤忠雄-住吉的长屋/plan.jpg", timeout=3)
    self.assertEqual(200, html.status_code)
    self.assertEqual(200, image.status_code)

def test_static_route_rejects_path_escape(self):
    for path in ("/demo/../.env", "/demo/%2e%2e/.env", "/.env"):
        with self.subTest(path=path):
            self.assertIn(requests.get(self.base_url + path, timeout=3).status_code, (403, 404))
```

另读取前端源码，断言不存在 `http://"+HOST+":8787`、`:8000` 或 `:8787/api`，且包含 `/api/architect_chat` 与 `/images/`。

- [ ] **步骤 2：运行测试并证明当前实现失败**

运行：

```powershell
E:\AI\python.exe -m unittest discover -s tests -p "test_web_release.py" -v
```

预期：根页面与静态资源返回 404；前端仍包含固定端口。

## 任务 2：实现受限静态路由

**文件：**
- 修改：`server.py:22-30,291-314`
- 测试：`tests/test_web_release.py`

- [ ] **步骤 1：增加最小静态响应函数**

新增 `mimetypes`、`unquote` 导入和允许目录：

```python
STATIC_ROOTS = {
    "/demo/": BASE / "demo",
    "/images/": BASE / "images",
}

def _resolve_static_path(url_path: str) -> Path | None:
    decoded = unquote(url_path)
    for prefix, root in STATIC_ROOTS.items():
        if decoded.startswith(prefix):
            candidate = (root / decoded[len(prefix):]).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                return None
            return candidate if candidate.is_file() else None
    return None
```

在 Handler 中增加 `_send_bytes()`，并让 `/` 返回 `demo/collaborator.html`；其他允许静态路径经 `_resolve_static_path()` 读取，未知或越界路径返回 JSON 404。

- [ ] **步骤 2：运行静态路由测试**

运行任务 1 命令。预期静态路由相关测试通过，前端同源断言仍失败。

## 任务 3：前端改为同源 URL

**文件：**
- 修改：`demo/collaborator.html:400,438,479`
- 测试：`tests/test_web_release.py`

- [ ] **步骤 1：最小修改 URL 常量和 fetch**

```javascript
const API="/api/architect_chat", IMG_BASE="", STORE="archai-collaborator-v1", PSTORE="archai-projects-v1";
```

把跨层分析、文档解析和图像分析调用改为 ``fetch(`/api/${endpoint}`...)``；案例图片保持 `${IMG_BASE}/images/...`，结果为同源 `/images/...`。

- [ ] **步骤 2：运行网页发布测试**

运行任务 1 命令。预期全部通过。

## 任务 4：收束 Windows 启停器

**文件：**
- 修改：`启动Demo.bat`
- 修改：`停止筑思Agent.bat`
- 修改：`tests/test_windows_launchers.py`

- [ ] **步骤 1：先更新测试形成失败**

测试要求启动器仅定义 `BACKEND_PORT=8787`，`APP_URL=http://127.0.0.1:8787/demo/collaborator.html`，不得启动 `http.server`；停止器只检查 8787。

- [ ] **步骤 2：运行启动器测试验证失败**

```powershell
E:\AI\python.exe -m unittest discover -s tests -p "test_windows_launchers.py" -v
```

预期：旧双端口标记导致失败。

- [ ] **步骤 3：最小修改启停脚本**

启动器保留 Python、依赖、`.env`、端口和 HTTP 轮询，只移除 8000 前端进程；启动成功后打开 8787 主页面。停止器只显示并确认终止监听 8787 的 Python 进程。

- [ ] **步骤 4：重新运行启动器测试**

预期全部通过。

## 任务 5：构建安全发布包

**文件：**
- 创建：`tools/build_web_release.ps1`
- 创建：`deploy/cloudflared-config.example.yml`
- 修改：`tests/test_web_release.py`

- [ ] **步骤 1：编写发布包失败测试**

测试在临时输出目录调用 PowerShell 脚本，断言发布目录包含 `server.py`、`demo/collaborator.html`、`images/`、`vector_db/`、`requirements.txt` 和 `manifest.sha256`，并递归断言不存在 `.env`、`*.key`、`__pycache__`、`_backup_*`、测试日志与实验脚本。

- [ ] **步骤 2：运行并确认脚本不存在或输出不合格**

运行任务 1 命令，预期发布包测试失败。

- [ ] **步骤 3：实现显式允许清单**

脚本参数：

```powershell
param(
  [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$OutputRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'releases')
)
```

只复制经运行时导入核实的 Python 文件及允许的资源目录；复制前验证源路径，输出目录必须位于明确传入的 `OutputRoot`。使用 `Get-FileHash -Algorithm SHA256` 生成清单。不得复制 `.env`。

Tunnel 示例仅包含：

```yaml
tunnel: YOUR_TUNNEL_UUID
credentials-file: C:/Users/YOU/.cloudflared/YOUR_TUNNEL_UUID.json
ingress:
  - hostname: demo.example.com
    service: http://127.0.0.1:8787
  - service: http_status:404
```

- [ ] **步骤 4：运行发布包测试并人工检查清单**

预期全部通过；使用 `rg -n "sk-|dataset-|API_KEY=" <release>` 确认没有真实密钥值。

## 任务 6：更新主页面 E2E 与文档

**文件：**
- 修改：`tests/e2e_collaborator.py`
- 修改：`README.md`

- [ ] **步骤 1：将 E2E 入口改为单端口**

页面地址使用 `http://127.0.0.1:8787/`。业务 API 仍由 Playwright 拦截，验证页面、项目记忆、知识面板、导出和移动端布局。

- [ ] **步骤 2：更新 README**

记录单进程启动、同源入口、构建发布包、固定 Tunnel 配置、更新与回退方式；明确 Named Tunnel 需要用户自有 Cloudflare 域名与授权，且网页可访问不等于 DeepSeek/Dify/Qwen 可用。

## 任务 7：自动验证与本机真实启动

**文件：**
- 验证：本计划全部修改文件

- [ ] **步骤 1：运行专项测试**

```powershell
E:\AI\python.exe -m unittest discover -s tests -p "test_web_release.py" -v
E:\AI\python.exe -m unittest discover -s tests -p "test_windows_launchers.py" -v
E:\AI\python.exe -m unittest discover -s tests -p "test_candidate_commitment_boundary.py"
E:\AI\python.exe -m unittest discover -s tests -p "test_negated_state_actions.py"
E:\AI\python.exe -m unittest discover -s tests -p "test_semantic_events.py"
E:\AI\python.exe -m unittest discover -s tests -p "test_candidate_route_ledger.py"
```

- [ ] **步骤 2：运行语法与全量回归**

```powershell
E:\AI\python.exe -m py_compile server.py architect_chat.py conversation_state.py
E:\AI\python.exe -m unittest discover -s tests -p "test_*.py"
```

预期：本次新增和相关测试全绿；全量测试若仍为既有知识注释 1 fail + 1 error，记录相同堆栈并确认本次没有新增失败，不宣称全量通过。

- [ ] **步骤 3：启动单进程并验证**

```powershell
E:\AI\python.exe server.py --host 127.0.0.1 --port 8787
```

另一个终端验证 `/api/health`、`/`、`/demo/collaborator.html` 和一个真实图片均为 200。

- [ ] **步骤 4：运行浏览器 E2E**

```powershell
E:\AI\python.exe tests\e2e_collaborator.py
```

预期输出 `{"status":"ok"}`，无页面脚本错误。

## 任务 8：固定 Tunnel 与异网验收

**文件：**
- 使用：`deploy/cloudflared-config.example.yml`
- 生成于用户 Cloudflare 配置目录：真实 tunnel 配置与凭据；不得复制回工程或发布包。

- [ ] **步骤 1：确认前置条件**

只读取确认 `cloudflared --version`、Cloudflare 账号、已接入 Cloudflare 的域名和拟使用子域名。缺少域名或授权时停止并向用户请求，不用 Quick Tunnel 冒充完成方案二。

- [ ] **步骤 2：创建 Named Tunnel 和固定 DNS 路由**

在用户批准 Cloudflare 登录和域名后执行官方 `cloudflared tunnel login/create/route dns` 流程，将固定主机名映射到 `http://127.0.0.1:8787`。

- [ ] **步骤 3：异网人工验收**

使用手机流量或另一网络打开固定 HTTPS 域名，完成页面加载、三轮真实 DeepSeek 对话、案例图片加载和设计记录导出。人工阅读回复并分别记录网页链、知识链和模型链状态。

- [ ] **步骤 4：验证持续更新和回退**

构建新候选包、验证后切换并重启服务，确认固定网址不变；再切回上一发布版确认恢复。

## 计划自检结果

- 规格中的同源架构、路径安全、密钥隔离、启停、发布、回退、访问保护和异网验证均有对应任务。
- 未引入新的业务 Layer 或 Boundary。
- 真实 Cloudflare 域名和凭据不写入计划或仓库，只在用户授权后进入其 Cloudflare 配置目录。
- 当前不是 Git 仓库，不能执行 commit；用版本化发布包、SHA256 清单和测试证据替代本轮提交点，且明确报告该限制。
