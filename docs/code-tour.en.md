# Code tour and implementation highlights

[繁體中文](code-tour.md) | [English](code-tour.en.md)

Start with the [complete engineering workflow](engineering-workflow.en.md) for the cross-stage development context, then follow the code entries below. This tour covers host tools, data, models, and the board-side system.

## 1. From recording to training data

| Program/function | Reading focus |
| --- | --- |
| [Standalone recording main.c](../kws/recording_firmware/FSBL/Src/main.c): MicRecord / MicCopy / MicCrc32 | Five-second RAM recording, warm-up, DMA half/full callbacks, 12-second timeout, error state, length, and CRC32; interrupts copy samples while the main loop transmits |
| [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) | ELF/BIN and vector-table checks; RAM loading; MSP, PC, xPSR, and mask-register setup; main/MicLine checkpoints; debug-session cleanup |
| [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py): capture / save | Exclusive serial access, handshake retries, deadline-based reads, audio header, exact byte count, trailer, and CRC32; WAV format and clipping statistics |
| [collect_n6.py](../kws/collect_n6.py) | Five-class recording plan, resuming completed work, format and source metadata |
| [prepare_dataset.py](../kws/prepare_dataset.py): speech_regions / extract_word | Short-time energy, utterance gaps, neighboring-word boundaries, and zero padding; grouping original recordings before cutting one-second clips |

The host tools carry forward the course15 recording work. They still require the matching recording firmware; see the [tool documentation](../kws/recording_tools/README.en.md).

The standalone recorder's [FSBL sources, IDE snapshot, and upstream diff](../kws/recording_firmware/README.en.md) are preserved for comparison with the later continuous capture driver.

## 2. Features, training, quantization, and data isolation

Start with features, augment, and build_model in the [final train_kws.py](../kws/training_snapshot/train_kws.py):

- A periodic Hann window, HTK Mel scale, natural logarithm, and orthonormal DCT produce 49×13 features.
- Gain variation, bounded time shifts, background noise, and signal-to-noise augmentation preserve utterance content.
- Depthwise-separable convolutions, batch normalization, global average pooling, and a five-class output.

Next read the [final train_kws_groupcv.py](../kws/training_snapshot/train_kws_groupcv.py):

| Function | Engineering focus |
| --- | --- |
| load_development | Create groups by original recording; detect overlap with held-out audio using PCM SHA-256; merge groups with identical PCM and check label conflicts |
| make_splits | Stratified grouped five-fold splits; five-class coverage in every fold, disjoint groups, and exactly one validation occurrence per item |
| make_training | Use only the fold's training data for normalization, background-noise selection, and augmentation; apply class weights |
| fit_model | Save training history, models, and epoch-selection results |
| export_int8 | Representative-data calibration, INT8 TFLite export, frontend coefficients, quantization scales, and zero points |
| main / metrics | Aggregate five folds, choose the final training duration, train the final model, and evaluate separately held-out audio |

[train_kws_live_v3.py](../kws/train_kws_live_v3.py) retains a live-data iteration; the [snapshot notes](../kws/training_snapshot/README.en.md) identify the final sources. Historical scripts preserve their original environment dependencies and are not plug-and-play packages for arbitrary directories.

The [training history](../kws/training_history/README.en.md) adds the earliest original script and describes code differences from fixed shifts/background augmentation to utterance-boundary constraints, live samples, and grouped validation.

## 3. Audio driver, DMA, and ring buffer

In [finder_mic.c](../firmware/Src/finder_mic.c), finder_mic_start configures the MDF1 clock, GPIO, digital filtering/decimation, and a circular linked list on GPDMA1 Channel6.

HAL_MDF_AcqHalfCpltCallback / HAL_MDF_AcqCpltCallback process 256 samples per callback. receive_block first handles DMA/CPU cache coherence, skips warm-up blocks, writes into the 32,768-sample ring buffer, and publishes the write position after a memory barrier.

finder_mic_take obtains the latest 16,000-sample snapshot with a 3,200-sample hop. Ring wraparound is handled with two copies. If copying is delayed long enough for data to be overwritten, the snapshot is discarded. Error callbacks and interrupt entries are retained in the same file.

## 4. C frontend, NPU interface, and comparison tools

[finder_kws.c](../firmware/Src/finder_kws.c) includes both production inference and development comparisons:

