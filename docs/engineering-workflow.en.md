# Complete workflow, cross-stage development, and implementation evidence

[繁體中文](engineering-workflow.md) | [English](engineering-workflow.en.md)

The engineering scope includes model deployment, audio drivers, dataset preparation, training and quantization, Python/C comparisons, NPU integration, real-time task scheduling, cache/memory configuration, and image delivery. Work was completed in stages, with some parts first validated in other course projects and development conversations before being carried into the dual-model object finder.

The [setup-to-freeze coverage map](development-coverage.en.md) checks work across projects and expands on shared clocks, DMA access attributes, buffer ownership, mask lifetimes, voice-error isolation, and host transfers. The earliest environment records and all historical conversations have not been obtained in full; currently accessible materials are not presented as 100% historical coverage.

## Development context

| Stage | Work accumulated | How this project carries it forward |
| --- | --- | --- |
| Earlier YOLO detection | COCO-class model export, quantization, and the N6 tool environment | Tools and workflow for later segmentation deployment; course14 deployment scripts retain earlier environment paths |
| course14 instance segmentation | PyTorch → ONNX → onnx2tf/SavedModel → ST INT8; output-mapping patches, camera/LCD, UART, fixed-input regression, performance and memory experiments | Vision interfaces, postprocessing adaptation, deployment, memory, and debugging experience; [full source and evidence](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| course15 on-board recording | MDF/DMA callbacks, five-second RAM recording, warm-up/timeouts, UART handshake and CRC32, RAM loading, and WAV storage | [Standalone firmware](../kws/recording_firmware/README.en.md) and [host tools](../kws/recording_tools/README.en.md) are included here; continuous capture was subsequently integrated in finder_mic.c |
| course17 dual model | Custom data collection, MFCC, KWS training/quantization, board comparisons, additional live samples, and grouped cross-validation | KWS and YOLO integrated under FreeRTOS into a voice-selected search-target system |

This page tracks both completed engineering work and the artifacts actually selected for this version. The historical SHA-256 of the model quantized in course14 is 312ea45821140094d6a637d11f2e7daf1c8eb3e9ad5f93b8ed6c595128eaec2e. The current vision model's source and 33167331… hash are recorded in [sources.txt](../sources.txt). The table above continues to link earlier quantization and Model Zoo patches to their original evidence.

## Vision export, quantization, and postprocessing continuity

The earlier segmentation project retains a [successful export log](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log): ONNX 1.16.1/opset 19 exports yolov8n-seg.onnx, followed by onnx2tf 1.26.3 and TensorFlow 2.18.0 producing SavedModel/TFLite. ST per-channel quantization has separate [configuration](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/configs/yolov8n_seg_int8_int8.yaml) and a [successful log](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/04_st_quantization_seg.log).

The [Model Zoo patch](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/patches/modelzoo_seg_output_mapping.patch) identifies 1×116×1344 detection data and 1×64×64×32 mask prototypes by shape and validates types, class count, mask coefficients, and output sizes. Local Neural-ART argument and image-alignment patches were also completed. These are deployment and postprocessing-interface engineering results.

The dual-model version connects generated vision code and ST postprocessing to the hand-example FreeRTOS framework, then adds target selection, consecutive-frame confirmation, and status display. Integration entries are retained in [app.c](../firmware/Src/app.c), the [postprocessing adapter](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c), and the [build list](../firmware/mks/ai.mk).

The earlier work also retains [C/H sources and two installers for the serial-interrupt experiment](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/docs/publication_supplement_20261113/uart_it/source_snapshot), covering a ring queue, whole-line submission, reserved space for important messages, HAL dependency fixes, deployment, and rollback. This is a historical experiment that was rolled back; production A1 still uses the original serial-transfer method.

## Step-by-step audio, training, and board deployment

Initial collection used the [standalone recorder main.c](../kws/recording_firmware/FSBL/Src/main.c). DMA half/full callbacks skip warm-up blocks and copy samples into RAM; the main loop handles timeout, stopping DMA, CRC32, and serial transmission. These sources and the upstream diff are preserved alongside the host tools.

| Stage | Work and engineering focus | Implementation to read |
| --- | --- | --- |
| 1. Recording-firmware launcher | Find IDE debugging tools; check ELF/BIN, stack/entry vectors, and recording-version string; set core state after RAM loading, verify main/MicLine breakpoints, then detach | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| 2. Recording transfer | Exclusive serial access, query handshake, recording start, fixed-length reads, timeout, trailer, CRC32, WAV format, and clipping statistics | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| 3. Raw data collection | Follow the cup/bottle/phone/unknown/silence plan; check format, retain source/session metadata, and resume completed clips | [collect_n6.py](../kws/collect_n6.py) |
| 4. Segmentation and grouping | Locate speech by short-time energy, pad one-second clips, avoid adjacent words; split five-second source recordings into train/validation before cutting short clips | [prepare_dataset.py](../kws/prepare_dataset.py) |
| 5. Audio features | Python mean removal, periodic Hann window, FFT, HTK Mel filters, logarithm, and orthonormal DCT; retained frontend coefficients | [Final train_kws.py](../kws/training_snapshot/train_kws.py) |
| 6. Custom KWS model | A depthwise-separable convolutional network with 49×13×1 input; five classes, augmentation, class weights, and training records | [Network and augmentation](../kws/training_snapshot/train_kws.py) |
| 7. Live-data iteration | Retain live-data retraining versions; select board windows by speech energy, add real background noise/live speech, and keep held-out data separate | [Live v3 training](../kws/train_kws_live_v3.py), [collection plan](../kws/live_collection_plan.json), [board capture](../firmware/Src/finder_kws.c) |
| 8. Leakage prevention | Group by original recording; identify identical audio by PCM hash and merge groups; reject development/holdout overlap; derive fold normalization/background noise from training groups only | [load_development / make_splits / make_training](../kws/training_snapshot/train_kws_groupcv.py) |
| 9. Grouped cross-validation | Stratified grouped five-fold validation, epoch selection, and final training; evaluate 16 separately held-out live clips | [Final grouped training](../kws/training_snapshot/train_kws_groupcv.py), [five-fold report](evidence/kws-groupcv.json) |
| 10. KWS quantization/export | Convert Keras/SavedModel to INT8 TFLite using representative data; save scales, zero points, frontend coefficients, and float/quantized results | [export_int8](../kws/training_snapshot/train_kws_groupcv.py), [held-out audio report](evidence/kws-int8-holdout.json) |
| 11. N6 model generation | Dedicated KWS RAM/Flash, generation options, and network name; compile through the tool's internal ONNX stage and Neural-ART, then link alongside vision | [Generation configuration](../kws/deployment/README.en.md), [original commands/reports](evidence/development-history/README.en.md), [kws.mk](../firmware/mks/kws.mk) |
| 12. Continuous capture integration | MDF1 clock/pins/filtering/decimation, GPDMA circular links, and half/full callbacks; after warm-up, write a ring buffer and extract one-second windows | [finder_mic.c](../firmware/Src/finder_mic.c) |
| 13. CPU/DMA coherence | Align buffers/descriptors; clean/invalidate caches and use barriers; discard snapshots if copying is delayed until overwrite becomes possible | [cache_prepare / receive_block / finder_mic_take](../firmware/Src/finder_mic.c) |
| 14. C frontend/model interface | CMSIS-DSP FFT and C MFCC, normalization, clipping, INT8 quantization; static shape/type checks and initialization checks of training/generated scales and zero points | [finder_kws.c](../firmware/Src/finder_kws.c), [coefficient table](../firmware/Inc/finder_kws_tables.h) |
| 15. CPU/NPU coherence | Before CPU input writes, handle NPU cache and stale CPU copies; clean CPU cache after writes; wait for asynchronous inference and reset state for the next invocation | [kws_begin_input_update / prepare_input_cache / finder_kws_classify](../firmware/Src/finder_kws.c) |
| 16. Layered comparison/debugging | Test the model directly with fixed INT8 inputs, then the entire C frontend with identical PCM; compare input differences and quantized outputs | [finder_kws_compare](../firmware/Src/finder_kws.c), [comparison settings](../firmware/Inc/finder_kws_compare.h) |
| 17. Live raw-data return | Return PCM, 637 INT8 features, and five outputs from the same window as hexadecimal chunks with CRC32 for PC comparison | [finder_kws_live_capture / live_send](../firmware/Src/finder_kws.c) |
| 18. Voice acceptance state machine | Amplitude, top score, margin, consecutive windows, command interval, and re-arming after quiet; accept a sustained utterance only once | [finder_voice_poll](../firmware/Src/app.c) |

The complete KWS route is Keras/SavedModel → INT8 TFLite → ST Edge AI internal ONNX and quantization metadata → Neural-ART → N6. The [original generation log](evidence/development-history/codegen_20261008/codegen.log) preserves the internal ONNX filename and actual compiler invocation; this is documented separately from YOLO's earlier PyTorch-to-ONNX export. Grouping here is by original recording and PCM content, not an unperformed cross-speaker validation.

The [training history](../kws/training_history/README.en.md) additionally includes the original 2026-10-05 script, showing the progression from early augmentation through live samples and utterance-boundary constraints to the final grouped version. The [48-clip live manifest](evidence/development-history/live_dataset_manifest_20261008.json) retains the 32 training/16 held-out split and per-clip PCM hashes.

## Real-time system, memory, and delivery

| Work | Implementation | Entry |
| --- | --- | --- |
| Dual-model scheduling | One inference task polls KWS and runs YOLO sequentially on the shared NPU; display and ISP are separate tasks | [nn_thread_fct / dp_thread_fct / isp_thread_fct](../firmware/Src/app.c) |
| Camera/display coordination | DCMIPP display/inference pipelines, double input buffers, counting semaphores, display mutex, mask snapshots, and cache maintenance | [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c) |
| Target/state consistency | Switch class after voice/button input; reject pre-switch results using target generations; display FOUND after consecutive-box IoU confirmation | [finder_select_target and result publication](../firmware/Src/app.c) |
| Startup integration | Clock, NPU, CPU cache, external memory, UART, display, and FreeRTOS initialization | [main.c](../firmware/Src/main.c) |
| Memory separation | Application SRAM, display/postprocessing PSRAM, separate vision-command region; reserved KWS RAM at 0x91FC0000/256 KiB and weight Flash at 0x70700000/64 KiB | [Linker script](../firmware/Gcc/STM32N657xx.ld), [KWS memory pool](../kws/deployment/kws.mpool) |
| Build integration | Both models, HAL MDF, CMSIS-DSP, and runtime; consistent FFT compilation settings; separate extraction of .flash_section | [Makefile](../firmware/Makefile), [kws.mk](../firmware/mks/kws.mk), [ai.mk](../firmware/mks/ai.mk) |
| IDE preparation | Source/header browsing links, existing-link checks, backups, concurrency checks, and atomic replacement; build entry supports GCC_PATH and checks GCC 14.3.1 | [Original sync tool](../tools/ide/README.en.md), [IDE project](../firmware/STM32CubeIDE/STM32N6570-DK/.project), [IDE build entry](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) |
| Freeze and delivery | Source versions, model/tool settings, training snapshot, local frozen five-image package, and existing write verification | [Provenance](source-provenance.json), [results](results.en.md), [build notes](build.en.md) |

KWS generation does not enable the epoch controller. The CPU executes model control flow while the NPU executes the corresponding hardware operations. Control code is linked into the main application and speech weights are allocated separately; there is no standalone KWS ecblob image. This is the version's configuration choice, not a claimed EC-on/off performance comparison.

The [final compiler report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt) records 11 hardware and 1 software Softmax stages, with 11,409 bytes of weights and 17,440 bytes of activations. These KWS compiler statistics are distinct from the complete integrated system's peak memory use.

The local five-image package contains FSBL, application, vision weights, KWS weights, and vision execution commands; it is not five AI models. Image packaging uses no-key mode (-nk), so the header is not described as a cryptographic signature.

## Validation history and publication scope

[Results](results.en.md) separates early deployment comparisons, live-data improvements, and the final grouped model, preserving the applicability of each result. Early INPUT/PCM comparisons and live PCM/feature return distinguish frontend, deployment, and model issues; these debugging methods are engineering results alongside final accuracy.

Published materials include earlier vision conversion/quantization logs, patches, A1–A5, and the serial-interrupt experiment; this project's standalone recorder, host tools, training history, comparison/live-capture code, configurations, and offline evaluation. [Original voice/vision logs, early comparisons, live collection, generation, and deployment records](evidence/development-history/README.en.md) were also added. Itemized provenance and original records still missing are listed in the [publication inventory](publication-review.en.md).

Upstream HAL, BSP, CMSIS-DSP, RTOS, model architectures, inference runtime, and postprocessing algorithms retain their attribution. Model conversion, parameter selection, interface patches, driver integration, data workflows, cache handling, scheduling, debugging, and validation are listed individually here. Publication scope for model weights and prebuilt images is described in the [third-party notices](../THIRD_PARTY_NOTICES.en.md).
