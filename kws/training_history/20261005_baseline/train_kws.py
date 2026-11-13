from pathlib import Path
from datetime import datetime
import os
import json
import shutil
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


def augment(samples, label, noises, rng):
    x = samples.copy()

    if label != 4:
        # 前後移動最多 100 毫秒，空出的部分補零。
        shift = int(rng.integers(-1600, 1601))
        shifted = np.zeros_like(x)
        if shift > 0:
            shifted[shift:] = x[:-shift]
        elif shift < 0:
            shifted[:shift] = x[-shift:]
        else:
            shifted[:] = x
        x = shifted

        # 只混入訓練組的背景聲，訊噪比為 15～30 分貝。
        noise = np.roll(
            noises[int(rng.integers(len(noises)))],
            int(rng.integers(SAMPLES)),
        )
        noise = noise - noise.mean()
        signal_rms = np.sqrt(np.mean(x ** 2) + 1e-12)
        noise_rms = np.sqrt(np.mean(noise ** 2) + 1e-12)
        snr = rng.uniform(15, 30)
        x = x + noise * (signal_rms / noise_rms) * 10 ** (-snr / 20)

    # 音量變化範圍：正負 6 分貝。
    x = x * 10 ** (rng.uniform(-6, 6) / 20)
    return np.clip(x, -1, 1).astype("float32")


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

    for _ in range(7):
        augmented.append(np.stack([
            features(augment(x, y, noises, rng))
            for x, y in zip(train_wav, y_train)
        ]))
        augmented_labels.append(y_train)

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
    (ROOT / "model_current.txt").write_text(str(out) + "\n")

    print(f"\nINT8 模型：{model_path}")
    print(f"模型大小：{model_path.stat().st_size} 位元組")
    print(f"輸入量化：scale={scale}；zero_point={zero}")
    print(f"輸出目錄：{out}")


if __name__ == "__main__":
    main()
