# Dual-model voice object finder: from data collection to N6 deployment

[繁體中文](engineering-workflow.md) | [English](engineering-workflow.en.md)

See [dual-model memory and deployment](memory-deployment.en.md) for the full runtime/storage address map, and [toolchain compatibility](toolchain-compatibility.en.md) for pinned upstream versions, actual build commands, and packaging changes.

This project builds a Keyword Spotting (KWS) and YOLOv8 instance-segmentation system on STM32N6570-DK. Its workflow covers data collection, MFCC preprocessing, custom-model training and INT8 quantization, N6 code generation, PC/board numerical comparisons, and audio, vision, and display integration under FreeRTOS.

Vision continuously processes the camera image; the voice commands cup, bottle, and phone change the search target. Both models use the NPU sequentially in one inference task, with separate display and ISP tasks. The [implementation and evidence index](development-coverage.en.md) maps each step to code, configuration, and results.

## Development sequence and stage-specific results

The project first established the vision application, then added a KWS model trained on collected data, and finally addressed real-time recognition and deployment issues. Earlier vision/recording projects and attempts that were not adopted are covered in the [original-history review](original-history-review.en.md); results remain attributed to the project and model version that produced them.

| Order/date | Work completed | Relationship to the final system |
| --- | --- | --- |
| Preceding recording dependency | course15 established N6 recording firmware and host reception tools | course17 reused this recording entry point for data collection; the recorder sources and tools it depends on were subsequently included in this repository |
| 2026-10-04: vision generation | Create course17, pin the official segmentation example and ST quantized YOLO source, generate code in its own `vision/` tree, match Runtime1201, build, and package | `vision_20261004_181810` records this project's own vision generation/reference-application build |
| 2026-10-04: main application | Base `firmware/` on the official dual-model hand example, bring in generated YOLO code, adapt postprocessing, center cropping, target selection, memory, and task handoffs; build the vision application and record board operation | `finder_vision_20261004_193031_265404` is the main application's vision build; USER1 selected targets at this stage, before voice control |
| 2026-10-05: data and initial KWS | Record five classes, segment/group source recordings, compute MFCCs, train, and export INT8 | The initial training source is retained separately from the later final grouped version |
| 2026-10-06: KWS core and capture integration | KWS generation, C features/model interface, dedicated memory, CMSIS-DSP build integration, continuous MDF/DMA capture, and voice acceptance state | Progress from a buildable core to the live dual-model system; compilation alone does not establish recognition performance |
| 2026-10-06 to 10-07: deployment/numerical debugging | Investigate the black screen and core fault, inspect payload offsets and restore `0x400` alignment; compare fixed features, identical PCM, and live windows between PC and board | Retain the packaging failure, feature/output comparisons, and silence-to-phone misclassification as distinct outcomes |
| 2026-10-07 to 10-08: data iteration and freeze | Add live data, prevent leakage, run grouped five-fold/held-out evaluation, deploy final KWS, and retain two accepted instances of each command | Corresponds to the validation table below; that run's vision messages have found=0, while earlier vision FOUND records are separate |
| After freezing: engineering delivery | Prepare IDE source access, build paths, provenance, code guides, training/deployment evidence, and readable public sources | Demonstration video and untested items keep explicit status |

## System setup and model responsibilities

| Stage | Work completed in this project | Implementation |
| --- | --- | --- |
| Platform and application framework | Pin GCC, ST Edge AI, Neural-ART, and runtime versions; adapt ST's dual-model FreeRTOS framework to speech and vision models | [Build environment](build.en.md), [provenance](source-provenance.json), [app.c](../firmware/Src/app.c) |
| Speech-data collection subsystem | Five-second MDF/DMA recording, RAM startup, UART handshake and CRC32, WAV storage, labeled collection, and segmentation | [Recording firmware](../kws/recording_firmware/README.en.md), [host tools](../kws/recording_tools/README.en.md), [collect_n6.py](../kws/collect_n6.py) |
| KWS model development | Collect five-class data, implement MFCC and depthwise-separable convolutions, apply augmentation and grouped cross-validation, and export INT8 | [Training snapshot](../kws/training_snapshot/README.en.md), [training evolution](../kws/training_history/README.en.md) |
| Dual-model deployment/integration | KWS generation, an existing quantized YOLO interface, ST postprocessing, memory separation, shared NPU access, and search state | [KWS deployment](../kws/deployment/README.en.md), [app.c](../firmware/Src/app.c), [linker script](../firmware/Gcc/STM32N657xx.ld) |

## Vision-model interface and postprocessing in this system

Vision uses the ST quantized model `yolov8n_256_quant_pc_ii_seg_coco-st.tflite`, whose source and hash are pinned in [sources.txt](../sources.txt). Its SHA-256 is `3316733125a5fb85d66ed33993627b5d293b3baceb348b137132071ca365ebd6`. On 2026-10-04 this project ran the official model-generation script in its newly created `vision/` tree, then integrated the generated artifacts and runtime into `firmware/`.

