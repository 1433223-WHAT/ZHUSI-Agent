# -*- coding: utf-8 -*-
"""验证：点击案例图卡中的图片 → 打开知识依据 + 定位高亮。"""
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

        send("我想做一个社区图书馆，功能有阅览区、儿童区、活动室。")
        send("光之教堂为什么用狭缝采光？")

        imgs = page.locator(".message .case-imgs img")
        n = imgs.count()
        check("图片数量", n >= 1, f"{n} 张")
        cur = page.evaluate("getComputedStyle(document.querySelector('.case-imgs img')).cursor")
        check("图片 cursor=pointer", cur == "pointer", cur)

        first = imgs.first
        card = first.locator("xpath=ancestor::figure")
        eid = card.locator(".case-link").get_attribute("data-eid")
        first.click()
        time.sleep(0.4)
        flashed = page.evaluate("!!document.querySelector('#knowledgeContent .source.source-flash')")
        check("点击图片→高亮", flashed, "")
        tab = page.evaluate("document.querySelector('[data-tab=knowledge]').classList.contains('active')")
        check("点击图片→切tab", tab, "")
        rect = page.evaluate(
            """(eid)=>{const el=[...document.querySelectorAll('#knowledgeContent .source')].find(c=>c.dataset.eid===eid);
              if(!el)return null;const r=el.getBoundingClientRect(),s=document.querySelector('.side').getBoundingClientRect();
              return r.top>=s.top-60&&r.bottom<=s.bottom+60}""",
            eid,
        )
        check("点击图片→定位evidence_id", bool(rect), str(eid))
        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\img_click_fix.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 30, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
