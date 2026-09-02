"""
generate_church_analysis_diagrams.py — 生成光之教堂分析示意图

用 matplotlib 绘制"AI 理解的建筑逻辑"分析图：
  1. plan_analysis.jpg    — 平面组织分析（三个立方体+斜墙+十字光缝+入口路径）
  2. light_path.jpg       — 光路径剖面分析（十字开口→光进入→精神焦点）
  3. spatial_sequence.jpg — 空间序列分析（外部→过渡→精神空间的压缩释放）
  4. material_light.jpg   — 材料与光分析（清水混凝土吸收→光凸显）

这些图用于 ArchAI Image DB，让 AI 不仅"看到"案例照片，
还能展示它从建筑中提取的设计逻辑。
"""

import sys
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无界面渲染
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import font_manager
from matplotlib.patches import FancyArrow, FancyArrowPatch

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── 中文字体 ────────────────────────────────────────────
def setup_chinese_font():
    for f in font_manager.fontManager.ttflist:
        if "jhenghei" in f.name.lower() or "simhei" in f.name.lower() or "yahei" in f.name.lower() or "microsoft" in f.name.lower():
            plt.rcParams["font.family"] = f.name
            plt.rcParams["axes.unicode_minus"] = False
            return True
    # 兜底 STSong
    for f in font_manager.fontManager.ttflist:
        if "st" in f.name.lower() and ("song" in f.name.lower() or "kai" in f.name.lower()):
            plt.rcParams["font.family"] = f.name
            return True
    return False

setup_chinese_font()

OUT = Path(__file__).resolve().parent / "images" / "Church_of_the_Light"
OUT.mkdir(parents=True, exist_ok=True)

# 配色（ArchAI 风格）
CONCRETE = "#8a8d8f"   # 清水混凝土
DARK = "#3a3a3a"       # 暗空间
LIGHT = "#f5d76e"      # 光
ACCENT = "#e94560"     # 强调
BG = "#fafafa"


def draw_plan():
    """平面组织分析：三个立方体 + 15°斜墙 + 十字光缝 + 入口路径"""
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # 建筑外轮廓（三个 5.9m 立方体：约 5.9×17.7）
    outer = patches.Rectangle((0, 0), 17.7, 5.9, linewidth=3, edgecolor=DARK, facecolor="none", zorder=2)
    ax.add_patch(outer)

    # 礼拜空间（右侧大空间）
    worship = patches.Rectangle((0, 0), 17.7, 5.9, linewidth=0, facecolor="#e8e8e8", alpha=0.5, zorder=1)
    ax.add_patch(worship)

    # 15° 斜墙（把空间分成交叉的两个体量）
    import numpy as np
    wall_pts = [(2.0, 0), (17.7, 4.2)]
    ax.plot([wall_pts[0][0], wall_pts[1][0]], [wall_pts[0][1], wall_pts[1][1]],
            color=DARK, linewidth=5, zorder=3)
    ax.text(12, 3.4, "15°斜墙\n空间分界", fontsize=10, color=DARK, ha="center", zorder=4)

    # 祭坛墙（礼拜空间后方，含十字光缝）
    altar_wall = patches.Rectangle((16.8, 1.2), 0.4, 3.5, linewidth=0, facecolor=DARK, zorder=3)
    ax.add_patch(altar_wall)

    # 十字光缝（祭坛墙中央）
    cx, cy = 17.0, 2.95
    cross_vert = patches.Rectangle((cx - 0.08, cy - 0.55), 0.16, 1.1, facecolor=LIGHT, edgecolor="none", zorder=5)
    cross_horiz = patches.Rectangle((cx - 0.35, cy - 0.08), 0.7, 0.16, facecolor=LIGHT, edgecolor="none", zorder=5)
    ax.add_patch(cross_vert)
    ax.add_patch(cross_horiz)
    ax.text(cx, cy + 0.7, "十字光缝", fontsize=9, color="#b8860b", ha="center", zorder=5)

    # 入口位置（斜墙起点附近，左下）
    entrance = patches.Circle((2.2, 2.6), 0.35, facecolor="white", edgecolor=ACCENT, linewidth=2, zorder=5)
    ax.add_patch(entrance)
    ax.text(2.2, 3.3, "入口", fontsize=10, color=ACCENT, ha="center", zorder=5)

    # 人行动线（入口 → 绕过斜墙 → 礼拜空间 → 祭坛）
    from matplotlib.patches import FancyArrowPatch
    path = [(2.4, 2.6), (6, 1.6), (11, 1.5), (15.5, 2.2), (16.5, 2.95)]
    for i in range(len(path) - 1):
        arrow = FancyArrowPatch(path[i], path[i+1], arrowstyle="-|>", mutation_scale=14,
                                color=ACCENT, linewidth=2, zorder=4)
        ax.add_patch(arrow)
    ax.text(7, 0.7, "动线：绕过斜墙 → 礼拜空间 → 祭坛", fontsize=9, color=ACCENT, ha="center")

    # 功能标注
    ax.text(6, 5.2, "礼拜空间（主空间）", fontsize=11, color=DARK, ha="center", fontweight="bold")
    ax.text(2.0, 0.9, "入口过渡区", fontsize=9, color="#666", ha="center")

    # 尺度标注
    ax.annotate("", xy=(17.7, -0.4), xytext=(0, -0.4), arrowprops=dict(arrowstyle="<->", color="#999"))
    ax.text(8.85, -0.85, "17.7m", fontsize=9, color="#999", ha="center")
    ax.annotate("", xy=(-0.4, 5.9), xytext=(-0.4, 0), arrowprops=dict(arrowstyle="<->", color="#999"))
    ax.text(-0.85, 2.95, "5.9m", fontsize=9, color="#999", va="center")

    ax.set_xlim(-2, 19)
    ax.set_ylim(-1.5, 6.3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("光之教堂 — 平面组织分析", fontsize=14, fontweight="bold", color=DARK, pad=15)

    # 图注
    fig.text(0.5, 0.02, "三个 5.9m 立方体 · 15° 斜墙划分空间 · 祭坛墙十字光缝 · 动线绕行进入",
             ha="center", fontsize=9, color="#666")

    plt.tight_layout()
    path = OUT / "plan_analysis.jpg"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"[OK] {path.name}")


