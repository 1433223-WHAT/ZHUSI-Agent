# -*- coding: utf-8 -*-
"""v2.3 深色主题专项验证：背景/气泡/文字色 + 对比度 + 截图。"""
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/demo/collaborator.html"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_3_dark_empty.png", full_page=True)

        # 深色断言
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        print("body bg:", bg, "->", "PASS" if bg in ("rgb(11, 18, 32)", "rgb(11, 18, 32)") else "CHECK")
        side = page.evaluate("getComputedStyle(document.querySelector('.side')).backgroundColor")
        print("side bg:", side)
        proj = page.evaluate("getComputedStyle(document.querySelector('.projbar')).backgroundColor")
        print("projbar bg:", proj)
        # 空状态后输入消息，验证气泡深色
        page.fill("#input", "我想做一个社区图书馆，功能有阅览区、儿童区、活动室。")
        page.press("#input", "Enter")
        deadline = time.time() + 120
        while time.time() < deadline:
            if page.locator(".typing").count() == 0 and page.locator("#messages .message").count() >= 2:
                break
            import time as _t
            _t.sleep(1)
        import time as _t2
        _t2.sleep(0.5)
        ab = page.evaluate("getComputedStyle(document.querySelector('.assistant .bubble')).backgroundColor")
        print("assistant bubble bg:", ab)
        at = page.evaluate("getComputedStyle(document.querySelector('.assistant .bubble')).color")
        print("assistant bubble text:", at)
        ub = page.evaluate("getComputedStyle(document.querySelector('.user .bubble')).backgroundColor")
        print("user bubble bg:", ub)
        ut = page.evaluate("getComputedStyle(document.querySelector('.user .bubble')).color")
        print("user bubble text:", ut)
        # 网格背景
        msgs = page.evaluate("getComputedStyle(document.querySelector('.messages')).backgroundImage")
        print("messages has grid:", "repeating-linear-gradient" in msgs)
        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_3_dark_chat.png", full_page=True)
        print("screenshots saved")
        browser.close()


if __name__ == "__main__":
    import time
    main()
