# -*- coding: utf-8 -*-
"""生成《筑思Agent_队友入组包_V1.0.docx》。"""
import sys
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

OUT = r"E:\AI\项目设计\筑智AI_ArchAI\05_比赛材料\筑思Agent_队友入组包_V1.0.docx"
INK = RGBColor(0x21, 0x1D, 0x17)
CLAY = RGBColor(0xB3, 0x54, 0x2E)
MUTED = RGBColor(0x75, 0x6C, 0x5E)


def set_font(run, name_cn="宋体", name_en="Calibri", size=11, bold=False, color=None, mono=False):
    run.font.name = "Consolas" if mono else name_en
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体" if not mono else "Consolas")


def h1(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_font(r, name_cn="黑体", size=18, bold=True, color=INK)
    p.paragraph_format.space_after = Pt(6)
    return p


def h2(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_font(r, name_cn="黑体", size=14, bold=True, color=CLAY)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    return p


def para(doc, text, size=11, bold=False, color=None, align=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_font(r, size=size, bold=bold, color=color)
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(3)
    return p


def mono(doc, text, size=9):
    for line in text.split("\n"):
        p = doc.add_paragraph()
        r = p.add_run(line if line else " ")
        set_font(r, size=size, mono=True, color=MUTED)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0


def bullet(doc, text, bold_head=None, size=11):
    p = doc.add_paragraph(style="List Bullet")
    if bold_head:
        r1 = p.add_run(bold_head)
        set_font(r1, size=size, bold=True)
    r2 = p.add_run(text)
    set_font(r2, size=size)
    p.paragraph_format.space_after = Pt(2)
    return p


def make_table(doc, headers, rows, widths=None, size=10.5):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        cell = t.cell(0, j)
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        set_font(r, name_cn="黑体", size=size, bold=True)
    for i, row in enumerate(rows, 1):
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.text = ""
            r = cell.paragraphs[0].add_run(str(val))
            set_font(r, size=size)
    if widths:
        for j, w in enumerate(widths):
            for row in t.rows:
                row.cells[j].width = Cm(w)
    doc.add_paragraph()
    return t


def main():
    doc = Document()
    for s in doc.sections:
        s.top_margin = Cm(2.0); s.bottom_margin = Cm(2.0)
        s.left_margin = Cm(2.2); s.right_margin = Cm(2.2)

    p = doc.add_paragraph(); r = p.add_run("筑思 Agent 队友入组包 V1.0")
    set_font(r, name_cn="黑体", size=22, bold=True, color=INK); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2 = doc.add_paragraph(); r2 = p2.add_run("证据约束型建筑设计协作工作台 · 一包读懂项目")
    set_font(r2, size=11, color=MUTED); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3 = doc.add_paragraph(); r3 = p3.add_run("2026-08-18 · V0.2 · 对象：三名队友")
    set_font(r3, size=10.5, color=MUTED); p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    h2(doc, "〇、一句话开场")
    para(doc, "筑思 Agent 是面向建筑学生的证据约束型设计协作工作台——AI 参与设计的每一步，但每个说法都可追溯到依据，设计决定始终由学生做出。", size=12, bold=True)
    para(doc, "对外一句话：「一个不会替你画图、但会陪你推敲，并且每个说法都有出处的建筑设计 AI 搭档。」", color=MUTED)

    h2(doc, "一、项目定位")
    para(doc, "研究命题：如何让生成式 AI 参与建筑设计过程，但不替代设计者的判断？筑思的核心贡献不是“AI 会设计建筑”，而是回答了“AI 在建筑设计教育中的最大风险，不是不会生成，而是不受约束地替学生生成”。这是 AI + 建筑教育方法的研究项目，四层边界模型本身就是可发表的方法论贡献。")

    h2(doc, "二、痛点（建筑学生用 AI 的三类真实困难）")
    make_table(doc, ["困难", "通用 AI 的表现", "筑思的解法"],
               [["AI 替学生决定", "“建议入口放北侧”（盖章式结论）", "证据分层 + 判断边界：经验写成可检验的判断路径"],
                ["案例不会迁移", "推荐案例名，不解释“为什么适合我”", "案例实体（文本+图片）+ 迁移分析（原问题→可迁移→条件→风险）"],
                ["图纸理解缺证据边界", "“这是一个开放式大厅”（看图编造）", "视觉分析三层：可见事实 / 推测（带依据+置信度）/ 未知项"]],
               widths=[3.2, 5.2, 7.4])

    h2(doc, "三、目标用户")
    bullet(doc, "建筑专业学生（课程设计 / 竞赛 / 毕业设计）", bold_head="用户：")
    bullet(doc, "方案构思 → 案例查证 → 图纸分析 → 评图前推敲", bold_head="场景：")
    bullet(doc, "打开网页 → 新建项目 → 开始设计（无注册门槛）", bold_head="形态：")

    h2(doc, "四、核心功能")
    bullet(doc, "推进不替代——每轮最多推进一个设计层级，判断留白给学生", bold_head="1. 设计对话协作：")
    bullet(doc, "“光之教堂图片”“有平面的吗”“你从知识库里找”——文本+视觉资产+上下文承接", bold_head="2. 案例实体查询：")
    bullet(doc, "上传草图 → 可见事实/推测/未知项三层，不编造", bold_head="3. 图纸视觉分析：")
    bullet(doc, "回答的每条依据都能点开看来源（案例/理论/方法 + 来源状态）", bold_head="4. 证据追溯：")
    bullet(doc, "设计记忆 / 项目文件 / 知识依据 / 过程记录自动沉淀", bold_head="5. 项目档案：")

    h2(doc, "五、四层边界（方法论核心）")
    para(doc, "因果链：输入错了 → 证据就会错 → 推进就会错 → 提问就会变成引导控制", bold=True)
    make_table(doc, ["边界", "核心问题", "控制风险"],
               [["① 输入边界", "AI 看到的信息，是不是用户真正提供的信息？", "误读"],
                ["② 证据边界", "AI 说的话有多少依据？（事实/观察/推测/建议/决定五层）", "幻觉"],
                ["③ 推进边界", "AI 推进设计到哪里？（每轮至多推进一层）", "替代"],
                ["④ 提问边界", "AI 什么时候问？（有目的+服务下一步+符合尺度）", "操控"]],
               widths=[3.0, 8.4, 4.4])
    para(doc, "工程化现状：证据边界已从 Prompt 原则落地为工程机制——Retrieved/Mentioned/Displayed 三层 + 无依据诚实标注（宁可说“本轮无依据”，不伪绑定相似证据）。", size=10.5, color=MUTED)

    h2(doc, "六、系统架构简图")
    mono(doc, """              学生（浏览器：暖色建筑编辑工作台 UI）
                            │  http://API
        ┌───────────────────▼───────────────────┐
        │           Python 后端（server.py）       │
        │  Intent Router（意图分类+路由）           │
        │  Evidence Boundary（A+ 三层证据映射）      │
        │  Retrieval Focus（上下文继承检索）        │
        └──┬────────────┬──────────────┬─────────┘
           │            │              │
   ┌───────▼──┐  ┌──────▼─────┐  ┌─────▼────────┐
   │ DeepSeek │  │ Qwen-VL    │  │ 知识系统      │
   │ 对话/分类 │  │ 图纸视觉分析│  │ BGE 向量检索  │
   │ 改写/评图 │  │ (DASHSCOPE)│  │ 案例实体索引   │
   └──────────┘  └────────────┘  │ 视觉资产(images)│
                                  │ 来源标注        │
                                  └────────────────┘""")

    h2(doc, "七、当前成果（V0.2 · Evidence-grounded Demo checkpoint）")
    bullet(doc, "回答 → 依据 → 追溯定位 → 诚实无依据标注（A+ 三层，E2E 9/9）", bold_head="✅ 证据链完整：")
    bullet(doc, "案例实体（文本+视觉资产+别名）+ 上下文继承检索", bold_head="✅ 知识资产链：")
    bullet(doc, "“光之教堂图片”→ 直接出 8 张真实资产卡（原始图纸/筑思分析图/空间照片分标注）", bold_head="✅ 案例图片调用：")
    bullet(doc, "V3 Warm Architectural Editorial Workspace", bold_head="✅ UI v3.3：")
    bullet(doc, "25 大师经典 + 3 课程题型（批 1 进行中，目标 30-40）；问题型检索测试通过", bold_head="✅ 案例库：")
    bullet(doc, "四层边界压力测试库 V0.2、证据链路 E2E、全链路回归 12/12、Router 12/12", bold_head="✅ 测试体系：")

    h2(doc, "八、比赛方向")
    bullet(doc, "互联网+（个人赛，李宇飞）", bold_head="赛事：")
    bullet(doc, "不是“AI 能生成方案”，而是“AI 如何不夺走学生的设计判断”", bold_head="核心卖点：")
    bullet(doc, "回答提到「安藤忠雄」但库中本轮无依据 → 如实标注“未挂接证据”", bold_head="演示亮点：")
    bullet(doc, "vs 通用 AI（不胡说/不替做决定/有出处）· vs 生成式工具（不生成完整方案）· vs 普通知识库（可对话调用的案例实体）", bold_head="差异化：")
    bullet(doc, "项目计划书 V2.1 / 四层边界模型 V1.0 / 技术架构 V0.1 / PPT 内容稿 / 路演稿 / 定位 / Demo 说明", bold_head="已有材料：")

    h2(doc, "九、Roadmap")
    make_table(doc, ["阶段", "内容", "状态"],
               [["① 知识系统 V2", "案例实体 + 图片调用 + 上下文检索", "✅ 完成"],
                ["② 课程题型案例库", "8 题型 × 3-5 个 ≈ 30-40 案例", "🔄 批 1 进行中"],
                ["③ UI 收尾", "V3 暖色工作台最终打磨", "大部分完成"],
                ["④ 公网部署", "前后端部署、Key 只留后端、上传处理、HTTPS/限流", "待做"],
                ["⑤ 外部测试", "5-10 名建筑同学真实使用", "待做"],
                ["⑥ V0.3", "根据外部使用 Bug 迭代", "待做"]],
               widths=[4.2, 8.0, 3.6])

    h2(doc, "十、三名队友分工")
    make_table(doc, ["角色", "负责", "具体任务"],
               [["李宇飞（主创 · 产品与设计判断）", "产品定位 / 四层边界 / UI 审美 / 建筑知识判断", "定位与边界把关、案例选题、UI 视觉方向、答辩演示、对外沟通"],
                ["队友 A（技术负责人）", "系统开发与部署", "前后端开发、API 与 Key 管理、知识库管线、自动化测试、公网部署、安全"],
                ["队友 B（内容与知识）", "案例库与知识体系", "课程题型案例 md 生产、图片资产、知识标注与别名、用户测试组织、比赛材料协助"]],
               widths=[5.4, 4.2, 6.2])
    para(doc, "协作节奏：每周 1 次同步会；李宇飞定内容方向 → 队友 B 生产案例 → 队友 A 验证/入库 → 三人合测（压力测试库 + 问题型检索）；Demo 前全员演练。", size=10.5, color=MUTED)

    h2(doc, "十一、5 分钟 Demo 脚本")
    make_table(doc, ["时间", "动作", "展示点"],
               [["0:00-0:30", "开场一句话定位", "“不会替你画图，但陪你推敲、每个说法有出处”"],
                ["0:30-2:00", "输入“我要做教学楼”→ 对话推进", "推进边界、提问边界"],
                ["2:00-3:00", "“社区图书馆有什么案例”→“光之教堂图片”→“有平面的吗”", "案例实体 + 多模态资产 + 上下文承接"],
                ["3:00-4:00", "点「查看知识依据 →」定位高亮；无依据诚实标注", "证据追溯 + 诚实边界"],
                ["4:00-5:00", "右栏：设计记忆/文件/知识/过程", "过程资产化 + 下一步"]],
               widths=[2.4, 7.0, 6.4])
    para(doc, "演示前必检：后端 8787 + 前端 8000 运行；Ctrl+F5；问题型检索可召回（“中国中学用地紧张”→ 北京四中房山）。", size=10.5, color=MUTED)

    doc.save(OUT)
    print("saved:", OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
