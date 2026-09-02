# Generator 拒绝拓扑生成前约束设计

日期：2026-09-02

## 目标

让已有 Candidate Commitment Boundary 在 Generator 首次生成前持续携带学生已经拒绝的空间关系拓扑，减少同构关系换名复活以及对后置 fallback 的依赖。

本轮只处理拒绝拓扑对 Generator 的控制，不处理专业经验事实化和追问控制。

## 修复前诊断

当前数据与控制路径：

1. 学生拒绝由 `_apply_state_revision` 写入 `rejected_assumptions`。
2. `_model_state` 把拒绝原文注入 `design_memory`。
3. `_apply_candidate_commitment_boundary_policy` 注入候选路线边界。
4. `_apply_candidate_confirmation_context` 在当前轮判为 `rejected` 时追加“不得换名复活”。
5. Generator 根据完整对话、State 与自然语言策略生成 `raw_draft`。
6. `_rejected_route_topology_conflicts` 检测原始回答或后续回答。
7. `_apply_rejected_route_topology_boundary_with_trace` 尝试改写，失败后进入安全 fallback。

相同六轮真实诊断证明：

- 第5轮 `raw_topology_conflicts=['centralized_organizer']`。
- 第6轮 `raw_topology_conflicts=['centralized_organizer', 'single_linear_organizer']`。
- 冲突在首次 Generator 草稿中已经存在，不是后置改写引入。
- `remaining_topology_conflicts=[]` 来自 fallback 清理，不能证明 Generator 已遵守拒绝。

现有机制失效原因：

- State 保存的是拒绝原文，没有直接给 Generator 可执行的关系约束。
- 当前策略只有“不得换名复活”的自然语言禁令，没有描述禁止的参与范围、媒介数量与依赖范围。
- 设计请求策略同时要求给出具体空间骨架，模型会用新形式填补被删除的中心或主线。
- 当前轮不再是 `rejected` 时，历史拓扑拒绝只留在通用 State 中，不再获得明确的生成策略优先级。

诊断证据：`03_AI测试记录/项目日志/2026年9月2日_Generator拒绝拓扑约束修复前A组诊断_000141.md`。

## 选定方案

在现有 `_apply_candidate_confirmation_context` 路径内追加一个内部生成前拓扑契约，不新增 Layer、Boundary、架构编号或 State 字段。

契约由已有 `_recent_route_rejection_context`、`_CENTRAL_TOPOLOGY_REJECTION_RE` 与 `_LINEAR_TOPOLOGY_REJECTION_RE` 生成，复用现有拒绝判断，不建立第二套拒绝语义。

## 拓扑契约行为

### 仅拒绝单一中心

Generator 不得生成：

- 全部或多个功能共同面向、围绕或依赖一个媒介。
- 一个媒介承担全局到达、识别、分流、互见或组织。

尚未被学生拒绝的线性候选仍可作为测试骨架，不能因中心拒绝而一并禁止。

### 仅拒绝单一主线

Generator 不得生成：

- 一条路径、连接关系或连续媒介串联全部功能。
- 通过更换主轴、街、带、缝等名称恢复单一全局连接。

### 同时拒绝中心和主线

Generator 必须从多个局部关系开始生成：

- 至少给出两组彼此独立的局部联系或两个独立到达点。
- 任一单独要素不得连接、面向或组织全部功能。
- 功能关系构成多条局部边，而不是一个中心或一条覆盖全局的链。

契约只限制关系拓扑，不限制体量、形式、剖面、层高、采光和空间体验。

## 持续与解除

- 当前学生消息直接拒绝关系时，契约立即生效。
- 后续普通推进、补充信息或要求深化时，只要学生没有确认替代路线，契约继续从近期拒绝上下文生成。
- 学生明确确认新路线时，沿用 `_recent_route_rejection_context` 的现有确认短路，当前生成不注入旧拒绝契约。
- 非设计请求不注入该契约。

## 设计劳动要求

生成前契约必须同时要求保留：

- 具体功能关系。
- 首层与二层的工作骨架。
- 至少一项体量或剖面继续动作。
- 学生可以直接外化的可画动作。

不得输出检查过程、拓扑标签、免责声明或空泛的“换一种思路”。

## 可观察性

真实回归继续记录：

- `raw_draft`
- `raw_topology_conflicts`
- `topology_conflicts_before`
- `topology_rewrite_applied`
- `topology_conflicts_after`
- `topology_fallback_used`

最终 B 组日志名称改为 `Generator拒绝拓扑约束修复后B组真实复测_<时间>.md`。

## 测试策略

先写失败测试：

1. 当前轮同时拒绝中心和主线时，生成策略包含结构契约和至少两组独立局部联系要求。
2. 拒绝发生在前一轮、当前轮只是继续推进时，结构契约仍存在。
3. 只拒绝中心时，不误禁尚未拒绝的线性候选。
4. 学生明确确认新路线时，不继续注入旧拒绝契约。
5. 非设计请求保持无操作。

然后做最小实现，运行 Candidate Boundary、State 否定动作、Semantic Events、Candidate Route Ledger 和语法检查。

## 真实验证与人工判读

使用修复前 A 组完全相同的六轮学生输入生成 B 组，人工检查：

- 第4轮中心拒绝后可以提出尚未被拒绝的线性测试骨架。
- 第5轮原始草稿不再生成共同中心或单主线。
- 第6轮原始草稿不再以链、节点、视线媒介或其他形式复活。
- 第5、6轮 `raw_topology_conflicts=[]`。
- fallback 不再成为稳定的主要输出路径。
- 功能、楼层、体量/剖面与可画动作仍然存在。

## 停止条件

如果两次生成前契约调整后，第5或第6轮原始草稿仍稳定产生同构冲突，停止继续堆叠 Prompt；记录失败结构，重新评估 Generator 是否需要结构化草稿协议。即使自动测试通过，也不得在未人工阅读真实回答前宣称问题整体解决。

## 执行结果（2026-09-02）

该方案经过两次生成前契约调整后仍未达到成功标准，已按停止条件终止并从生产路径回退：

- 第一次完整链 B 组第5轮仍生成单一院落中心；第6轮生成覆盖全部功能的单链。
- 第二次采用精简安全 Prompt 的真实 A/B 中，B 组第5轮仍生成“多个组团共同指向一个中间媒介”；第6轮仍用唯一通道承担两组之间的全部联系。
- 自动冲突检测在部分单链表达上返回空集合，但人工阅读确认关系仍同构，说明仅靠 Prompt 契约和当前 detector 都不足以约束自由文本 Generator。

生产代码中的生成前契约及其测试已撤回，保留诊断日志和隔离实验脚本作为失败证据。若继续，应先评审可被代码验证的结构化关系草稿协议，不应进行第三次 Prompt 扩写。
