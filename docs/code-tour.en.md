# Code tour and implementation highlights

[繁體中文](code-tour.md) | [English](code-tour.en.md)

The project's engineering work covers speech-data and KWS model development, N6 code generation and deployment for YOLOv8 and KWS, the C frontend port and numerical comparisons, and coordination of continuous audio capture, vision inference, target state, and LCD rendering. This tour points directly to implementation functions: how data is acquired, how numerical behavior is checked, and how two models share the NPU, allocate memory, and coordinate real-time tasks.

See the [engineering workflow](engineering-workflow.en.md) for the overall sequence, [dual-model memory and deployment](memory-deployment.en.md) for the runtime/storage address map, and [toolchain compatibility](toolchain-compatibility.en.md) for version matching, actual build commands, and packaging changes.

The [complete 32-step development route](development-steps.en.md) follows requirements, vision deployment, speech data and models, real-time integration, debugging iterations, and delivery. The [step-to-source map](development-source-map.json) provides code, configuration, and result entry points for every step. This page explains the key functions and data handoffs in more detail.

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

## 7. Host-side comparison, data collection, and deployment code

Python workflows originally executed in the terminal are retained in [tools/development-history](../tools/development-history/README.en.md). They preserve the data handling, diagnostic-mode installation, build, and programming procedures used during development, separately from the frozen firmware. The directory documents each program's source, historical execution result, publication changes, and hashes.

| Steps | Host programs | What to inspect |
| --- | --- | --- |
| 2–5: vision-project setup and model deployment | [Prepare the vision project](../tools/development-history/vision_01_prepare_vision.sh), [run generation and build](../tools/development-history/vision_03_generate_and_build_vision.sh), [migrate six artifacts](../tools/development-history/vision_05_copy_vision_artifacts.sh), [pair the application runtime](../tools/development-history/vision_06_match_main_runtime.py) | Pin model/source versions, execute generation, pair the runtime, and bring network code, interfaces, weights, and commands into the application project |
| 6–11: vision application and memory migration | [Import postprocessing](../tools/development-history/vision_08_import_postprocessing.py), [integrate application/interrupt handoffs](../tools/development-history/vision_12_integrate_vision_application.py), [configure camera and memory](../tools/development-history/vision_13_configure_camera_and_memory.py), [build the application and images](../tools/development-history/vision_14_build_main_vision.py) | Retain the complete workflows that changed search logic, camera cropping, interrupt semaphores, linker sections, and build/packaging; frozen implementations are in the firmware files above |
| 22: boot-payload inspection and correction | [Inspect the payload](../tools/development-history/inspect_boot_payload.py), [realign and program](../tools/development-history/realign_and_flash_application.sh), [handle the read-only replacement follow-up](../tools/development-history/retry_aligned_application_flash.sh) | Compare raw and packaged program contents, locate the `0x240`/`0x400` mismatch, repackage and verify identical bytes, then handle replacement and deployment |
| 23: fixed-feature and audio comparisons | [Export fixed references](../tools/development-history/export_fixed_reference.py), [install board comparisons](../tools/development-history/install_fixed_comparison.py), [build and deploy the comparison version](../tools/development-history/build_flash_fixed_comparison.py) | Generate five-class PCM, INT8 features, and PC outputs from the same model and coefficients for the board's two comparison paths |
| 23–24: three-path live comparisons | [Install live capture](../tools/development-history/install_live_comparison.py), [build and deploy](../tools/development-history/build_flash_live_comparison.py), [receive and recompute on the PC](../tools/development-history/compare_live_windows.py) | Receive PCM, 637 actual features, and five outputs from the same window; check length, offsets, and CRC32, then compare the board with two PC inference paths |
| 24–25: field diagnostics | [Record command diagnostics](../tools/development-history/record_voice_diagnostics.py) | Retain prompted operation and serial output within one session to investigate command acceptance, misses, and quiet intervals |
| 26: live-data expansion | [Prepare collection mode](../tools/development-history/prepare_live_collection.py), [build and deploy collection firmware](../tools/development-history/build_flash_live_collection.py), [collect data](../tools/development-history/collect_live_dataset.py), [inspect the dataset](../tools/development-history/check_live_dataset.py) | Execute the 48-clip plan, check integrity, retain labels and usage, and separate 32 development clips from 16 held-out clips |
| 28: final-model generation and synchronization | [Generate the model](../tools/development-history/generate_groupcv_model.py), [inspect outputs](../tools/development-history/inspect_groupcv_codegen.py), [install and build](../tools/development-history/install_build_groupcv.py) | Connect training outputs to N6 generation, inspect formal outputs, back up and synchronize the model, coefficients, and quantization parameters, then disable development modes and build/package |
| 29–30: final deployment and operation records | [Program and verify](../tools/development-history/flash_groupcv.py), [record final operation](../tools/development-history/record_voice_groupcv.py) | Check image hashes and boot headers, update the application and KWS weights, and retain write verification, version pointers, and command-acceptance records |

The original generation workflow stopped its file check after the compiler completed because a recursive search found duplicate output names. The follow-up `inspect_groupcv_codegen.py` restricted inspection to the formal output directory. Both programs preserve the diagnosis and correction; their execution status is documented in the [historical-tool guide](../tools/development-history/README.en.md).

## Validation scope

The function descriptions above document source-code implementations; measured numerical, training, and board-operation results are described in [results and version mapping](results.en.md). The speech error path is a source-level fault-isolation design. It has not undergone fault-injection testing and does not implement automatic recovery; it excludes initialization assertion failures and does not guarantee continued operation after a shared-hardware failure. Memory figures are static allocation and link records, rather than runtime measurements of whole-system peak memory.

## Engineering contributions and sources

The project's implementation covers the speech-data workflow, a KWS model trained and quantized for this application, N6 code generation and memory allocation for both models, the C frontend and numerical comparisons, model-interface and build integration, continuous audio capture, cache coherence, cross-task data and state coordination, and deployment tools. The entries above link directly to the corresponding code.

The platform uses ST examples, HAL/BSP, CMSIS-DSP, FreeRTOS, camera middleware, and STAI/ATON. Clock, NPU/AXISRAM, CPU cache, external-memory, GPU2D, access-attribute, UART, and operating-system initialization in `main.c`, together with the three static tasks and their priorities, come from the official framework; this project builds the model and application integration on that foundation. Vision code generation for N6, runtime pairing, model interfaces, target selection, and display integration were completed in this project. Input-source versions and artifact handoffs are documented in the [vision conversion records](../vision/deployment/README.en.md). NMS and mask reconstruction retain ST postprocessing attribution.

Generated coefficients and generated model code are identified as artifacts; their configuration, export, and consistency checks belong to the deployment workflow. Source attribution is recorded in the [publication inventory](publication-review.en.md). Each component retains its original copyright and license; see [third-party sources and publication scope](../THIRD_PARTY_NOTICES.en.md).
