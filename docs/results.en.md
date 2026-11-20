# Existing results, original evidence, and version scope

[繁體中文](results.md) | [English](results.en.md)

This page summarizes retained development and final-version results for the dual-model voice object finder, separating model versions and test methods. The data comes from evaluation reports, build/write logs, board-operation records, and a renewed review of the original conversations and attachments. The [original development-history review](original-history-review.en.md) identifies the latter sources and their corresponding development stages.

## Results of the final grouped-training version

| Item | Result | Original material |
| --- | --- | --- |
| Five-fold INT8 development validation | 224/227, 98.68%; aggregate across folds, used for development and epoch selection | [Cross-validation report](evidence/kws-groupcv.json) |
| Final-model held-out audio | 15/16, 93.75% for both float and INT8; identical classifications on 16 clips, with one cup classified as phone | [Holdout report](evidence/kws-int8-holdout.json) |
| Single-window score conditions on held-out audio | 11 of 12 command clips were correctly classified and passed the score conditions; 0 of 4 non-command clips falsely passed | [Original training-output reference](original-history-review.en.md); this does not apply the board's volume gate, consecutive-hit requirement, or cooldown |
| On-board voice operation, 2026-10-08 | Two correct acceptances each for cup, bottle, and phone; no accepted commands for hello or two quiet intervals | [Original voice log](evidence/development-history/voice_groupcv_20261008.log) |
| Vision in the same session | All 53 retained FINDER lines report found=0 | Same log; [line-by-line observation summary](evidence/development-history/observations.json) |
| Application and KWS-weight deployment | Application written at 0x70100000 and KWS weights at 0x70700000, with successful verification and retained image hashes | [Image manifest](evidence/development-history/deployment_20261008/flash_manifest.json), [verification record](evidence/development-history/deployment_20261008/flash_verified.json) |

The final KWS model SHA-256 is bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b. The log preserves candidate hits, command acceptance, and FINDER targets. The target matched each of the six accepted commands; CUP was already selected before the first cup acceptance, while the subsequent five acceptances changed the target class. These results describe one board-operation session; cross-environment success rates and long-term false-trigger rates require larger and longer tests.

For the misclassified held-out clip `cup/take_45.wav`, the INT8 model's highest score, for phone, was 60.9375%, below the 90% command-score threshold. This score condition would reject the window despite its incorrect classification. The 15/16 result measures single-window classification; 11/12 and 0/4 check offline score conditions; the six correct acceptances come from a separate board-operation session. Each result is presented according to its test method.

The original grouped-training attachment retains the end of fold 5, the five-fold summary, every epoch from 1 through 66 of final training, and both float and INT8 holdout results. The best epochs were `[82, 28, 66, 9, 79]`; their median, 66, was used to retrain on all 227 development clips. The attachment confirms completion of final training; its retained per-epoch cross-validation log begins late in fold 5.

## Earlier deployment debugging and data improvements

Earlier comparisons used model ffdec67ca044a3b8b94e8e670ee0a1f13225d00569827fdc6e20d9a1fa1bbd40, recorded separately from the final grouped-training model.

| Stage | Retained observation | Evidence and interpretation |
| --- | --- | --- |
| Earlier failure in actual use | Live predictions sometimes favored phone rather than the intended command or environment, prompting fixed-input and live-audio diagnostics | The [original development-history review](original-history-review.en.md) records the initial problem and the resulting diagnostic work |
| Fixed reference audio for five classes | PC reference predictions, quantization parameters, model and frontend-coefficient hashes | [Public reference.json copy](evidence/development-history/fixed_reference_20261007.json); this JSON itself contains PC references only |
| Fixed INPUT/PCM comparison results | Both direct INT8-feature input and PCM recomputation classified all five cases correctly, 5/5 per path. Each case had zero differing elements and zero maximum difference across 637 features. In both paths, the maximum integer output difference was 1 for silence and 0 for the other cases | [Comparison code](../firmware/Src/finder_kws.c), [original CMP-output reference](original-history-review.en.md); the original conversation contains ten result lines between `CMP,BEGIN` and `CMP,END`, establishing results as well as the method |
| Four live comparisons | Matching INT8 input features for silence, cup, bottle, and phone; maximum output integer differences of 0, 0, 3, and 1 | [Original comparison report](evidence/development-history/live_comparison_20261007.json), [serial-event excerpt](evidence/development-history/live_serial_events_20261007.log) |
| Silence misclassification | The silence case was classified as phone by the board, PC feature-input path, and PC PCM-frontend path | The same original report retains the failure to distinguish model/data issues from porting issues |
| Retraining with four live clips | Training grew from 142 to 146 clips while validation remained at 49; both float and INT8 scored 48/49 (97.96%) | [Original training-output reference](original-history-review.en.md), [training script from that stage](../kws/train_kws.py); rechecking the four added training clips was not independent validation |
| Live-data iteration | 48 clips collected: 32 for training and 16 held out, with labels, usage, and PCM hashes | [Live dataset manifest](evidence/development-history/live_dataset_manifest_20261008.json), [training evolution](../kws/training_history/README.en.md) |

The fixed references and four live cases test different inputs. Passing the fixed five-class comparison, together with the matching silence misclassification across all three live paths, focused subsequent improvements on data and training. Numerical comparison verifies porting consistency for these samples; model accuracy is measured separately on evaluation datasets. The live-v3 training script is retained, while its separate completed training log remains unavailable and its completion metrics await supporting records. Comparison and live-collection switches are disabled in the final version; the original code remains for reading the debugging methods used at the time.

## Earlier vision and demonstration scope

The [2026-10-04 vision log](evidence/development-history/finder_vision_20261004.log) retains 5 PHONE lines and 8 CUP lines with found=1. The counts use log lines as their unit, and an originally truncated line is also preserved. This record corresponds to that vision revision; scene-recognition rates and the integrated version's three-object performance are assessed from their respective tests or demonstrations.

The [hardware demonstration video](https://youtu.be/m7wET9g5u6k) is available. Standalone power, autonomous boot from external Flash, and cold boot of the dual-model system are not listed as tested.

## Code-generation and delivery evidence

The [final generation report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt) and [configuration information](evidence/development-history/codegen_20261008/kws_network_c_info.json) record the internal ST Edge AI ONNX stage, 11 hardware and 1 software execution stages, 11,409 bytes of weight allocation, and 17,440 bytes of activation allocation. These are compiler statistics from that run, not the measured total RAM peak of the dual-model system.

The [final build log](evidence/development-history/deployment_20261008/build.log) records 535,544 bytes of application SRAM, 230,528 bytes of vision-command Flash, and 8,949,920 bytes of application/display PSRAM. Generated KWS code uses absolute addresses in its reserved RAM region, so the linker's zero must not be interpreted as no usage. The [code tour](code-tour.en.md) maps region addresses, capacities, and usage.

Both the [KWS-weight write log](evidence/development-history/deployment_20261008/flash_kws_weights.bin.log) and [application write log](evidence/development-history/deployment_20261008/flash_finder_signed.bin.log) record successful verification. That deployment updated and verified two images. The FSBL, vision weights, and vision commands in the local five-image delivery package reused existing contents. See the [third-party notices](../THIRD_PARTY_NOTICES.en.md) for the publication scope of models, raw recordings, and flash images.

Preparation methods and hashes are in the [evidence index](evidence/development-history/README.en.md), with source mappings in the [project source-material inventory](evidence/development-history/review_inventory.json).
