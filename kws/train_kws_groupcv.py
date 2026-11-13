from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import json
import shutil
import wave

# 沿用已完成板上比對的特徵、資料增強及網路架構。
import train_kws as B
import numpy as np
import sklearn
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parent
LABELS = B.LABELS
SEED = 20261008
FOLDS = 5
MAX_EPOCHS = 300
WARMUP = 80
PATIENCE = 50

# 每段原音檔另外建立的增強版本數；原音檔另保留一份。
AUG = np.array([24, 72, 24, 24, 120])

# 五類在訓練損失中的目標相對比重。
PRIORITY = np.array([1.0, 1.5, 1.0, 1.0, 1.5])


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def pcm_sha(path):
    with wave.open(str(path), "rb") as wav:
        return hashlib.sha256(wav.readframes(wav.getnframes())).hexdigest()


def load_development():
    dataset = Path((ROOT / "dataset_current.txt").read_text().strip())
    manifest = json.loads((dataset / "manifest.json").read_text())
    if manifest["labels"] != LABELS:
        raise ValueError("原始資料集類別順序不符。")

    rows = []
    for r in manifest["clips"]:
        if r["split"] in ("train", "validation"):
            rows.append({
                "file": str((dataset / r["file"]).resolve()),
                "label": r["label"],
                "group": "original:" + r["source"],
            })

    earlier = ROOT / "live_comparison/20261007_201024_942174"
    for label in ("cup", "bottle", "phone", "silence"):
        path = earlier / (label + ".wav")
        rows.append({
            "file": str(path), "label": label, "group": str(path)
        })

    collection = ROOT / "live_datasets/20261008_005213_207370"
    live = json.loads((collection / "manifest.json").read_text())
    expected = Counter({
        ("train", label): n
        for label, n in zip(LABELS, (8, 8, 8, 4, 4))
    })
    expected.update({
        ("holdout", label): n
        for label, n in zip(LABELS, (4, 4, 4, 2, 2))
    })
    if (
        live.get("complete") is not True
        or Counter(
            (r["split"], r["label"]) for r in live["clips"]
        ) != expected
    ):
        raise ValueError("現場收集分組數量不符。")

    if len({r["file"] for r in live["clips"]}) != 48:
        raise ValueError("現場清單重複引用檔案。")

    holdout = []
    for r in live["clips"]:
        path = collection / r["file"]
        item = {
            "file": str(path), "label": r["label"],
            "group": str(path), "pcm_sha256": r["pcm_sha256"]
        }
        (rows if r["split"] == "train" else holdout).append(item)

    reserved = {r["pcm_sha256"] for r in holdout}
    waves = []
    for row in rows:
        waves.append(B.read_wav(row["file"]))
        digest = pcm_sha(row["file"])
        if row.get("pcm_sha256", digest) != digest:
            raise ValueError("錄音雜湊不符：" + row["file"])
        if digest in reserved:
            raise ValueError("開發資料與保留測試重複：" + row["file"])
        row["pcm_sha256"] = digest

    # 若不同來源名稱實際包含相同 PCM，也合併為同一組。
    parent = {r["group"]: r["group"] for r in rows}

    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    seen = {}
    for row in rows:
        digest = row["pcm_sha256"]
        if digest in seen:
            previous = seen[digest]
            if previous["label"] != row["label"]:
                raise ValueError("相同音訊被標成不同類別。")
            parent[find(row["group"])] = find(previous["group"])
        seen[digest] = row

    for row in rows:
        row["group"] = find(row["group"])

    y = np.array(
        [LABELS.index(r["label"]) for r in rows], dtype="int32"
    )
    groups = np.array([r["group"] for r in rows])
    return dataset, rows, np.stack(waves), y, groups, holdout


def make_splits(y, groups):
    for i, label in enumerate(LABELS):
        n = len(set(groups[y == i]))
        print(
            f"{label:7}：片段 {int((y == i).sum())}；"
            f"原始錄音組 {n}"
        )
        if n < FOLDS:
            raise ValueError(
                f"{label} 不足 {FOLDS} 組獨立錄音，請貼回此訊息。"
            )

    # 只按類別與組別找可行分組，不用模型分數挑分組。
    for seed in range(SEED, SEED + 32):
        splitter = StratifiedGroupKFold(
            FOLDS, shuffle=True, random_state=seed
        )
        splits = list(
            splitter.split(np.zeros(len(y)), y, groups)
        )
        if all(
            np.all(np.bincount(y[v], minlength=5) > 0)
            and np.all(np.bincount(y[t], minlength=5) > 0)
            for t, v in splits
        ):
            break
    else:
        raise ValueError("五折無法讓每折都包含五類，請貼回組數。")

    coverage = np.zeros(len(y), dtype=int)
    for t, v in splits:
        if set(groups[t]) & set(groups[v]):
            raise ValueError("同一原始錄音跨入訓練與驗證。")
        coverage[v] += 1

    if not np.all(coverage == 1):
        raise ValueError("交叉驗證未完整覆蓋所有片段。")

    return splits, seed


