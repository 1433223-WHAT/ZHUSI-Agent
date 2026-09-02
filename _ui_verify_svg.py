# -*- coding: utf-8 -*-
"""v2.1 打磨验证：SVG 图标渲染、打字动画、头像标识、reduced-motion 规则。"""
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/demo/collaborator.html"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")

        checks = page.evaluate("""(()=>{
          const r={};
          r.svgs = document.querySelectorAll('button svg').length;
          r.speakerDot = getComputedStyle(document.querySelector('.speaker'),'::before').backgroundColor;
          r.typingKeyframe = [...document.styleSheets].some(s=>{try{return [...s.cssRules].some(c=>c.name==='typing-pulse')}catch(e){return false}});
          r.reducedMotion = [...document.styleSheets].some(s=>{try{return [...s.cssRules].some(c=>c.type===CSSRule.MEDIA_RULE && c.conditionText.includes('prefers-reduced-motion'))}catch(e){return false}});
          r.attachSvg = document.querySelector('#attachBtn svg')!==null;
          r.sendSvg = document.querySelector('#sendBtn svg')!==null;
          return r;
        })()""")
        for k, v in checks.items():
            print(("PASS" if v not in (0, "", "rgba(0, 0, 0, 0)") else "FAIL"), "-", k, "=", v)

        # 项目列表删除按钮 SVG（renderProjects 模板）
        page.click("#projAdd")
        page.wait_for_timeout(300)
        del_svg = page.evaluate("document.querySelectorAll('.proj-del svg').length")
        print(("PASS" if del_svg >= 1 else "FAIL"), "- proj-del svg =", del_svg)

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_1_polish.png", full_page=True)
        print("screenshot saved: v2_1_polish.png")
        browser.close()


if __name__ == "__main__":
    main()
