# -*- coding: utf-8 -*-
"""三层一致性回归：上传两张真实图 → 视觉分析成功 → 对话确认/指代/无图诚实。
（Backend=能看 / UI=能看 / AI=也能看，不再互打架）"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8000/demo/collaborator.html"
IMG_A = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\images\Church_of_the_Light\plan.jpg"
IMG_B = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\images\Church_of_the_Light\space_01.jpg"
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")

        # 上传前先关掉原生 confirm（图片上传授权弹窗）——接受
        page.on("dialog", lambda d: d.accept())

        # 上传图 A、图 B（真实 Qwen-VL 分析）
        for img, name in [(IMG_A, "图A"), (IMG_B, "图B")]:
            page.set_input_files("#fileInput", img)
            # 等待分析完成（右栏出现"视觉分析完成"pill）
            dl = time.time() + 120
            while time.time() < dl:
                pills = page.locator("#filesContent .pill").all_text_contents()
                if any("视觉分析完成" in t for t in pills):
                    break
                time.sleep(2)
            time.sleep(1)
            pills = page.locator("#filesContent .pill").all_text_contents()
            check(f"上传{name} 视觉分析完成", any("视觉分析完成" in t for t in pills), str(pills[-3:]))

        # 对话："看到这两张图了吗" → 必须确认，禁止"没有图像识别能力"
        page.fill("#input", "看到这两张图片了吗")
        page.press("#input", "Enter")
        dl = time.time() + 120
        while time.time() < dl:
            if page.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.6)
        t = page.locator("#messages .message").last.text_content()
        check("对话 确认两张图", ("两张" in t or "两张图片" in t or "图片" in t), t[:60])
        check("对话 无'没有图像识别能力'", "没有图像识别能力" not in t and "无法直接读取" not in t, "")

        # "第一张是什么" → 用第一张 visible_facts，不读第二张
        page.fill("#input", "第一张是什么？")
        page.press("#input", "Enter")
        dl = time.time() + 120
        while time.time() < dl:
            if page.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.6)
        t2 = page.locator("#messages .message").last.text_content()
        check("对话 第一张能回答(非看不了)", "没有图像识别能力" not in t2 and "无法直接读取" not in t2, t2[:60])

        # 无图场景：新项目 → "看到图了吗" → 诚实"没有可用图片"
        page.click("#resetBtn")
        page.wait_for_timeout(600)
        page.fill("#input", "看到图了吗")
        page.press("#input", "Enter")
        dl = time.time() + 120
        while time.time() < dl:
            if page.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.6)
        t3 = page.locator("#messages .message").last.text_content()
        check("无图 诚实(没图)", ("没有" in t3 and "图片" in t3) or ("图" in t3 and "上传" in t3), t3[:60])

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\vision_context_fix.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 30, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
