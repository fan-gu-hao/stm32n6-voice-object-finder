from pathlib import Path
from datetime import datetime
import os
import json
import shutil
import hashlib
import wave

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
from scipy.fft import rfft, dct

ROOT = Path(__file__).resolve().parent
LABELS = ["cup", "bottle", "phone", "unknown", "silence"]
RATE, SAMPLES = 16000, 16000
FRAME, HOP, FFT = 480, 320, 512
MELS, MFCC = 40, 13
SEED = 20261005

# 固定前處理：週期型漢寧窗、HTK 梅爾刻度、自然對數、正交 DCT。
WINDOW = (
    0.5 - 0.5 * np.cos(2 * np.pi * np.arange(FRAME) / FRAME)
).astype("float32")

mel_edges = np.linspace(
    2595 * np.log10(1 + 20 / 700),
    2595 * np.log10(1 + 7600 / 700),
    MELS + 2,
)
edges = 700 * (10 ** (mel_edges / 2595) - 1)
frequencies = np.fft.rfftfreq(FFT, 1 / RATE)[:, None]
left = (frequencies - edges[:-2]) / (edges[1:-1] - edges[:-2])
right = (edges[2:] - frequencies) / (edges[2:] - edges[1:-1])
MEL_BANK = np.maximum(0, np.minimum(left, right)).T.astype("float32")
DCT_BANK = dct(
    np.eye(MELS, dtype="float32"), type=2, norm="ortho", axis=0
)[:MFCC]


def read_wav(path):
    with wave.open(str(path), "rb") as f:
        actual = (
            f.getframerate(), f.getnchannels(), f.getsampwidth(),
            f.getnframes(), f.getcomptype(),
        )
        if actual != (RATE, 1, 2, SAMPLES, "NONE"):
            raise ValueError(f"音檔格式不符：{path}")
        return (
            np.frombuffer(f.readframes(SAMPLES), dtype="<i2")
            .astype("float32") / 32768
        )


def features(samples):
    x = np.asarray(samples, dtype="float32")
    x = x - x.mean()
    frames = np.lib.stride_tricks.sliding_window_view(x, FRAME)[::HOP]
    spectrum = rfft(frames * WINDOW, n=FFT, axis=1)
    power = spectrum.real ** 2 + spectrum.imag ** 2
    log_mel = np.log(np.maximum(power @ MEL_BANK.T, 1e-10))
    return (log_mel @ DCT_BANK.T).astype("float32")


# FINDER_KWS_LIVE_TRAIN_V2
def augment(samples, label, noises, rng):
    x = samples.copy()
    x -= x.mean()
    noise = np.roll(
        noises[int(rng.integers(len(noises)))],
        int(rng.integers(SAMPLES)),
    ).copy()
    noise -= noise.mean()

    if label == 4:
        # 安靜樣本混合不同訓練背景，並改變起點及音量。
        x = np.roll(x, int(rng.integers(SAMPLES)))
        mix = rng.uniform(0.25, 0.75)
        x = mix * x + (1 - mix) * noise
        gain_db = rng.uniform(-9, 9)
    else:
        # 估計發音區段，前後保留 100 ms，再限制平移範圍。
        level = np.sqrt(np.mean(x.reshape(-1, 160) ** 2, axis=1))
        threshold = max(float(np.percentile(level, 20)) * 2.5,
                        float(level.max()) * 0.10)
        active = np.flatnonzero(level > threshold)
        shift = 0
        if len(active):
            begin = max(0, int(active[0]) * 160 - 1600)
            end = min(SAMPLES, (int(active[-1]) + 1) * 160 + 1600)
            shift = int(rng.integers(
                max(-4000, -begin), min(4000, SAMPLES - end) + 1
            ))
        shifted = np.zeros_like(x)
        if shift > 0:
            shifted[shift:] = x[:-shift]
        elif shift < 0:
            shifted[:shift] = x[-shift:]
        else:
            shifted[:] = x
        x = shifted

        signal_rms = np.sqrt(np.mean(x ** 2) + 1e-12)
        noise_rms = np.sqrt(np.mean(noise ** 2) + 1e-12)
        snr = rng.uniform(8, 30)
        x += noise * (signal_rms / noise_rms) * 10 ** (-snr / 20)
        gain_db = rng.uniform(-9, 6)

    return np.clip(x * 10 ** (gain_db / 20), -1, 1).astype("float32")


