# STM32N6 Dual-Model Voice Object Finder

[繁體中文](README.md) | [English](README.en.md)

**Embedded AI, audio peripheral integration, model quantization and deployment, and FreeRTOS task coordination.**

On the STM32N6570-DK, a keyword spotting (KWS) model trained on a custom audio dataset selects a search target while YOLOv8 instance segmentation continuously processes the camera stream. Say `cup`, `bottle`, or `phone` to select the target. The LCD shows the target, search status, bounding box, and segmentation mask; the USER1 button provides manual selection.

Development spans model export, quantization, and Model Zoo patches in the earlier vision project; on-board audio capture, dataset preparation, custom KWS training, and Python/C numerical comparisons; and integration of two models sharing one neural processing unit (NPU). This page presents the implementation at each stage, with links to source code and original records.

**Recorded results:** **98.68% (224/227)** in five-fold development validation, **93.75% (15/16)** in INT8 evaluation on 16 held-out audio clips, and **zero** INT8 feature differences in four earlier board/PC comparisons. [Results and version scope](docs/results.en.md)

## Core implementation

| Engineering area | Work completed | Source code and evidence |
| --- | --- | --- |
| **Model conversion and quantization** | Converted original YOLO weights through ONNX and SavedModel to ST per-channel INT8; compared original, float, and quantized models and checked their interfaces | [Earlier vision model workflow](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md) |
| **Model Zoo and deployment patches** | Corrected detection/mask output mapping, checked generated headers, supplied local Neural-ART settings, and fixed image alignment | [Model Zoo patches and deployment code](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| **Audio peripherals and DMA** | Configured MDF clocks, pins, and access permissions; implemented circular DMA integration, cache maintenance, a ring buffer, and one-second sliding windows | [finder_mic.c](firmware/Src/finder_mic.c) |
| **Data collection toolchain** | Standalone recording firmware, RAM loading and vector checks, serial handshakes, CRC32, WAV storage, labeled collection, and energy-based segmentation | [Recording firmware](kws/recording_firmware/README.en.md), [host tools](kws/recording_tools/README.en.md), [dataset preparation](kws/prepare_dataset.py) |
| **Custom model and data quality** | MFCC, depthwise-separable convolutions, four training stages, augmentation, source-group merging, leakage prevention, five-fold validation, and INT8 export | [Training history](kws/training_history/README.en.md), [grouped training](kws/training_snapshot/train_kws_groupcv.py) |
| **Numerical porting and layered debugging** | C feature extraction, quantization-parameter contracts, CPU/NPU cache ordering, fixed-input/PCM comparisons, and live data return | [finder_kws.c](firmware/Src/finder_kws.c), [comparison records](docs/evidence/development-history/README.en.md) |
| **Task and state consistency** | Three cooperating tasks, sequential NPU use by two models, target generations, mask snapshots, voice acceptance state machine, and button fallback | [app.c](firmware/Src/app.c), [camera adaptation](firmware/Src/app_cam.c) |
| **Memory, build, and delivery** | Memory partitioning, separate model-command image, consistent DSP compilation settings, IDE source synchronization, and source/image hash traceability | [Linker script](firmware/Gcc/STM32N657xx.ld), [build fragment](firmware/mks/kws.mk), [IDE tool](tools/ide/README.en.md) |

## Model conversion, quantization, and postprocessing adaptation

### Complete vision deployment path

The earlier [vision instance-segmentation project](https://github.com/fan-gu-hao/stm32n6-instance-segmentation) completed:

**Upstream pretrained weights (PyTorch) → ONNX → onnx2tf/SavedModel → ST per-channel INT8 TFLite → ST Edge AI/Neural-ART → N6.**

- Checked the original model on images and a webcam, then compared the original model, float TFLite, and ST INT8. Model hashes, parameters, logs, and result images were retained.
- Modified the Model Zoo configuration generator to identify the `1×116×1344` detection output and `1×64×64×32` mask prototypes by tensor shape. Checks cover 80 classes, 1344 candidates, 32 mask coefficients, data types, and quantization parameters.
- Patched local code-generation arguments to pass Neural-ART profiles, memory pools, and input/output formats; matched generated code to the runtime library; and corrected image-header and alignment handling.
- Integrated ST postprocessing into the dual-model version, adding target-class filtering, consecutive-frame confirmation, and mapping of boxes and masks to display coordinates.

The quantization and tooling patches above are engineering results from the earlier project. This dual-model version uses the ST vision model recorded in [sources.txt](sources.txt), with the two model versions tracked separately. NMS and mask reconstruction use ST's implementation; this project's changes focus on output adaptation, deployment, and application integration.

### Custom-trained speech model

**On-board recording → segmentation and grouping → MFCC → Keras training → INT8 TFLite → ST internal ONNX/quantization metadata → Neural-ART → N6.**

KWS compilation uses a separate network name, memory pool, and quantized interface. The generation report records **11 hardware execution stages and 1 CPU Softmax stage**, with **11,409 bytes** allocated for weights and **17,440 bytes** for activations. These are KWS compiler allocation statistics. [Code-generation command and original reports](kws/deployment/README.en.md)

## From standalone recording to continuous audio input

The standalone recorder adapts the official MDF example to capture five seconds into RAM before sending it to the PC. DMA half/full callbacks skip warm-up blocks and copy samples; the main loop handles timeout, errors, recording length, and CRC32. Audio comes from the board's digital microphone through the multifunction digital filter (MDF).

The host launcher checks image size, initial stack pointer, and entry vector, then confirms startup through RAM loading and breakpoints. The receiver handles exclusive serial access, nonblocking reads, deadlines, handshakes, exact length, a trailer, and CRC32 before saving a complete WAV. The labeled collection tool supports resuming after interruption and retains source and session metadata.

For the dual-model system, capture runs continuously:

- **Shared clocks and permissions:** preserve the existing PLL2 and configure only the microphone IC8 divider; configure PE2/PE8 and MDF/DMA access attributes.
- **DMA and caches:** align circular-list descriptors and sample buffers to 64 and 32 bytes respectively. Callbacks maintain cache coherence and publish ring-buffer positions with a memory barrier.
- **Sliding-window consistency:** nominal 16 kHz sampling, 16,000 samples per window, and a new window about every 200 ms. Handle ring wraparound and discard a snapshot if copying is delayed long enough for data to be overwritten.

Code: [Standalone recorder and upstream diff](kws/recording_firmware/README.en.md) · [RAM launcher and receiver](kws/recording_tools/README.en.md) · [Continuous capture module](firmware/Src/finder_mic.c)

## Dataset engineering and KWS training evolution

The dataset contains five classes: `cup`, `bottle`, `phone`, `unknown`, and `silence`. Short-time energy locates utterances; neighboring-word boundaries constrain segmentation, and clips are padded to one second. Original recordings are grouped before segmentation so related clips from the same source remain in one group.

Training evolved from the initial version through live-data versions 2 and 3 to the final grouped cross-validation version:

- **Features and network:** 49×13×1 MFCC input, a depthwise-separable convolutional network, class weights, and INT8 export.
- **Live-data improvements:** add board-captured speech and background noise; apply gain, noise, and time shifts, limiting shifts by utterance boundaries to avoid cutting off words.
- **Leakage prevention:** identify identical PCM by hash and merge source groups; reject conflicting labels and development/holdout overlap. Each fold derives normalization and background noise only from its training partition.
- **Traceable evaluation:** check class coverage and group separation in each fold, select the final training duration through five-fold validation, and retrain. A separate live collection manifest records usage and hashes for 48 clips: 32 for training and 16 held out.

Code: [Segmentation and grouping](kws/prepare_dataset.py) · [MFCC and model](kws/training_snapshot/train_kws.py) · [Grouped validation and quantization](kws/training_snapshot/train_kws_groupcv.py) · [Version history](kws/training_history/README.en.md)

## Python/C numerical comparisons and fault localization

The board uses a CMSIS-DSP floating-point FFT, followed by Mel filtering, logarithms, and DCT, then normalization, clipping, and INT8 quantization. The port handles the real FFT's special DC/Nyquist storage layout and checks shapes, types, scales, and zero points at compile time and initialization.

Debugging has three layers: **test the model with fixed INT8 inputs → test the full C frontend with identical PCM → return live PCM, features, and outputs for PC recomputation.** In four earlier live windows, board and PC INT8 features matched exactly; maximum output integer differences were 0, 0, 3, and 1 respectively.

One silent window was classified as `phone` on all three paths: the board, PC inference from features, and the complete PC frontend. This localized that case to model/data behavior and supported later live-data iteration. The failed case and final-model results are retained separately.

Code: [Frontend, inference, and comparison tools](firmware/Src/finder_kws.c) · [Frontend coefficients](firmware/Inc/finder_kws_tables.h) · [Original comparisons and results](docs/results.en.md)

## FreeRTOS tasks and shared-resource integration

On the Cortex-M55, inference, display, and image signal processing (ISP) run as three cooperating tasks. **Vision runs continuously; voice changes the search target. KWS and YOLO use the NPU sequentially within one inference task.**

| Engineering problem | Implementation |
| --- | --- |
| Camera capture and inference share data | Copy the camera buffer into the model input and complete cache maintenance before returning the camera buffer, separating capture and inference data lifetimes |
| CPU/DMA/NPU may see different data | Maintain CPU cache after DMA reception; handle old NPU cache contents before the CPU writes new model input, then clean CPU cache after writing, with alignment and memory barriers |
| Target changes during inference | Check a target-generation number, discard stale results, and restart consecutive-hit accumulation |
| Postprocessing overwrites a mask being displayed | Copy model output into a result snapshot; the display task takes its own drawing snapshot under a mutex and draws outside the lock |
| Camera crop and LCD coordinates differ | Take a central square from the display field of view as the 256×256 model input, then map boxes and masks back to the corresponding LCD region |
| Repeated or unstable voice acceptance | Combine amplitude, score, score margin, two consecutive windows, a minimum interval, and re-arming after quiet windows |
| Transient bounding-box changes | Select the highest-confidence result of the target class and require two consecutive frames with box intersection over union (IoU) of at least 0.30 before displaying FOUND |
| Voice path returns a runtime error | Disable voice and display an error while retaining vision and USER1 selection paths; the button uses rising-edge detection and a 200 ms debounce interval |

The system reuses the startup, static-task, and camera framework from ST's dual-model hand example, adapting it to audio/vision models and the data/state handoffs above. Voice-error isolation describes the code design; it has not received a separate fault-injection test and does not cover initialization assertion failures.

Code: [Inference, display, and state machines](firmware/Src/app.c) · [Camera crop](firmware/Src/app_cam.c) · [CPU/NPU cache ordering](firmware/Src/finder_kws.c)

## Memory, build, and delivery

| Allocation | Location and purpose |
| --- | --- |
| Reserved KWS activation region | `0x91FC0000`, 256 KiB, separated from application/display PSRAM |
| Reserved KWS weight region | `0x70700000`, 64 KiB |
| Vision command region | `0x71380000`, 2 MiB, extracted separately from the ELF `.flash_section` |

These are reserved capacities; actual model allocations are checked separately in generation reports. Build fragments integrate MDF, CMSIS-DSP, both models, and the runtime, with consistent compilation settings for FFT and frontend objects. Delivery is split into five images: **FSBL, application, vision weights, KWS weights, and vision commands**, with addresses, model versions, source and image hashes, and existing write-verification records.

The IDE source synchronization tool checks existing links, previews changes, makes backups, detects concurrent changes by hash, and performs atomic replacement. The build entry supports `GCC_PATH` and checks GCC 14.3.1, separating IDE source browsing from the actual Makefile compilation list.

Code: [Linker script](firmware/Gcc/STM32N657xx.ld) · [Makefile](firmware/Makefile) · [KWS build](firmware/mks/kws.mk) · [IDE synchronization](tools/ide/README.en.md) · [Deployment evidence](docs/evidence/development-history/README.en.md)

## Recorded results and scope

| Item | Result | Evidence and interpretation |
| --- | --- | --- |
| Five-fold KWS development validation | **224/227, 98.68%** | [Cross-validation report](docs/evidence/kws-groupcv.json); used for development and epoch selection |
| INT8 evaluation on held-out audio | **15/16, 93.75%** | [Holdout report](docs/evidence/kws-int8-holdout.json); offline single-window evaluation on 16 clips, with one cup classified as phone |
| Earlier live deployment consistency | **Zero INT8 input-feature differences in all four cases** | [Comparison record](docs/evidence/development-history/live_comparison_20261007.json); used to diagnose numerical and porting issues |
| Final-version on-board voice record | **Two correct acceptances each for cup, bottle, and phone** | [Operation log](docs/evidence/development-history/voice_groupcv_20261008.log); vision records in that session all had `found=0`, so this row measures voice acceptance |
| Earlier vision-version record | CUP and PHONE produced `found=1` | [Vision log](docs/evidence/development-history/finder_vision_20261004.log); a different version from the final voice session |

The demonstration video is pending. Standalone power and cold boot of this dual-model version have not been listed as experimentally verified. [Full results and version mapping](docs/results.en.md)

## Earlier vision validation and historical experiments

Before dual-model integration, the [vision instance-segmentation project](https://github.com/fan-gu-hao/stm32n6-instance-segmentation) completed and published the following work:

| Stage | Work performed |
| --- | --- |
| A1: source and rebuild | Pinned upstream versions, retained changes and binary dependencies, restored sources in isolation, performed a clean rebuild in the existing environment, and verified flash readback |
| A2: correctness | Fixed pixels, raw-tensor numerical comparisons, shared box/mask postprocessing, backend-difference diagnosis, and 50-image regression |
| A3: performance | Pipeline timing, repeated inference after warm-up, block-level analysis, and serial/measurement-log overhead |
| A4: memory | Changed memory pools with other settings fixed, checked physical allocations, timed both versions, and verified byte-identical outputs on 50 images |
| A5: reliability | Cold boots, region events, long-run anomaly analysis and retesting, capture-notification timeout injection, and restoration of production firmware |
| UART interrupt experiment | Ring queue, whole-line submission, reserved space for important messages, HAL dependency fixes, two installer versions, deployment, and rollback |

These tests and experiments belong to the earlier project. The UART interrupt version and A4 experimental configuration are preserved as history; their adoption status in production vision firmware is documented separately. [Complete implementation and evidence index](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md)

## Documentation, build, and sources

- [Work and evidence from setup to freeze](docs/development-coverage.en.md): cross-stage results and early historical materials still to be obtained.
- [Code tour](docs/code-tour.en.md) and [architecture](docs/architecture.en.md): functions, execution flow, and configuration.
- [Engineering workflow](docs/engineering-workflow.en.md) and [original evidence](docs/evidence/development-history/README.en.md): model, data, deployment, and measurement records.
- [Build and external dependencies](docs/build.en.md): GCC 14.3.1, ST Edge AI 4.0.1, Neural-ART 1.1.3-275, CubeIDE 2.2.0, and dependencies.
- [Publication inventory](docs/publication-review.en.md) and [third-party sources](THIRD_PARTY_NOTICES.en.md): retained materials and licensing.

The public repository provides application and training sources, configurations, patches, and engineering evidence. Model weights, generated model code, raw audio, and prebuilt images are not included; a complete build requires the matching dependencies. HAL, BSP, CMSIS-DSP, FreeRTOS, the ST inference runtime, and vision postprocessing retain their upstream attribution. This project's data, training, adaptation, integration, debugging, and validation work is described above.
