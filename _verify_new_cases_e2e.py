# -*- coding: utf-8 -*-
"""新案例对话级验证：问社区图书馆案例 → 能引用天津滨海新区图书馆；藤幼儿园图片 → 诚实"暂无视觉资料"。"""
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

        def send(q, ws=150):
            page.fill("#input", q)
            page.press("#input", "Enter")
            dl = time.time() + ws
            while time.time() < dl:
                if page.locator(".typing").count() == 0:
                    break
                time.sleep(1)
            time.sleep(0.6)

        # 1. 社区图书馆案例 → 知识卡应含天津滨海新区图书馆
        send("我想做一个社区图书馆，有什么案例可以参考")
        cards = page.locator("#messages .message").last.locator(".case-card .case-title").all_text_contents()
        all_text = page.locator("#messages .message").last.text_content()
        check("对话引用新案例 天津滨海", any("天津滨海" in c for c in cards), str(cards[:5]))

        # 2. 藤幼儿园图片 → 实体存在但无图 → 诚实"暂无视觉资料"（无图时提供上传选项是合理能力说明）
        send("藤幼儿园图片")
        t = page.locator("#messages .message").last.text_content()
        check("藤幼儿园无图→诚实提示", "没有视觉资料" in t, t[:60])

        # 3. 奥雷斯塔高中 教学楼中庭 → 能引用
        send("教学楼的中庭怎么组织比较好")
        t3 = page.locator("#messages .message").last.text_content()
        cards3 = page.locator("#messages .message").last.locator(".case-card .case-title").all_text_contents()
        check("教学楼中庭→引用奥雷斯塔", any("奥雷斯塔" in c for c in cards3), str(cards3[:5]))

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_new_cases.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 30, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
