# Dual-model voice object finder: from data collection to N6 deployment

[繁體中文](engineering-workflow.md) | [English](engineering-workflow.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](toolchain-compatibility.en.md).

This project builds a Keyword Spotting (KWS) and YOLOv8 instance-segmentation system on STM32N6570-DK. The workflow covers requirements and project setup, YOLO conversion and firmware migration, camera/postprocessing/display integration, speech data and MFCC preprocessing, custom KWS training and INT8 quantization, shared-NPU firmware, memory allocation, numerical debugging, final deployment, and demonstration.

The [complete 32-step development workflow](development-steps.en.md) follows implementation from requirements through the hardware demonstration. The [step-to-source inventory](development-source-map.json) maps each step to code, configuration, and records. This page retains development stages, model integration, and deployment details; host-side comparison, data-collection, and deployment programs are preserved as [historical workflow sources](../tools/development-history/README.en.md).

Vision continuously processes the camera image; the voice commands cup, bottle, and phone change the search target. Both models use the NPU sequentially in one inference task, with separate display and ISP tasks. The [implementation and evidence index](development-coverage.en.md) maps each step to code, configuration, and results.

See [dual-model memory and deployment](memory-deployment.en.md) for the full runtime/storage address map, and [toolchain compatibility](toolchain-compatibility.en.md) for pinned upstream versions, actual build commands, and packaging changes.

## Development sequence and stage-specific results

The project first established the vision application, then added a KWS model trained on collected data, and finally addressed real-time recognition and deployment issues. Earlier vision/recording projects and attempts that were not adopted are covered in the [original-history review](original-history-review.en.md); results remain attributed to the project and model version that produced them.

| Development stage | Work completed | Relationship to the final system |
| --- | --- | --- |
| Preceding recording dependency | course15 established N6 recording firmware and host reception tools | course17 reused this recording entry point for data collection; the recorder sources and tools it depends on were subsequently included in this repository |
| Vision generation | Create course17, pin the official segmentation example and ST quantized YOLO source, generate code in its own `vision/` tree, match Runtime1201, build, and package | Completes this project's vision generation and reference-application build |
| Main application | Base `firmware/` on the official dual-model hand example, bring in generated YOLO code, adapt postprocessing, center cropping, target selection, memory, and task handoffs; build the vision application and record board operation | Completes the main application's vision build; voice control had not yet been integrated at this stage |
| Data and initial KWS | Record five classes, segment/group source recordings, compute MFCCs, train, and export INT8 | The initial training source is retained separately from the later final grouped version |
| KWS core and capture integration | KWS generation, C features/model interface, dedicated memory, CMSIS-DSP build integration, continuous MDF/DMA capture, and voice acceptance state | Progress from a buildable core to the live dual-model system; compilation alone does not establish recognition performance |
| Deployment and numerical debugging | Investigate the black screen and core fault, inspect payload offsets and restore `0x400` alignment; compare fixed features, identical PCM, and live windows between PC and board | Retain the packaging failure, feature/output comparisons, and silence-to-phone misclassification as distinct outcomes |
| Data iteration and freeze | Add live data, prevent leakage, run grouped five-fold/held-out evaluation, deploy final KWS, and retain two accepted instances of each command | Corresponds to the validation table below; that run's vision messages have found=0, while earlier vision FOUND records are separate |
| After freezing: engineering delivery | Prepare IDE source access, build paths, provenance, code guides, training/deployment evidence, and readable public sources | Demonstration video and untested items keep explicit status |

## Functional requirements, project setup, and model responsibilities

Development steps **1–2** define the on-board interaction and establish separate vision, firmware, and speech-data/training directories.

