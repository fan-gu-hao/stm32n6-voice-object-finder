# Keyword-spotting training evolution

[繁體中文](README.md) | [English](README.en.md)

This directory adds the early script that had previously existed only in a training-output directory and links it to the published later versions. Each version is an original file that was actually retained, rather than a newly written substitute for presentation. Retained code, completed training, offline evaluation, and board operation are identified separately; see the [original development-history review](../../docs/original-history-review.en.md) for conversation and attachment evidence.

| Stage | Program and main content |
| --- | --- |
| Initial version, 2026-10-05 | [train_kws.py](20261005_baseline/train_kws.py): 49×13 MFCC and depthwise-separable five-class convolutional model; checks that original recordings do not cross train/validation splits; normalization and quantization calibration use training data only; up to 80 epochs with validation-loss model selection and early stopping |
| Live-data version 2 | [Retained train_kws.py](../train_kws.py): adds live clips from four classes; constrains shifts to utterance boundaries to keep speech in the window; adds silence mixing and a wider noise range, and separately rechecks clips already used in training. Original output confirms completed retraining and 48/49 validation accuracy for both float and INT8 |
| Live-data version 3 | [train_kws_live_v3.py](../train_kws_live_v3.py): preserves the subsequent version of live-data retraining and augmentation; no separate completed training log has been found for this version, so no completion metrics are assigned to it |
| Final grouped cross-validation version | [train_kws_groupcv.py](../training_snapshot/train_kws_groupcv.py): merges source groups sharing identical PCM hashes, applies stratified grouped five-fold validation and training-only normalization per fold, selects the epoch count, exports final INT8, and evaluates held-out audio; the original attachment confirms completed 66-epoch final training and evaluation |

The initial version already had fixed frontend coefficients, source separation, augmentation with training background audio, class weights, float/INT8 confusion matrices, and model snapshots. It used shifts up to ±100 ms, a 15–30 dB signal-to-noise ratio, ±6 dB gain, and seven augmentation passes. Later versions added utterance-boundary-constrained shifts, silence mixing, and live data. These differences can be inspected directly in the code.

## From live failures to the final grouped model

| Stage | Original execution results and rationale |
| --- | --- |
| Earlier live predictions did not match expectations | Retained records show predictions favoring phone; fixed-input comparisons were introduced to examine model porting separately from audio preprocessing |
| Fixed five-class comparison | Both INPUT and PCM paths classified 5/5 cases correctly, with identical 637-element INT8 features for every case. The maximum integer output difference was 1 for silence and 0 for the other cases in both paths |
| Four live diagnostic cases | Input features still matched for silence, cup, bottle, and phone; maximum integer output differences were 0, 0, 3, and 1. Silence was classified as phone on the board and both PC paths, identifying a model failure on that live sample |
| Retraining with four added clips | On 2026-10-07, training grew from 142 to 146 clips while validation remained at 49; both float and INT8 scored 48/49 (97.96%). All four added clips were correctly classified when rechecked, but they were training samples, not independent validation |
| Expanded live collection | On 2026-10-08, 48 clips were completed: 32 training and 16 held out. Training included 8 clips each for cup/bottle/phone and 4 each for unknown/silence; the holdout contained 4 of each command and 2 of each non-command class |
| Grouped five-fold validation and final training | Five-fold validation on 227 development clips evaluated each clip once, totaling 224/227 (98.68%) for INT8. Final training used the median best epoch count, 66, before evaluation on the separate 16-clip holdout |

[Earlier board comparisons and live-data records](../../docs/evidence/development-history/README.en.md) retain the silence misclassification, numerical-consistency results, and collection manifest. The [original development-history review](../../docs/original-history-review.en.md) adds conversation evidence for fixed CMP output and completed retraining. Model identity is determined by each report's SHA-256, not inferred solely from a script snapshot's date.

## Data separation and limits of the results

The 227 development clips in the grouped stage comprise the earlier 142 training and 49 validation clips, four live diagnostic clips, and 32 newly collected training clips. The earlier fixed 49-clip validation set thus became part of grouped cross-validation, while the 16 newly collected holdout clips remained excluded from training and epoch selection. The earlier 48/49 and final 15/16 results use different evaluation sets.

The grouped script starts with original-recording groups and merges source groups containing identical PCM, preventing duplicate audio from crossing training and validation folds. This is not deletion of every duplicate sample. It also rejects development/holdout overlap, checks label conflicts, and uses only each fold's training subset to estimate normalization and construct background-noise augmentation and quantization calibration data.

The five best epoch counts were `[82, 28, 66, 9, 79]`. The original training attachment starts near the end of fold 5 and includes the five-fold summary, every final-training epoch from 1 through 66, INT8 export, and holdout evaluation. It is not a complete epoch-by-epoch log of all five folds. Cross-validation was used for development and epoch selection, not as an additional independent test set.

The final float and INT8 models both classified 15/16 held-out clips correctly (93.75%), with identical predicted classes. The incorrect `cup/take_45.wav` was classified as phone, but its INT8 phone score was only 60.9375%, below the 90% command threshold. Correct command classification with passing single-window score conditions was 11/12; non-command false passes were 0/4. These checks do not include the volume gate, consecutive hits, or cooldown, and must not be combined with the six correct board acceptances as one test. See the [holdout report](../../docs/evidence/kws-int8-holdout.json) and [results](../../docs/results.en.md).

The initial source was `kws/runs/kws_20261005_203338_212380/train_kws.py`, with SHA-256 `8d68ffccd2566085664e33c23228b74018848e62d1c1576e8f1d761240f8c980`. The public copy is identical. The original program uses its own directory as its working root; this location is a historical archive, not a ready-to-rerun training workspace. Raw audio and model weights are not included, and no retraining was performed during preparation.
