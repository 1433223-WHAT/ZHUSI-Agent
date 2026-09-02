# -*- coding: utf-8 -*-
"""Architectural Foundation V0.1 验收：7 题（建筑制图与图纸阅读）+ 计算器。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI\项目设计\筑智AI_ArchAI\ArchAI_Builder")

from arch_utils import mm_to_m, m_to_mm, fmt_length, scale_rule_text, verify_seven
from architect_chat import _resolve_measurement

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


# 计算器单元
check("265000mm = 265m", mm_to_m(265000) == 265.0, f"{mm_to_m(265000)}")
check("26.5m = 26500mm", m_to_mm(26.5) == 26500.0, f"{m_to_mm(26.5)}")
check("6000mm = 6m", fmt_length(6000) == "6m", fmt_length(6000))

# 7 题验收
r1 = verify_seven("1:100是什么意思")
check("题1 1:100=比例尺+制图规则", "1:100" in r1 and "不因图纸比例尺" in r1, r1[:60])
r2 = verify_seven("6000是多少米")
check("题2 6000=6m", "6m" in r2, r2[:60])
r3 = verify_seven("标注尺寸需不需要乘100")
check("题3 不需乘比例", "不需要乘比例" in r3, r3[:60])
r4 = verify_seven("265000mm是多少米")
check("题4 265000=265m", "265m" in r4 and "26.5m" not in r4, r4[:60])
r5 = verify_seven("26.5m应该标多少mm")
check("题5 26.5m=26500mm", "26500mm" in r5, r5[:60])
r6 = verify_seven("哪个数字是总尺寸")
check("题6 总尺寸需绑定验证", "绑定验证" in r6 and "不得叫" in r6, r6[:60])
r7 = verify_seven("不确定对应对象时能不能叫总长")
check("题7 未绑定不叫总长", "总长" in r7 and "不得" in r7, r7[:60])

# 拦截器
check("拦截 265000mm换算", "265m" in _resolve_measurement("265000mm是多少米"), "")
check("拦截 无关句不触发", _resolve_measurement("帮我看看这个方案") == "", "")

fails = [r for r in results if not r[1]]
print("=" * 40, f"{len(results)} 项，失败 {len(fails)}")
raise SystemExit(1 if fails else 0)