def normalize(raw, mean, std):
    return np.clip(
        (raw - mean) / std, -6, 6
    )[..., None].astype("float32")


def make_training(indices, waves, y, raw, seed):
    rng = np.random.default_rng(seed)
    mean = raw[indices].mean(axis=(0, 1), keepdims=True)
    std = np.maximum(
        raw[indices].std(axis=(0, 1), keepdims=True), 1.0
    )

    # 背景噪音只能來自本折訓練組。
    noises = waves[indices[y[indices] == 4]]
    if not len(noises):
        raise ValueError("本折訓練資料沒有背景音訊。")

    size = int(np.sum(AUG[y[indices]] + 1))
    features = np.empty((size, 49, B.MFCC), dtype="float32")
    labels = np.empty(size, dtype="int32")
    pos = 0

    for i in indices:
        features[pos], labels[pos] = raw[i], y[i]
        pos += 1
        for _ in range(int(AUG[y[i]])):
            value = B.augment(
                waves[i], int(y[i]), noises, rng
            )
            features[pos], labels[pos] = B.features(value), y[i]
            pos += 1

    counts = np.bincount(labels, minlength=5)
    weights = PRIORITY / PRIORITY.sum() * size / counts
    print(
        "本次訓練增強後筆數：",
        dict(zip(LABELS, counts.tolist())),
        flush=True,
    )
    return (
        normalize(features, mean, std), labels, mean, std,
        {i: float(w) for i, w in enumerate(weights)},
    )


def learning_rate(epoch, current):
    if epoch < 50:
        return 1e-3
    if epoch < 100:
        return 3e-4
    if epoch < 180:
        return 1e-4
    return 3e-5


def fit_model(
    tf, folder, x, y, weights, seed,
    validation=None, epochs=MAX_EPOCHS
):
    # 每折從新模型開始，不沿用上一折的權重。
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)

    options = tf.data.Options()
    options.threading.private_threadpool_size = 2

    train = tf.data.Dataset.from_tensor_slices((x, y))
    train = (
        train.shuffle(len(y), seed=seed)
        .batch(32).with_options(options)
    )

    val = None
    if validation is not None:
        val = (
            tf.data.Dataset.from_tensor_slices(validation)
            .batch(32).with_options(options)
        )

    model = B.build_model(tf)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    callbacks = [
        tf.keras.callbacks.LearningRateScheduler(learning_rate),
        tf.keras.callbacks.CSVLogger(str(folder / "history.csv")),
        tf.keras.callbacks.TerminateOnNaN(),
    ]

    if val is not None:
        callbacks += [
            tf.keras.callbacks.ModelCheckpoint(
                str(folder / "kws.keras"),
                monitor="val_loss", save_best_only=True,
            ),
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=PATIENCE,
                start_from_epoch=WARMUP, verbose=1,
            ),
        ]

    history = model.fit(
        train, validation_data=val, epochs=epochs,
        class_weight=weights, callbacks=callbacks, verbose=2,
    )

    if not all(
        np.isfinite(v).all() for v in history.history.values()
    ):
        raise ValueError("訓練出現非有限數值。")

    best = epochs
    if val is not None:
        best = int(np.argmin(history.history["val_loss"]) + 1)
        model = tf.keras.models.load_model(
            folder / "kws.keras", compile=False
        )
    else:
        model.save(folder / "kws.keras")

    save_json(folder / "history.json", history.history)
    return model, best