| Porting step | Changes and evidence |
| --- | --- |
| Pin reference sources | Segmentation example at `42f7d645f1ed61967a922defa4aa97b95d390b16`; model source at `176ecaa749b79a3f53ce077d2b14412fa45e81a0`. The main application separately uses hand-example commit `6c313001f69d3ddb1ffa7bd700aba74f9c11037b` (v2.2.0) |
| Generate vision code in this project | Run `generate-n6-model_STM32N6570-DK.sh` in `vision/Model/`; the tool reported ST Edge AI Core `4.0.1-20581` and STM32CubeAI `12.0.1-RC2`. User terminal output confirms generation, ELF linking, and image packaging |
| Match the GCC runtime | Change the reference application from Runtime1200 to Runtime1201, and the main application from Runtime1100 to `NetworkRuntime1201_CM55_GCC.a`; update `Inc`, `Lib`, and `Npu` together, retaining the FreeRTOS OS abstraction and asynchronous execution mode |
| Import artifacts and update the build | Bring `network.c/.h`, `network_ecblobs.h`, `stai_network.c/.h`, and weights into the main application; its [Makefile](../firmware/Makefile) compiles YOLO and removes the palm/landmark models and `Src/ld.c` from the build |
| Connect ST postprocessing | [ai.mk](../firmware/mks/ai.mk) includes the vision postprocessing core and `app_postprocess_iseg_yolo_v8_ui.c`; adapt model I/O, postprocessing configuration, and display data while retaining ST algorithm attribution |
| Repartition memory/images | Reduce application SRAM from 1535 KiB to 1023 KiB (`0x34000400–0x34100000`) to avoid model activations; collect vision commands as `.flash_blob` in `.flash_section` at `0x71380000` (2 MiB); place postprocessing buffers in the existing PSRAM `NOLOAD` section through `.psram_bss` |
| Extract and package separately | Use `objcopy` to exclude/extract only `.flash_section`, producing application and vision-command binaries without a large address-gap-filled image. The vision stage has four images: FSBL, application at `0x70100000`, vision weights at `0x70380000`, and commands at `0x71380000`; KWS weights later make five |
| Fix buffer acquisition in interrupts | Camera callbacks call `bqueue_get_free`. This project uses `xSemaphoreTakeFromISR` and `portYIELD_FROM_ISR` in interrupt context, retaining `xSemaphoreTake` in task context. Upstream already handled interrupt-side release of the ready semaphore; the added correction concerns acquisition of the free semaphore |

The main vision application's build recorded 351,240 bytes of SRAM, 230,528 bytes in the vision-command region, and 8,949,920 bytes of PSRAM. These belong to the **2026-10-04 version before KWS integration**, not the final dual-model memory footprint. Original execution outputs, version distinctions, and evidence limits are covered in the [original-history review](original-history-review.en.md); current build entry points are in the [build notes](build.en.md).

The resulting vision interface and search application are:

| Interface/processing | Integration |
| --- | --- |
| Camera input | Take a central square from the display field of view and resize it to `256×256 RGB UINT8`; check input size and type |
| Model outputs | Two INT8 tensors carry `1×116×1344` detection data and `1×64×64×32` mask prototypes; use the ST adapter to identify outputs and obtain quantization parameters |
| Postprocessing | Connect ST decoding, non-maximum suppression (NMS), and mask generation; confidence threshold 0.50, NMS IoU 0.40, and at most 10 results |
| Search target | Filter the 80-class result for cup=41, bottle=39, and cell phone=67; select the highest-confidence box and publish FOUND after two consecutive frames with box IoU at least 0.30 |
| Display adaptation | Map boxes/masks back to the central square on the LCD; retain mask snapshots so subsequent postprocessing cannot overwrite display data |

Integration entries are in [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c), the [postprocessing adapter](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c), and the [build list](../firmware/mks/ai.mk). NMS and mask reconstruction retain ST attribution; this project implements model connection, target/state management, coordinate adaptation, and cross-task data handoffs.

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

The complete KWS route is Keras/SavedModel → INT8 TFLite → ST Edge AI internal ONNX and quantization metadata → Neural-ART → N6. The [original generation log](evidence/development-history/codegen_20261008/codegen.log) preserves the internal ONNX filename and actual compiler invocation; this ONNX is an internal intermediate representation produced by the ST toolchain. Grouping here is by original recording and PCM content, not an unperformed cross-speaker validation.

The [training history](../kws/training_history/README.en.md) additionally includes the original 2026-10-05 script, showing the progression from early augmentation through live samples and utterance-boundary constraints to the final grouped version. The [48-clip live manifest](evidence/development-history/live_dataset_manifest_20261008.json) retains the 32 training/16 held-out split and per-clip PCM hashes.

