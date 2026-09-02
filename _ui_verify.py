# -*- coding: utf-8 -*-
"""UI v2.0 打磨后程序化验证：断言关键 CSS 修复生效 + 主链路可用。"""
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/demo/collaborator.html"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        time.sleep(0.5)

        # A3: :root font-family
        fam = page.evaluate("getComputedStyle(document.documentElement).fontFamily")
        check("A3 :root 字体", "Segoe UI" in fam and "Times New Roman" not in fam, fam)

        # A1: version-foot 走 token（V3 暖色 --muted-2 = #9a9082）
        vf = page.evaluate("getComputedStyle(document.querySelector('.version-foot')).color")
        check("A1 版本脚注 token", vf == "rgb(154, 144, 130)", vf)

        # A4: 面板内 hint 左对齐（不再居中限宽）
        page.click('[data-tab="files"]')
        time.sleep(0.2)
        hint_align = page.evaluate("""(()=>{const h=document.querySelector('.panel .hint');return h?getComputedStyle(h).textAlign:null})()""")
        check("A4 面板 hint 左对齐", hint_align == "left", str(hint_align))
        page.click('[data-tab="memory"]')
        time.sleep(0.2)

        # B2: 键盘 Tab 到按钮出现 focus-visible 焦点环
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")  # 第二个可聚焦元素
        foc = page.evaluate("(()=>{const el=document.activeElement;return el?getComputedStyle(el).outlineStyle:'none'})()")
        check("B2 键盘焦点环", foc == "solid", foc + " on " + str(page.evaluate("document.activeElement?.className")))

        # 主链路冒烟：对话 → 知识检索 → 证据卡片
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

        msgs = page.locator("#messages .message").count()
        check("链路 对话消息渲染", msgs >= 4, f"{msgs} 条")
        ev = page.locator(".case-card").count()
        check("链路 案例图卡(杂志式)", ev >= 1, f"{ev} 张")
        case_title = page.locator(".case-title").first.text_content() if page.locator(".case-title").count() else ""
        check("链路 案例卡标题", len(case_title) > 0, case_title)
        case_link = page.locator(".case-link").count()
        check("链路 查看知识依据按钮", case_link >= 1, f"{case_link} 个")
        # 项目头部
        ph_name = page.evaluate("document.getElementById('projHeaderName')?.textContent || ''")
        check("头部 项目名显示", "图书馆" in ph_name or "未命名" in ph_name or len(ph_name) > 0, ph_name)
        ph_meta = page.evaluate("document.getElementById('projHeaderMeta') ? '' : document.querySelector('.ph-meta')?.textContent || ''")
        check("头部 阶段/日期/计数", "设计决定" in ph_meta, ph_meta)
        # 知识依据面板应显示 source 卡片
        page.click('[data-tab="knowledge"]')
        time.sleep(0.3)
        src = page.locator("#knowledgeContent .source").count()
        check("面板 知识依据有来源卡片", src >= 1, f"{src} 张")
        # 设计记忆面板应有已确认项目信息
        page.click('[data-tab="memory"]')
        time.sleep(0.3)
        mem = page.locator("#memoryContent .fact").count()
        check("面板 设计记忆有项目事实", mem >= 1, f"{mem} 条")

        page.screenshot(path=r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_polish_verify.png", full_page=True)

        fails = [r for r in results if not r[1]]
        print("=" * 40)
        print(f"总计 {len(results)} 项，失败 {len(fails)} 项")
        browser.close()
        raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
