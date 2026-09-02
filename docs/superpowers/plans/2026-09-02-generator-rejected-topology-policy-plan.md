# Generator 拒绝拓扑生成前约束实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 在当前会话内逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪。用户明确禁止创建子任务；当前目录不是 Git 仓库，因此以红绿测试和日志文件代替逐任务 commit。

**目标：** 让已有 Candidate 确认策略在 Generator 首次生成前持续携带被拒绝拓扑的结构契约，使相同六轮第5、6轮原始草稿不再复活中心或单主线。

**架构：** 复用 `_recent_route_rejection_context` 与现有中心/线性拒绝判断，生成一个只供 Generator 使用的关系约束文本，并由 `_apply_candidate_confirmation_context` 注入现有 `policy`。不新增 State 字段、Layer 或 Boundary；后置 topology boundary 保留为最后防线。

**技术栈：** Python 3、`re`、`unittest`、现有 DeepSeek 回归脚本。

---

## 文件职责

- 修改：`tests/test_candidate_commitment_boundary.py`——生成前契约的红绿测试。
- 修改：`architect_chat.py`——构造并持续注入拒绝拓扑契约。
- 修改：`_candidate_topology_live_regression.py`——将输出名称切换为修复后 B 组，保留原始草稿诊断字段。
- 创建：`03_AI测试记录/项目日志/2026年9月2日_Generator拒绝拓扑约束修复后B组真实复测_<时间>.md`——同输入真实证据。

### 任务 1：建立生成前策略失败测试

**文件：**
- 修改：`tests/test_candidate_commitment_boundary.py`

- [ ] **步骤 1：当前轮同时拒绝中心和主线时要求结构契约**

```python
def test_rejected_center_and_line_inject_distributed_generator_contract(self):
    state = {"rejected_assumptions": []}
    policy = ac._apply_candidate_confirmation_context(
        "base policy",
        "不要一个中心，也不要一条主线，请用别的关系继续。",
        state,
        "design_request",
    )
    self.assertIn("拒绝拓扑生成前契约", policy)
    self.assertIn("参与范围=全局", policy)
    self.assertIn("至少两组彼此独立的局部联系", policy)
    self.assertIn("不得用一个有序序列覆盖全部功能", policy)
```

- [ ] **步骤 2：历史拒绝在普通推进轮继续生效**

```python
def test_rejected_topology_generator_contract_persists_after_rejection_turn(self):
    state = {
        "rejected_assumptions": [
            {"text": "我不想靠一个中心，也不要一条主线。"}
        ]
    }
    policy = ac._apply_candidate_confirmation_context(
        "base policy",
        "功能不变，继续把首层和二层说清楚。",
        state,
        "design_request",
    )
    self.assertIn("拒绝拓扑生成前契约", policy)
    self.assertIn("至少两组彼此独立的局部联系", policy)
```

- [ ] **步骤 3：验证不过度限制与合法解除**

```python
def test_center_only_rejection_does_not_forbid_unrejected_linear_candidate(self):
    policy = ac._apply_candidate_confirmation_context(
        "base policy",
        "我不想靠一个中心，请改一版。",
        {},
        "design_request",
    )
    self.assertIn("单一中心关系", policy)
    self.assertNotIn("至少两组彼此独立的局部联系", policy)

def test_confirmed_replacement_clears_historical_topology_contract(self):
    state = {
        "rejected_assumptions": [
            {"text": "我不想靠一个中心，也不要一条主线。"}
        ]
    }
    policy = ac._apply_candidate_confirmation_context(
        "base policy",
        "我决定采用这个新关系，就按这个继续。",
        state,
        "design_request",
    )
    self.assertNotIn("拒绝拓扑生成前契约", policy)
```

- [ ] **步骤 4：运行新增测试并确认行为断言失败**

运行：

```powershell
E:\AI\python.exe -m unittest test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_rejected_center_and_line_inject_distributed_generator_contract test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_rejected_topology_generator_contract_persists_after_rejection_turn test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_center_only_rejection_does_not_forbid_unrejected_linear_candidate test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_confirmed_replacement_clears_historical_topology_contract -v
```

工作目录：`E:/AI/项目设计/筑智AI_ArchAI/ArchAI_Builder/tests`

预期：前三项因缺少生成前拓扑契约而失败；确认解除项保持通过。

### 任务 2：实现最小生成前拓扑契约

**文件：**
- 修改：`architect_chat.py:1644-1684`
- 修改：`architect_chat.py:2194-2210`
- 测试：`tests/test_candidate_commitment_boundary.py`

- [ ] **步骤 1：增加内部契约构造函数**

