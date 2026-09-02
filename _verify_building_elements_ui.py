# -*- coding: utf-8 -*-
"""Building Elements UI 验证：真实上传住宅平面图 → 右栏展示结构化窗/门 → 聊天收到窗信息。
（full-access 运行：需要 Chromium）"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
URL = "http://127.0.0.1:8000/demo/collaborator.html"
IMG = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\新建文件夹\微信图片_20260818200451_55_360.jpg"
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
        page.on("dialog", lambda d: d.accept())

        # 上传住宅平面图（真实 Qwen 分析，新 prompt）
        page.set_input_files("#fileInput", IMG)
        dl = time.time() + 180
        while time.time() < dl:
            pills = page.locator("#filesContent .pill").all_text_contents()
            if any("视觉分析完成" in t for t in pills):
                break
            time.sleep(2)
        time.sleep(1)
        pills = page.locator("#filesContent .pill").all_text_contents()
        check("上传住宅平面图 分析完成", any("视觉分析完成" in t for t in pills), str(pills[-3:]))

        # 右栏展示 building_elements（结构化识别）
        files_html = page.locator("#filesContent").inner_text()
        check("右栏显示'建筑要素（结构化识别）'", "建筑要素（结构化识别）" in files_html)
        check("右栏显示窗条目", "窗：" in files_html, "")
        check("右栏显示门编号", "M2421" in files_html or "门：" in files_html, "")

        # 聊天：问窗户（不诱导视觉分析——分析已完成，问句只进 chat）
        page.fill("#input", "你能看到窗户吗？")
        page.press("#input", "Enter")
        dl = time.time() + 150
        while time.time() < dl:
            if page.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.6)
        t = page.locator("#messages .message").last.text_content()
        check("聊天回答含'窗'", "窗" in t, t[:120])
        bad = "没有窗" in t or "没看到窗" in t or "无窗" in t
        check("聊天未断言'没有窗'", not bad, t[:400])
        print("\n===== 完整回答 =====")
        print(t)
        print("====================")

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\building_elements_ui.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 30, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
