# -*- coding: utf-8 -*-
"""v2.1 改动点标注截图：红色虚线框 + 数字角标，一眼看出改了哪里。"""
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/demo/collaborator.html"
OUT = r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder\demo\shots\v2_1_diff_guide.png"

HIGHLIGHT_JS = """(labels) => {
  const mk = (el, n, color) => {
    if (!el) return;
    el.style.outline = '2px dashed ' + color;
    el.style.outlineOffset = '3px';
    const b = document.createElement('span');
    b.textContent = n;
    b.style.cssText = 'position:absolute;top:-14px;left:-8px;z-index:9999;background:' + color + ';color:#fff;font:700 12px/1 sans-serif;padding:2px 6px;border-radius:6px;pointer-events:none';
    el.style.position = el.style.position === 'static' || !el.style.position ? 'relative' : el.style.position;
    el.appendChild(b);
  };
  // 1 顶栏导出/刷新 SVG 图标
  document.querySelectorAll('.icon-btn').forEach((el, i) => mk(el, i + 1, '#ef4444'));
  // 4 左下新建项目 + 图标
  mk(document.querySelector('#projAdd'), 4, '#ef4444');
  // 5 输入框 回形针/发送 SVG 图标
  mk(document.querySelector('#attachBtn'), 5, '#ef4444');
  mk(document.querySelector('#sendBtn'), 6, '#ef4444');
  // 2 消息说话人前的小圆点
  document.querySelectorAll('.speaker').forEach((el, i) => mk(el, 2, '#3b82f6'));
  // 3 版本脚注 v2.1
  mk(document.querySelector('.version-foot'), 3, '#f59e0b');
  return 'ok';
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        page.evaluate(HIGHLIGHT_JS)
        page.screenshot(path=OUT, full_page=True)
        print("saved:", OUT)
        browser.close()


if __name__ == "__main__":
    main()
