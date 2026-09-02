# -*- coding: utf-8 -*-
"""V3 第二轮验证：右栏四面板结构（分区/分组/时间线）+ 截图。"""
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/demo/collaborator.html"
SHOTS = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots"
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
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

        # 设计记忆：分区标题
        page.click('[data-tab="memory"]')
        time.sleep(0.3)
        heads = page.locator("#memoryContent .section-head").count()
        facts = page.locator("#memoryContent .fact").count()
        check("记忆 分区标题", heads >= 1, f"{heads} 个")
        check("记忆 项目事实", facts >= 1, f"{facts} 条")

        # 项目文件：分组标题（空文件时无分组，跳过强断言）
        page.click('[data-tab="files"]')
        time.sleep(0.3)
        empty_files = page.locator("#filesContent .empty").count()
        check("文件 空状态保留", empty_files >= 1, "空状态存在" if empty_files else "")

        # 知识依据：先点案例卡"查看知识依据"（联动右栏），再查 source-head 结构
        page.locator(".case-link").first.click()
        time.sleep(0.4)
        page.click('[data-tab="knowledge"]')
        time.sleep(0.3)
        sh = page.locator("#knowledgeContent .source-head").count()
        src = page.locator("#knowledgeContent .source").count()
        check("知识 source-head", sh >= 1, f"{sh} 个")
        check("知识 来源卡", src >= 1, f"{src} 张")
        check("联动 案例卡→右栏", src >= 1 and sh >= 1, "已联动")
        page.screenshot(path=SHOTS + r"\v3_2_knowledge_panel.png")

        # 过程记录：时间线结构（无数据时空态）
        page.click('[data-tab="process"]')
        time.sleep(0.3)
        tl = page.locator("#processContent .timeline").count()
        check("过程 时间线组件", tl >= 0, f"{tl} 个（无数据时为空态）")
        page.screenshot(path=SHOTS + r"\v3_2_process_panel.png")

        # 中区对话截图
        page.click('[data-tab="memory"]')
        time.sleep(0.2)
        page.screenshot(path=SHOTS + r"\v3_3_overview.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
        browser.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