| Stage | Work completed in this project | Implementation |
| --- | --- | --- |
| Functional requirements and project organization | Run speech and vision inference on STM32N6570-DK; cup/bottle/phone select the target while the LCD shows search state, boxes, and masks. Keep vision reference, main firmware, and speech workflows in `vision/`, `firmware/`, and `kws/` | [Architecture](architecture.en.md), [project setup workflow](../tools/development-history/vision_01_prepare_vision.sh) |
| Platform and application framework | Pin GCC, ST Edge AI, Neural-ART, and runtime versions; adapt ST's dual-model FreeRTOS framework to speech and vision models | [Build environment](build.en.md), [provenance](source-provenance.json), [app.c](../firmware/Src/app.c) |
| Speech-data collection subsystem | Five-second MDF/DMA recording, RAM startup, UART handshake and CRC32, WAV storage, labeled collection, and segmentation | [Recording firmware](../kws/recording_firmware/README.en.md), [host tools](../kws/recording_tools/README.en.md), [collect_n6.py](../kws/collect_n6.py) |
| KWS model development | Collect five-class data, implement MFCC and depthwise-separable convolutions, apply augmentation and grouped cross-validation, and export INT8 | [Training snapshot](../kws/training_snapshot/README.en.md), [training evolution](../kws/training_history/README.en.md) |
| Dual-model deployment/integration | Generate N6 code for YOLOv8 and KWS, pair the shared runtime, and port model/postprocessing interfaces; allocate model memory and implement shared-NPU scheduling and search state | [Vision deployment](../vision/deployment/README.en.md), [KWS deployment](../kws/deployment/README.en.md), [app.c](../firmware/Src/app.c), [linker script](../firmware/Gcc/STM32N657xx.ld) |

## Step-by-step vision generation, firmware migration, and search display

This stage establishes a working vision application before adding the speech model, covering development steps **3–11**. The sequence below follows model conversion, artifact handoff, image processing, and memory allocation.

| Step | Work and engineering focus | Implementation to read |
| --- | --- | --- |
| 3. YOLO conversion and N6 generation | Pin the YOLOv8n-seg input, fingerprint, Neural-ART settings, and memory pool; run ST Edge AI in this project's `vision/` tree to generate network code, interfaces, weights, and execution commands, then compile, link, and package the reference application | [Generation and build workflow](../tools/development-history/vision_03_generate_and_build_vision.sh), [vision generation settings](../vision/deployment/README.en.md) |
| 4. Match inference support components | Align Network Runtime **12.0.0** from the vision reference and **11.0.0** from the main framework to **12.0.1**; update headers, libraries, and NPU support sources together while retaining the FreeRTOS abstraction and asynchronous wait/completion handling | [Reference runtime alignment](../tools/development-history/vision_02_match_vision_runtime.py), [main runtime alignment](../tools/development-history/vision_06_match_main_runtime.py), [ai.mk](../firmware/mks/ai.mk) |
| 5. Transfer artifacts and replace build entries | Move six vision artifacts into `firmware/Model/`; remove the palm/hand-landmark model build entries, adapt initialization and I/O pointers, and check tensor counts, shapes, types, and quantization parameters | [Six-artifact handoff](../tools/development-history/vision_05_copy_vision_artifacts.sh), [build-list changes](../tools/development-history/vision_07_update_model_build_list.py), [model-data adaptation](../tools/development-history/vision_11_adapt_model_data.py) |
| 6. Configure camera and model input | Configure DCMIPP display and inference paths; crop the central square from the displayed field of view, resize it to **256×256 RGB UINT8**, and establish the geometry between model input and LCD output | [app_cam.c](../firmware/Src/app_cam.c), [camera/memory configuration](../tools/development-history/vision_13_configure_camera_and_memory.py) |
| 7. Integrate instance-segmentation postprocessing | Connect ST's postprocessing core and YOLOv8 adapter to the **1×116×1344** detection tensor and **1×64×64×32** mask prototypes; integrate quantization information, box decoding, non-maximum suppression (NMS), and mask reconstruction | [Postprocessing import](../tools/development-history/vision_08_import_postprocessing.py), [YOLOv8 adapter](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c), [configuration](../firmware/Inc/postprocess_conf.h) |
| 8. Implement target search | Map cup, bottle, and phone to classes **41, 39, and 67**; choose the highest-confidence box for the current target and require **two consecutive frames with box IoU at least 0.30** before reporting FOUND; clear previous state when the target changes | [Search-application integration](../tools/development-history/vision_12_integrate_vision_application.py), [app.c](../firmware/Src/app.c) |
| 9. Display boxes, masks, and state | Map model coordinates to the LCD's central recognition area; keep result and drawing masks separately, copy snapshots while holding the display mutex, then draw outside the lock so subsequent postprocessing cannot overwrite displayed data | [Result/drawing snapshots in app.c](../firmware/Src/app.c), [data-handoff architecture](architecture.en.md) |
| 10. Correct interrupt and image handoffs | Coordinate images through buffer queues and counting semaphores; use `xSemaphoreTakeFromISR` and `portYIELD_FROM_ISR` in the interrupt path of `bqueue_get_free`; return camera buffers only after cache handling, copying, and model-input cache maintenance | [Queue/inference code in app.c](../firmware/Src/app.c), [interrupt/application integration](../tools/development-history/vision_12_integrate_vision_application.py) |
| 11. Allocate vision memory and split images | Reduce application SRAM from **1,535 KiB to 1,023 KiB**, ending at `0x34100000`; place vision commands in a separate region at `0x71380000` and large buffers in external PSRAM; extract application and command images separately to avoid address-gap inflation | [Linker script](../firmware/Gcc/STM32N657xx.ld), [Makefile](../firmware/Makefile), [memory layout and image boundaries](memory-deployment.en.md) |

