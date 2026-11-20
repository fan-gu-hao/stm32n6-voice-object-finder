# Original development evidence

[繁體中文](README.md) | [English](README.en.md)

This directory preserves records from recording, model comparison, code generation, builds, flashing, and board operation during development of the dual-model voice object finder. [Sources and hashes](source_provenance.json) map originals to public copies; the [project source-material inventory](review_inventory.json) indexes this project's sources and its actual recording dependencies.

## Versions and results

| Date/version | Original material | What can be confirmed |
| --- | --- | --- |
| Vision stage, 2026-10-04 | [finder_vision_20261004.log](finder_vision_20261004.log) | PHONE and CUP produced `found=1`; this is an earlier vision version |
| Fixed references, 2026-10-07 | [fixed_reference_20261007.json](fixed_reference_20261007.json) | PC reference predictions for five classes, model/coefficient SHA-256, and input/output quantization parameters |
| Live comparison on the same day | [live_comparison_20261007.json](live_comparison_20261007.json), [serial events](live_serial_events_20261007.log) | Matching board/PC features for identical windows; maximum output differences of 0, 0, 3, and 1 in the four cases |
| Live collection, 2026-10-08 | [live_dataset_manifest_20261008.json](live_dataset_manifest_20261008.json) | 48 clips collected: 32 for training and 16 held out, with labels, usage, peaks, times, and PCM hashes |
| Final grouped model on the same day | [config.json](codegen_20261008/config.json), [model SHA-256](codegen_20261008/model_sha256.txt) | Frontend, data methods, 66-epoch final training, INT8 interface, and model version |
| Final code generation | [Command](codegen_20261008/command.json), [log](codegen_20261008/codegen.log), [report](codegen_20261008/kws_network_generate_report.txt) | TFLite passes through internal ONNX/quantization information into Neural-ART; hardware/software partition and memory allocation |
| Final deployment | [Build log](deployment_20261008/build.log), [image manifest](deployment_20261008/flash_manifest.json), [verification record](deployment_20261008/flash_verified.json) | Addresses, hashes, and existing successful write verification for KWS weights and application image |
| Final voice operation | [voice_groupcv_20261008.log](voice_groupcv_20261008.log) | Two acceptances each for cup, bottle, and phone; none for hello or two quiet intervals; vision in that session remained `found=0` |

The earlier comparison used model `ffdec67ca044a3b8b94e8e670ee0a1f13225d00569827fdc6e20d9a1fa1bbd40` and coefficient file `72fe3e5f73fa012d763d53df4c8cf7ec99a4c8a75534c8d2c4b7d8068861475d`. The later final grouped model is `bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b`. Results must be interpreted against their own versions.

## How comparisons localized problems

The four live cases are ordered silence, cup, bottle, phone. All four record `input_diff=0` and `input_max=0`, meaning the board C frontend and PC produced identical INT8 features for those same PCM windows. Maximum output differences are differences between quantized integers, not percentage errors.

The silence case was classified as phone by all three paths: the board, PC inference from features, and the complete PC PCM frontend. This matching misclassification localized the issue to the model and data, prompting later [training evolution](../../../kws/training_history/README.en.md) and live-data collection. These four windows check deployment consistency; model generalization is evaluated separately on validation and held-out data.

The fixed five-class `reference.json` contains PC reference data, while line-by-line board INPUT/PCM output is preserved in the original development conversation. On 2026-11-20, review recovered the actual CMP output. The [review and excerpts](../../original-history-review.en.md) document five correct classes in each path, 637 matching INT8 features per PCM case, and maximum integer output differences of zero except for silence at one. These records are retained as terminal-result excerpts in the conversation; the complete original serial log remains unavailable. They are identified separately from the PC reference JSON here.

## Code generation, memory, and writes

ST Edge AI 4.0.1 accepts the final INT8 TFLite, internally creates `kws_int8_OE_3_3_1.onnx` and [quantization metadata](codegen_20261008/kws_int8_OE_3_3_1_Q.json), then invokes Neural-ART 1.1.3-275. This is the intermediate representation used by the N6 compilation tools for this project's quantized KWS model.

The [compiler configuration information](codegen_20261008/kws_network_c_info.json) and text report record:

- 12 execution stages: 11 hardware-only and 1 software Softmax, with no hybrid stages and no epoch-controller command blob.
- 11,409 bytes of KWS weights and 17,440 bytes of activations, placed in the 64 KiB `kwsFlash` and 256 KiB `kwsRAM` pools respectively.
- Runtime overhead of 40,870 bytes for code/read-only data and 29 bytes of additional RAM. These are statistics from that KWS generation report, not the dual-model system's total peak memory usage.

Both the [KWS write log](deployment_20261008/flash_kws_weights.bin.log) and [application write log](deployment_20261008/flash_finder_signed.bin.log) retain successful verification messages. Their addresses are `0x70700000` and `0x70100000`. The filename's `signed` follows the original tool naming; no-key packaging includes a boot header without a cryptographic signature.

## Record formatting and publication scope

Local project/tool prefixes and debugger serial numbers in JSON/text records were replaced with placeholders, and terminal control codes were removed. Model hashes, numerical values, failure cases, and image-verification results were preserved. Original models, ONNX model files, weights, images, and personal recordings were not added to this repository. The two published compiler JSON files contain graph, quantization-parameter, and allocation information.

The exported report of the original live serial file had already omitted 1,181 `LIVE,D` packet lines; the public excerpt additionally omits one remaining hexadecimal fragment. It is therefore called an event excerpt and cannot be used to revalidate CRC32 for the complete PCM transfer. Original and excerpt hashes are retained separately. The log begins with residual events from a previous run, followed by the complete four-case collection; the two portions are not combined in the counts.

The [log observation summary](observations.json) was parsed from retained text. An earlier vision-log line has a truncated ending and remains unchanged; line counts are not scene-recognition rates. The [hardware demonstration video](https://youtu.be/m7wET9g5u6k) is available; these materials do not contain passing standalone-power or cold-boot test records for the dual-model system.
