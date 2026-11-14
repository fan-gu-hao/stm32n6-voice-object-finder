# From setup to freeze: engineering work and evidence

[繁體中文](development-coverage.md) | [English](development-coverage.en.md)

This page connects the earlier vision project, standalone recording, and dual-model object finder into a development history. Stage numbers aid reading; they do not represent known effort proportions or completion percentages. Original models, quantization, porting, failures, fixes, validation, and archiving all form part of the engineering work. Versions and results are retained even when an experiment was not ultimately adopted.

Review baselines: dual-model commit `a18c48ebde80370ba29f8649232e58f65fbe49ad`, vision commit `a427ca1b8ba5914a3c5c760ddd22c77899c1fd51`, supplied original-project documents, and 67 original materials. This is a **coverage inventory of accessible materials**. All historical STM32N6 project conversations and a complete inventory of early projects have not yet been obtained, so the inventory cannot claim that 100% of historical implementations are accounted for.

Status terminology: **Located** means specific code or original records were found; **Partially located** means only some materials or an existing document summary are available; **To obtain** means the item cannot yet be checked, not that the work was never done. Located also does not mean every operation has its complete original script or can be rerun directly in a new environment.

## 0. Environment setup and earlier work

| Work | Confirmed content | Evidence and coverage |
| --- | --- | --- |
| Development tools and versions | Later IDE, GCC, ST Edge AI, Neural-ART, CubeProgrammer, HAL, RTOS, and Python environments | [Build notes](build.en.md), [vision environments](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/requirements). **Partially located:** version snapshots are not the complete initial installation, dependency-conflict, and debugging history |
| Earlier COCO 80-class detection | course14 scripts reuse course13 model-export and Model Zoo environments | [Vision workflow](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md). **Partially located:** the full history of course13 modifications, model processing, and tests is still missing |
| Earlier board bring-up/model experiments | A driver or algorithm present in later code does not establish which independent experiments were completed earlier | **To obtain:** early conversations, actual project inventory, and change records; confirm which work feeds into this topic rather than including items merely because names are similar |

## 1. Vision models from PC to N6