**Six-artifact handoff:** `network.c`, `network.h`, `network_ecblobs.h`, `stai_network.c`, `stai_network.h`, and `network_data.xSPI2.bin`. These carry network code, model interfaces, vision execution commands, and weights. The handoff checks source completeness before moving them into the main application.

**Postprocessing and vision-stage results:** the model has 80 classes, 1,344 candidate locations, and 32 mask prototypes of 64×64. Confidence is **0.50**, NMS IoU is **0.40**, and at most **10** results are retained. ST's algorithms retain their attribution; this project adapts interfaces, parameters, builds, search state, and display data flow. The [vision application build workflow](../tools/development-history/vision_14_build_main_vision.py) and [board-operation record](evidence/development-history/finder_vision_20261004.log) retain build and operation results before KWS integration.

## Step-by-step audio, training, and board deployment

Initial collection used the [standalone recorder main.c](../kws/recording_firmware/FSBL/Src/main.c). DMA half/full callbacks skip warm-up blocks and copy samples into RAM; the main loop handles timeout, stopping DMA, CRC32, and serial transmission. These sources and the upstream diff are preserved alongside the host tools.

The following steps cover development stages **12–20**, from initial recordings through on-board model integration. Live-data retraining and final synchronization appear later in their own section.

| Stage | Work and engineering focus | Implementation to read |
| --- | --- | --- |
| Recording-firmware launcher | Find IDE debugging tools; check ELF/BIN, stack/entry vectors, and recording-version string; set core state after RAM loading, verify main/MicLine breakpoints, then detach | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| Recording transfer | Exclusive serial access, query handshake, recording start, fixed-length reads, timeout, trailer, CRC32, WAV format, and clipping statistics | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| Raw data collection | Record cup/bottle/phone/unknown/silence: 12 clips per command, 8 unknown, and 3 silence, totaling **47 five-second recordings** at **16 kHz, 16-bit mono**; check format, retain source/session metadata, and resume collection while skipping completed clips | [collect_n6.py](../kws/collect_n6.py) |
| Segmentation and grouping | Locate utterances by short-time energy and pad one-second clips without including adjacent words; split five-second source recordings before segmentation, producing **142 training and 49 validation clips** initially | [prepare_dataset.py](../kws/prepare_dataset.py) |
| Audio features | For 16,000 audio samples, remove the mean and use a **480-sample periodic Hann window, 320-sample hop, and 512-point FFT**; apply 40 HTK Mel filters, logarithm, and orthonormal DCT to produce **49×13×1 MFCC features**; derive normalization from training data and export frontend coefficients | [Final train_kws.py](../kws/training_snapshot/train_kws.py) |
| Custom KWS model | A depthwise-separable convolutional network with 49×13×1 input; five classes, augmentation, class weights, and training records | [Network and augmentation](../kws/training_snapshot/train_kws.py) |
| KWS quantization/export | Convert Keras/SavedModel to INT8 TFLite using representative data; save scales, zero points, frontend coefficients, and float/quantized results | [export_int8](../kws/training_snapshot/train_kws_groupcv.py), [held-out audio report](evidence/kws-int8-holdout.json) |
| N6 model generation | Dedicated KWS RAM/Flash, generation options, and network name; compile through the tool's internal ONNX stage and Neural-ART, then link alongside vision | [Generation configuration](../kws/deployment/README.en.md), [original commands/reports](evidence/development-history/README.en.md), [kws.mk](../firmware/mks/kws.mk) |
| Continuous capture integration | Configure MDF1 pins/filtering/decimation and IC8 division while preserving the shared PLL2; use circular GPDMA half/full callbacks, skip warm-up, and write a **32,768-sample ring buffer**. Extract the latest **16,000 samples** after at least **3,200 new samples**, nominally 200 ms subject to scheduling | [finder_mic.c](../firmware/Src/finder_mic.c) |
| CPU/DMA coherence | Align buffers/descriptors; clean/invalidate caches and use barriers; discard snapshots if copying is delayed until overwrite becomes possible | [cache_prepare / receive_block / finder_mic_take](../firmware/Src/finder_mic.c) |
| C frontend/model interface | Port MFCC with CMSIS-DSP real FFT, explicitly handle DC/Nyquist storage, normalize, clip, and quantize into **637 INT8 features**; use static workspaces and check model shapes, types, scales, and zero points | [finder_kws.c](../firmware/Src/finder_kws.c), [coefficient table](../firmware/Inc/finder_kws_tables.h) |
| CPU/NPU coherence | Before CPU input writes, handle NPU cache and stale CPU copies; clean CPU cache after writes; wait for asynchronous inference and reset state for the next invocation | [kws_begin_input_update / prepare_input_cache / finder_kws_classify](../firmware/Src/finder_kws.c) |

