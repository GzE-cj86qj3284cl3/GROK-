#!/usr/bin/env python3
"""計算真正的章節漢字數（不是檔案位元組）。

以 Python 內建程式庫執行，無需額外安裝。若任一章未達 8,000 漢字，
預設以非零退出碼結束。使用 --allow-drafts 允許初稿檢查通過並顯示警告。
支援 --volume 1|2|3|all（預設 all），並自動更新第一、二卷字數驗收 JSON。
"""
from pathlib import Path
import argparse
import json
import re
import sys

MIN_HAN_CHARS = 8000
HAN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
CHAPTER = re.compile(r"^第(\d{3})章_.+\.md$")


def count_han(markdown: str) -> int:
    lines = [line for line in markdown.splitlines() if not line.lstrip().startswith("#")]
    return len(HAN.findall("\n".join(lines)))


def volume_of(chapter_num: int) -> int:
    if 1 <= chapter_num <= 10:
        return 1
    if 11 <= chapter_num <= 20:
        return 2
    return 3


def expected_range(volume: str, present_nums: list[int]) -> list[int]:
    if volume == "1":
        return list(range(1, 11))
    if volume == "2":
        return list(range(11, 21))
    if volume == "3":
        v3 = [n for n in present_nums if n >= 21]
        if not v3:
            return [21]
        return list(range(21, max(v3) + 1))
    if not present_nums:
        return list(range(1, 11))
    return list(range(1, max(present_nums) + 1))


def write_vol1_report(root: Path, results: list[dict], minimum: int) -> None:
    report_path = root / "planning" / "字數驗收.json"
    if not report_path.parent.exists():
        return
    existing = {}
    if report_path.exists():
        try:
            existing = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    payload = {
        "minimum": minimum,
        "total_han": sum(x["han_characters"] for x in results),
        "passing_chapters": sum(1 for x in results if x["meets_minimum"]),
        "total_chapters": len(results),
        "chapters": [
            {
                "chapter": x["chapter"],
                "file": x["file"],
                "han_characters": x["han_characters"],
                "meets_minimum": x["meets_minimum"],
                "missing": x["missing"],
            }
            for x in results
        ],
    }
    for k in ("editorial_note", "last_verified"):
        if k in existing:
            payload[k] = existing[k]
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_vol2_report(root: Path, results: list[dict], minimum: int) -> None:
    report_path = root / "planning" / "第二卷_字數驗收.json"
    if not report_path.parent.exists():
        return
    existing = {}
    if report_path.exists():
        try:
            existing = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    prev_status = {
        c.get("chapter"): c.get("status", "complete_draft")
        for c in existing.get("chapters", [])
        if isinstance(c, dict)
    }
    written_nums = {x["chapter"] for x in results}
    payload = {
        "volume": 2,
        "volume_title": existing.get("volume_title", "借名航線"),
        "minimum": minimum,
        "chapters_planned": 10,
        "chapters_written": len(results),
        "passing_chapters": sum(1 for x in results if x["meets_minimum"]),
        "total_han": sum(x["han_characters"] for x in results),
        "chapters": [
            {
                "chapter": x["chapter"],
                "file": x["file"],
                "han_characters": x["han_characters"],
                "meets_minimum": x["meets_minimum"],
                "status": prev_status.get(x["chapter"], "complete_draft"),
            }
            for x in results
        ],
        "pending_chapters": [n for n in range(11, 21) if n not in written_nums],
        "count_method": "U+3400–U+4DBF, U+4E00–U+9FFF, U+F900–U+FAFF; exclude # heading lines",
    }
    for k in ("volume_status", "adult_scene_details_pending", "adult_scene_details_completed", "last_verification"):
        if k in existing:
            payload[k] = existing[k]
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--minimum", type=int, default=MIN_HAN_CHARS)
    ap.add_argument("--volume", choices=["1", "2", "3", "all"], default="all")
    ap.add_argument("--allow-drafts", action="store_true")
    args = ap.parse_args()

    chapter_dir = args.root / "chapters"
    all_results = []
    for path in sorted(chapter_dir.glob("第*章_*.md")):
        match = CHAPTER.fullmatch(path.name)
        if not match:
            continue
        chap_num = int(match.group(1))
        count = count_han(path.read_text(encoding="utf-8"))
        all_results.append({
            "chapter": chap_num,
            "volume": volume_of(chap_num),
            "file": path.name,
            "han_characters": count,
            "meets_minimum": count >= args.minimum,
            "missing": max(0, args.minimum - count),
        })

    if args.volume == "all":
        selected = all_results
    else:
        target_vol = int(args.volume)
        selected = [x for x in all_results if x["volume"] == target_vol]

    actual = [x["chapter"] for x in selected]
    expected = expected_range(args.volume, actual)
    if actual != expected:
        print(f"ERROR: 預期章號 {expected[0]:03}～{expected[-1]:03}，實際章號 {actual}", file=sys.stderr)
        return 2

    print("卷別\t章節\t漢字數\t尚缺\t字數驗收")
    for x in selected:
        print(
            f"V{x['volume']}\t{x['chapter']:03}\t{x['han_characters']}\t{x['missing']}\t"
            f"{'通過' if x['meets_minimum'] else '未通過'}"
        )

    print("--- 分卷彙總 ---")
    for v, label in ((1, "第一卷"), (2, "第二卷"), (3, "第三卷(021+)")):
        sub = [x for x in selected if x["volume"] == v]
        if not sub:
            continue
        v_pass = sum(1 for x in sub if x["meets_minimum"])
        v_tot = sum(x["han_characters"] for x in sub)
        print(f"{label}：{v_tot:,} 漢字；達標 {v_pass}/{len(sub)} 章")

    passed = sum(1 for x in selected if x["meets_minimum"])
    total = sum(x["han_characters"] for x in selected)
    print(f"總計：{total:,} / {len(selected) * args.minimum:,} 漢字；達標 {passed}/{len(selected)} 章")

    vol1_items = [x for x in selected if x["volume"] == 1]
    vol2_items = [x for x in selected if x["volume"] == 2]
    if vol1_items:
        write_vol1_report(args.root, vol1_items, args.minimum)
    if vol2_items:
        write_vol2_report(args.root, vol2_items, args.minimum)

    return 0 if passed == len(selected) or args.allow_drafts else 1


if __name__ == "__main__":
    raise SystemExit(main())
