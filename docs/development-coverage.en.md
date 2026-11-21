# Dual-model implementation and evidence index

[繁體中文](development-coverage.md) | [English](development-coverage.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](toolchain-compatibility.en.md).

This index covers platform and recording tools, vision-model generation, speech data and KWS training, numerical porting, dual-model integration, flashing, and freeze. Each stage links code, configuration, and results. Work overlapped, and sections are organized by engineering topic. See the [engineering workflow](engineering-workflow.en.md) for the full process and the [original development-history review](original-history-review.en.md) for version evolution, troubleshooting, and execution results.

## 0. System goals, platform, and model interfaces

| Work | Implementation | Code and configuration |
| --- | --- | --- |
| System behavior | Voice commands cup/bottle/phone select a target; vision runs continuously and the LCD shows search state, boxes, and masks | [app.c](../firmware/Src/app.c), [architecture](architecture.en.md) |
| Tools and runtime | GCC 14.3.1, ST Edge AI 4.0.1, Neural-ART 1.1.3-275, HAL 1.3.0, and FreeRTOS 10.6.2; configure model, MDF, and CMSIS-DSP build dependencies | [Build notes](build.en.md), [ai.mk](../firmware/mks/ai.mk), [kws.mk](../firmware/mks/kws.mk) |
| Application framework | Integrate KWS/YOLO, target state, and display data into ST's dual-model FreeRTOS/camera framework | [Provenance](source-provenance.json), [app.c](../firmware/Src/app.c) |
| Vision-model source | Select the ST quantized instance-segmentation model with a pinned source/SHA-256 and integrate its N6-generated/runtime interface | [sources.txt](../sources.txt), [model interfaces](engineering-workflow.en.md) |
| Vision generation/runtime alignment | Run ST Edge AI 4.0.1 vision generation and the reference build in this project; move six generated files into the application and align headers, libraries, and NPU support to Runtime 1201 | [Vision deployment](engineering-workflow.en.md), [original history](original-history-review.en.md) |
| Vision input/output | 256×256 RGB UINT8 input and two INT8 outputs; check shapes, types, pointers, and sizes, and connect detection/mask-prototype outputs | [app.c](../firmware/Src/app.c), [ST postprocessing adapter](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c) |
| Postprocessing/target selection | Connect ST decoding, non-maximum suppression (NMS), and mask generation, filter the three target classes, and add consecutive-frame confirmation and display mapping | [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c) |

## 1. Audio data from board to training set

| Work | Implementation | Code and evidence |
| --- | --- | --- |
| Standalone recording firmware | Adapt official playback example to five-second RAM recording; DMA half/full copying, warm-up, timeout, errors, length, and CRC32 | [Recording FSBL and upstream diff](../kws/recording_firmware/README.en.md) |
| RAM startup/debugging | ELF/BIN, stack/entry vector checks, version string, loading, core state, breakpoints, and detach | [Host tools](../kws/recording_tools/README.en.md) |
| Recording build/startup debugging | Add UART/UART_EX build links, reducing 14 errors to zero; distinguish verified RAM writes from actual execution and check GDB breakpoints, handshake, CRC32, and WAV playback | [Original history](original-history-review.en.md), [recorder source diff](../kws/recording_firmware/README.en.md) |
| Recording protocol/receiver | Exclusive serial access, query/start handshake, fixed length, trailer, timeout, CRC32, WAV format, and clipping statistics | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| Labeled collection | cup/bottle/phone/unknown/silence plan, source/session metadata, format checks, and resume after interruption | [collect_n6.py](../kws/collect_n6.py) |
| Segmentation/grouping | Locate speech by short-time energy, one-second clips with padding, neighboring-utterance boundaries; group originals before cutting clips | [prepare_dataset.py](../kws/prepare_dataset.py) |
| Continuous capture port | MDF/GPDMA circular links, clocks/access attributes, DMA caches, ring buffer, and sliding windows | [finder_mic.c](../firmware/Src/finder_mic.c) |
| Raw live-window return | Matching PCM, INT8 features, and model outputs, hexadecimal chunks, and CRC32 for layered comparison | [finder_kws.c](../firmware/Src/finder_kws.c) |
| Live-data iteration | Collection manifest, labels, train/holdout usage, and per-clip PCM hashes | [48-clip manifest](evidence/development-history/live_dataset_manifest_20261008.json) |

