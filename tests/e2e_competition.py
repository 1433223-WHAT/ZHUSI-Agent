import json
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:8000/demo/mentor.html"
SHOT = Path(__file__).resolve().parents[1] / "demo" / "competition-e2e.png"


def fulfill(route, payload):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload, ensure_ascii=False))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.route("**/api/discuss_assess", lambda route: fulfill(route, {
        "understanding_percent": 80, "is_sufficient": True,
        "filled_dimensions": [
            {"dim": "project_type", "label": "项目类型", "value": "乡村民宿", "status": "clear"},
            {"dim": "user", "label": "使用者", "value": "亲子家庭", "status": "clear"},
            {"dim": "site", "label": "场地", "value": "村口旧粮仓", "status": "clear"},
            {"dim": "goal", "label": "设计目标", "value": "亲近自然", "status": "clear"},
            {"dim": "constraint", "label": "限制条件", "value": "保留木架", "status": "clear"},
            {"dim": "design_intent", "label": "设计意图", "value": "", "status": "unknown"},
        ],
        "fact_states": {}, "changes": [], "conflicts": [], "progress_reason": "信息已足以生成方向。",
    }))
    page.route("**/api/discuss_ask", lambda route: fulfill(route, {"need_more": False}))
    page.route("**/api/propose_directions", lambda route: fulfill(route, {
        "core_conflict": "旧粮仓保护与亲子使用之间的平衡",
        "key_questions": ["如何保留木架？"], "knowledge_note": {"status": "verified", "message": "已核验"},
        "retrieved_cases": [{}], "retrieved_theories": [{}], "retrieved_methods": [{}],
        "directions": [{
            "name": "院落生活型", "core_strategy": "以院落组织亲子活动", "suitable_for": "乡村民宿", "risk": "注意冬季使用",
            "evidence_status": "verified", "cases": ["住吉的长屋"],
            "evidence": {
                "case": {"name": "住吉的长屋", "strategy": "内向院落", "source_text": "原建筑以中庭组织日常。", "why": "迁移院落关系", "fit": {"project_type": 80, "scale": 80, "function": 75, "site_climate": 65, "average": 75, "transferable": "院落关系", "not_copy": "露天交通", "risk": "气候适应"}},
                "theory": {"name": "场所精神", "source_text": "回应场地。", "why": "回应村庄"},
                "method": {"name": "框景借景", "source_text": "控制视域。", "why": "引入田野"},
            },
        }] * 3,
    }))
    page.route("**/api/design_loop", lambda route: fulfill(route, {
        "initial_proposal": "# 初稿\n<script>window.bad=1</script>院落方案",
        "revision": "# V1\n完整方案", "critic": {"score": 78, "strengths": [], "problems": [], "criteria": {}},
        "selected_direction": {"name": "院落生活型", "evidence": {"case": {"name": "住吉的长屋"}}},
        "version": {"number": 1, "direction": "院落生活型", "knowledge_evidence": {}},
    }))

    feedback_count = {"value": 1}
    def feedback_handler(route):
        feedback_count["value"] += 1
        number = feedback_count["value"]
        fulfill(route, {
            "revised_plan": f"# V{number}\n完整更新方案", "diff_summary": {"feedback_response": "已落实", "changes": [], "kept": ["院落"], "removed": []},
            "evidence_changes": {"kept": ["住吉的长屋"], "added": [], "invalidated": []},
            "version": {"number": number, "parent_version": number - 1, "direction": "院落生活型", "knowledge_evidence": {}},
        })
    page.route("**/api/feedback", feedback_handler)

    page.goto(BASE, wait_until="networkidle")
    page.fill("#msgInput", "乡村民宿完整需求")
    page.click("#sendBtn")
    page.get_by_text("确认理解，开始生成方向").click()
    page.get_by_text("确认方向，进入深化").click()
    page.wait_for_selector("text=优化方案 V1")
    assert page.evaluate("window.bad") is None

    for expected_version, feedback in ((2, "入口更开放"), (3, "增加雨天亲子空间")):
        page.fill("#msgInput", feedback)
        page.click("#sendBtn")
        page.wait_for_selector(f"text=方案更新 V{expected_version}")

    assert page.get_by_role("button", name="V1").count() == 1
    assert page.get_by_role("button", name="V2").count() == 1
    assert page.get_by_role("button", name="V3").count() == 1
    page.get_by_role("button", name="V1").click()
    assert page.locator("#version-1").is_visible()
    page.reload(wait_until="networkidle")
    assert page.get_by_role("button", name="V3").count() == 1
    assert page.get_by_title("导出设计过程").count() == 1
    assert page.get_by_title("载入比赛演示案例").count() == 1
    assert page.get_by_title("新建设计任务").count() == 1
    with page.expect_download() as download_info:
        page.get_by_title("导出设计过程").click()
    assert download_info.value.suggested_filename.endswith(".md")
    page.get_by_title("载入比赛演示案例").click()
    assert "乡村" in page.input_value("#msgInput")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.screenshot(path=str(SHOT), full_page=True)
    assert not errors, errors
    browser.close()

print(json.dumps({"status": "ok", "screenshot": str(SHOT)}, ensure_ascii=False))
