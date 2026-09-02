# 被拒绝拓扑结构签名修复实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 在当前会话内逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。用户明确禁止创建子任务。

**目标：** 在不新增 Layer、Boundary 或架构编号的前提下，让现有 Candidate Commitment Boundary 根据空间关系拓扑识别“单一中心、单一主线、单一全局媒介”的换名复活。

**架构：** 保留现有拒绝上下文、冲突检测、DeepSeek 改写与安全回退流程。在 `_rejected_route_topology_conflicts` 内增加一个小型结构签名提取器，把肯定句归纳为参与范围、媒介数量和依赖范围；仅当三者构成全局单一依赖时，映射到现有冲突标签。为同一现有边界补充可观察字段，证明检测、改写和回退分别是否发生。

**技术栈：** Python 3、`re`、`unittest`、`unittest.mock`、DeepSeek 现有调用封装。

---

## 文件职责

- 修改：`tests/test_candidate_commitment_boundary.py`——增加抽象拓扑漏检、局部关系安全例和边界追踪的失败测试。
- 修改：`architect_chat.py`——在现有拒绝拓扑冲突函数中加入结构签名，并从现有边界返回追踪数据。
- 修改：`_candidate_topology_live_regression.py`——把结构冲突、改写和回退的阶段字段写入真实模拟日志。
- 创建：`03_AI测试记录/项目日志/2026年9月1日_候选拓扑结构签名修复后真实复测_<时间>.md`——使用同一六轮输入生成 B 组证据。

### 任务 1：建立失败测试

**文件：**
- 修改：`tests/test_candidate_commitment_boundary.py`

- [ ] **步骤 1：增加当前实现会漏掉的抽象断言**

```python
def test_bare_surround_relation_to_one_shared_referent_is_conflict(self):
    conflicts = ac._rejected_route_topology_conflicts(
        "三个独立单元围一个共同对象。",
        "我不想依赖一个中心，请改用多个局部联系。",
    )
    self.assertIn("centralized_organizer", conflicts)

def test_enclosing_relation_creating_one_shared_referent_is_conflict(self):
    conflicts = ac._rejected_route_topology_conflicts(
        "四个部分共同围合出一个联系对象。",
        "不要再用单一全局媒介组织全部空间。",
    )
    self.assertIn("centralized_organizer", conflicts)

def test_global_participants_depending_on_one_abstract_mediator_is_conflict(self):
    conflicts = ac._rejected_route_topology_conflicts(
        "所有部分的到达与识别都依赖一个共同媒介。",
        "不要再依赖一条主线组织空间。",
    )
    self.assertIn("single_linear_organizer", conflicts)
```

- [ ] **步骤 2：增加不能被误伤的局部关系断言**

```python
def test_pairwise_local_relations_do_not_form_global_single_dependency(self):
    draft = (
        "甲与乙形成一处局部联系，乙与丙另设一处联系。"
        "每组之间各画一条短线，发生在不同位置。"
    )
    conflicts = ac._rejected_route_topology_conflicts(
        draft,
        "我不想依赖一个中心，也不要一条主线。",
    )
    self.assertEqual(set(), conflicts)
```

- [ ] **步骤 3：增加阶段可观察性断言**

使用现有 `_call_deepseek(..., return_stages=True)` 测试夹具，断言返回字典包含：

```python
self.assertEqual(["centralized_organizer"], stages["topology_conflicts_before"])
self.assertTrue(stages["topology_rewrite_applied"])
self.assertEqual([], stages["topology_conflicts_after"])
self.assertFalse(stages["topology_fallback_used"])
```

- [ ] **步骤 4：只运行新增测试，确认出现断言失败**

运行：

```powershell
E:\AI\python.exe -m unittest tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_bare_surround_relation_to_one_shared_referent_is_conflict tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_enclosing_relation_creating_one_shared_referent_is_conflict tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_global_participants_depending_on_one_abstract_mediator_is_conflict -v
```

预期：至少“围一个”和“围合出一个”断言失败，证明不是测试装配错误。

### 任务 2：在现有冲突检测中加入最小结构签名

**文件：**
- 修改：`architect_chat.py:2037-2184`
- 测试：`tests/test_candidate_commitment_boundary.py`

- [ ] **步骤 1：定义内部结构签名函数**

```python
def _topology_relation_signature(reply: str) -> dict[str, str]:
    asserted = _affirmed_topology_clauses(reply)
    participant_scope = "global" if re.search(_GLOBAL_TOPOLOGY_PARTICIPANT_RE, asserted) else "unknown"
    mediator_scope = "single" if re.search(_SINGLE_TOPOLOGY_REFERENT_RE, asserted) else "unknown"
    dependency_scope = (
        "shared_global"
        if participant_scope == "global"
        and mediator_scope == "single"
        and _GLOBAL_SINGLE_DEPENDENCY_RE.search(asserted)
        else "unknown"
    )
    return {
        "participant_scope": participant_scope,
        "mediator_scope": mediator_scope,
        "dependency_scope": dependency_scope,
    }
```