The following entries belong to the [vision project](https://github.com/fan-gu-hao/stm32n6-instance-segmentation). Details and original materials are in its [work index](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md). All entries are located; gaps in original temporary operation scripts are listed later.

| Work | Implementation and engineering purpose | Main public materials |
| --- | --- | --- |
| Original-model baseline | Confirm YOLOv8n-seg classes, boxes, and masks; check image and webcam operation | `docs/pc_baseline.md`, `scripts/pc_webcam.sh` |
| Model format conversion | Upstream pretrained `.pt` → ONNX → onnx2tf → SavedModel/TFLite | `results/checkpoints/2026-09-09/logs/03_export_seg.log` |
| ST INT8 quantization | Per-channel quantization using calibration images, distinguishing exporter INT8 from the production ST INT8 model | `configs/yolov8n_seg_int8_int8.yaml`, `04_st_quantization_seg.log` |
| Interfaces and three-model comparison | Check shapes, types, scales, and zero points; compare original, float TFLite, and ST INT8 | `results/quantization/`, `scripts/check_seg_models_pc.sh`, `results/pc_tflite_check/` |
| Postprocessing output adaptation | Modify the Model Zoo configuration generator to identify detection/mask prototypes by shape and check classes, coefficients, types, and size conditions | `patches/modelzoo_seg_output_mapping.patch`, `tools/model_zoo_overrides/` |
| Automatic pre-generation checks | Check 80 classes, 1344 candidates, 32 mask coefficients, 64×64 prototypes, quantization parameters, and model hash | `scripts/check_n6_seg_header.py`, `results/deployment_precheck/` |
| Local generation workflow patches | Pass Neural-ART profiles, memory pools, input/output formats, and correctly quoted arguments | `patches/modelzoo_n6_local_benchmark.patch`, `scripts/n6_benchmark_local.sh` |
| NPU compilation/configuration | ST Edge AI generates internal ONNX/quantization information from TFLite; Neural-ART then produces model code, weights, and command data | `results/checkpoints/2026-09-09/n6_deployment/`, `docs/session_2026-09-09.md` |
| Runtime/linker integration | Match generated code, runtime library, command sections, and postprocessing working memory | Firmware `.cproject`/linker script, `patches/a1_source_20260918/dependencies.json` |
| Boot image and board deployment | Correct image-header/alignment arguments, select ST-LINK, build, write, and retain results | `patches/instance_segmentation_signing_alignment.patch`, `scripts/deploy_n6_seg.sh` |

There are two distinct ONNX stages: original-model export and internal ST compiler conversion. The quantized model's INT8 input and the N6-generated UINT8/NHWC interface are also documented as separate layers. Postprocessing adaptation is engineering work; NMS and mask reconstruction still use ST's core and are not described as newly invented algorithms.

## 2. Vision system, debugging, and validation

| Work | Completed and retained content | Public entry and version boundaries |
| --- | --- | --- |
| Camera/display integration | Continuous display capture, single-shot model capture, synchronous inference, postprocessing, LCD, and cache maintenance | Vision `firmware/` and work index; the production vision project uses a main loop and interrupt callbacks |
| Structured serial output | FRAME/DET/END, class/confidence/box/mask-pixel statistics, and shared frame sequence numbers | `patches/uart_inference_result.patch` |
| Person-region state machine | Bottom-center-of-box test, consecutive-frame entry/exit, counters, and display state | `project_region_event.h`, region-event patch |
| Validity and fault handling | Check objects, coordinates, and scores; clear stale boxes, report invalidity, and stop publishing on timeout/error | Region module and A5; invalidity is not normal exit, and manual reset is required |
| Performance instrumentation | Frame sequence, capture timing, inference/postprocessing/UART/display/cache/full-cycle timing, and log cost | `docs/a3_performance_20260918/instrumentation/` |
| UART interrupt experiment | Ring queue, whole-line submission, reserved important-message space, short critical sections, barriers, callbacks, statistics, and HAL dependency fixes | [Historical C/H, two installers, deployment/rollback](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/docs/publication_supplement_20261113/uart_it); not adopted in production, with no separate speedup conclusion |
| A1 sources and rebuild | Pinned upstream, modification/addition/deletion and dependency records; isolated source restoration, clean rebuild in the existing environment, and flash readback | `docs/a1_reproducible_20260918/`; the isolated restoration directory was used for source checks, not a build in that directory |
| A2 fixed input and numerical diagnosis | Identical pixels, raw tensors, quantization error, separate box/score/coefficient analysis, and PC backend differences | `docs/a2_validation_20260918/`, supplementary `a2/` |
| A2 boxes/masks and 50-image regression | Shared postprocessing, one-to-one matching, annotations and worst cases, exclusion of overlapping images, and false-positive/negative analysis | Same materials; no claim of pixelwise board-C postprocessing equivalence or full COCO accuracy |
| A3 performance analysis | Complete cycles with/without people, repeated inference after warm-up, block analysis, output checks, and timing sources | `docs/a3_performance_20260918/`; model-call and end-to-end timing are separate |
| A4 memory experiment | Change npuRAM6 capacity with other settings fixed; compare physical pools, time both versions, and regress outputs | `docs/a4_memory_20260918/`; the experimental configuration did not replace production camera firmware, and tiny timing differences are not called speedups |
| A5 cold boot and state tests | Cold boot, sequence synchronization, controlled entry/exit, and display checks | `docs/a5_acceptance_20260919/`; applies only to the vision project |
| A5 long runs and fault injection | Retain first-run anomalies, analyze sequences, and retest; simulate capture-notification timeout in software, restore production image, and verify it | Same materials and supplementary `a5/`; first-run root cause remains undetermined and failure records are preserved |

## 3. Audio data from board to training set

| Work | Implementation | Located public entry |
| --- | --- | --- |
| Standalone recording firmware | Adapt official playback example to five-second RAM recording; DMA half/full copying, warm-up, timeout, errors, length, and CRC32 | [Recording FSBL and upstream diff](../kws/recording_firmware/README.en.md) |
| RAM startup/debugging | ELF/BIN, stack/entry vector checks, version string, loading, core state, breakpoints, and detach | [Host tools](../kws/recording_tools/README.en.md) |
| Recording protocol/receiver | Exclusive serial access, query/start handshake, fixed length, trailer, timeout, CRC32, WAV format, and clipping statistics | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| Labeled collection | cup/bottle/phone/unknown/silence plan, source/session metadata, format checks, and resume after interruption | [collect_n6.py](../kws/collect_n6.py) |
| Segmentation/grouping | Locate speech by short-time energy, one-second clips with padding, neighboring-utterance boundaries; group originals before cutting clips | [prepare_dataset.py](../kws/prepare_dataset.py) |
| Continuous capture port | MDF/GPDMA circular links, clocks/access attributes, DMA caches, ring buffer, and sliding windows | [finder_mic.c](../firmware/Src/finder_mic.c) |
| Raw live-window return | Matching PCM, INT8 features, and model outputs, hexadecimal chunks, and CRC32 for layered comparison | [finder_kws.c](../firmware/Src/finder_kws.c) |
| Live-data iteration | Collection manifest, labels, train/holdout usage, and per-clip PCM hashes | [48-clip manifest](evidence/development-history/live_dataset_manifest_20261008.json) |

## 4. KWS from features to NPU

| Work | Implementation | Located public entry |
| --- | --- | --- |
| Python frontend | Mean removal, Hann window, FFT, HTK Mel, logarithm, DCT, normalization, and saved coefficients | [Final training](../kws/training_snapshot/train_kws.py) |
| Custom five-class network | 49×13×1 input, depthwise-separable convolutions, augmentation, class weights, and training records | Same source, [initial version and evolution](../kws/training_history/README.en.md) |
| Live-misclassification improvement process | Compare early silence errors, add live speech/noise, constrain augmentation by utterance boundaries, and retain retraining versions | [History](../kws/training_history/README.en.md), [live comparison](evidence/development-history/live_comparison_20261007.json) |
| Leakage prevention | Group original recordings, merge groups sharing identical PCM and reject label conflicts, reject development/holdout overlap, and use fold-training data only for normalization/background noise | [Grouped training](../kws/training_snapshot/train_kws_groupcv.py) |
| Five-fold/final training | Stratified grouped five-fold validation, epoch selection, and final training; separate held-out audio evaluation | [Cross-validation and holdout reports](evidence/README.en.md) |
| INT8 export | Representative data, scales/zero points, model/frontend coefficients, and float/quantized results | `export_int8`, [training snapshot](../kws/training_snapshot/README.en.md) |
| N6 generation | Dedicated network name and memory pool; TFLite → ST internal ONNX/quantization information → Neural-ART | [Configuration](../kws/deployment/README.en.md), [original compiler records](evidence/development-history/README.en.md) |
| C frontend/interface | CMSIS-DSP floating-point FFT, Mel/DCT, normalization then INT8 quantization; shape/type and scale/zero-point checks | [finder_kws.c](../firmware/Src/finder_kws.c), [coefficient table](../firmware/Inc/finder_kws_tables.h) |
| CPU/NPU coherence | Handle stale caches before writes and clean afterward; wait for asynchronous inference and reset the next invocation's state | Same source; KWS preprocessing is not entirely fixed-point |
| Layered comparison | Fixed INT8 INPUT tests the model; identical PCM tests the C frontend; compare three paths for live windows | [Comparison code](../firmware/Src/finder_kws.c), [results and evidence boundaries](results.en.md) |

Five-fold results are development/epoch-selection data; the held-out test is 16 single-window clips. Grouping original recordings does not constitute cross-speaker validation. Earlier comparison and final grouped models retain distinct hashes, and results are not pooled across them.

## 5. Dual-model system integration

| Work | Implementation | Located public entry |
| --- | --- | --- |
| Framework adaptation | Use ST's hand dual-model FreeRTOS framework as the base and connect YOLO/KWS | [Provenance](source-provenance.json), [app.c](../firmware/Src/app.c) |
| Shared NPU | Poll KWS and run YOLO sequentially within one inference task, with separate display/ISP tasks | `nn_thread_fct` / `dp_thread_fct` / `isp_thread_fct` |
| Camera-input adaptation | Replace upstream hand-model aspect-ratio handling with a central square scaled to the model input | [app_cam.c](../firmware/Src/app_cam.c) |
| Target selection/voice acceptance | Three objects, amplitude/score/margin, consecutive windows, command interval, quiet re-arming, and USER1 operation | `finder_voice_poll`, `finder_select_target` |
| Cross-task consistency | Target generations reject stale results after switching; consecutive-frame box IoU, mask snapshots, and display mutex | [app.c](../firmware/Src/app.c) |
| Memory/build | Application SRAM, display/postprocessing PSRAM, vision command region, dedicated KWS RAM/Flash; link MDF, DSP, and both models | [Linker script](../firmware/Gcc/STM32N657xx.ld), [build fragment](../firmware/mks/kws.mk) |
| Diagnostics/degraded behavior | Startup/inference errors, voice/search state, capture statistics, and manual-selection paths | [app.c](../firmware/Src/app.c), [finder_mic.c](../firmware/Src/finder_mic.c) |

Vision runs continuously while voice changes the target. Interleaving three tasks does not mean two models occupy the NPU simultaneously. Low-level clocks, AXISRAM, GPU2D, RIF, UART, and FreeRTOS startup largely reuse upstream code. Selection, adaptation, and integration are part of this work; the entire framework is not described as independently rewritten.

### Integration details to make explicit in the published code

This code was already public. The review adds engineering explanations, not firmware functionality. Fault-related descriptions below describe source-code design, not newly performed fault-injection tests.

| Detail | Handling and purpose shown in code | Code entry |
| --- | --- | --- |
| Shared clocks | Preserve PLL2, set only the IC8 divider to 61, and check the MDF clock to add capture to the running system | [finder_mic_start](../firmware/Src/finder_mic.c) |
| Peripheral access/DMA | PE2/PE8, MDF security/privilege and DMA permissions; read the high 16 bits of DFLTDR; align descriptors/buffers to 64/32 bytes | Same source |
| Audio snapshot ownership | Callbacks maintain caches/barriers before publishing ring positions; one-second snapshots handle wraparound and are discarded if delayed until overwrite is possible | `receive_block`, `finder_mic_take` |
| RAM startup diagnostics | Check vectors/entry and Boot ROM state, set core registers; main/MicLine and error breakpoints retain failure diagnostics; clean up debug processes | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| Linux receiver reliability | File locking and serial exclusivity, nonblocking reads, monotonic deadlines, integrity checks, endianness, and restoration of settings on exit | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| Feature numerical format | Handle real-FFT DC/Nyquist storage correctly; quantize only after floating-point Mel/log/DCT processing | [encode_mfcc](../firmware/Src/finder_kws.c) |
| Training-group integrity | Merge groups with identical PCM rather than deleting all duplicate rows; check five-class coverage, disjoint groups, and exactly one validation occurrence per item | [make_splits and related functions](../kws/training_snapshot/train_kws_groupcv.py) |
| Camera/model buffers | Invalidate the camera buffer's cache, copy into the model input, clean cache, then return the camera buffer, separating next-frame capture from model-input lifetime | [nn_thread_fct](../firmware/Src/app.c) |
| Model/display mask isolation | Copy postprocessing masks into a result snapshot; the display task takes a drawing snapshot under lock, then draws outside it | `nn_thread_fct`, `dp_thread_fct` |
| Crop/display coordinates | Take a central square from the same display field of view, map boxes/masks back into the LCD square, and handle mask boundaries/transparency | [app_cam.c](../firmware/Src/app_cam.c), [Display_NetworkOutput](../firmware/Src/app.c) |
| Voice-error isolation | Runtime capture/classification errors disable voice and display an error; vision/button paths can continue. This does not claim automatic recovery or cover initialization assertion failures | `finder_voice_poll`, `nn_thread_fct`, `dp_thread_fct` |
| Manual fallback/debounce | USER1 rising edge and 200 ms interval, sharing the target-selection interface with voice | `dp_thread_fct`, `finder_select_target` |
| DSP compilation consistency | Use the same compilation settings for FFT and frontend objects to match this version's CMSIS-DSP path | [kws.mk](../firmware/mks/kws.mk); not described as a custom FFT implementation or MVE optimization |

Upstream comparison also confirms that `main.c` changes focus on model headers and startup information, while `FreeRTOSConfig.h` matches the ST base. Three tasks, static allocation, camera queues, and some interrupt handoffs already existed upstream. This version adds the audio/vision application and new data/state handoffs. This attribution preserves the actual integration contribution without overstating authorship of low-level components.

## 6. Freeze, IDE, and public delivery

| Work | Retained content | Coverage |
| --- | --- | --- |
| Five-image roles | FSBL, application, vision weights, KWS weights, and vision commands; addresses/hashes and separate ELF section extraction | [Workflow](engineering-workflow.en.md), [sources and evidence](evidence/development-history/README.en.md). Five images are not five models |
| Existing build/writes | Final build report, application/KWS weight writes, and verification | [Deployment records](evidence/development-history/deployment_20261008/). Located |
| Pre-archive rebuild comparison | Original README records an isolated temporary rebuild, application differences limited to build-time characters, and identical vision commands | **Partially located:** this is an existing document statement; full original comparison logs were not located in the supplied materials, and it is not described as a new retest |
| Source/version archiving | Original firmware/vision sources, model versions, training snapshot, integrated local Git, frozen package, and hashes | [Provenance](source-provenance.json), [training snapshot](../kws/training_snapshot/README.en.md); public and complete local archive scopes differ |
| IDE source synchronization | Linked resources, path checks, preview, backup, hash-based concurrency checks, atomic replacement, and compiler entry | [Sync tool](../tools/ide/README.en.md), [build notes](build.en.md) |
| Publication preparation | Attribution, code guide, evidence index, model/image publication scope, commits, and synchronization | [Material inventory](publication-review.en.md), [third-party notices](../THIRD_PARTY_NOTICES.en.md) |
| Demonstration video | Planned recording of integrated-system operation | Pending; tests of other versions do not replace it |

The standalone recording example's FSBL sources and the official prebuilt boot FSBL used by the integrated system are distinct materials. Publishing the former does not provide complete build sources for the latter. No-key image-header packaging is not described as a cryptographic signature.

## Historical materials still to obtain

| Gap | Available content | Missing content and checking method |
| --- | --- | --- |
| All project conversations | Current conversation, partial summaries, attachments, and public records | Complete original STM32N6 project chats including execution results; distinguish proposals, executed work, failures, fixes, and abandoned approaches |
| Setup and course13 | Later environment versions and inherited environment paths in course14 | Actual early-project inventory, course13 Model Zoo changes, and materials in unspecified directories; guessed folder names cannot establish completeness |
| Temporary terminal programs | Settings, methods, and results for export/quantization, A1–A5, and KWS coefficient generation/reception/analysis | Unsaved original terminal programs must be recovered from full conversations or existing records; later reconstructions must be labeled as such |
| Fixed INPUT/PCM comparison | Board comparison code, PC reference.json, and existing summary | Original line-by-line board CMP logs; PC reference JSON cannot replace board output |
| Early audio/training runs | Recording/segmentation tools, four training-source versions, final evaluation, and live manifest | Earliest launcher/receiver logs, original segmentation manifest, and full intermediate-training results; code presence does not establish every run's outcome |
| Earlier three-image writes and pre-archive rebuild | Original README records 2026-10-04 three-image writes and pre-archive checks; final application/KWS logs are public | Earlier write logs and original full rebuild comparisons; strengthen the evidence level only after locating each |

The earlier 67-item collection script scanned matching extensions at the course13/course15 roots, then recursively scanned specified scripts, tools, configs, patches, and docs directories. The report contains no course13 file entries and explicitly excluded Model Zoo and other directories. It is not a complete inventory of the STM32N6 workspace. A specified directory's absence does not imply no engineering work occurred at that stage.

No training, builds, flashing, or hardware acceptance tests were added. Model weights, raw recordings, generated model code, and prebuilt images remain under the established publication scope; withholding those artifacts does not mean the work is undocumented. Further historical completion will extend this page using actual original text and files obtained, rather than treating the current number of located items as the project's total.
