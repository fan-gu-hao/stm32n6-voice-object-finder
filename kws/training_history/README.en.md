# Keyword-spotting training evolution

[繁體中文](README.md) | [English](README.en.md)

This directory adds the early script that had previously existed only in a training-output directory and links it to the published later versions. Each version is an original file that was actually retained, rather than a newly written substitute for presentation.

| Stage | Program and main content |
| --- | --- |
| Initial version, 2026-10-05 | [train_kws.py](20261005_baseline/train_kws.py): 49×13 MFCC and depthwise-separable five-class convolutional model; checks that original recordings do not cross train/validation splits; normalization and quantization calibration use training data only; up to 80 epochs with validation-loss model selection and early stopping |
| Live-data version 2 | [Retained train_kws.py](../train_kws.py): adds live clips from four classes; constrains shifts to utterance boundaries to keep speech in the window; adds silence mixing and a wider noise range, and separately rechecks clips already used in training |
| Live-data version 3 | [train_kws_live_v3.py](../train_kws_live_v3.py): preserves the subsequent version of live-data retraining and augmentation |
| Final grouped cross-validation version | [train_kws_groupcv.py](../training_snapshot/train_kws_groupcv.py): PCM-hash duplicate handling, stratified grouped five-fold validation, training-only normalization per fold, epoch selection, final INT8 export, and held-out audio evaluation |

The initial version already had fixed frontend coefficients, source separation, augmentation with training background audio, class weights, float/INT8 confusion matrices, and model snapshots. It used shifts up to ±100 ms, a 15–30 dB signal-to-noise ratio, ±6 dB gain, and seven augmentation passes. Later versions added utterance-boundary-constrained shifts, silence mixing, and live data. These differences can be inspected directly in the code.

[Earlier board comparisons and live-data records](../../docs/evidence/development-history/README.en.md) retain the silence misclassification and numerical-consistency observations. Model identity is determined by each report's SHA-256, not inferred solely from a script snapshot's date.

The initial source was `kws/runs/kws_20261005_203338_212380/train_kws.py`, with SHA-256 `8d68ffccd2566085664e33c23228b74018848e62d1c1576e8f1d761240f8c980`. The public copy is identical. The original program uses its own directory as its working root; this location is a historical archive, not a ready-to-rerun training workspace. Raw audio and model weights are not included, and no retraining was performed during preparation.
