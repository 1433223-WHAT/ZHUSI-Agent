# -*- coding: utf-8 -*-
"""验证 lightbox：点击案例图 → 大图显示 → 三种方式关闭。"""
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

        img = page.locator(".message .case-imgs img").first
        src = img.get_attribute("src")
        img.click()
        time.sleep(0.5)

        lb_hidden = page.evaluate("document.getElementById('lightbox').hidden")
        check("点击图片→lightbox 打开", not lb_hidden, "")
        lb_src = page.evaluate("document.getElementById('lightboxImg').getAttribute('src')")
        check("大图 src 匹配", lb_src == src, "/".join(lb_src.split("/")[-2:]) if lb_src else "")
        nw = page.evaluate("document.getElementById('lightboxImg').naturalWidth")
        check("大图真实加载", nw > 0, f"{nw}px")

        # 关闭方式 1：点击遮罩
        page.mouse.click(30, 450)
        time.sleep(0.3)
        check("点遮罩关闭", page.evaluate("document.getElementById('lightbox').hidden"), "")

        # 关闭方式 2：ESC
        img.click()
        time.sleep(0.3)
        page.keyboard.press("Escape")
        time.sleep(0.3)
        check("ESC 关闭", page.evaluate("document.getElementById('lightbox').hidden"), "")

        # 关闭方式 3：关闭按钮
        img.click()
        time.sleep(0.3)
        page.click(".lightbox-close")
        time.sleep(0.3)
        check("关闭按钮关闭", page.evaluate("document.getElementById('lightbox').hidden"), "")

        # 知识依据按钮仍可用（点击图改为大图后，追溯走按钮）
        link = page.locator(".message .case-link").first
        link.click()
        time.sleep(0.4)
        tab = page.evaluate("document.querySelector('[data-tab=knowledge]').classList.contains('active')")
        check("知识依据按钮仍可用", tab, "")

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\lightbox_fix.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 30, f"{len(results)} 项，失败 {len(fails)}")
        b.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
