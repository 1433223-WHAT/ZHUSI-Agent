# 筑思 Agent 阶段与任务侧重点路由实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 让筑思 Agent 在连续聊天中识别设计阶段与任务侧重点，以自然语言追问、结构化记录并支持经学生确认的状态切换。

**架构：** 新建专门的 `collaboration_focus.py` 管理状态、学生证据、待确认切换和 DeepSeek 回答策略；`conversation_state.py` 只负责把该结构放入空状态；`architect_chat.py` 在每轮调用模型前更新状态并把路由策略加入模型上下文。界面不新增控件。

**技术栈：** Python 3、正则表达式、现有 DeepSeek Chat API、`unittest`/`unittest.mock`。

---

### 任务 1：阶段与任务侧重点状态机

**文件：**
- 创建：`collaboration_focus.py`
- 修改：`conversation_state.py`
- 测试：`tests/test_collaboration_focus.py`

- [x] **步骤 1：编写失败测试**

覆盖默认 `undecided`、明确建筑本体优先、明确场地回应、后续场地条件触发待确认切换、学生确认切换、状态不变时不重复切换提示。

- [x] **步骤 2：运行红灯测试**

运行：`python -m unittest discover -s tests -p "test_collaboration_focus.py" -v`

预期：因 `collaboration_focus` 模块不存在而失败。

- [x] **步骤 3：实现最小状态机**

提供以下稳定接口：

```python
def empty_focus() -> dict: ...
def update_focus(state: dict, message: str, turn_id: int) -> dict: ...
def response_policy(state: dict) -> str: ...
```

状态字段固定为 `design_stage`、`task_focus`、`external_context_priority`、`pending_switch`；确认值保存 `value/evidence/source/turn_id/status`，切换写入现有 `change_log`。

- [x] **步骤 4：运行绿灯测试**

运行：`python -m unittest discover -s tests -p "test_collaboration_focus.py" -v`

预期：全部通过。

### 任务 2：接入连续聊天与 DeepSeek 回答策略

**文件：**
- 修改：`architect_chat.py`
- 测试：`tests/test_architect_chat.py`

- [x] **步骤 1：编写失败测试**

测试模型上下文包含结构化状态和本轮策略；早期未决状态要求自然追问；建筑本体优先要求形成可画空间骨架且不反复索要场地；已有方案的评图服从任务重点；模型失败时状态仍保留。

- [x] **步骤 2：运行红灯测试**

运行：`python -m unittest discover -s tests -p "test_architect_chat.py" -v`

预期：新断言因模型上下文缺少 `collaboration_focus` 与 `response_policy` 而失败。

- [x] **步骤 3：实现最小接入**

在 `chat_turn()` 更新普通事实后调用 `update_focus()`；在 `_model_state()` 暴露状态；在 `_call_deepseek()` 的系统上下文加入 `response_policy`。系统提示词增加总路由规则，但不生成固定按钮、问卷或每轮模式声明。

- [x] **步骤 4：运行绿灯测试**

运行：`python -m unittest discover -s tests -p "test_architect_chat.py" -v`

预期：全部通过。

### 任务 3：切换、回归与真实对话验收

**文件：**
- 修改：`tests/test_collaboration_focus.py`
- 修改：`docs/superpowers/plans/2026-08-14-collaboration-focus-routing-plan.md`

- [x] **步骤 1：增加多轮验收测试**

按“大学生活动中心无场地 → 建筑本体优先 → 老师补充具体基地 → 学生确认综合推进”的顺序验证状态、待确认切换、变更记录和回答策略。

- [x] **步骤 2：运行完整测试与编译检查**

运行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m py_compile collaboration_focus.py conversation_state.py architect_chat.py server.py
```

预期：测试全部通过，编译命令退出码为 0。

- [x] **步骤 3：调用真实本地 API 走完整链路**

对 `http://127.0.0.1:8787/api/architect_chat` 连续发送四轮消息，验证实际 DeepSeek 回复采用自然追问、后续不重复声明，并在状态变化时提出一次切换确认。若外部模型不可用，只报告本地状态链验证，不宣称真实回复已通过。

- [x] **步骤 4：完成计划清单**

根据实际命令输出逐项勾选，不创建 Git commit；当前目录不是 Git 仓库。
