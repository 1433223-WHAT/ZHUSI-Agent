# 增量需求理解实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框跟踪进度。

**目标：** 让理解进度反映 AI 对用户需求的真实掌握程度，允许一句话补充多项或不补充任何项，并保证进度不倒退。

**架构：** `design_discussion.py` 负责从本轮用户表达中提取有文本证据的事实与理解状态，合并既有认知并计算单调进度；`mentor.html` 只提交对话和既有认知，不再把回答强制绑定到当前问题；追问器根据未明确或仍有疑问的内容动态追问。

**技术栈：** Python、DeepSeek JSON 接口、原生 JavaScript、unittest。

---

### 任务 1：定义增量认知行为

**文件：**
- 修改：`tests/test_direction_proposer.py`
- 修改：`design_discussion.py`

- [ ] 编写失败测试：一句回答可更新多个事实、答非所问不自动填当前维度、历史进度不倒退、信息充分后停止追问。
- [ ] 运行 `python -m unittest discover -s tests -p "test_*.py" -v`，确认测试因旧的强制绑定逻辑失败。
- [ ] 增加本轮事实提取与证据校验，只接受能在用户表达中找到依据的模型输出。
- [ ] 合并历史事实与理解状态，使用历史百分比作为下限。
- [ ] 再次运行测试，确认新增行为通过。

### 任务 2：修复前端状态传递

**文件：**
- 修改：`demo/mentor.html`
- 修改：`server.py`

- [ ] 前端删除 `knownFacts[currentQuestion.dimension] = text` 的强制绑定。
- [ ] 将后端返回的已确认事实作为下一轮唯一认知状态，并传递历史完整度。
- [ ] 在认知板展示“已明确、部分理解、待确认”状态。
- [ ] 用 Node 解析页面脚本，确认无 JavaScript 语法错误。

### 任务 3：完整对话验收

**文件：**
- 验证：`design_discussion.py`、`server.py`、`demo/mentor.html`

- [ ] 重启单一 8787 后端。
- [ ] 实跑“乡村民宿”及多轮自由回答，确认一句话可更新多项、模糊回答不乱填、进度不倒退。
- [ ] 运行 Python 编译、全套 unittest、前端脚本解析和页面 HTTP 检查。