def export_int8(
    tf, model, folder, x, y, mean, std, config, seed
):
    np.savez(
        folder / "frontend.npz",
        window=B.WINDOW, mel=B.MEL_BANK, dct=B.DCT_BANK,
        mean=mean.reshape(-1), std=std.reshape(-1),
    )

    archive = tf.keras.export.ExportArchive()
    archive.track(model)
    archive.add_endpoint(
        "serve",
        fn=lambda value: model(value, training=False),
        input_signature=[
            tf.TensorSpec([1, 49, B.MFCC, 1], tf.float32)
        ],
    )
    archive.write_out(
        str(folder / "saved_model"), verbose=False
    )

    # 量化校正也只能使用本次訓練資料。
    rng = np.random.default_rng(seed)
    calibration = np.concatenate([
        rng.choice(
            np.flatnonzero(y == i),
            min(100, int((y == i).sum())),
            replace=False,
        )
        for i in range(5)
    ])

    def representative():
        for i in calibration:
            yield [x[i:i + 1]]

    converter = tf.lite.TFLiteConverter.from_saved_model(
        str(folder / "saved_model")
    )
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS_INT8
    ]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    path = folder / "kws_int8.tflite"
    path.write_bytes(converter.convert())

    interpreter = tf.lite.Interpreter(
        model_path=str(path), num_threads=2
    )
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    output = interpreter.get_output_details()[0]
    scale, zero = inp["quantization"]
    out_scale, out_zero = output["quantization"]

    if (
        inp["dtype"] != np.int8
        or output["dtype"] != np.int8
        or min(scale, out_scale) <= 0
    ):
        raise ValueError("INT8 輸入輸出格式不符。")

    save_json(
        folder / "config.json",
        dict(
            config,
            input_quantization={
                "scale": float(scale), "zero_point": int(zero)
            },
            output_quantization={
                "scale": float(out_scale),
                "zero_point": int(out_zero),
            },
            tensorflow=tf.__version__, seed=seed,
        ),
    )

    def predict(values):
        scores = []
        for value in values:
            q = np.clip(
                np.rint(value[None] / scale) + zero, -128, 127
            ).astype("int8")
            interpreter.set_tensor(inp["index"], q)
            interpreter.invoke()
            result = interpreter.get_tensor(
                output["index"]
            )[0].astype("float32")
            scores.append((result - out_zero) * out_scale)
        return np.stack(scores)

    return predict


def metrics(title, y, scores):
    if not np.isfinite(scores).all():
        raise ValueError("推論分數包含非有限數值。")

    pred = scores.argmax(axis=1)
    result = B.show_result(title, y, pred)
    matrix = np.array(result["confusion_matrix"])
    recall = np.diag(matrix) / np.maximum(matrix.sum(axis=1), 1)
    precision = np.diag(matrix) / np.maximum(matrix.sum(axis=0), 1)
    f1 = (
        2 * precision * recall
        / np.maximum(precision + recall, 1e-12)
    )

    ordered = np.sort(scores, axis=1)
    gap = ordered[:, -1] - ordered[:, -2]
    gate = (
        (pred < 3)
        & (scores.max(axis=1) >= 0.90)
        & (gap >= 0.25)
    )
    command = y < 3

    result.update(
        macro_f1=float(f1.mean()),
        recall=dict(zip(LABELS, recall.tolist())),
        command_pass=int(np.sum(command & (pred == y) & gate)),
        commands=int(command.sum()),
        false_pass=int(np.sum((~command) & gate)),
        noncommands=int((~command).sum()),
    )

    print(
        "各類召回率：",
        "；".join(f"{s}={r:.1%}" for s, r in zip(LABELS, recall)),
    )
    print(
        f"宏平均 F1={result['macro_f1']:.3f}；"
        f"命令答對且通過單窗分數="
        f"{result['command_pass']}/{result['commands']}；"
        f"非命令誤通過="
        f"{result['false_pass']}/{result['noncommands']}"
    )
    return result