## 2. KWS from features to NPU

| Work | Implementation | Code and evidence |
| --- | --- | --- |
| Python frontend | Mean removal, Hann window, FFT, HTK Mel, logarithm, DCT, normalization, and saved coefficients | [Final training](../kws/training_snapshot/train_kws.py) |
| Custom five-class network | 49×13×1 input, depthwise-separable convolutions, augmentation, class weights, and training records | Same source, [initial version and evolution](../kws/training_history/README.en.md) |
| Live-misclassification improvement process | Compare early silence errors, add live speech/noise, constrain augmentation by utterance boundaries, and retain retraining versions | [History](../kws/training_history/README.en.md), [live comparison](evidence/development-history/live_comparison_20261007.json) |
| Leakage prevention | Group original recordings, merge groups sharing identical PCM and reject label conflicts, reject development/holdout overlap, and use fold-training data only for normalization/background noise | [Grouped training](../kws/training_snapshot/train_kws_groupcv.py) |
| Five-fold/final training | Stratified grouped five-fold validation, epoch selection, and final training; separate held-out audio evaluation | [Cross-validation and holdout reports](evidence/README.en.md) |
| INT8 export | Representative data, scales/zero points, model/frontend coefficients, and float/quantized results | `export_int8`, [training snapshot](../kws/training_snapshot/README.en.md) |
| N6 generation | Dedicated network name and memory pool; TFLite → ST internal ONNX/quantization information → Neural-ART | [Configuration](../kws/deployment/README.en.md), [original compiler records](evidence/development-history/README.en.md) |
| C frontend/interface | CMSIS-DSP floating-point FFT, Mel/DCT, normalization then INT8 quantization; shape/type and scale/zero-point checks | [finder_kws.c](../firmware/Src/finder_kws.c), [coefficient table](../firmware/Inc/finder_kws_tables.h) |
| CPU/NPU coherence | Handle stale caches before writes and clean afterward; wait for asynchronous inference and reset the next invocation's state | Same source; preprocessing uses floating-point arithmetic and quantizes model inputs to INT8 |
| Layered comparison | Fixed INT8 INPUT tests the model; identical PCM tests the C frontend; compare three paths for live windows | [Comparison code](../firmware/Src/finder_kws.c), [results and evidence boundaries](results.en.md) |

Five-fold results support development and epoch selection; the held-out test uses 16 single-window clips. Validation groups original recordings; cross-speaker validation is outside the recorded test scope. Earlier comparison and final grouped models retain distinct hashes, with results reported separately by model version.

## 3. Dual-model system integration

| Work | Implementation | Code and evidence |
| --- | --- | --- |
| Framework adaptation | Integrate the YOLO/KWS model and application interfaces using ST's hand dual-model FreeRTOS framework | [Provenance](source-provenance.json), [app.c](../firmware/Src/app.c) |
| Shared NPU | Poll KWS and run YOLO sequentially within one inference task, with separate display/ISP tasks | `nn_thread_fct` / `dp_thread_fct` / `isp_thread_fct` |
| Camera-input adaptation | Replace upstream hand-model aspect-ratio handling with a central square scaled to the model input | [app_cam.c](../firmware/Src/app_cam.c) |
| Camera interrupt queue adaptation | Correct interrupt-context semaphore acquisition and required task switching in the upstream queue with `xSemaphoreTakeFromISR` and `portYIELD_FROM_ISR` | [Camera input queue](../firmware/Src/app.c), [original history](original-history-review.en.md) |
| Target selection/voice acceptance | Three objects, amplitude/score/margin, consecutive windows, command interval, and quiet re-arming | `finder_voice_poll`, `finder_select_target` |
| Cross-task consistency | Target generations reject stale results after switching; consecutive-frame box IoU, mask snapshots, and display mutex | [app.c](../firmware/Src/app.c) |
| Memory/build | Application SRAM, display/postprocessing PSRAM, vision command region, dedicated KWS RAM/Flash; link MDF, DSP, and both models | [Linker script](../firmware/Gcc/STM32N657xx.ld), [build fragment](../firmware/mks/kws.mk) |
| Diagnostics/degraded behavior | Startup/inference errors, voice/search state, and capture statistics | [app.c](../firmware/Src/app.c), [finder_mic.c](../firmware/Src/finder_mic.c) |