def build_model(tf):
    L = tf.keras.layers
    inputs = L.Input(shape=(49, MFCC, 1), name="mfcc")

    x = L.Conv2D(
        32, (5, 3), strides=(2, 2), padding="same", use_bias=False
    )(inputs)
    x = L.BatchNormalization(momentum=0.9)(x)
    x = L.ReLU()(x)

    for _ in range(4):
        x = L.DepthwiseConv2D(3, padding="same", use_bias=False)(x)
        x = L.BatchNormalization(momentum=0.9)(x)
        x = L.ReLU()(x)
        x = L.Conv2D(32, 1, use_bias=False)(x)
        x = L.BatchNormalization(momentum=0.9)(x)
        x = L.ReLU()(x)

    x = L.GlobalAveragePooling2D()(x)
    x = L.Dropout(0.25)(x)
    outputs = L.Dense(
        len(LABELS), activation="softmax", name="scores"
    )(x)
    return tf.keras.Model(inputs, outputs, name="finder_kws")


def show_result(title, truth, prediction):
    matrix = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    np.add.at(matrix, (truth, prediction), 1)
    accuracy = float(np.mean(truth == prediction))

    print(
        f"\n{title}：{accuracy:.2%}"
        f"（{int(np.trace(matrix))}/{len(truth)}）"
    )
    print("混淆矩陣：列是真實類別，欄是模型預測。")
    print(" " * 10 + " ".join(f"{name:>8}" for name in LABELS))
    for name, row in zip(LABELS, matrix):
        print(f"{name:10}" + " ".join(f"{int(n):8d}" for n in row))

    return {
        "accuracy": accuracy,
        "confusion_matrix": matrix.tolist(),
    }


