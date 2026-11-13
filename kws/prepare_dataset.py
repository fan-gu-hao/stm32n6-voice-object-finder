from pathlib import Path
from datetime import datetime
from collections import Counter
import json
import wave
import numpy as np

ROOT = Path(__file__).resolve().parent
LABELS = ["cup", "bottle", "phone", "unknown", "silence"]

RATE = 16000
LENGTH = 16000
FRAME = 320
HOP = 160


def read_wav(path):
    with wave.open(str(path), "rb") as f:
        actual = (
            f.getnchannels(),
            f.getsampwidth(),
            f.getframerate(),
            f.getcomptype(),
        )
        if actual != (1, 2, RATE, "NONE"):
            raise ValueError("需要 16000 Hz、單聲道、16 位元 PCM")

        if f.getnframes() != 80000:
            seconds = f.getnframes() / RATE
            raise ValueError(f"預期五秒，實際 {seconds:.2f} 秒")

        samples = np.frombuffer(
            f.readframes(f.getnframes()), dtype="<i2"
        ).copy()

    if len(samples) != 80000:
        raise ValueError("音訊資料不完整")

    return samples


def speech_regions(samples):
    # 使用短時間能量估計發音位置。
    x = samples.astype(np.float32) / 32768.0
    x -= x.mean()

    frames = np.lib.stride_tricks.sliding_window_view(
        x, FRAME
    )[::HOP]

    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    rms = np.convolve(rms, np.ones(3) / 3, mode="same")

    noise = float(np.percentile(rms, 20))
    loud = float(np.percentile(rms, 95))
    observed = set()

    # 合併單字內的短暫停頓，並嘗試幾個音量門檻。
    for gap in (10, 16, 22, 28):
        for ratio in (0.08, 0.12, 0.18, 0.25):
            threshold = max(noise * 3.0, loud * ratio, 0.0003)
            groups = []

            for index in np.flatnonzero(rms > threshold):
                index = int(index)

                if not groups or index - groups[-1][1] > gap:
                    groups.append([index, index + 1])
                else:
                    groups[-1][1] = index + 1

            regions = [
                (a * HOP, min(len(x), (b - 1) * HOP + FRAME))
                for a, b in groups
                if (b - a) * HOP >= 1280
            ]

            observed.add(len(regions))

            if len(regions) == 4 and all(
                b - a <= 15040 for a, b in regions
            ):
                return regions

    counts = "/".join(map(str, sorted(observed)))
    raise ValueError(
        f"無法可靠切出四次發音；候選段數 {counts}，"
        "或單字超過一秒"
    )


def extract_word(samples, regions, index):
    a, b = regions[index]

    # 相鄰單字之間取中點作為界線，避免切入下一個字。
    left = (
        0 if index == 0
        else (regions[index - 1][1] + a) // 2
    )
    right = (
        len(samples) if index + 1 == len(regions)
        else (b + regions[index + 1][0]) // 2
    )

    start = (a + b) // 2 - LENGTH // 2
    lo = max(start, left, 0)
    hi = min(start + LENGTH, right, len(samples))

    clip = np.zeros(LENGTH, dtype="<i2")
    clip[lo - start:hi - start] = samples[lo:hi]
    return clip


def write_wav(path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(samples.astype("<i2").tobytes())


def main():
    rng = np.random.default_rng(20261005)
    prepared = []
    failures = []
    counts = {}

    for label in LABELS:
        folder = ROOT / "data_raw" / label
        files = sorted(folder.glob("*.wav"))

        if len(files) < 3:
            raise SystemExit(
                f"{folder} 只有 {len(files)} 段，"
                "需要至少三段原始錄音"
            )

        # 先按原始錄音分組，再切成短片段。
        validation_count = max(1, round(len(files) * 0.25))
        validation_files = set(
            map(
                int,
                rng.permutation(len(files))[:validation_count],
            )
        )
        counts[label] = len(files)

        for file_index, path in enumerate(files):
            split = (
                "validation"
                if file_index in validation_files
                else "train"
            )

            try:
                samples = read_wav(path)

                if label == "silence":
                    spans = [
                        (i, i + LENGTH)
                        for i in range(0, len(samples), LENGTH)
                    ]
                    clips = [samples[a:b] for a, b in spans]
                else:
                    spans = speech_regions(samples)
                    clips = [
                        extract_word(samples, spans, i)
                        for i in range(4)
                    ]

                for index, (clip, span) in enumerate(
                    zip(clips, spans), 1
                ):
                    prepared.append(
                        (split, label, path, index, clip, span)
                    )

            except (ValueError, OSError, EOFError, wave.Error) as error:
                failures.append(f"{label}/{path.name}：{error}")

    if failures:
        print("以下錄音需要調整切段，這次尚未建立資料集：")
        for message in failures:
            print(message)

        raise SystemExit(
            "請貼上以上檔名與訊息，先處理這幾段即可。"
        )

    out = ROOT / "datasets" / datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    out.mkdir(parents=True, exist_ok=False)

    manifest = []

    for split, label, source, index, samples, span in prepared:
        rel = (
            Path(split) / label /
            f"{source.stem}_{index:02d}.wav"
        )
        write_wav(out / rel, samples)

        manifest.append({
            "file": str(rel),
            "label": label,
            "split": split,
            "source": str(source.relative_to(ROOT)),
            "speech_start_s": span[0] / RATE,
            "speech_end_s": span[1] / RATE,
        })

    (out / "manifest.json").write_text(
        json.dumps(
            {
                "sample_rate": RATE,
                "samples": LENGTH,
                "labels": LABELS,
                "clips": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    (ROOT / "dataset_current.txt").write_text(
        str(out) + "\n", encoding="utf-8"
    )

    totals = Counter(
        (item["split"], item["label"]) for item in manifest
    )

    print("\n類別       原始段數  訓練片段  驗證片段")
    for label in LABELS:
        train_count = totals["train", label]
        validation_count = totals["validation", label]
        print(
            f"{label:10s} {counts[label]:8d}"
            f" {train_count:9d} {validation_count:9d}"
        )

    print(f"\n資料集：{out}")
    print("切段清單：", out / "manifest.json")
    print("每段：一秒、16000 Hz、單聲道、16 位元")
    print("同一份五秒錄音的切片，全部分配到同一組。")


if __name__ == "__main__":
    main()