Vision runs continuously while voice changes the target. Three tasks interleave, and one inference task runs the two models sequentially on the NPU. This project integrates the models, adapts camera input, manages targets, and implements cross-task data handoffs. Low-level clocks, AXISRAM, GPU2D, RIF, UART, and FreeRTOS startup largely reuse the ST framework.

### Data ownership, numerical handling, and fault paths

The following details describe buffer, peripheral, feature, and state handoffs. Voice-error isolation handles runtime capture/classification errors. Initialization assertion failures are outside its scope, and separate fault-injection validation has not been performed.

| Detail | Handling and purpose shown in code | Code entry |
| --- | --- | --- |
| Shared clocks | Preserve PLL2, set only the IC8 divider to 61, and check the MDF clock to add capture to the running system | [finder_mic_start](../firmware/Src/finder_mic.c) |
| Peripheral access/DMA | PE2/PE8, MDF security/privilege and DMA permissions; read the high 16 bits of DFLTDR; align descriptors/buffers to 64/32 bytes | Same source |
| Audio snapshot ownership | Callbacks maintain caches/barriers before publishing ring positions; one-second snapshots handle wraparound and are discarded if delayed until overwrite is possible | `receive_block`, `finder_mic_take` |
| RAM startup diagnostics | Check vectors/entry and Boot ROM state, set core registers; main/MicLine and error breakpoints retain failure diagnostics; clean up debug processes | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| Linux receiver reliability | File locking and serial exclusivity, nonblocking reads, monotonic deadlines, integrity checks, endianness, and restoration of settings on exit | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| Feature numerical format | Handle real-FFT DC/Nyquist storage correctly; quantize only after floating-point Mel/log/DCT processing | [encode_mfcc](../firmware/Src/finder_kws.c) |
| Training-group integrity | Retain rows sharing identical PCM and merge their source groups; check five-class coverage, disjoint groups, and exactly one validation occurrence per item | [make_splits and related functions](../kws/training_snapshot/train_kws_groupcv.py) |
| Camera/model buffers | Invalidate the camera buffer's cache, copy into the model input, clean cache, then return the camera buffer, separating next-frame capture from model-input lifetime | [nn_thread_fct](../firmware/Src/app.c) |
| Model/display mask isolation | Copy postprocessing masks into a result snapshot; the display task takes a drawing snapshot under lock, then draws outside it | `nn_thread_fct`, `dp_thread_fct` |
| Crop/display coordinates | Take a central square from the same display field of view, map boxes/masks back into the LCD square, and handle mask boundaries/transparency | [app_cam.c](../firmware/Src/app_cam.c), [Display_NetworkOutput](../firmware/Src/app.c) |
| Voice-error isolation | Runtime capture/classification errors disable voice and display an error while retaining vision; automatic recovery and initialization assertion failures are outside this handling scope | `finder_voice_poll`, `nn_thread_fct`, `dp_thread_fct` |
| DSP compilation consistency | Use the same compilation settings for FFT and frontend objects to match this version's CMSIS-DSP path | [kws.mk](../firmware/mks/kws.mk) |

