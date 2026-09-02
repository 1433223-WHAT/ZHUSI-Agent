# -*- coding: utf-8 -*-
"""V3 第一轮截图：空状态（项目头部）+ 对话（杂志式案例图卡）。"""
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/demo/collaborator.html"
SHOTS = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        time.sleep(0.4)
        page.screenshot(path=SHOTS + r"\v3_1_empty.png", full_page=True)

        # 对话触发知识检索 → 案例图卡
        page.fill("#input", "我想做一个社区图书馆，功能有阅览区、儿童区、活动室。")
        page.press("#input", "Enter")
        deadline = time.time() + 120
        while time.time() < deadline:
            if page.locator(".typing").count() == 0 and page.locator("#messages .message").count() >= 2:
                break
            time.sleep(1)
        time.sleep(0.6)
        page.fill("#input", "光之教堂为什么用狭缝采光？")
        page.press("#input", "Enter")
        deadline = time.time() + 150
        while time.time() < deadline:
            if page.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.6)
        page.screenshot(path=SHOTS + r"\v3_2_case_cards.png", full_page=True)

        # 暖色断言
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        print("body bg:", bg)
        side = page.evaluate("getComputedStyle(document.querySelector('.side')).backgroundColor")
        print("side bg:", side)
        bubble = page.evaluate("getComputedStyle(document.querySelector('.assistant .bubble')).backgroundColor")
        print("assistant bubble:", bubble)
        mark = page.evaluate("getComputedStyle(document.querySelector('.mark')).display")
        print("mark (吉祥物) display:", mark, "->", "PASS(已移除)" if mark == "none" else "CHECK")
        clay = page.evaluate("getComputedStyle(document.querySelector('.send')).backgroundImage")
        print("send bg:", clay)
        case = page.locator(".case-card").count()
        print("case cards:", case)
        img = page.locator(".case-imgs img").count()
        print("case images:", img)
        ph = page.evaluate("document.getElementById('projHeaderName')?.textContent || ''")
        print("proj header name:", ph)
        print("screenshots saved")
        browser.close()


if __name__ == "__main__":
    main()