def main():
    dataset, rows, waves, y, groups, holdout = load_development()
    splits, split_seed = make_splits(y, groups)

    print(
        f"開發資料 {len(rows)} 段；{FOLDS} 折；"
        f"另外保留 {len(holdout)} 段。"
    )

    out = ROOT / "runs" / datetime.now().strftime(
        "kws_groupcv_%Y%m%d_%H%M%S_%f"
    )
    out.mkdir(parents=True)
    print("本次輸出：", out, flush=True)

    shutil.copy2(__file__, out / "train_kws_groupcv.py")
    shutil.copy2(B.__file__, out / "train_kws.py")
    save_json(
        out / "splits.json",
        {
            "rows": rows, "holdout": holdout,
            "split_seed": split_seed,
            "folds": [
                {"train": t.tolist(), "validation": v.tolist()}
                for t, v in splits
            ],
        },
    )

    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)

    # 固定特徵可預先計算；平均值與標準差仍逐折計算。
    raw = np.stack([B.features(x) for x in waves])

    config = {
        "labels": LABELS,
        "sample_rate": B.RATE, "samples": B.SAMPLES,
        "frame_length": B.FRAME, "frame_step": B.HOP,
        "fft_length": B.FFT,
        "mel_bins": B.MELS, "mfcc_count": B.MFCC,
        "mel_scale": "HTK", "fmin": 20, "fmax": 7600,
        "window": "periodic_hann", "center": False,
        "power": 2, "log": "natural", "floor": 1e-10,
        "remove_clip_mean": True, "dct_norm": "ortho",
        "normalization_clip": [-6, 6],
        "input_shape": [1, 49, B.MFCC, 1],
        "dataset": str(dataset),
        "augmentation_version": "GROUP_CV_V1",
        "augmentation_extra": AUG.tolist(),
        "loss_priority": PRIORITY.tolist(),
        "max_epochs": MAX_EPOCHS,
        "warmup_epochs": WARMUP,
        "patience": PATIENCE,
        "split_manifest": str(out / "splits.json"),
        "scikit_learn": sklearn.__version__,
        "learning_rate_schedule": {
            "0": 0.001, "50": 0.0003,
            "100": 0.0001, "180": 0.00003,
        },
    }

    reports, best_epochs = [], []
    oof = np.zeros((len(y), 5), dtype="float32")

    for fold, (train, val) in enumerate(splits, 1):
        folder = out / f"fold_{fold}"
        folder.mkdir()
        seed = SEED + fold

        print(
            f"\n【第 {fold}/{FOLDS} 折】"
            f"訓練 {len(train)}；驗證 {len(val)}",
            flush=True,
        )

        x, ya, mean, std, weights = make_training(
            train, waves, y, raw, seed
        )
        xv = normalize(raw[val], mean, std)

        model, best = fit_model(
            tf, folder, x, ya, weights, seed, (xv, y[val])
        )
        predict = export_int8(
            tf, model, folder, x, ya, mean, std,
            dict(config, fold=fold, selected_epochs=best),
            seed,
        )

        scores = predict(xv)
        oof[val] = scores
        report = metrics(
            f"第 {fold} 折 INT8 驗證", y[val], scores
        )
        report.update(
            fold=fold, best_epoch=best,
            validation_indices=val.tolist(),
            scores=scores.tolist(),
        )
        save_json(folder / "report.json", report)

        reports.append(report)
        best_epochs.append(best)
        del predict, model, x, ya

    overall = metrics(
        "五折合併開發驗證（每段各驗證一次）", y, oof
    )
    accuracies = np.array([r["accuracy"] for r in reports])
    print(
        f"五折正確率平均={accuracies.mean():.2%}；"
        f"標準差={accuracies.std(ddof=1):.2%}"
    )

    final_epochs = int(np.median(best_epochs))
    save_json(
        out / "cv_report.json",
        {
            "folds": reports, "overall": overall,
            "accuracy_mean": float(accuracies.mean()),
            "accuracy_std": float(accuracies.std(ddof=1)),
            "best_epochs": best_epochs,
            "final_epochs": final_epochs,
            "note": "用於模型開發與選輪；非獨立測試集結果。",
        },
    )

    folder = out / "final"
    folder.mkdir()
    print(
        f"\n【最終重訓】全部 {len(y)} 段；"
        f"五折最佳輪數={best_epochs}；"
        f"採中位數 {final_epochs} 輪。"
    )

    x, ya, mean, std, weights = make_training(
        np.arange(len(y)), waves, y, raw, SEED + 100
    )
    model, _ = fit_model(
        tf, folder, x, ya, weights,
        SEED + 100, epochs=final_epochs
    )
    predict = export_int8(
        tf, model, folder, x, ya, mean, std,
        dict(
            config,
            final_epochs=final_epochs,
            cv_report=str(out / "cv_report.json"),
        ),
        SEED + 100,
    )

    # 五折與最終重訓都完成後，才讀取保留測試音訊。
    held_waves = []
    for row in holdout:
        if pcm_sha(row["file"]) != row["pcm_sha256"]:
            raise ValueError(
                "保留測試雜湊不符：" + row["file"]
            )
        held_waves.append(B.read_wav(row["file"]))

    xh = normalize(
        np.stack([B.features(x) for x in held_waves]),
        mean, std,
    )
    yh = np.array([LABELS.index(r["label"]) for r in holdout])
    fp = model(xh, training=False).numpy()
    scores = predict(xh)

    result = {
        "float32": metrics("保留測試：浮點模型", yh, fp),
        "int8": metrics("保留測試：INT8 模型", yh, scores),
        "files": holdout,
        "scores": scores.tolist(),
        "float32_scores": fp.tolist(),
    }

    for row, s in zip(holdout, scores):
        target = LABELS.index(row["label"])
        print(
            f"{Path(row['file']).name}：真實={row['label']}；"
            f"預測={LABELS[int(s.argmax())]}；"
            f"目標分數={s[target]:.1%}"
        )

    save_json(folder / "report.json", result)
    (ROOT / "model_candidate_current.txt").write_text(
        str(folder) + "\n"
    )

    print("\n五折最佳輪數：", best_epochs)
    print("最終重訓輪數：", final_epochs)
    print("完整輸出：", out)
    print("候選模型：", folder / "kws_int8.tflite")
    print("單窗分數結果尚未涵蓋板上的音量門檻與連續命中規則。")


if __name__ == "__main__":
    main()