def draw_light_path():
    """光路径剖面分析：十字开口→自然光进入→精神焦点"""
    fig, ax = plt.subplots(1, 1, figsize=(10, 7))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor("#1a1a1a")  # 暗背景突出光

    # 建筑剖面轮廓（礼拜空间 5.9m 高）
    # 外墙
    ax.plot([0, 0], [0, 5.9], color=CONCRETE, linewidth=4)
    ax.plot([6.5, 6.5], [0, 5.9], color=CONCRETE, linewidth=4)
    ax.plot([0, 6.5], [5.9, 5.9], color=CONCRETE, linewidth=4)
    ax.plot([0, 6.5], [0, 0], color=CONCRETE, linewidth=4)

    # 地面
    ax.fill_between([0, 6.5], 0, -0.3, color="#555", zorder=1)

    # 祭坛墙（右侧内墙，含十字开口）
    ax.plot([5.2, 5.2], [0, 5.9], color=CONCRETE, linewidth=5)

    # 十字光缝（祭坛墙上方开口 — 实际是后方墙面）
    # 光从右侧后方进入
    gap_top, gap_bot = 3.2, 2.0
    # 十字开口
    ax.add_patch(patches.Rectangle((5.2, gap_bot), 0.6, gap_top - gap_bot, facecolor=LIGHT, edgecolor="none", alpha=0.95, zorder=3))

    # 光线路径（从开口向左下射入）
    from matplotlib.patches import Polygon
    # 光锥
    ray = Polygon([(5.2, gap_top), (0.8, 2.0), (5.2, gap_bot)], closed=False,
                  facecolor=LIGHT, alpha=0.18, edgecolor="none", zorder=2)
    ax.add_patch(ray)

    # 光箭头
    for y_start, y_end in [(3.3, 2.6), (2.9, 2.2), (2.5, 1.9)]:
        arrow = FancyArrowPatch((5.2, y_start), (2.0, y_end), arrowstyle="-|>",
                                mutation_scale=12, color=LIGHT, linewidth=1.5, alpha=0.8, zorder=4)
        ax.add_patch(arrow)

    ax.text(3.2, 3.9, "自然光通过十字形开口进入", fontsize=11, color=LIGHT, ha="center", fontweight="bold", zorder=5)
    ax.text(2.0, 1.4, "光在地面和墙面形成\n明暗对比 · 动态变化", fontsize=9, color=LIGHT, ha="center", alpha=0.8, zorder=5)

    # 空间标注
    ax.text(2.5, 5.3, "礼拜空间（暗）", fontsize=10, color="#ccc", ha="center")
    ax.text(5.7, 4.5, "祭坛墙\n十字光缝", fontsize=8, color=LIGHT, ha="left")
    ax.text(2.5, -0.8, "地面（深色木材/混凝土）", fontsize=9, color="#999", ha="center")

    # 高度标注
    ax.annotate("", xy=(-0.6, 5.9), xytext=(-0.6, 0), arrowprops=dict(arrowstyle="<->", color="#999"))
    ax.text(-0.95, 2.95, "5.9m", fontsize=9, color="#999", va="center")

    ax.set_xlim(-1.5, 7.5)
    ax.set_ylim(-1.2, 6.6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("光之教堂 — 光路径分析", fontsize=14, fontweight="bold", color="white", pad=15)

    fig.text(0.5, 0.02, "唯一的自然光入口 · 光成为空间主角 · 明暗对比制造精神焦点",
             ha="center", fontsize=9, color="#888")

    plt.tight_layout()
    path = OUT / "light_path.jpg"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#1a1a1a")
    plt.close()
    print(f"[OK] {path.name}")


def draw_spatial_sequence():
    """空间序列分析：外部→过渡→精神空间的压缩释放"""
    fig, ax = plt.subplots(1, 1, figsize=(11, 4.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # 四个空间节点（从左到右：外部 → 入口过渡 → 礼拜空间 → 光核心）
    nodes = [
        ("外部世界", "开放 · 明亮", "#c8c8c8", 1.0),
        ("过渡空间", "收束 · 变暗", "#9a9a9a", 0.7),
        ("礼拜空间", "封闭 · 暗", "#5a5a5a", 0.55),
        ("光之核心", "十字光 · 精神焦点", "#f5d76e", 0.9),
    ]

    box_w, box_h = 2.0, 2.2
    y_center = 2.0
    xs = [0.5, 3.5, 6.5, 9.5]

    for i, (name, desc, color, scale) in enumerate(nodes):
        x, y = xs[i], y_center
        w, h = box_w * scale + (0 if scale == 1 else 0.3), box_h * scale + (0 if scale == 1 else 0.3)
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                                      facecolor=color, edgecolor=DARK, linewidth=1.5, alpha=0.85, zorder=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.45, name, fontsize=12, color="white" if color != "#c8c8c8" else DARK,
                ha="center", fontweight="bold", zorder=3)
        ax.text(x + w/2, y + 0.5, desc, fontsize=9, color="white" if color != "#c8c8c8" else "#555",
                ha="center", zorder=3)

    # 箭头连接
    for i in range(3):
        arrow = FancyArrowPatch((xs[i] + 2.0, y_center + 1.0), (xs[i+1] - 0.1, y_center + 1.0),
                                arrowstyle="-|>", mutation_scale=20, color=ACCENT, linewidth=2.5, zorder=4)
        ax.add_patch(arrow)

    # 情绪曲线（压缩→释放）
    import numpy as np
    curve_x = np.linspace(0.5, 12, 100)
    # 表达情绪：外部平缓 → 过渡下降（压缩）→ 礼拜低谷 → 光核心骤升（释放）
    curve_y = []
    for x in curve_x:
        if x < 3:
            curve_y.append(2.2)
        elif x < 6:
            curve_y.append(2.2 - (x - 3) * 0.5)
        elif x < 9:
            curve_y.append(0.7)
        else:
            curve_y.append(0.7 + (x - 9) * 1.2)
    ax.plot(curve_x, curve_y, color=ACCENT, linewidth=2, linestyle="--", alpha=0.6, zorder=1)
    ax.text(11.5, 4.3, "情绪曲线：压缩 → 释放", fontsize=9, color=ACCENT, ha="right", alpha=0.8)

    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("光之教堂 — 空间序列分析（压缩—释放）", fontsize=14, fontweight="bold", color=DARK, pad=12)

    fig.text(0.5, 0.02, "外部 → 过渡 → 精神空间 · 由明到暗再到光的递进 · 情绪先抑后扬",
             ha="center", fontsize=9, color="#666")

    plt.tight_layout()
    path = OUT / "spatial_sequence.jpg"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"[OK] {path.name}")


def draw_material_light():
    """材料与光分析：清水混凝土吸收光线→光凸显"""
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    fig.patch.set_facecolor(BG)

    # 左图：混凝土表面（粗糙、吸收光）
    ax[0].set_facecolor("#8a8d8f")
    # 模拟混凝土纹理
    import numpy as np
    rng = np.random.default_rng(42)
    for _ in range(80):
        x, y = rng.uniform(0, 1, 2)
        ax[0].plot(x, y, "o", color="#7a7d7f", markersize=rng.uniform(2, 8), alpha=0.4)
    ax[0].set_title("清水混凝土表面\n吸收光线 · 无反射", fontsize=11, color="white")
    ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1)
    ax[0].axis("off")

    # 右图：光在暗背景上凸显
    ax[1].set_facecolor("#1a1a1a")
    # 十字光
    cx, cy = 0.5, 0.5
    ax[1].add_patch(patches.Rectangle((cx - 0.04, cy - 0.3), 0.08, 0.6, facecolor=LIGHT, alpha=0.95))
    ax[1].add_patch(patches.Rectangle((cx - 0.18, cy - 0.04), 0.36, 0.08, facecolor=LIGHT, alpha=0.95))
    # 光晕
    for r in [0.35, 0.5]:
        circle = plt.Circle((cx, cy), r, color=LIGHT, alpha=0.15 - r*0.2, zorder=0)
        ax[1].add_patch(circle)
    ax[1].set_title("十字光在暗背景上凸显\n成为唯一视觉焦点", fontsize=11, color="white")
    ax[1].set_xlim(0, 1); ax[1].set_ylim(0, 1)
    ax[1].axis("off")

    fig.suptitle("材料与光的关系：混凝土的暗，成就光的亮", fontsize=14, fontweight="bold", color=DARK, y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = OUT / "material_light.jpg"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"[OK] {path.name}")


if __name__ == "__main__":
    print("=== 生成光之教堂分析图 ===")
    draw_plan()
    draw_light_path()
    draw_spatial_sequence()
    draw_material_light()
    print("\n完成！输出目录:", OUT)