其中 `_GLOBAL_SINGLE_DEPENDENCY_RE` 只表达关系角色和数量结构，覆盖“围／围合出／面向／依赖／通过／接入”等关系变化，不枚举大厅、道路、院子、场、缝隙、平台等空间名称。

- [ ] **步骤 2：把结构签名映射到已有冲突标签**

```python
signature = _topology_relation_signature(asserted_reply)
has_single_global_dependency = signature == {
    "participant_scope": "global",
    "mediator_scope": "single",
    "dependency_scope": "shared_global",
}
```

中心拒绝时映射为 `centralized_organizer`，线性拒绝时映射为 `single_linear_organizer`；保留已有规则作为兼容路径，不新增 Boundary。

- [ ] **步骤 3：运行新增正反例测试**

运行：

```powershell
E:\AI\python.exe -m unittest tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_bare_surround_relation_to_one_shared_referent_is_conflict tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_enclosing_relation_creating_one_shared_referent_is_conflict tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_global_participants_depending_on_one_abstract_mediator_is_conflict tests.test_candidate_commitment_boundary.CandidateCommitmentBoundaryTests.test_pairwise_local_relations_do_not_form_global_single_dependency -v
```

预期：4 项通过。

### 任务 3：补充同一边界的执行追踪

**文件：**
- 修改：`architect_chat.py:2301-2357`
- 修改：`architect_chat.py:3948-3983`
- 测试：`tests/test_candidate_commitment_boundary.py`

- [ ] **步骤 1：抽出带追踪数据的内部执行函数**

```python
def _apply_rejected_route_topology_boundary_with_trace(reply, last_user, state=None):
    trace = {
        "topology_conflicts_before": sorted(_rejected_route_topology_conflicts(reply, last_user, state)),
        "topology_rewrite_applied": False,
        "topology_conflicts_after": [],
        "topology_fallback_used": False,
    }
    # 沿用现有两次改写和 fallback 逻辑；每条返回路径同步填写 trace。
    return result, trace
```

公开的 `_apply_rejected_route_topology_boundary` 仍返回字符串，避免改变现有调用者。

- [ ] **步骤 2：让生成流水线记录追踪字段**

```python
topology_checked_draft, topology_trace = (
    _apply_rejected_route_topology_boundary_with_trace(
        candidate_body_draft, last_user, state
    )
)
```

在 `return_stages` 字典中展开四个 `topology_*` 字段，同时保留现有字段。

- [ ] **步骤 3：运行可观察性测试与 Candidate Boundary 全套**

运行：

```powershell
E:\AI\python.exe -m unittest tests.test_candidate_commitment_boundary -v
```

预期：原有 110 项与新增测试全部通过。

### 任务 4：自动回归与语法验证

**文件：**
- 不修改生产范围外文件。

- [ ] **步骤 1：运行四组相关回归**

```powershell
E:\AI\python.exe -m unittest tests.test_candidate_commitment_boundary tests.test_negated_state_actions tests.test_semantic_events tests.test_candidate_route_ledger -v
```

预期：原有 183 项及本轮新增项全部通过。

- [ ] **步骤 2：运行语法检查**

```powershell
E:\AI\python.exe -m py_compile architect_chat.py conversation_state.py _candidate_topology_live_regression.py
```

预期：退出码 0，无输出。

### 任务 5：同输入 DeepSeek B 组与人工判读

**文件：**
- 修改：`_candidate_topology_live_regression.py`
- 创建：`E:/AI/项目设计/筑智AI_ArchAI/03_AI测试记录/项目日志/2026年9月1日_候选拓扑结构签名修复后真实复测_<时间>.md`

- [ ] **步骤 1：在日志中增加四个阶段字段**

```python
"topology_conflicts_before",
"topology_rewrite_applied",
"topology_conflicts_after",
"topology_fallback_used",
```

- [ ] **步骤 2：确认六轮输入与 A 组完全相同后运行真实模拟**

```powershell
E:\AI\python.exe _candidate_topology_live_regression.py
```

预期：生成含六轮原始输入、原始输出、最终输出和阶段字段的新 Markdown 日志。

- [ ] **步骤 3：人工逐轮比较 A/B**

比较固定 A 组 `2026年9月1日_候选路线语义复发修复后真实复测_133541.md` 与新 B 组，逐项记录：第 4、5、6 轮拒绝是否立即生效；是否以任意新名称复活；是否仍存在单一全局组织媒介；功能关系、楼层/体量/剖面和可画动作是否保留；是否退化为免责声明或空泛回答。

- [ ] **步骤 4：按停止条件汇报**

若自动测试通过但真实回答仍以未覆盖措辞复活，不宣称整体解决；记录结构签名的漏口。若连续需要三次扩充关系措辞仍无法形成稳定概念判断，停止继续补词并回到结构抽取方案评审。汇报“修了什么、是否有效、残余问题、下一步”，然后等待用户决定。
