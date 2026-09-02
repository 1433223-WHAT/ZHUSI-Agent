# -*- coding: utf-8 -*-
"""V2 第一阶段验收：用户四步连续对话（光之教堂图片 → 有平面的吗 → 你从知识库里找 → 这张图里的光）。"""
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

        def last_assets():
            msgs = page.locator("#messages .message")
            return msgs.last.locator(".asset-item img").count()

        # 第 1 步：光之教堂图片 → 直接出视觉资产卡，不让上传
        send("光之教堂图片")
        t1 = last_text()
        check("步1 出资产卡", last_assets() == 8, f"{last_assets()} 张")
        check("步1 不让上传(无'上传')", "上传" not in t1, "")
        check("步1 资产来源标注", "筑思分析图" in t1 and "原始图纸" in t1, "")

        # 第 2 步：有平面的吗 → 继承光之教堂，筛平面类资产
        send("有平面的吗")
        t2 = last_text()
        a2 = last_assets()
        check("步2 继承筛选平面", a2 == 2, f"{a2} 张（期望 plan+plan_analysis）")

        # 第 3 步：你从知识库里找 → 对象仍光之教堂（不裸检索，知识卡含光之教堂，无误报 unsupported 光之教堂）
        send("你从知识库里找")
        t3 = last_text()
        kb_cards = page.locator("#messages .message").last.locator(".case-card .case-title").all_text_contents()
        check("步3 知识卡含光之教堂", any("光之教堂" in c for c in kb_cards), str(kb_cards))
        check("步3 无误报'提及光之教堂无依据'", "提及「光之教堂」" not in t3, "")

        # 第 4 步：这张图里的光是怎么处理的 → 上传分析不拦截，普通回答（文本知识可用）
        send("这张图里的光是怎么处理的")
        t4 = last_text()
        check("步4 正常回答(非'请上传')", "先上传" not in t4, t4[:60])

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_case_assets.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
