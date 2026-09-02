# -*- coding: utf-8 -*-
"""诊断：真实对话中案例图是否真正加载成功（naturalWidth/complete/error）+ 截图。"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8000/demo/collaborator.html"


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
            time.sleep(0.8)

        send("我想做一个社区图书馆，功能有阅览区、儿童区、活动室。")
        send("光之教堂为什么用狭缝采光？")

        # 收集所有案例图加载状态
        info = page.evaluate("""()=>[...document.querySelectorAll('.case-imgs img')].map(img=>({
            src: img.getAttribute('src') ? img.getAttribute('src').split('/').slice(-3).join('/') : '(null)',
            complete: img.complete,
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight,
            hasFallback: img.classList.contains('img-fallback'),
            broken: img.complete && img.naturalWidth===0
        }))""")
        for i, it in enumerate(info, 1):
            flag = "BROKEN" if it["broken"] else "ok"
            print(f"{i:2d}. [{flag}] {it['src']}  complete={it['complete']} natural={it['naturalWidth']}x{it['naturalHeight']} fallback={it['hasFallback']}")
        broken = [it for it in info if it["broken"]]
        total = len(info)
        print(f"--- {total} 张图，broken {len(broken)} ---")

        # 抓网络失败的请求（更可靠：监听 requestfailed/response>=400）
        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\img_diag.png", full_page=True)

        # 重载页面并监听图片请求
        page2 = b.new_page(viewport={"width": 1500, "height": 900})
        failed = []
        bad_resp = []
        page2.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
        page2.on("response", lambda r: bad_resp.append((r.url, r.status)) if r.status >= 400 else None)
        page2.goto(URL, wait_until="networkidle")
        page2.evaluate("localStorage.clear()")
        page2.reload(wait_until="networkidle")
        page2.fill("#input", "光之教堂为什么用狭缝采光？")
        page2.press("#input", "Enter")
        dl = time.time() + 150
        while time.time() < dl:
            if page2.locator(".typing").count() == 0:
                break
            time.sleep(1)
        time.sleep(0.8)
        print("--- requestfailed ---")
        for u, f in failed[:10]:
            print("FAIL:", u, f)
        print("--- response >= 400 ---")
        for u, s in bad_resp[:10]:
            print(f"{s}:", u)
        print("failed 总数:", len(failed), "| 4xx/5xx 总数:", len(bad_resp))
        b.close()


if __name__ == "__main__":
    main()
