#!/usr/bin/env python3
"""Extract reusable title/content mechanisms from an engagement snapshot.

This is deliberately a feature extractor, not a trend detector. It preserves
the original title and emits evidence-backed fields that a later language
model or human can use to write candidate directions. It never infers
interaction or publication times.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


ANGLE_RULES: list[tuple[str, str, str]] = [
    ("risk_warning", r"警告|别踩|千万别|避坑|小心", "风险警告/避坑"),
    ("contrarian_reframe", r"不是.{0,16}(而是|就是)|不要.{0,16}(要|是)|最重要的不是", "否定常识后重定义"),
    ("question_solution", r"[？?].{0,16}(试试|方法|五步|三步|怎么办|如何)", "失败场景提问后给解法"),
    ("result_time", r"\d+(?:小时|天|分钟|h|H).{0,20}(满|拉|涨|做到|完成|人|群)", "明确结果+时间承诺"),
    ("numbered_template", r"\d+\s*(?:大|个|句|种|步|期|条|张|套)|直接套|全流程|日历表", "数字清单/模板可复制"),
    ("identity_authority", r"我做.{0,8}\d+年|甲方|操盘手|班主任|爸爸带娃|创始人|女工", "身份/经验背书"),
    ("local_benefit", r"贵阳|重庆|上海|西安|同城|周边|家门口|门票|几十块|不收", "地点+成本/适用性利益"),
    ("scenario_experience", r"当你|第一次|陪朋友|平时想|吃完|看完|等了|终于|现场|日常", "具体场景叙事"),
    ("emotion_curiosity", r"竟然|原来|最后|秘密|不信你看|怎么办|太|哇塞|！|…", "情绪或悬念驱动"),
]

AUDIENCE_RULES: list[tuple[str, str]] = [
    ("门店/商家", r"门店|水果店|超市|农庄|烧烤|美食店"),
    ("社群/私域运营者", r"社群|私域|裂变|引流|运营|群"),
    ("新手", r"新手|新人"),
    ("家长/带娃人群", r"宝宝|小朋友|孩子|带娃|遛娃|亲子|女儿|母婴"),
    ("本地休闲人群", r"同城|周边游|玩水|露营|野炊|烧烤|农家乐"),
    ("职场/组织角色", r"甲方|班主任|老板|职场"),
]

CONFLICT_RULES: list[tuple[str, str]] = [
    ("失败/停滞", r"死群|废了|没人|不变|下滑|不见了|没位置"),
    ("风险/损失", r"坑|别踩|最贵|恶意|伤透|生气|谨慎"),
    ("成本/门槛", r"不收门票|免费|几十块|低成本|不爆肝|不用"),
    ("认知反差", r"不是|而是|鄙视链|最重要|竟然|原来|相反"),
]

PROMISE_RULES: list[tuple[str, str]] = [
    ("增长/规模", r"\d+\s*(?:人|万)|拉满|涨到|增长|裂变|引流|上热门"),
    ("可执行解法", r"方法|玩法|步骤|五步|三步|教程|SOP|表格|日历|案例|直接套|秘诀"),
    ("省钱/低门槛", r"免费|不收门票|几十块|低成本|不爆肝|家门口"),
    ("情绪/体验", r"舒服|美好|快乐|治愈|搞笑|温馨|帅|震撼|感受"),
]

SETTING_RULES: list[tuple[str, str, str]] = [
    ("role_context", r"水果店|超市|甲方|班主任|爸爸带娃|新人|女友|闺蜜|朋友|老板|门店|店长", "角色/行业设定"),
    ("place_context", r"贵阳|重庆|上海|西安|同城|周边|家门口|景区|农庄|酒吧|KTV", "地点/现场设定"),
    ("time_context", r"暑假|夏天|凌晨|开学|全年|\d+天|\d+小时|\d+分钟|\d+h", "时间压力设定"),
]

WORDING_RULES: list[tuple[str, str, str]] = [
    ("imperative", r"别|试试|直接|抄|冲|赶紧|记住", "命令/行动催促"),
    ("question", r"[？?]", "问句"),
    ("warning", r"警告|谨慎|千万别|不信你看", "警告/风险提示"),
    ("contrast", r"不是.{0,16}(而是|就是)|关键是|相反|竟然|最重要的不是", "转折/反差"),
    ("colloquial", r"咋|哈|就|太|哇塞|别急|不行|干喝|馋了", "口语代入"),
    ("emotion_punctuation", r"[！!…🔥❗🚫]", "情绪标点"),
    ("identity_first_person", r"我|我们|做了|陪朋友|我在", "第一人称/身份"),
    ("number_time_price", r"\d|小时|天|分钟|免费|几十块|不收门票", "数字/时间/价格锚点"),
]

TEMPLATES = {
    "risk_warning": "血泪警告！[目标场景]的[数字]个坑千万别踩",
    "contrarian_reframe": "做[目标事情]最重要的不是[常见目标]，而是[被忽略的关键]",
    "question_solution": "[具体失败场景]？先别急着[惯性动作]，试试这[数字]步",
    "result_time": "[时间]做到[可验证结果]，真正关键的不是[表面动作]",
    "numbered_template": "给[具体角色]的[数字]个[场景]模板，直接套",
    "identity_authority": "做了[年限]年[具体工作]，我现在只保留这[数字]个动作",
    "local_benefit": "[地点/半径]的[目标人群]，这个地方关键是[利益点]",
    "scenario_experience": "当你遇到[具体场景]，真正尴尬/有效的是[反差结果]",
    "emotion_curiosity": "[结果/体验]竟然是这样，最后一个细节最关键",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Snapshot JSONL")
    parser.add_argument("--output", required=True, type=Path, help="Analysis JSONL")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_number}: expected JSON object")
            key = (str(row.get("platform", "")), str(row.get("list_type", "")), str(row.get("content_id", "")))
            if not all(key):
                raise ValueError(f"line {line_number}: platform/list_type/content_id are required")
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return rows


def matches(text: str, rules: Iterable[tuple[str, ...]]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for rule in rules:
        code, pattern = rule[:2]
        label = rule[2] if len(rule) > 2 else code
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            found.append({"code": code, "label": label, "evidence": match.group(0)})
    return found


def choose_angle(angles: list[dict[str, str]]) -> dict[str, str]:
    if not angles:
        return {"code": "unclassified", "label": "需人工判断", "evidence": ""}
    return angles[0]


def analyze_row(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("title") or "").strip()
    angles = matches(title, ANGLE_RULES)
    audiences = matches(title, AUDIENCE_RULES)
    conflicts = matches(title, CONFLICT_RULES)
    promises = matches(title, PROMISE_RULES)
    settings = matches(title, SETTING_RULES)
    wording = matches(title, WORDING_RULES)
    primary = choose_angle(angles)
    pattern = TEMPLATES.get(primary["code"], "[具体场景]+[冲突/利益]+[可执行承诺]")
    return {
        "platform": row.get("platform"),
        "list_type": row.get("list_type"),
        "content_id": row.get("content_id"),
        "title": row.get("title"),
        "content_url": row.get("content_url"),
        "coverage_status": row.get("coverage_status"),
        "analysis": {
            "primary_angle": primary,
            "angle_candidates": angles,
            "audience_signals": audiences,
            "conflict_signals": conflicts,
            "promise_signals": promises,
            "setting_signals": settings,
            "wording_devices": wording,
            "title_pattern_template": pattern,
            "needs_deep_read": not bool(title) or primary["code"] == "unclassified",
            "fact_boundary": "仅依据列表可见标题；正文、视频字幕和真实表现未验证",
        },
    }


def main() -> int:
    args = parse_args()
    analyzed = [analyze_row(row) for row in read_rows(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in analyzed:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"input": str(args.input), "output": str(args.output), "rows": len(analyzed)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