```python
def _rejected_topology_generator_contract(
    last_user: str,
    state: dict | None = None,
) -> str:
    rejection_context = _recent_route_rejection_context(last_user, state)
    central_rejected = bool(
        _CENTRAL_TOPOLOGY_REJECTION_RE.search(rejection_context)
    )
    linear_rejected = bool(
        _LINEAR_TOPOLOGY_REJECTION_RE.search(rejection_context)
    )
    if not (central_rejected or linear_rejected):
        return ""
    rules = [
        "【拒绝拓扑生成前契约】只约束关系结构，不限制体量、形式、剖面、采光或体验。",
    ]
    if central_rejected:
        rules.append(
            "已拒绝单一中心关系：不得生成参与范围=全局、媒介数量=单一、"
            "依赖范围=共享全局的中心组织。"
        )
    if linear_rejected:
        rules.append(
            "已拒绝单一主线关系：不得让一条路径、连续媒介或一个有序序列"
            "承担全部功能的连接与到达。"
        )
    if central_rejected and linear_rejected:
        rules.append(
            "本轮必须从至少两组彼此独立的局部联系或两个独立到达点开始；"
            "每组联系有自己的局部连接，不得用一个有序序列覆盖全部功能。"
        )
    rules.append(
        "仍须提供具体功能关系、首层与二层工作骨架、体量或剖面继续动作和可画动作；"
        "输出前先检查关系图，若任一单独媒介连接或组织全部功能，必须在生成内部重做。"
    )
    return "\n".join(rules)
```

- [ ] **步骤 2：在现有确认策略中持续注入**

在 `_apply_candidate_confirmation_context` 中计算：

```python
topology_contract = _rejected_topology_generator_contract(last_user, state)
```

行为：

- `status == "rejected"`：在现有拒绝协议后追加契约。
- `status == "candidate"` 或没有学生决定：返回 `policy + topology_contract`。
- `status == "confirmed"`：现有 `_recent_route_rejection_context` 确认短路使契约为空，继续执行确认协议。
- 非设计请求仍直接返回原 policy。

- [ ] **步骤 3：运行新增测试**

运行任务 1 步骤 4 的同一命令。

预期：4项全部通过。

- [ ] **步骤 4：运行 Candidate Boundary 全套**

```powershell
E:\AI\python.exe -m unittest discover -s tests -p 'test_candidate_commitment_boundary.py'
```

预期：现有119项及本轮新增4项全部通过。

### 任务 3：完整自动回归

**文件：**
- 不修改其他生产模块。

- [ ] **步骤 1：运行四组相关回归**

```powershell
E:\AI\python.exe -m unittest discover -s tests -p 'test_candidate_commitment_boundary.py'
E:\AI\python.exe -m unittest discover -s tests -p 'test_negated_state_actions.py'
E:\AI\python.exe -m unittest discover -s tests -p 'test_semantic_events.py'
E:\AI\python.exe -m unittest discover -s tests -p 'test_candidate_route_ledger.py'
```

预期：所有测试退出码为0。

- [ ] **步骤 2：运行语法检查**

```powershell
E:\AI\python.exe -m py_compile architect_chat.py conversation_state.py _candidate_topology_live_regression.py
```

预期：退出码0，无输出。

### 任务 4：相同六轮真实 B 组

**文件：**
- 修改：`_candidate_topology_live_regression.py`
- 创建：`E:/AI/项目设计/筑智AI_ArchAI/03_AI测试记录/项目日志/2026年9月2日_Generator拒绝拓扑约束修复后B组真实复测_<时间>.md`

- [ ] **步骤 1：只切换日志标题和文件名**

保留 `MESSAGES`、`raw_draft`、`raw_topology_conflicts` 和所有 topology trace 字段不变，将 A 组标题改为 B 组标题。

- [ ] **步骤 2：确认六轮输入和 A 组逐字相同**

用脚本读取 A 组的六条 `**学生：**` 文本，与 `MESSAGES` 比较，要求输出 `same_six_inputs=True`。

- [ ] **步骤 3：运行真实 DeepSeek**

```powershell
E:\AI\python.exe _candidate_topology_live_regression.py
```

- [ ] **步骤 4：人工逐轮检查**

必须读取第4、5、6轮原始草稿和最终回答，记录：

- 第4轮是否只避开中心且仍允许尚未拒绝的线性候选。
- 第5、6轮 `raw_topology_conflicts` 是否为空。
- 是否仍出现一个媒介组织全局、单一有序链或换名复活。
- `topology_fallback_used` 是否下降。
- 功能、楼层、体量/剖面与可画动作是否保留。
- 是否出现免责声明、空泛回答或学生决定污染。

- [ ] **步骤 5：按停止条件结束**

如果首次 B 组仍有原始同构冲突，只允许依据真实失败结构调整一次契约并重新做红绿测试。第二次仍失败则停止堆 Prompt，报告需要评估结构化草稿协议。无论测试是否通过，都按重要性汇报有效结果与残余问题，然后等待用户决定。

## 执行结论（2026-09-02）

停止条件已触发。两次生成前 Prompt 契约均未稳定约束 DeepSeek 原始草稿；第二次安全精简 Prompt A/B 仍在 B 组第5轮生成单一中心，第6轮生成单一全局通道。生产实现与对应测试已经回退到本轮开始前状态，未继续尝试第三次 Prompt 修改。下一步需要单独设计和审批“结构化关系草稿 → 确定性校验 → 正文生成”的协议，本计划不授权实现该架构变化。
