#!/usr/bin/env python3
"""計算真正的章節漢字數（不是檔案位元組）。

以 Python 內建程式庫執行，無需額外安裝。若任一章未達 8,000 漢字，
預設以非零退出碼結束。使用 --allow-drafts 允許初稿檢查通過並顯示警告。
"""
from pathlib import Path
import argparse
import json
import re
import sys

HAN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
CHAPTER = re.compile(r"^第(\d{3})章_.+\.md$")


def count_han(markdown: str) -> int:
    body = re.sub(r"^#\s+.*\n", "", markdown, count=1)
    return len(HAN.findall(body))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--minimum", type=int, default=8000)
    ap.add_argument("--allow-drafts", action="store_true")
    args = ap.parse_args()
    chapter_dir = args.root / "chapters"
    results = []
    for path in sorted(chapter_dir.glob("第*章_*.md")):
        match = CHAPTER.fullmatch(path.name)
        if not match:
            continue
        count = count_han(path.read_text(encoding="utf-8"))
        results.append({"chapter": int(match.group(1)), "file": path.name,
                        "han_characters": count,
                        "meets_minimum": count >= args.minimum,
                        "missing": max(0, args.minimum - count)})
    expected = list(range(1, 11))
    actual = [item["chapter"] for item in results]
    if actual != expected:
        print(f"ERROR: 預期第001～010章，實際章號 {actual}", file=sys.stderr)
        return 2
    passed = sum(x["meets_minimum"] for x in results)
    total = sum(x["han_characters"] for x in results)
    print("章節\t漢字數\t尚缺\t字數驗收")
    for x in results:
        print(f'{x["chapter"]:03}\t{x["han_characters"]}\t{x["missing"]}\t'
              f'{"通過" if x["meets_minimum"] else "未通過"}')
    print(f"合計：{total:,} / {len(results) * args.minimum:,} 漢字；達標 {passed}/{len(results)} 章")
    report_path = args.root / "planning" / "字數驗收.json"
    if report_path.parent.exists():
        report_path.write_text(json.dumps({"minimum": args.minimum, "total_han": total,
            "passing_chapters": passed, "total_chapters": len(results),
            "chapters": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if passed == len(results) or args.allow_drafts else 1


if __name__ == "__main__":
    raise SystemExit(main())