def main():
    import tensorflow as tf

    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.keras.utils.set_random_seed(SEED)
    rng = np.random.default_rng(SEED)

    dataset = Path((ROOT / "dataset_current.txt").read_text().strip())
    manifest = json.loads((dataset / "manifest.json").read_text())

    if manifest["labels"] != LABELS:
        raise ValueError("資料集類別順序不同，請貼上 manifest.json。")

    def load(split):
        rows = [r for r in manifest["clips"] if r["split"] == split]
        waves = np.stack([read_wav(dataset / r["file"]) for r in rows])
        labels = np.array(
            [LABELS.index(r["label"]) for r in rows], dtype="int32"
        )
        return waves, labels, rows

    train_wav, y_train, train_rows = load("train")
    val_wav, y_val, val_rows = load("validation")

    if {r["source"] for r in train_rows} & {r["source"] for r in val_rows}:
        raise ValueError("同一份原始錄音跨入訓練與驗證，請先修正資料集。")
    if np.any(np.bincount(y_train, minlength=5) == 0):
        raise ValueError("訓練資料缺少類別。")

    out = ROOT / "runs" / datetime.now().strftime(
        "kws_%Y%m%d_%H%M%S_%f"
    )
    out.mkdir(parents=True)

    print(f"TensorFlow：{tf.__version__}")
    print(f"本次輸出：{out}")
    print(f"原始訓練片段：{len(y_train)}；驗證片段：{len(y_val)}")

    # FINDER_KWS_COLLECTION_TRAIN_V3
    from collections import Counter

    collection = ROOT / "live_datasets/20261008_005213_207370"
    live_manifest = json.loads((collection / "manifest.json").read_text())
    expected = Counter({
        ("train", "cup"): 8, ("train", "bottle"): 8,
        ("train", "phone"): 8, ("train", "unknown"): 4,
        ("train", "silence"): 4,
        ("holdout", "cup"): 4, ("holdout", "bottle"): 4,
        ("holdout", "phone"): 4, ("holdout", "unknown"): 2,
        ("holdout", "silence"): 2,
    })
    rows = live_manifest["clips"]
    counts_live = Counter((r["split"], r["label"]) for r in rows)
    if live_manifest.get("complete") is not True or counts_live != expected:
        raise ValueError("現場資料尚未完成，或分組數量不符。")
    if len({r["file"] for r in rows}) != 48:
        raise ValueError("現場清單重複引用檔案。")

    new_train = [r for r in rows if r["split"] == "train"]
    holdout_rows = [r for r in rows if r["split"] == "holdout"]
    holdout_hashes = {r["pcm_sha256"] for r in holdout_rows}

    def pcm_sha(path):
        with wave.open(str(path), "rb") as wav:
            return hashlib.sha256(wav.readframes(wav.getnframes())).hexdigest()

    old_train_hashes = {pcm_sha(dataset / r["file"]) for r in train_rows}
    val_hashes = {pcm_sha(dataset / r["file"]) for r in val_rows}
    if old_train_hashes & val_hashes:
        raise ValueError("原始訓練與驗證包含完全相同的音訊。")
    if holdout_hashes & (old_train_hashes | val_hashes):
        raise ValueError("保留測試音訊已出現在原始訓練或驗證資料中。")

    earlier = ROOT / "live_comparison/20261007_201024_942174"
    items = [
        (label, earlier / (label + ".wav"), None)
        for label in ("cup", "bottle", "phone", "silence")
    ]
    items += [
        (r["label"], collection / r["file"], r["pcm_sha256"])
        for r in new_train
    ]

    live_names, waves, extra_training = [], [], []
    extra_dir = out / "extra_training"
    extra_dir.mkdir()
    for index, (label, path, expected_hash) in enumerate(items):
        pcm = read_wav(path)
        digest = pcm_sha(path)
        if expected_hash is not None and digest != expected_hash:
            raise ValueError(f"錄音雜湊不符：{path}")
        if digest in holdout_hashes or digest in val_hashes:
            raise ValueError(f"補訓音訊與驗證／保留測試重複：{path}")
        live_names.append(label)
        waves.append(pcm)
        saved = extra_dir / f"{index + 1:02d}_{label}.wav"
        shutil.copy2(path, saved)
        extra_training.append({
            "label": label, "source": str(path),
            "file": str(saved.relative_to(out)), "split": "train",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "pcm_sha256": digest,
        })

    live_wav = np.stack(waves)
    live_y = np.array([LABELS.index(s) for s in live_names], dtype="int32")
    train_wav = np.concatenate([train_wav, live_wav])
    y_train = np.concatenate([y_train, live_y])
    shutil.copy2(collection / "manifest.json", out / "live_manifest.json")
    print(f"加入先前現場 4 段＋本次 32 段；訓練共 {len(y_train)} 段；"
          f"驗證 {len(y_val)} 段；另保留 {len(holdout_rows)} 段測試。",
          flush=True)

    raw_train = np.stack([features(x) for x in train_wav])

    # 標準化參數只從原始訓練資料計算。
    mean = raw_train.mean(axis=(0, 1), keepdims=True)
    std = np.maximum(
        raw_train.std(axis=(0, 1), keepdims=True), 1.0
    )

    def normalize(x):
        return np.clip(
            (x - mean) / std, -6, 6
        )[..., None].astype("float32")

    x_val = normalize(np.stack([features(x) for x in val_wav]))
    noises = train_wav[y_train == 4]

    augmented = [raw_train]
    augmented_labels = [y_train]
    print("建立訓練資料增強；驗證資料維持原樣。", flush=True)

    for _ in range(11):
        augmented.append(np.stack([
            features(augment(x, y, noises, rng))
            for x, y in zip(train_wav, y_train)
        ]))
        augmented_labels.append(y_train)

    # 增加現場樣本的比重；這些變體仍只用於訓練。
    for _ in range(32):
        augmented.append(np.stack([
            features(augment(x, y, noises, rng))
            for x, y in zip(live_wav, live_y)
        ]))
        augmented_labels.append(live_y)

    x_train = normalize(np.concatenate(augmented))
    y_aug = np.concatenate(augmented_labels)

    # 之後移植 N6 時沿用這些前處理係數。
    np.savez(
        out / "frontend.npz",
        window=WINDOW, mel=MEL_BANK, dct=DCT_BANK,
        mean=mean.reshape(-1), std=std.reshape(-1),
    )

    config = {
        "labels": LABELS,
        "sample_rate": RATE,
        "samples": SAMPLES,
        "frame_length": FRAME,
        "frame_step": HOP,
        "fft_length": FFT,
        "mel_bins": MELS,
        "mfcc_count": MFCC,
        "mel_scale": "HTK",
        "fmin": 20,
        "fmax": 7600,
        "window": "periodic_hann",
        "center": False,
        "power": 2,
        "log": "natural",
        "floor": 1e-10,
        "remove_clip_mean": True,
        "dct_norm": "ortho",
        "normalization_clip": [-6, 6],
        "input_shape": [1, 49, MFCC, 1],
        "dataset": str(dataset),
        "seed": SEED,
        "tensorflow": tf.__version__,
        "augmentation_version": "FINDER_KWS_LIVE_TRAIN_V2",
        "extra_training": extra_training,
        "collection_training_version": "FINDER_KWS_COLLECTION_TRAIN_V3",
        "live_dataset": str(collection),
    }
    (out / "config.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )

    options = tf.data.Options()
    options.threading.private_threadpool_size = 2

    training = tf.data.Dataset.from_tensor_slices((x_train, y_aug))
    training = (
        training.shuffle(len(y_aug), seed=SEED)
        .batch(32).with_options(options)
    )

    validation = tf.data.Dataset.from_tensor_slices((x_val, y_val))
    validation = validation.batch(32).with_options(options)

    # 平衡五類資料數量不同造成的訓練影響。
    counts = np.bincount(y_aug, minlength=5)
    weights = {
        i: float(len(y_aug) / (5 * count))
        for i, count in enumerate(counts)
    }

    model = build_model(tf)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    print(
        f"模型參數：{model.count_params()}；"
        f"輸入形狀：{model.input_shape}"
    )

    history = model.fit(
        training,
        validation_data=validation,
        epochs=80,
        class_weight=weights,
        verbose=2,
        callbacks=[
            tf.keras.callbacks.ModelCheckpoint(
                str(out / "kws.keras"),
                monitor="val_loss",
                save_best_only=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5,
                patience=4, min_lr=1e-5,
            ),
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=12,
            ),
            tf.keras.callbacks.TerminateOnNaN(),
        ],
    )

    model = tf.keras.models.load_model(
        out / "kws.keras", compile=False
    )
    fp_scores = model(x_val, training=False).numpy()
    fp_result = show_result(
        "浮點模型驗證正確率", y_val, fp_scores.argmax(axis=1)
    )

    print("\n轉換 INT8 模型；量化校正只使用訓練資料。", flush=True)

    export = tf.keras.export.ExportArchive()
    export.track(model)
    export.add_endpoint(
        "serve",
        fn=lambda x: model(x, training=False),
        input_signature=[
            tf.TensorSpec([1, 49, MFCC, 1], tf.float32)
        ],
    )
    export.write_out(str(out / "saved_model"), verbose=False)

    converter = tf.lite.TFLiteConverter.from_saved_model(
        str(out / "saved_model")
    )
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    calibration = np.concatenate([
        rng.choice(
            np.flatnonzero(y_aug == i),
            size=min(60, int(counts[i])),
            replace=False,
        )
        for i in range(5)
    ])

    def representative():
        for i in calibration:
            yield [x_train[i:i + 1]]

    converter.representative_dataset = representative
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS_INT8
    ]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    model_path = out / "kws_int8.tflite"
    model_path.write_bytes(converter.convert())

    interpreter = tf.lite.Interpreter(
        model_path=str(model_path), num_threads=2
    )
    interpreter.allocate_tensors()

    inp = interpreter.get_input_details()[0]
    output = interpreter.get_output_details()[0]
    scale, zero = inp["quantization"]
    out_scale, out_zero = output["quantization"]

    if (
        inp["dtype"] != np.int8
        or output["dtype"] != np.int8
        or scale <= 0
    ):
        raise ValueError("模型輸入／輸出量化格式不符。")

    scores = []
    for x in x_val:
        q = np.clip(
            np.rint(x[None] / scale) + zero, -128, 127
        ).astype("int8")
        interpreter.set_tensor(inp["index"], q)
        interpreter.invoke()
        result = interpreter.get_tensor(
            output["index"]
        )[0].astype("float32")
        scores.append((result - out_zero) * out_scale)

    scores = np.stack(scores)
    predictions = scores.argmax(axis=1)
    int_result = show_result(
        "INT8 模型驗證正確率", y_val, predictions
    )

    print("\n現場補訓樣本回看（已參與訓練，不列入驗證正確率）：")
    live_replay = []
    for label, pcm in zip(live_names, live_wav):
        value = normalize(features(pcm)[None])
        q = np.clip(np.rint(value / scale) + zero, -128, 127).astype("int8")
        interpreter.set_tensor(inp["index"], q)
        interpreter.invoke()
        s = (interpreter.get_tensor(output["index"]).reshape(-1)
             .astype("float32") - out_zero) * out_scale
        best = int(s.argmax())
        margin = float(np.sort(s)[-1] - np.sort(s)[-2])
        gate = best < 3 and float(s[best]) >= 0.90 and margin >= 0.25
        print(f"  {label:7} -> {LABELS[best]:7}，分數 {s[best]:.1%}，"
              f"差距 {margin:.1%}，單窗命令分數條件={int(gate)}")
        live_replay.append({"expected": label, "predicted": LABELS[best],
                            "scores": s.tolist(), "score_gate": bool(gate)})

    # 模型已選定並完成量化，現在才讀取保留測試音訊。
    holdout_waves = []
    for row in holdout_rows:
        path = collection / row["file"]
        if pcm_sha(path) != row["pcm_sha256"]:
            raise ValueError(f"保留測試錄音雜湊不符：{path}")
        holdout_waves.append(read_wav(path))
    x_holdout = normalize(np.stack([features(x) for x in holdout_waves]))
    y_holdout = np.array(
        [LABELS.index(r["label"]) for r in holdout_rows], dtype="int32"
    )
    fp_holdout = model(x_holdout, training=False).numpy()
    holdout_fp_result = show_result(
        "現場保留測試：浮點模型", y_holdout, fp_holdout.argmax(axis=1)
    )

    int_holdout = []
    for x in x_holdout:
        q = np.clip(np.rint(x[None] / scale) + zero, -128, 127).astype("int8")
        interpreter.set_tensor(inp["index"], q)
        interpreter.invoke()
        s = (interpreter.get_tensor(output["index"]).reshape(-1)
             .astype("float32") - out_zero) * out_scale
        int_holdout.append(s)
    int_holdout = np.stack(int_holdout)
    if not np.isfinite(int_holdout).all() or not np.isfinite(fp_holdout).all():
        raise ValueError("保留測試分數包含非有限數值。")
    h_pred = int_holdout.argmax(axis=1)
    holdout_int_result = show_result(
        "現場保留測試：INT8 模型", y_holdout, h_pred
    )

    margin = np.sort(int_holdout, axis=1)[:, -1] - np.sort(int_holdout, axis=1)[:, -2]
    gate = (h_pred < 3) & (int_holdout.max(axis=1) >= 0.90) & (margin >= 0.25)
    command = y_holdout < 3
    correct_gate = command & (h_pred == y_holdout) & gate
    false_gate = (~command) & gate
    print("\n現場保留測試逐段結果（INT8）：")
    holdout_details = []
    for i, row in enumerate(holdout_rows):
        best = int(h_pred[i])
        print(f"  {row['file']}：預測={LABELS[best]}，"
              f"目標分數={int_holdout[i, y_holdout[i]]:.1%}，"
              f"最高分={int_holdout[i, best]:.1%}，"
              f"差距={margin[i]:.1%}，命令分數條件={int(gate[i])}")
        holdout_details.append({
            "file": row["file"], "true": row["label"],
            "predicted": LABELS[best], "scores": int_holdout[i].tolist(),
            "float32_scores": fp_holdout[i].tolist(),
            "score_gate": bool(gate[i]), "pcm_sha256": row["pcm_sha256"],
        })
    print(f"\n命令答對且通過單窗分數條件：{int(correct_gate.sum())}/{int(command.sum())}")
    print(f"非命令卻通過單窗分數條件：{int(false_gate.sum())}/{int((~command).sum())}")
    print("以上只檢查單窗分數，尚未測試板上的音量門檻與連續兩次命中規則。")
    holdout_report = {
        "dataset": str(collection), "float32": holdout_fp_result,
        "int8": holdout_int_result, "details": holdout_details,
        "correct_command_gate": int(correct_gate.sum()),
        "command_count": int(command.sum()),
        "noncommand_false_gate": int(false_gate.sum()),
        "noncommand_count": int((~command).sum()),
        "score_threshold": 0.90, "margin_threshold": 0.25,
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "frontend_sha256": hashlib.sha256((out / "frontend.npz").read_bytes()).hexdigest(),
    }

    config["input_quantization"] = {
        "scale": float(scale), "zero_point": int(zero)
    }
    config["output_quantization"] = {
        "scale": float(out_scale), "zero_point": int(out_zero)
    }
    (out / "config.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )

    report = {
        "float32": fp_result,
        "int8": int_result,
        "history": history.history,
        "extra_training_replay": live_replay,
        "holdout": holdout_report,
        "validation": [
            {
                "file": r["file"],
                "true": LABELS[int(y)],
                "predicted": LABELS[int(p)],
                "scores": s.tolist(),
            }
            for r, y, p, s in zip(
                val_rows, y_val, predictions, scores
            )
        ],
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    shutil.copy2(__file__, out / "train_kws.py")
    (ROOT / "model_candidate_current.txt").write_text(str(out) + "\n")

    print(f"\nINT8 模型：{model_path}")
    print(f"模型大小：{model_path.stat().st_size} 位元組")
    print(f"輸入量化：scale={scale}；zero_point={zero}")
    print(f"輸出目錄：{out}")


if __name__ == "__main__":
    main()
