# Code tour and implementation highlights

[繁體中文](code-tour.md) | [English](code-tour.en.md)

The project's engineering work covers speech-data and KWS model development, N6 code generation and deployment for YOLOv8 and KWS, the C frontend port and numerical comparisons, and coordination of continuous audio capture, vision inference, target state, and LCD rendering. This tour points directly to implementation functions: how data is acquired, how numerical behavior is checked, and how two models share the NPU, allocate memory, and coordinate real-time tasks.

See the [engineering workflow](engineering-workflow.en.md) for the overall sequence, [dual-model memory and deployment](memory-deployment.en.md) for the runtime/storage address map, and [toolchain compatibility](toolchain-compatibility.en.md) for version matching, actual build commands, and packaging changes.

## 1. From recording to training data

The recording pipeline turns board samples into training data with integrity checks, source metadata, and recording groups. Interrupts collect samples; the main loop and host tools handle transmission, validation, and storage, keeping serial transmission outside audio interrupts.

| Program/function | Reading focus |
| --- | --- |
| [Standalone recording main.c](../kws/recording_firmware/FSBL/Src/main.c): MicRecord / MicCopy / MicCrc32 | Five-second RAM recording, warm-up, DMA half/full callbacks, 12-second timeout, error state, length, and CRC32; interrupts copy samples while the main loop transmits |
| [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) | ELF/BIN and vector-table checks; RAM loading; MSP, PC, xPSR, and mask-register setup; main/MicLine checkpoints; debug-session cleanup |
| [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py): capture / save | Exclusive serial access, handshake retries, deadline-based reads, audio header, exact byte count, trailer, and CRC32; WAV format and clipping statistics |
| [collect_n6.py](../kws/collect_n6.py) | Five-class recording plan, resuming completed work, format and source metadata |
| [prepare_dataset.py](../kws/prepare_dataset.py): speech_regions / extract_word | Short-time energy, utterance gaps, neighboring-word boundaries, and zero padding; grouping original recordings before cutting one-second clips |

The host tools require the matching standalone recording firmware; see the [tool documentation](../kws/recording_tools/README.en.md). Data collection uses RAM loading, while deployment of the dual-model application uses the external-Flash boot procedure.

The standalone recorder's [FSBL sources, IDE snapshot, and upstream diff](../kws/recording_firmware/README.en.md) are preserved for comparison with the later continuous capture driver.

## 2. Features, training, quantization, and data isolation

The project builds a five-class KWS model with feature definitions, augmentation, network architecture, and quantized export in one training workflow. Start with features, augment, and build_model in the [final train_kws.py](../kws/training_snapshot/train_kws.py):

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

[train_kws_live_v3.py](../kws/train_kws_live_v3.py) retains a live-data iteration; the [snapshot notes](../kws/training_snapshot/README.en.md) identify the final sources. Running historical scripts requires tools and paths configured for their original environment dependencies.

The [training history](../kws/training_history/README.en.md) adds the earliest original script and describes code differences from fixed shifts/background augmentation to utterance-boundary constraints, live samples, and grouped validation.

## 3. Audio driver, DMA, and ring buffer

[finder_mic.c](../firmware/Src/finder_mic.c) integrates standalone recording into continuous audio input that operates alongside the vision system. finder_mic_start retains the existing system PLL2, configures the IC8 divider, and checks the MDF1 clock. It then sets up PE2/PE8, peripheral and DMA access attributes, digital filtering/decimation, and a circular linked list on GPDMA1 Channel6. The DMA descriptor and sample buffer are aligned to 64 and 32 bytes respectively.

HAL_MDF_AcqHalfCpltCallback / HAL_MDF_AcqCpltCallback process 256 samples per callback. receive_block first handles DMA/CPU cache coherence, skips 16 warm-up blocks, writes into the 32,768-sample ring buffer, and publishes the write position after a memory barrier.

finder_mic_take obtains the latest 16,000-sample snapshot after at least 3,200 new samples; the actual interval depends on DMA block delivery and inference-task scheduling. Ring wraparound is handled with two copies. If copying is delayed long enough for data to be overwritten, the snapshot is discarded. Error callbacks and interrupt entries are retained in the same file.

