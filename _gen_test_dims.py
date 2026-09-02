# -*- coding: utf-8 -*-
"""合成建筑尺寸测试图：横向 6000+8000=14000（总宽），纵向 4500+3500+6000=14000（总长），
干扰项：门洞 1200、墙厚 200——验证 Qwen-max 识别 + NumericVerifier 不求和。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont

OUT = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\_test_dims.png"
W, H = 900, 700
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

def font(sz):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()

f_small = font(20)
f_dim = font(22)

# 建筑轮廓（矩形）
x0, y0, x1, y1 = 200, 200, 640, 520  # 宽 440px，高 320px
d.rectangle([x0, y0, x1, y1], outline="black", width=3)

# 顶部尺寸线：总宽 14000（外侧）+ 分段 6000 + 8000
ty = y0 - 40
d.line([x0, ty, x1, ty], fill="black", width=2)
d.line([x0, ty - 8, x0, ty + 8], fill="black", width=2)
d.line([x1, ty - 8, x1, ty + 8], fill="black", width=2)
d.text(((x0 + x1) / 2 - 30, ty - 34), "14000", fill="black", font=f_dim)
# 分段 6000 | 8000
mx = x0 + int(440 * 6000 / 14000)
d.line([mx, ty - 6, mx, ty + 6], fill="black", width=2)
d.text((x0 + (mx - x0) / 2 - 20, ty - 30), "6000", fill="black", font=f_dim)
d.text((mx + (x1 - mx) / 2 - 20, ty - 30), "8000", fill="black", font=f_dim)

# 左侧尺寸线：总长 14000（外侧）+ 分段 4500 + 3500 + 6000
lx = x0 - 50
d.line([lx, y0, lx, y1], fill="black", width=2)
d.line([lx - 8, y0, lx + 8, y0], fill="black", width=2)
d.line([lx - 8, y1, lx + 8, y1], fill="black", width=2)
d.text((lx - 60, (y0 + y1) / 2 - 10), "14000", fill="black", font=f_dim)
# 分段
seg_y = [int(320 * 4500 / 14000), int(320 * 3500 / 14000), int(320 * 6000 / 14000)]
cur = y0
for i, dy in enumerate(seg_y):
    my = cur + dy
    d.line([lx - 6, my, lx + 6, my], fill="black", width=2)
    d.text((lx - 55, cur + dy / 2 - 10), ["4500", "3500", "6000"][i], fill="black", font=f_dim)
    cur = my

# 房间内部干扰尺寸：门洞 1200、墙厚 200
d.line([x0 + 120, y0, x0 + 120, y0 + 60], fill="black", width=2)
d.text((x0 + 126, y0 + 24), "1200", fill="black", font=f_small)
d.rectangle([x0 + 250, y0 + 120, x0 + 258, y0 + 126], outline="black", width=2)
d.text((x0 + 264, y0 + 116), "墙厚200", fill="black", font=f_small)

d.text((20, 20), "测试平面图：横向总宽14000(6000+8000)，纵向总长14000(4500+3500+6000)", fill="black", font=f_small)
img.save(OUT)
print("合成图:", OUT)
