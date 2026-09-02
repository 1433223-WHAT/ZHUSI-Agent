# -*- coding: utf-8 -*-
"""case_transfer E2E：参考光之教堂设计教学楼 → 只出案例卡+开放式问，无六步越权。"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8000/demo/collaborator.html"
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

        def send(q, ws=120):
            page.fill("#input", q)
            page.press("#input", "Enter")
            dl = time.time() + ws
            while time.time() < dl:
                if page.locator(".typing").count() == 0:
                    break
                time.sleep(1)
            time.sleep(0.6)

        def last_text():
            msgs = page.locator("#messages .message")
            return msgs.last.text_content() if msgs.count() else ""

        # 第 1 轮：参考光之教堂设计教学楼
        send("我想参考光之教堂设计教学楼")
        t1 = last_text()
        assets = page.locator("#messages .message").last.locator(".asset-card").count()
        check("首轮 出案例资产卡", assets >= 1, f"{assets} 张")
        check("首轮 不定义唯一核心", "核心是" not in t1 and "精神性场所" not in t1, "")
        check("首轮 不判局部/整体", "局部" not in t1 and "而不是" not in t1, "")
        check("首轮 不给迁移路线", "画剖面" not in t1 and "列出" not in t1 and "3 个空间" not in t1, "")
        check("首轮 不造二元框架", "还是偏" not in t1 and "仪式感" not in t1, "")
        check("首轮 开放式问兴趣", "被哪一点吸引" in t1 or "从几个角度阅读" in t1, t1[:60])

        # 第 2 轮：表达兴趣
        send("我喜欢它那个光")
        t2 = last_text()
        check("二轮 确认兴趣", "光吸引" in t2, t2[:50])
        check("二轮 不进入迁移路线", all(w not in t2 for w in ["画剖面", "楼梯", "走廊", "光缝怎么做", "局部"]), "")

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\case_transfer_fix.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 30, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