## 4. C frontend, NPU interface, and comparison tools

[finder_kws.c](../firmware/Src/finder_kws.c) ports the training frontend to C and checks frontend and model outputs in layers using fixed features, fixed audio, and live windows. Production inference and development comparisons share this interface. The frame, spectrum, power, and log_mel arrays are static to avoid placing them on the task stack. These shared workspaces are restricted to a single inference task.

| Function/section | Reading focus |
| --- | --- |
| Static assertions and finder_kws_init | Check input/output counts, shapes, INT8 types, and quantization parameters from training versus generated code |
| encode_mfcc | DC removal, a 480-sample window/320-sample hop, and 512-point real FFT; handle the separate DC/Nyquist storage locations, then compute the power spectrum, 40 Mel filters, 13-dimensional DCT, normalization, clipping, and quantization |
| kws_begin_input_update | Clean and invalidate the NPU's 64-byte cache lines before the CPU writes new input, invalidate the CPU's stale copy, and issue a barrier |
| prepare_input_cache | After writing, clean using CPU-cache-line alignment so the NPU can read the input |
| finder_kws_classify | Asynchronous execution state and event waiting, separate MFCC/model timing; the final Softmax runs on the CPU, so read its CPU-produced quantized output directly and prepare the next inference |
| finder_kws_compare | Test inference directly with reference INT8 features, then frontend plus inference with reference PCM; report input_diff, input_max, output_max, and CMP_Q |
| finder_kws_live_capture / live_send | Select windows by audio energy and return matching PCM, actual INT8 features, and outputs with offsets and CRC32 |

The [comparison switches](../firmware/Inc/finder_kws_compare.h) are disabled in the final version, with the development comparison code and reference data retained. Frontend coefficients and reference data are in [finder_kws_tables.h](../firmware/Inc/finder_kws_tables.h) and [finder_kws_compare_data.h](../firmware/Inc/finder_kws_compare_data.h).

## 5. Dual models, real-time tasks, and state consistency

[app.c](../firmware/Src/app.c) coordinates model execution and application state. nn_thread_fct calls stai_runtime_init once at startup, initializes the vision network_ctx, and invokes finder_kws_init to initialize the speech-specific context. Each model has its own generated name, context, and input/output pointers, linked to one runtime. The inference task polls KWS and runs YOLO in sequence, giving the models sequential NPU access. Asynchronous model calls use LL_ATON_OSAL_WFE when waiting and reset inference state after completion.

nn_thread_fct, dp_thread_fct, and isp_thread_fct handle inference, display, and image signal processor (ISP) updates respectively. The project corrects interrupt-context semaphore acquisition and task switching in the [camera input queue](../firmware/Src/app.c) with `xSemaphoreTakeFromISR` and `portYIELD_FROM_ISR`, and adds the model-data and target-state handoffs below. Vision runs continuously; speech changes the search target.

| Function/data | Integration work in this project |
| --- | --- |
| nn_thread_fct / nn_input_queue | Counting semaphores hand off camera buffers; invalidate cache, copy into model input, clean cache, and only then return the camera buffer |
| finder_voice_poll | Peak of at least 2500, score of at least 0.90, margin of at least 0.25 over the runner-up, two consecutive windows, and a 1200 ms minimum interval; re-arm after two quiet windows |
| finder_select_target / generation | Increment the generation and clear found state on a target change; reject stale results after inference and restart consecutive-hit accumulation |
| box_iou / FINDER_CONFIRM_FRAMES | Select the highest-confidence result of the requested class; require two consecutive frames with box IoU of at least 0.30 before reporting FOUND |
| result_mask / drawing_mask | Copy model output into a result snapshot; the display task takes a second drawing snapshot under the mutex, then draws outside the lock to avoid overwrite by later postprocessing |
| DCMIPP_PipeInitNn / Display_NetworkOutput | Take a central square from the LCD field of view and map boxes/masks back to the same square; render transparent overlays from non-maximum suppression (NMS) and mask-reconstruction results |
| dp_thread_fct | USER1 rising-edge detection and a 200 ms debounce interval share the speech target-selection interface; clean cache after drawing and swap foreground buffers |
| voice_error path in finder_voice_poll | Disable speech and show an error when capture/classification returns a runtime error, retaining code paths for vision and button operation |

