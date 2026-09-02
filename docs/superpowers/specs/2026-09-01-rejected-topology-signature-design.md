# 拒绝拓扑结构签名修复设计

## 目标

修复学生拒绝单一中心、单一主线或单一全局媒介后，Generator 通过“围、围合、共享场、视觉锚点”等新表达复活同构空间关系的问题。

本阶段只改现有 Candidate Commitment Boundary 内部实现，不新增 Layer、Boundary 或架构编号，不处理专业经验事实化和追问控制。

## 修复前诊断门禁

每次工程修复开始前必须保留：

1. 当前数据和控制流程。
2. 根因证据，以及 State、Prompt、Generator、Boundary、最终输出的责任区分。
3. 现有机制未发挥作用的原因和误导性成功指标。
4. 修复手段、成功标准和停止条件。

## 已确认根因

1. 拒绝状态已经及时生效，不是 State 未写入。
2. Generator 前置策略只有自然语言禁令，仍会生成新的同构表达。
3. `_rejected_route_topology_conflicts` 主要依赖局部正则句法；等价表达会因“围着 / 围 / 围合”等形式差异得到不同结论。
4. 重写验收和日志验收复用同一检测器，检测器漏检时会形成自证通过。
5. `candidate_commitment_body_patched` 合并了 Candidate 正文修补和拓扑修补，不能单独证明拓扑边界执行成功。

## 方案

### 1. 结构签名

在 `architect_chat.py` 现有拓扑检查附近增加内部函数，将回答中的肯定空间关系归纳为以下内部字段：

- `participant_scope`: `global`、`pairwise_local` 或 `unknown`
- `mediator_scope`: `single`、`multiple` 或 `unknown`
- `dependency_scope`: `shared_global`、`local_edges` 或 `unknown`

当结构为 `global + single + shared_global` 时，判为单一全局组织媒介。若拒绝上下文包含中心拒绝，则返回 `centralized_organizer`；若包含单主线拒绝，则返回 `single_linear_organizer`。

多个明确的两两局部联系、不同位置联系或多个独立到达点必须归为 `pairwise_local / multiple / local_edges`，不得误报。

结构签名只判断关系角色，不判断媒介名称；不新增“院、场、平台、缝”等空间名词词表。

### 2. 接入范围

- 保留现有 `_rejected_route_topology_conflicts` 入口和返回值。
- 结构签名作为现有正则的概念级补充；本阶段不删除已有经过回归验证的规则。
- `_apply_rejected_route_topology_boundary` 继续使用现有两次重写和安全回退流程。
- 不修改 `conversation_state.py` 的状态结构。

### 3. 观测字段

在 `_call_deepseek(..., return_stages=True)` 中分别记录：

- `topology_conflicts_before`
- `topology_rewrite_applied`
- `topology_conflicts_after`
- `topology_fallback_used`

`candidate_commitment_body_patched` 保留兼容，但不再作为拓扑修复是否执行的唯一证据。

真实复测日志同步输出这些字段。

## 测试

先写失败测试，至少覆盖：

1. `三个单元围一个共同对象`。
2. `三个单元围合出一个共同对象`。
3. 不出现空间名词、但表达“所有单元共同依赖一个媒介”。
4. `A-B、B-C、C-D` 多个局部边不得误报。
5. 每组关系各画一条线不得误报为单一全局主线。
6. 重写阶段观测字段能区分未触发、重写成功和安全回退。

随后运行 Candidate Boundary、State 否定动作、Semantic Events、Candidate Route Ledger 和 Python 语法检查。

## 真实验证

使用与 A 组完全相同的六轮普通学生对话运行 DeepSeek。人工检查第 4、5、6 轮：

- 拒绝是否立即生效；
- 是否以新名称复活单一中心、主线或全局媒介；
- 是否保留功能关系、楼层骨架和可画动作；
- 是否退化为免责声明、空泛回答或机械安全模板。

## 停止条件

若结构签名连续三次修改仍因新的表面动词产生漏检，停止继续扩充规则，报告该本地确定性方案不足，不进入新的 Layer 或外部语义裁判实现。
