from pathlib import Path
from datetime import datetime
import json
import re
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
paths = [
    fw / "Src/app.c",
    fw / "Src/finder_kws.c",
    fw / "Inc/finder_kws_compare.h",
]
app, kws, control = [
    p.read_text(encoding="utf-8") for p in paths
]
marker = "FINDER_KWS_COLLECT_V1"
plan_path = root / "kws/live_collection_plan.json"

if any(marker in s for s in (app, kws, control)):
    raise SystemExit("收集模式已加入；請接著編譯，不要重複修改。")

if "FINDER_VOICE_TRACE_V1" not in app:
    raise SystemExit("找不到目前的詳細紀錄版本，尚未修改。")

plan = []
unknown = iter([
    "hello", "music", "window", "seven", "hello", "window"
])

for split, rounds in (("train", 8), ("holdout", 4)):
    for r in range(rounds):
        words = ["cup", "bottle", "phone"]
        words = words[r % 3:] + words[:r % 3]
        extra = "silence" if r % 2 == 0 else "unknown"

        for label in words + [extra]:
            plan.append({
                "index": len(plan),
                "split": split,
                "label": label,
                "say": next(unknown) if label == "unknown" else label,
            })

assert len(plan) == 48

def replace_one(text, pattern, replacement):
    matches = list(re.finditer(pattern, text, re.M | re.S))
    if len(matches) != 1:
        raise SystemExit(
            "找不到唯一的修改位置，尚未寫入：" + pattern
        )
    m = matches[0]
    return text[:m.start()] + replacement + text[m.end():]

control = replace_one(
    control,
    r"^#define[ \t]+FINDER_KWS_LIVE_CAPTURE[ \t]+0[ \t]*$",
    "#define FINDER_KWS_LIVE_CAPTURE 1\n"
    "/* FINDER_KWS_COLLECT_V1 */\n"
    "#define FINDER_KWS_LIVE_CASES 48U",
)

if not re.search(
    r"^#define\s+FINDER_KWS_COMPARE_ENABLED\s+0\s*$",
    control, re.M
):
    raise SystemExit("固定資料比對尚未關閉，尚未寫入。")

match = re.search(
    r"(?ms)^static void finder_voice_poll\(void\)\s*\{.*?^\}",
    app,
)
if not match:
    raise SystemExit("找不到語音工作函式，尚未寫入。")

body = replace_one(
    match[0],
    r"^[ \t]*if\s*\(ret\s*<\s*0\)\s*goto voice_error;",
    "  if (ret < 0) goto voice_error;\n"
    "  /* FINDER_KWS_COLLECT_V1 */\n"
    "#if FINDER_KWS_LIVE_CAPTURE\n"
    "  finder_kws_result_t captured;\n"
    "  ret = finder_kws_classify(voice_pcm, &captured);\n"
    "  if (ret != 0) goto voice_error;\n"
    "  finder_kws_live_capture(voice_pcm, &captured);\n"
    "  return;\n"
    "#endif",
)
app = app[:match.start()] + body + app[match.end():]

kws, count = re.subn(
    r"\blive_stage(\s*(?:>=|==|<|=)\s*)4U\b",
    r"live_stage\g<1>FINDER_KWS_LIVE_CASES",
    kws,
)
if count != 4:
    raise SystemExit("原有四段收集流程與預期不同，尚未寫入。")

kws = replace_one(
    kws,
    r"^static const char \*const live_labels\[\]\s*=\s*\{.*?\};",
    "static const char *const live_labels[] = {\n  "
    + ",\n  ".join(
        ", ".join(json.dumps(p["label"]) for p in plan[i:i+4])
        for i in range(0, len(plan), 4)
    )
    + "\n};",
)

# 所有類別均按音訊能量取窗，不以模型預測篩選樣本。
kws = replace_one(
    kws,
    r"if \(!selected \|\| \(live_stage == 0U \? "
    r"command > best_command\s*: energy > best_energy\)\)",
    "if (!selected || energy > best_energy)",
)

for pattern in (
    r"^[ \t]*static float best_command;[^\n]*\n",
    r"^[ \t]*best_command = -1\.0f;[^\n]*\n",
    r"^[ \t]*float command = fmaxf\(.*?;[^\n]*\n",
    r"^[ \t]*best_command = command;[^\n]*\n",
):
    kws = replace_one(kws, pattern, "")

kws = kws.replace(
    "/* 靜音：保留最像命令的片段；說話：保留音訊能量最大的片段。 */",
    "/* FINDER_KWS_COLLECT_V1: 按音訊能量選窗。 */",
)

backup = root / "backups" / datetime.now().strftime(
    "before_collection_%Y%m%d_%H%M%S_%f"
)

for path in paths + ([plan_path] if plan_path.exists() else []):
    dest = backup / path.relative_to(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)

for path, content in zip(paths, (app, kws, control)):
    path.write_text(content, encoding="utf-8")

plan_path.write_text(
    json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("已加入現場收集模式：32 段訓練、16 段保留測試。")
print("備份：", backup)
print("請接著編譯及燒錄。")