The complete KWS route is Keras/SavedModel → INT8 TFLite → ST Edge AI internal ONNX and quantization metadata → Neural-ART → N6. The [original generation log](evidence/development-history/codegen_20261008/codegen.log) preserves the internal ONNX filename and actual compiler invocation; this ONNX is an internal intermediate representation produced by the ST toolchain. Validation groups samples by original recording and PCM content, and its scope is those source groups; cross-speaker testing has not been performed.

## Real-time system, memory, and delivery

Development steps **17–21** connect the second model, capture, caches, and tasks; the build and IDE entries also cover steps **22 and 31**. The final image/boot handoff is detailed below.

| Work | Implementation | Entry |
| --- | --- | --- |
| Dual-model scheduling | One inference task polls KWS and runs YOLO sequentially on the shared NPU; display and ISP are separate tasks | [nn_thread_fct / dp_thread_fct / isp_thread_fct](../firmware/Src/app.c) |
| Camera/display coordination | DCMIPP display/inference pipelines, double input buffers, counting semaphores, display mutex, mask snapshots, and cache maintenance | [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c) |
| Target/state consistency | Switch class after an accepted voice command; reject pre-switch results using target generations; display FOUND after consecutive-box IoU confirmation | [finder_select_target and result publication](../firmware/Src/app.c) |
| Startup integration | Reuse ST clock, NPU, CPU-cache, external-memory, UART, display, and FreeRTOS startup and connect this project's models | [main.c](../firmware/Src/main.c) |
| Memory separation | Application SRAM, display/postprocessing PSRAM, separate vision-command region; reserved KWS RAM at 0x91FC0000/256 KiB and weight Flash at 0x70700000/64 KiB | [Linker script](../firmware/Gcc/STM32N657xx.ld), [KWS memory pool](../kws/deployment/kws.mpool) |
| Build integration | Both models, HAL MDF, CMSIS-DSP, and runtime; consistent FFT compilation settings; separate extraction of .flash_section | [Makefile](../firmware/Makefile), [kws.mk](../firmware/mks/kws.mk), [ai.mk](../firmware/mks/ai.mk) |
| IDE preparation | Source/header browsing links, existing-link checks, backups, concurrency checks, and atomic replacement; build entry supports GCC_PATH and checks GCC 14.3.1 | [Original sync tool](../tools/ide/README.en.md), [IDE project](../firmware/STM32CubeIDE/STM32N6570-DK/.project), [IDE build entry](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) |
| Freeze and delivery | Source versions, model/tool settings, training snapshot, local frozen five-image package, and existing write verification | [Provenance](source-provenance.json), [results](results.en.md), [build notes](build.en.md) |

KWS generation does not enable the epoch controller. The CPU executes model control flow while the NPU executes the corresponding hardware operations. Control code is linked into the main application and speech weights are allocated separately; there is no standalone KWS ecblob image. One inference task executes the two models sequentially, with control flow and weights linked according to their respective configurations.

The [final compiler report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt) records 11 hardware and 1 software Softmax stages, with 11,409 bytes of weights and 17,440 bytes of activations. These KWS compiler statistics are distinct from the complete integrated system's peak memory use.

The local delivery package divides the dual-model system into five images: FSBL, application, vision weights, KWS weights, and vision execution commands. Image packaging uses no-key mode (-nk), producing the header required for startup without a cryptographic signature.

## Packaging diagnosis, numerical comparison, and live behavior

Development steps **22–25** first establish correct image startup, then compare fixed inputs and live audio layer by layer to distinguish data/model behavior from command-acceptance conditions.