This project connects model headers and startup information in `main.c`, corrects interrupt-context camera-queue semaphore handling in the application, and integrates audio/vision models with new data/state handoffs. The three tasks, static allocation, and camera queues use the ST framework; `FreeRTOSConfig.h` retains the ST base contents.

## 4. Freeze, IDE, and delivery

| Work | Retained content | Code and evidence |
| --- | --- | --- |
| Five-image roles | FSBL, application, vision weights, KWS weights, and vision commands; addresses/hashes and separate ELF section extraction | [Workflow](engineering-workflow.en.md), [sources and evidence](evidence/development-history/README.en.md) |
| Existing build/writes | Final build report, application/KWS weight writes, and verification | [Deployment records](evidence/development-history/deployment_20261008/) |
| Source/version archiving | Original firmware/vision sources, model versions, training snapshot, integrated local Git, frozen package, and hashes | [Provenance](source-provenance.json), [training snapshot](../kws/training_snapshot/README.en.md); public and complete local archive scopes differ |
| IDE source synchronization | Linked resources, path checks, preview, backup, hash-based concurrency checks, atomic replacement, and compiler entry | [Sync tool](../tools/ide/README.en.md), [build notes](build.en.md) |
| Publication preparation | Attribution, code guide, evidence index, model/image publication scope, commits, and synchronization | [Material inventory](publication-review.en.md), [third-party notices](../THIRD_PARTY_NOTICES.en.md) |
| Demonstration video | [Watch the hardware demonstration](https://youtu.be/m7wET9g5u6k) | Video provided; recorded measurements and version scope remain tied to their respective evidence |

This repository retains the standalone recording example's FSBL sources. The integrated system uses an official prebuilt boot FSBL, whose complete build sources are not included. The application image receives a boot header in no-key mode, without a cryptographic signature.

## 5. Results and version mapping

| Result | Material | Interpretation |
| --- | --- | --- |
| Earlier four-example live comparison | [live_comparison_20261007.json](evidence/development-history/live_comparison_20261007.json) | All INT8 feature differences are zero; maximum integer output differences are 0, 0, 3, and 1; this evaluates the numerical port |
| Fixed INPUT/PCM paths | [Comparison code](../firmware/Src/finder_kws.c), [PC reference](evidence/development-history/fixed_reference_20261007.json), [actual output retained in the original conversation](original-history-review.en.md) | Both paths classify all five classes correctly; each PCM case has 637 matching INT8 features. Maximum output integer differences are zero except for silence at one. This is a numerical consistency check on five fixed examples |
| Grouped-model five-fold validation | [kws-groupcv.json](evidence/kws-groupcv.json) | 224/227, 98.68%, used for development and epoch selection |
| Final INT8 held-out audio | [kws-int8-holdout.json](evidence/kws-int8-holdout.json) | 15/16, 93.75%, based on 16 single-window offline examples |
| Final on-board voice acceptance | [2026-10-08 operation log](evidence/development-history/voice_groupcv_20261008.log) | Each of three commands is accepted twice; this row counts voice acceptance. Vision has found=0 throughout the same run, with no recorded end-to-end object-finding success |
| Earlier vision-integration version within this project | [2026-10-04 vision log](evidence/development-history/finder_vision_20261004.log) | CUP and PHONE have FOUND records; this is a different version from the final voice log |
| Application/KWS-weight deployment | [flash_verified.json](evidence/development-history/deployment_20261008/flash_verified.json) | Retains successful write verification for two images; archive-copy hash checks are distinct from verification of board Flash |

See [results](results.en.md) for model versions, numerical comparisons, and operation results. Standalone power and cold boot are not listed as tested passes for this project. The public repository provides application/training code, tools, configuration, and evidence. Weights, raw audio, generated model code, and prebuilt images follow the [publication scope](../THIRD_PARTY_NOTICES.en.md); rebuilding requires the [documented dependencies](build.en.md).