## Real-time system, memory, and delivery

| Work | Implementation | Entry |
| --- | --- | --- |
| Dual-model scheduling | One inference task polls KWS and runs YOLO sequentially on the shared NPU; display and ISP are separate tasks | [nn_thread_fct / dp_thread_fct / isp_thread_fct](../firmware/Src/app.c) |
| Camera/display coordination | DCMIPP display/inference pipelines, double input buffers, counting semaphores, display mutex, mask snapshots, and cache maintenance | [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c) |
| Target/state consistency | Switch class after voice/button input; reject pre-switch results using target generations; display FOUND after consecutive-box IoU confirmation | [finder_select_target and result publication](../firmware/Src/app.c) |
| Startup integration | Reuse ST clock, NPU, CPU-cache, external-memory, UART, display, and FreeRTOS startup and connect this project's models | [main.c](../firmware/Src/main.c) |
| Memory separation | Application SRAM, display/postprocessing PSRAM, separate vision-command region; reserved KWS RAM at 0x91FC0000/256 KiB and weight Flash at 0x70700000/64 KiB | [Linker script](../firmware/Gcc/STM32N657xx.ld), [KWS memory pool](../kws/deployment/kws.mpool) |
| Build integration | Both models, HAL MDF, CMSIS-DSP, and runtime; consistent FFT compilation settings; separate extraction of .flash_section | [Makefile](../firmware/Makefile), [kws.mk](../firmware/mks/kws.mk), [ai.mk](../firmware/mks/ai.mk) |
| IDE preparation | Source/header browsing links, existing-link checks, backups, concurrency checks, and atomic replacement; build entry supports GCC_PATH and checks GCC 14.3.1 | [Original sync tool](../tools/ide/README.en.md), [IDE project](../firmware/STM32CubeIDE/STM32N6570-DK/.project), [IDE build entry](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) |
| Freeze and delivery | Source versions, model/tool settings, training snapshot, local frozen five-image package, and existing write verification | [Provenance](source-provenance.json), [results](results.en.md), [build notes](build.en.md) |

KWS generation does not enable the epoch controller. The CPU executes model control flow while the NPU executes the corresponding hardware operations. Control code is linked into the main application and speech weights are allocated separately; there is no standalone KWS ecblob image. One inference task executes the two models sequentially, with control flow and weights linked according to their respective configurations.

The [final compiler report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt) records 11 hardware and 1 software Softmax stages, with 11,409 bytes of weights and 17,440 bytes of activations. These KWS compiler statistics are distinct from the complete integrated system's peak memory use.

The local five-image package contains FSBL, application, vision weights, KWS weights, and vision execution commands; it is not five AI models. Image packaging uses no-key mode (-nk), so the header is not described as a cryptographic signature.

## Validation and version mapping

| Stage | Retained result | Applicability |
| --- | --- | --- |
| Frontend/deployment comparison | Four live examples have identical PC/board INT8 features, with maximum integer output differences of 0, 0, 3, and 1 | [Original report for the earlier comparison model](evidence/development-history/live_comparison_20261007.json); fixed INPUT/PCM comparison code is also retained in the firmware |
| Model/data diagnosis | The same silence sample is classified as phone on the board, with PC feature input, and with the complete PC PCM frontend | The same comparison report retains the failure, separately from subsequent live-data improvements |
| Final grouped model | Five-fold development validation: 224/227 (98.68%); held-out INT8 audio: 15/16 (93.75%) | [Evaluation reports](evidence/README.en.md); folds serve development/epoch selection, while the holdout is 16 single-window offline examples |
| Final on-board operation | cup, bottle, and phone accepted twice each; all retained vision messages in that run have found=0 | [2026-10-08 log](evidence/development-history/voice_groupcv_20261008.log); counts voice acceptance, separately from earlier vision FOUND records |
| Deployment | Successful writing and verification of the application and KWS weights | [Deployment manifests/logs](evidence/development-history/deployment_20261008/); other images retain their existing configured contents |

The [results page](results.en.md) distinguishes versions by model hashes and logs. A demonstration video remains pending; standalone power and cold boot of the dual-model system are not listed as tested passes.

This repository retains data-collection firmware and host tools, training evolution, comparison/live-capture code, model configurations, the integrated application, and [original evidence](evidence/development-history/README.en.md). HAL, BSP, CMSIS-DSP, FreeRTOS, ST inference runtime, and vision postprocessing retain upstream attribution. Publication scope for weights, raw audio, generated model code, and prebuilt images, together with build dependencies, is documented in the [third-party notices](../THIRD_PARTY_NOTICES.en.md) and [build notes](build.en.md).