| Stage | Work and engineering focus | Implementation to read |
| --- | --- | --- |
| Startup and packaging diagnosis | Investigate a version with successful Flash verification but no display or serial output; compare ELF, raw binary, and packaged payload, confirm identical program content, correct the payload offset from **`0x240` to `0x400`**, then repackage, check alignment/content, and resume deployment | [Payload inspection](../tools/development-history/inspect_boot_payload.py), [alignment workflow](../tools/development-history/realign_and_flash_application.sh), [follow-up programming](../tools/development-history/retry_aligned_application_flash.sh) |
| Layered comparison/debugging | Test the model directly with fixed INT8 inputs, then the entire C frontend with identical PCM; compare input differences and quantized outputs | [finder_kws_compare](../firmware/Src/finder_kws.c), [comparison settings](../firmware/Inc/finder_kws_compare.h) |
| Live raw-data return | Return PCM, 637 INT8 features, and five outputs from the same window as hexadecimal chunks with CRC32 for PC comparison | [finder_kws_live_capture / live_send](../firmware/Src/finder_kws.c) |
| Diagnose live errors and missed commands | The same quiet window is classified as phone on both board and PC; bottle ranks first but does not meet the acceptance threshold. Compare peak amplitude, features, five scores, top-two margin, and clipping for the same window to separate data/model behavior from frontend or deployment problems | [Live comparison report](evidence/development-history/live_comparison_20261007.json), [diagnostic recording](../tools/development-history/record_voice_diagnostics.py) |
| Voice acceptance state machine | Require peak amplitude **≥2,500**, top score **≥90%**, a top-two margin **≥25 percentage points**, two consecutive qualifying windows, and a command interval **≥1,200 ms**; re-arm after two quiet windows and retain the last accepted command on the display | [finder_voice_poll](../firmware/Src/app.c) |

## Live-data iteration and final-model synchronization

Development steps **26–28**. Adding four live clips did not resolve the observed missed commands, so collection expanded by **48 board-captured clips**: **32** for development and **16** held out. The original 142 training clips, 49 validation clips, four earlier live clips, and 32 new clips form **227 development clips**; the original 49 are no longer an independent holdout.

| Stage | Work and engineering focus | Implementation to read |
| --- | --- | --- |
| Live-data iteration | Retain live-data retraining versions; select board windows by speech energy, add real background noise/live speech, and keep held-out data separate | [Live v3 training](../kws/train_kws_live_v3.py), [collection plan](../kws/live_collection_plan.json), [board capture](../firmware/Src/finder_kws.c) |
| Leakage prevention | Group by original recording; identify identical audio by PCM hash and merge groups; reject development/holdout overlap; derive fold normalization/background noise from training groups only | [load_development / make_splits / make_training](../kws/training_snapshot/train_kws_groupcv.py) |
| Grouped cross-validation | Complete stratified grouped five-fold validation with **224/227 INT8 results (98.68%)**; use the median **66 epochs** from fold selections **82, 28, 66, 9, and 79** to train on all 227 development clips; float and INT8 evaluations on 16 held-out clips both yield **15/16 (93.75%)** | [Final grouped training](../kws/training_snapshot/train_kws_groupcv.py), [five-fold report](evidence/kws-groupcv.json) |
| Synchronize the final model and frontend | Regenerate and update model code, weights, feature coefficients, quantization scales, and zero points together; input zero point changes from **8 to 7**. Disable development collection/comparison modes, build final firmware, and retain model hashes/settings | [Final generation](../tools/development-history/generate_groupcv_model.py), [installation/build](../tools/development-history/install_build_groupcv.py), [board coefficients](../firmware/Inc/finder_kws_tables.h) |
| Check final generated outputs | The original artifact check stopped because it also counted same-named files in the tool's working directory; restrict inspection to the final output directory, confirm the artifacts, then complete installation and building | [Generated-output inspection](../tools/development-history/inspect_groupcv_codegen.py), [KWS deployment settings](../kws/deployment/README.en.md) |

The [training history](../kws/training_history/README.en.md) additionally includes the original baseline training script, showing the progression from early augmentation through live samples and utterance-boundary constraints to the final grouped version. The [48-clip live manifest](evidence/development-history/live_dataset_manifest_20261008.json) retains the 32 training/16 held-out split and per-clip PCM hashes.

## Five images, boot handoff, and final deployment

Development steps **29–32** align generated-model allocation, firmware link addresses, and Flash programming locations, retain image lengths and hashes, and deploy the final update.