| Function/section | Reading focus |
| --- | --- |
| Static assertions and finder_kws_init | Check input/output counts, shapes, INT8 types, and quantization parameters from training versus generated code |
| encode_mfcc | DC removal, a 480-sample window/320-sample hop, 512-point real FFT, power spectrum, 40 Mel filters, 13-dimensional DCT, normalization, clipping, and quantization |
| kws_begin_input_update | Clean the NPU's 64-byte cache lines before the CPU writes new input, invalidate the CPU's stale copy, and issue a barrier |
| prepare_input_cache | After writing, clean using CPU-cache-line alignment so the NPU can read the input |
| finder_kws_classify | Asynchronous execution state and event waiting, separate MFCC/model timing, quantized-output reading, and preparation for the next inference |
| finder_kws_compare | Test inference directly with reference INT8 features, then frontend plus inference with reference PCM; report input_diff, input_max, output_max, and CMP_Q |
| finder_kws_live_capture / live_send | Select windows by audio energy and return matching PCM, actual INT8 features, and outputs with offsets and CRC32 |

The [comparison switches](../firmware/Inc/finder_kws_compare.h) are disabled in the final version. Code is retained to explain the deployment-validation method used during development. Frontend coefficients and reference data are in [finder_kws_tables.h](../firmware/Inc/finder_kws_tables.h) and [finder_kws_compare_data.h](../firmware/Inc/finder_kws_compare_data.h).

## 5. Dual models, real-time tasks, and state consistency

[app.c](../firmware/Src/app.c) divides responsibilities among nn_thread_fct, dp_thread_fct, and isp_thread_fct. The inference task runs KWS and YOLO sequentially. Counting semaphores hand off camera buffers, while a mutex and mask snapshots coordinate display data.

finder_voice_poll implements the acceptance state machine: peak amplitude, score, score margin, consecutive hits, minimum interval, and re-arming after quiet windows. finder_select_target updates the target and generation number. If the target changes during inference, old results cannot overwrite the new state. Vision uses the target class and consecutive-box IoU to determine FOUND.

Vision input adaptation, Model Zoo patches, and earlier conversion evidence are covered in the [engineering workflow](engineering-workflow.en.md). This version uses official NMS/mask reconstruction as its core; application code adds target selection, result confirmation, coordinate drawing, and display integration.

## 6. Startup, memory, code generation, and build

- [main.c](../firmware/Src/main.c): clock, NPU, CPU cache, external memory, UART, and operating-system initialization.
- [app_cam.c](../firmware/Src/app_cam.c): camera pipelines and model-input interface.
- [Linker script](../firmware/Gcc/STM32N657xx.ld): application SRAM, vision command Flash, display/postprocessing PSRAM, and reserved KWS RAM.
- [KWS generation settings](../kws/deployment/README.en.md): separate model name, RAM/Flash addresses, and Neural-ART options.
- [Makefile](../firmware/Makefile), [ai.mk](../firmware/mks/ai.mk), [kws.mk](../firmware/mks/kws.mk): linking models, runtime, CMSIS-DSP, and firmware, with separate extraction of vision command data.
- [IDE build entry](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh): project-relative paths, GCC_PATH, and compiler-version checks.

Some model working memory is allocated at absolute addresses by generated code and must be checked against the memory pools and generation reports. The linker's KWS_RAM usage alone omits these allocations.

[Original generation and deployment evidence](evidence/development-history/README.en.md) records the ST tool's internal ONNX stage, quantization metadata, 11 hardware and 1 software execution stages, memory allocation, and existing write verification. The [IDE synchronization tool](../tools/ide/README.en.md) additionally demonstrates path validation, backups, concurrent-configuration-change detection, and atomic updates.

## Sources and contributions

The project uses ST examples, HAL/BSP, CMSIS-DSP, FreeRTOS, camera middleware, STAI/ATON, and official postprocessing. Engineering contributions include the data workflow, model training/quantization, deployment-interface patches, driver integration, cache coherence, task coordination, tooling, and validation described above. Each entry links to actual code.

Generated coefficients and generated model code are identified as artifacts; their configuration, export, and consistency checks belong to the deployment workflow. Upstream reuse and this project's engineering work are both documented in the [publication inventory](publication-review.en.md).
