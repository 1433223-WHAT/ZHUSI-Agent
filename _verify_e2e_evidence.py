# -*- coding: utf-8 -*-
"""证据链路 E2E 验收：P0-1 分层 / P0-2 跳转定位 / 图片 / 来源分级（真实对话链路）。"""
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
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")

        def send(q, wait_s=150):
            page.fill("#input", q)
            page.press("#input", "Enter")
            deadline = time.time() + wait_s
            while time.time() < deadline:
                if page.locator(".typing").count() == 0:
                    break
                time.sleep(1)
            time.sleep(0.6)

        send("我想做一个社区图书馆，功能有阅览区、儿童区、活动室。")
        send("光之教堂为什么用狭缝采光？")

        # ① P0-1 A+：mentioned / retrieved 分组
        mentioned = page.locator(".message:not(.typing) .case-card").count()
        # 折叠区外的 case-card = mentioned 区（retrieved 折叠内也有 case-card）
        all_cards = page.locator(".case-card").count()
        fold = page.locator(".retrieved-fold").count()
        fold_summary = page.locator(".retrieved-fold summary").first.text_content() if fold else ""
        check("A+ 有提及依据卡", mentioned >= 1, f"{mentioned} 张")
        check("A+ 相关检索折叠存在", fold >= 1, fold_summary or "")
        check("A+ mentioned ⊆ 全部卡", mentioned <= all_cards, f"{mentioned}/{all_cards}")

        # ② P1-1 图片：无 fallback（后端给真实文件列表）
        fb = page.locator(".case-imgs img.img-fallback").count()
        check("图片 无 404 fallback", fb == 0, f"{fb} 张坏图")

        # ③ 来源分级：无"来源已核验"，有"来源可追溯"
        body_text = page.evaluate("document.body.innerText")
        check("分级 无「来源已核验」", "来源已核验" not in body_text, "")
        check("分级 有「来源可追溯」", "来源可追溯" in body_text, "")

        # ④ P0-2：点击 mentioned 区某案例卡 → 跳转定位
        first_link = page.locator(".message .case-link").first
        eid = first_link.get_attribute("data-eid")
        first_link.click()
        time.sleep(0.3)
        flashed = page.evaluate("""()=>{const el=document.querySelector('#knowledgeContent .source.source-flash');return !!el}""")
        check("跳转 高亮闪过", flashed, "")
        time.sleep(0.9)
        tab_active = page.evaluate("document.querySelector('[data-tab=\"knowledge\"]').classList.contains('active')")
        check("跳转 tab 切到知识依据", tab_active, "")
        target_rect = page.evaluate("""(eid)=>{const el=[...document.querySelectorAll('#knowledgeContent .source')].find(c=>c.dataset.eid===eid);if(!el)return null;const r=el.getBoundingClientRect();const s=document.querySelector('.side').getBoundingClientRect();return {top:r.top,bottom:r.bottom,sideTop:s.top,sideBottom:s.bottom}}""", eid)
        in_view = target_rect and target_rect["top"] >= target_rect["sideTop"] - 60 and target_rect["bottom"] <= target_rect["sideBottom"] + 60
        check("跳转 定位到对应 evidence_id", bool(target_rect) and in_view, str(target_rect))

        # ⑤ unsupported 提示（信息性：若回答提到库外/未命中专名）
        uns = page.locator(".unsupported-note").count()
        print("INFO - unsupported-note:", uns, "|", (page.locator(".unsupported-note").first.text_content() if uns else "无"))

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\evidence_fix_e2e.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
        browser.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