| Image | Storage location | Runtime role |
| --- | --- | --- |
| First-stage bootloader (FSBL) | Addresses embedded in `ai_fsbl.hex` | Prepare the loading environment and load the main application into SRAM |
| Application `finder_signed.bin` | Flash starting at `0x70100000` | Linked for execution in internal SRAM starting at `0x34000400`; contains FreeRTOS, peripherals, model control, and application logic |
| Vision weights `vision_weights.bin` | Flash starting at `0x70380000` | YOLO model weights |
| Speech weights `kws_weights.bin` | Flash starting at `0x70700000`, with 64 KiB reserved | KWS model weights |
| Vision commands `vision_commands.bin` | Flash starting at `0x71380000`, with 2 MiB reserved | Vision epoch-controller commands |

**Boot handoff:** Boot ROM loads the FSBL, which loads the main application from Flash into SRAM and transfers control. Application startup enters `main()`, starts the FreeRTOS scheduler, and then uses the initialization task to configure clocks, NPU, external memory, and peripherals before creating inference, display, and ISP tasks. [Main initialization](../firmware/Src/main.c) and [task creation](../firmware/Src/app.c) retain the actual sequence.

**Boundaries and update scope:** check the actual end of vision-weight content against the KWS start address; the entire upstream vision pool cannot be treated as available capacity in the dual-model application. The final update directly programs and verifies the **application and KWS weights**; the other three images retain their existing configuration. See the [final programming workflow](../tools/development-history/flash_groupcv.py), [image manifest](evidence/development-history/deployment_20261008/flash_manifest.json), [verification summary](evidence/development-history/deployment_20261008/flash_verified.json), and [complete memory layout](memory-deployment.en.md).

**Preservation and demonstration:** IDE source access, configurable-compiler build paths, source/configuration preservation, bilingual documentation, and GitHub publication are complete; the [hardware demonstration video](https://youtu.be/m7wET9g5u6k) is linked from the homepage. Standalone power and power-cycle startup remain recorded as not yet verified.

## Validation and version mapping

| Stage | Retained result | Applicability |
| --- | --- | --- |
| Vision application | Board records before KWS integration include FOUND results for cup and phone | [Vision-stage operation log](evidence/development-history/finder_vision_20261004.log); separate from final voice-acceptance records |
| Fixed five-class numerical comparison | One sample per class produces matching PC/board classifications through fixed-feature INPUT and raw-audio PCM paths; all 637 INT8 features per PCM sample match, with maximum output difference at most one quantized integer unit | [Fixed reference data](evidence/development-history/fixed_reference_20261007.json) and [original comparison results](original-history-review.en.md); applies to the earlier comparison version |
| Frontend/deployment comparison | Four live examples have identical PC/board INT8 features, with maximum integer output differences of 0, 0, 3, and 1 | [Original report for the earlier comparison model](evidence/development-history/live_comparison_20261007.json); fixed INPUT/PCM comparison code is also retained in the firmware |
| Model/data diagnosis | The same silence sample is classified as phone on the board, with PC feature input, and with the complete PC PCM frontend | The same comparison report retains the failure, separately from subsequent live-data improvements |
| Final grouped model | Five-fold development validation: 224/227 (98.68%); held-out INT8 audio: 15/16 (93.75%) | [Evaluation reports](evidence/README.en.md); folds serve development/epoch selection, while the holdout is 16 single-window offline examples |
| Final on-board operation | cup, bottle, and phone accepted twice each; all retained vision messages in that run have found=0 | [Final board-operation log](evidence/development-history/voice_groupcv_20261008.log); counts voice acceptance, separately from earlier vision FOUND records |
| Deployment | Successful writing and verification of the application and KWS weights | [Deployment manifests/logs](evidence/development-history/deployment_20261008/); other images retain their existing configured contents |

The [results page](results.en.md) distinguishes versions by model hashes and logs. The [hardware demonstration video](https://youtu.be/m7wET9g5u6k) is available; standalone power and cold boot of the dual-model system are not listed as tested passes.

This repository retains data-collection firmware and host tools, training evolution, comparison/live-capture code, model configurations, the integrated application, and [original evidence](evidence/development-history/README.en.md). HAL, BSP, CMSIS-DSP, FreeRTOS, ST inference runtime, and vision postprocessing retain upstream attribution. Publication scope for weights, raw audio, generated model code, and prebuilt images, together with build dependencies, is documented in the [third-party notices](../THIRD_PARTY_NOTICES.en.md) and [build notes](build.en.md).
