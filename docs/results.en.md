# Existing results, original evidence, and version scope

[繁體中文](results.md) | [English](results.en.md)

This page presents results against the actual models and records from each stage. Publication preparation on 2026-11-13 did not add training, builds, flashing, or board tests.

## Results of the final grouped-training version

| Item | Result | Original material |
| --- | --- | --- |
| Five-fold development validation | 224/227, 98.68%; used for development and epoch selection | [Cross-validation report](evidence/kws-groupcv.json) |
| INT8 evaluation on held-out audio | 15/16, 93.75%; one cup classified as phone, in offline single-window evaluation | [Holdout report](evidence/kws-int8-holdout.json) |
| On-board voice operation, 2026-10-08 | Two correct acceptances each for cup, bottle, and phone; no accepted commands for hello or two quiet intervals | [Original voice log](evidence/development-history/voice_groupcv_20261008.log) |
| Vision in the same session | All 53 retained FINDER lines report found=0 | Same log; [line-by-line observation summary](evidence/development-history/observations.json) |
| Application and KWS-weight deployment | Existing writes and verification succeeded; addresses and image hashes are retained | [Image manifest](evidence/development-history/deployment_20261008/flash_manifest.json), [verification record](evidence/development-history/deployment_20261008/flash_verified.json) |

The final KWS model SHA-256 is bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b. The six command acceptances describe that operation session, not a success rate across arbitrary environments. Short non-command samples also do not establish a long-term false-trigger rate.

## Earlier deployment debugging and data improvements

Earlier comparisons used model ffdec67ca044a3b8b94e8e670ee0a1f13225d00569827fdc6e20d9a1fa1bbd40, recorded separately from the final grouped-training model.

| Stage | Retained observation | Evidence and interpretation |
| --- | --- | --- |
| Fixed reference audio for five classes | PC reference predictions, quantization parameters, model and frontend-coefficient hashes | [Public reference.json copy](evidence/development-history/fixed_reference_20261007.json); this JSON itself contains PC references only |
| Fixed INPUT/PCM board comparisons | Earlier development records describe matching board/PC predictions for all five classes, no input-feature differences, and maximum quantized-output difference of 1 | [Comparison code](../firmware/Src/finder_kws.c) and the existing development summary; the received materials do not include the original line-by-line CMP serial output |
| Four live comparisons | Matching INT8 input features for silence, cup, bottle, and phone; maximum output integer differences of 0, 0, 3, and 1 | [Original comparison report](evidence/development-history/live_comparison_20261007.json), [serial-event excerpt](evidence/development-history/live_serial_events_20261007.log) |
| Silence misclassification | The silence case was classified as phone by the board, PC feature-input path, and PC PCM-frontend path | The same original report retains the failure to distinguish model/data issues from porting issues |
| Live-data iteration | 48 clips collected: 32 for training and 16 held out, with labels, usage, and PCM hashes | [Live dataset manifest](evidence/development-history/live_dataset_manifest_20261008.json), [training evolution](../kws/training_history/README.en.md) |

Deployment consistency in four cases is not overall model accuracy. Comparison and live-collection switches are disabled in the final version; the original code remains for reading the debugging methods used at the time.

## Earlier vision and demonstration scope

The [2026-10-04 vision log](evidence/development-history/finder_vision_20261004.log) retains 5 PHONE lines and 8 CUP lines with found=1. These line counts are not scene success rates; an originally truncated line is also preserved. This earlier vision record does not replace a three-object demonstration of the current integrated version.

The demonstration video is pending. Standalone power, autonomous boot from external Flash, and cold boot of the dual-model system are not listed as tested. The earlier vision project's A1–A5 stages have their own original evidence; those results are not reassigned to the dual-model version.

## Code-generation and delivery evidence

The [final generation report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt) and [configuration information](evidence/development-history/codegen_20261008/kws_network_c_info.json) record the internal ST Edge AI ONNX stage, 11 hardware and 1 software execution stages, 11,409 bytes of weight allocation, and 17,440 bytes of activation allocation. These are compiler statistics from that run, not the measured total RAM peak of the dual-model system.

The two application/KWS-weight write logs are public. The other three images in the complete local five-image delivery package reuse earlier contents. Models, raw recordings, and flash images retain their established publication scope.

Preparation methods and hashes are in the [evidence index](evidence/development-history/README.en.md). Disposition of all supplied inputs is listed in the [publication inventory](publication-review.en.md).
