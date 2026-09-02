# -*- coding: utf-8 -*-
"""UI 审计：提取当前 v2.0 的 token + 截图关键区域。"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots")
BASE.mkdir(parents=True, exist_ok=True)
URL = "http://127.0.0.1:8000/demo/collaborator.html"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        time.sleep(0.5)
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        time.sleep(0.5)

        # 1 初始页截图（空状态）
        page.screenshot(path=str(BASE / "audit_1_empty.png"), full_page=True)

        # 2 对话 + 知识卡片
        page.fill("#input", "我想做一个社区图书馆，功能有阅览区、儿童区、活动室。")
        page.press("#input", "Enter")
        deadline = time.time() + 120
        while time.time() < deadline:
            if page.locator(".typing").count() == 0 and page.locator("#messages .message").count() >= 2:
                break
            time.sleep(1)
        time.sleep(0.5)
        page.fill("#input", "光之教堂为什么用狭缝采光？")
        page.press("#input", "Enter")
        deadline = time.time() + 150
        while time.time() < deadline:
            if page.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.5)
        page.screenshot(path=str(BASE / "audit_2_chat_knowledge.png"), full_page=True)

        # 3 各面板截图
        for tab in ["memory", "files", "knowledge", "process"]:
            page.click(f'[data-tab="{tab}"]')
            time.sleep(0.3)
            page.locator(f"#{tab}Content").screenshot(path=str(BASE / f"audit_panel_{tab}.png"))

        # 4 提取当前 CSS token
        tokens = page.evaluate("""(()=>{
            const s=getComputedStyle(document.documentElement);
            return {
                teal: s.getPropertyValue('--teal').trim(),
                ink: s.getPropertyValue('--ink').trim(),
                muted: s.getPropertyValue('--muted').trim(),
                line: s.getPropertyValue('--line').trim(),
                work: s.getPropertyValue('--work').trim(),
                radius: s.getPropertyValue('--radius').trim(),
                radiusSm: s.getPropertyValue('--radius-sm').trim(),
                shadowSm: s.getPropertyValue('--shadow-sm').trim(),
                shadowMd: s.getPropertyValue('--shadow-md').trim(),
                fontFamily: s.fontFamily
            };
        })()""")
        print("当前 token:", json_dumps(tokens))

        # 5 检查主要元素
        checks = {}
        checks["assistant_bubble_bg"] = page.evaluate("getComputedStyle(document.querySelector('.assistant .bubble')).backgroundColor")
        checks["user_bubble_bg"] = page.evaluate("getComputedStyle(document.querySelector('.user .bubble')).backgroundColor")
        checks["send_bg"] = page.evaluate("getComputedStyle(document.querySelector('.send')).backgroundImage")
        checks["topbar_bg"] = page.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundImage")
        print("元素样式:", json_dumps(checks))
        browser.close()


def json_dumps(o):
    import json
    return json.dumps(o, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