## 6. Startup, memory, code generation, and build

- [main.c](../firmware/Src/main.c): connect this version's vision-model header and startup information to platform initialization.
- [app_cam.c](../firmware/Src/app_cam.c): camera pipelines and model-input interface.
- [Linker script](../firmware/Gcc/STM32N657xx.ld): application SRAM, vision command Flash, display/postprocessing PSRAM, and reserved KWS RAM.
- [KWS generation settings](../kws/deployment/README.en.md): separate model name, RAM/Flash addresses, and Neural-ART options.
- [Makefile](../firmware/Makefile), [ai.mk](../firmware/mks/ai.mk), [kws.mk](../firmware/mks/kws.mk): link both models, the runtime, MDF, and CMSIS-DSP, with consistent compiler settings for FFT and frontend objects. Exclude .flash_section from the application image and extract it separately as vision_commands.bin.
- [IDE build entry](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh): project-relative paths, GCC_PATH, and compiler-version checks.

The [final build log](evidence/development-history/deployment_20261008/build.log) can be read alongside the linker script:

| Region | Start/capacity | Usage reported by that link |
| --- | --- | ---: |
| Application SRAM | 0x34000400 / 1023 KiB | 535,544 bytes |
| Vision-command Flash | 0x71380000 / 2 MiB | 230,528 bytes |
| Application/display PSRAM | 0x91000000 / 16,128 KiB | 8,949,920 bytes |
| Reserved KWS RAM | 0x91FC0000 / 256 KiB | Reported as 0; generated code allocates at absolute addresses |

KWS activations use absolute addresses, with 17,440 bytes reported by code generation, so their usage must be read alongside the generation report; the linker reports 0 for that reserved region. KWS weights have a 64 KiB reservation at 0x70700000. Reserved capacity, linker usage, and model allocation describe different levels of static allocation.

[Original generation and deployment evidence](evidence/development-history/README.en.md) records the ST tool's internal ONNX stage, quantization metadata, 11 hardware stages and 1 CPU Softmax stage, memory allocation, and existing write verification. KWS control code is linked into the application; there is no separate KWS epoch-controller command blob. The [IDE synchronization tool](../tools/ide/README.en.md) additionally demonstrates path validation, backups, concurrent-configuration-change detection, and atomic updates.

## Validation scope

The function descriptions above document source-code implementations; measured numerical, training, and board-operation results are described in [results and version mapping](results.en.md). The speech error path is a source-level fault-isolation design. It has not undergone fault-injection testing and does not implement automatic recovery; it excludes initialization assertion failures and does not guarantee continued operation after a shared-hardware failure. Memory figures are static allocation and link records, rather than runtime measurements of whole-system peak memory.

## Engineering contributions and sources

The project's implementation covers the speech-data workflow, a KWS model trained and quantized for this application, N6 code generation and memory allocation for both models, the C frontend and numerical comparisons, model-interface and build integration, continuous audio capture, cache coherence, cross-task data and state coordination, and deployment tools. The entries above link directly to the corresponding code.

The platform uses ST examples, HAL/BSP, CMSIS-DSP, FreeRTOS, camera middleware, and STAI/ATON. Clock, NPU/AXISRAM, CPU cache, external-memory, GPU2D, access-attribute, UART, and operating-system initialization in `main.c`, together with the three static tasks and their priorities, come from the official framework; this project builds the model and application integration on that foundation. Vision uses ST's quantized YOLOv8 model and official NMS and mask reconstruction. The project supplies interface adaptation, target selection, and display integration.

Generated coefficients and generated model code are identified as artifacts; their configuration, export, and consistency checks belong to the deployment workflow. Source attribution is recorded in the [publication inventory](publication-review.en.md). Each component retains its original copyright and license; see [third-party sources and publication scope](../THIRD_PARTY_NOTICES.en.md).
