# Published contents, provenance, and build dependencies

[繁體中文](publication-review.md) | [English](publication-review.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](toolchain-compatibility.en.md).

This repository provides application, data-processing, model-training, firmware-integration, and deployment materials for the STM32N6 dual-model voice object finder. The main application is in `firmware/`; `kws/` contains the speech-data workflow, model training, recording firmware, and host tools; `vision/` retains the instance-segmentation reference sources used for vision deployment. The sections below identify code entry points, source attribution, and materials required for a complete build.

## What each part provides

| Part | Published contents | Reading entry |
| --- | --- | --- |
| Dual-model application | Sequential NPU use, voice acceptance, target changes, consecutive-frame confirmation, camera and LCD coordination | [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c) |
| Continuous audio and C frontend | MDF/circular DMA, ring-buffer windows, caches, MFCC, quantized interfaces, and layered comparisons | [finder_mic.c](../firmware/Src/finder_mic.c), [finder_kws.c](../firmware/Src/finder_kws.c) |
| Data-collection tools | Five-second recorder, RAM startup, serial reception, length and CRC32 checks | [Recording sources](../kws/recording_firmware/README.en.md), [host tools](../kws/recording_tools/README.en.md) |
| Data and training | Labeled recording, segmentation, source groups, features, augmentation, five-fold validation, and quantization | [collect_n6.py](../kws/collect_n6.py), [prepare_dataset.py](../kws/prepare_dataset.py), [training history](../kws/training_history/README.en.md), [final snapshot](../kws/training_snapshot/README.en.md) |
| Model deployment | Vision generation, runtime alignment, and postprocessing port; KWS network name, memory pools, generation command, internal ONNX stage, and compiler reports | [Vision/speech workflow](engineering-workflow.en.md), [KWS deployment settings](../kws/deployment/README.en.md), [generation records](evidence/development-history/README.en.md) |
| System build | Model/DSP build lists, memory regions, separate command image, and IDE entry | [Makefile](../firmware/Makefile), [kws.mk](../firmware/mks/kws.mk), [linker script](../firmware/Gcc/STM32N657xx.ld), [build notes](build.en.md) |
| Results and versions | Grouped evaluation, held-out audio, live comparisons, collection manifest, voice/vision logs, and write verification | [Results](results.en.md), [evidence index](evidence/README.en.md) |
| Development tools | IDE source synchronization, path checks, preview, backups, concurrency checks, and atomic replacement | [IDE tool](../tools/ide/README.en.md) |
| Host diagnostics and deployment workflows | Fixed-reference export, live audio/feature comparisons, field-data collection, final generation/installation, packaging, and write verification | [Development workflow sources](../tools/development-history/README.en.md), [provenance and publication changes](../tools/development-history/source-provenance.json) |

## The 32-step workflow and its source code

The [complete development workflow](development-steps.en.md) presents 32 steps covering requirements, vision generation and postprocessing, speech data and training/quantization, dual-model memory and real-time coordination, numerical diagnostics, data iteration, deployment, and demonstration. The [step-to-source inventory](development-source-map.json) maps each step to existing code, configuration, and results. The homepage also lists all 32 steps with direct code entry points.

This update adds [host-side workflows](../tools/development-history/README.en.md) previously embedded in development-conversation code blocks. Published files are extracted from the complete programs used at the time, retaining diagnostic-mode switching, reference-data preparation, collection, artifact synchronization, and deployment logic. Device identifiers are supplied through environment variables; provenance records preserve hashes of the original code block, extracted body, and public version, together with the changes. Existing core firmware, training sources, memory settings, and measurement records remain available.

Environment dependencies and historical execution status are documented per file. For example, final code generation and the subsequent output-search check are recorded separately, alongside the original follow-up correction. Availability of generated model code, weights, and prebuilt images remains explicit in the build-material and source inventories below.

## Engineering implementation and source attribution

Project implementation covers the five-class speech dataset and model, live-data iteration, Python/C frontend port, continuous audio capture, quantization-interface checks, CPU/DMA/NPU cache handling, vision generation and runtime alignment, camera interrupt-queue adaptation, joint model build, search state and inter-task data handoffs, memory layout, and deployment verification. The [code tour](code-tour.en.md) maps these to functions and files.

The KWS model was built, trained, and quantized for this project. Vision work runs N6 code generation for YOLOv8 and completes runtime pairing, artifact migration, and application integration. The generation-input record from 2026-10-04 points to an ST-published quantized TFLite; its pinned version, file hash, and conversion artifacts are documented in the [vision deployment records](../vision/deployment/README.en.md). ST's hand dual-model example supplies the FreeRTOS, camera, display, and inference-runtime base; ST's instance-segmentation example supplies the model interface and postprocessing. HAL, BSP, CMSIS-DSP, FreeRTOS, and STAI/ATON are upstream components. Their versions, original file headers, and license indexes are retained in [third-party notices](../THIRD_PARTY_NOTICES.en.md), [model sources](../sources.txt), and [source versions](source-provenance.json).

The standalone recorder used by labeled collection originally lived in `course15_n6_mic_test`. It is retained here as a data-collection dependency with its original version and upstream diff. Training and recording-IDE snapshots also retain their original path and environment assumptions, documented in each directory.

## Source materials and hashes

The [project source-material inventory](evidence/development-history/review_inventory.json) traces the sources and public locations of 25 dual-model materials and 23 recording-dependency materials. These 48 items count selected development materials; the total repository file count is separate. [Supplementary provenance](evidence/development-history/source_provenance.json) retains original/public hashes, path substitutions, and excerpt methods. [Evaluation provenance](evidence/provenance.json) traces final training and evaluation files.

Model comparisons, voice acceptance, and vision records are presented against their respective versions. Fixed PC reference JSON, board comparison code, and original serial logs are preserved separately; their purposes and results are described in the [test records](results.en.md).

Both original development conversations and their attachments were reviewed turn by turn on 2026-11-20 to document recording startup, vision generation, image alignment, fixed five-class comparisons, and model iteration. The [development history](original-history-review.en.md) labels actual terminal output, proposed fixes, and steps without reported execution results separately. Published material is limited to engineering summaries and necessary de-identified output excerpts; private conversation transcripts and early source archives are not included. The 48-item inventory retains its original file-review scope; conversation attachments are addressed separately in the development history.

## Material-integrity checks and documentation added on 2026-11-20

The check baseline is commit `cc42386d9dba5ee3896b9b1547de3fc125046b6b`. Of the 48 items in the existing source inventory, all 45 mapped repository files are present; the other three reference pinned STM32CubeN6 SDK sources. All 40 public-version SHA-256 values in the provenance records also match. Recorded source/public differences include path parameterization, device-identifier removal, and log excerpts. The [publication audit](evidence/publication_audit_20261120.json) records item-level results. The checks cover the inventoried custom application, data/training pipeline, and recording dependencies; a line-by-line review of third-party SDK code is outside this scope.

A static review of the full GCC/LCD source graph expanded 11 build files into 132 C/assembly sources: 128 are present, while four are the externally supplied YOLO/KWS generated sources. The corresponding model headers and include directories must also come from those external dependencies. Application/GCC support sources, all six finder headers, Runtime1201, and the NemaGFX library are present.

The [vision-generation script/configuration reference](../vision/deployment/README.en.md) provides three unmodified files from a pinned official commit, with hashes, sources, and licensing. Upstream reference snapshots and historical local artifacts are labeled separately. Bilingual [dual-model memory/deployment](memory-deployment.en.md) and [toolchain compatibility](toolchain-compatibility.en.md) pages explain allocation, version integration, and packaging corrections, with allocation tables and summaries on the homepage.

That update retained existing firmware and training behavior. Its Makefile change was limited to clarifying the comment about one model executing at a time; sequential NPU sharing remained unchanged. The recorded work covered sources, configuration, and documentation, without rerunning training, model generation, or hardware programming.

## Materials required for a complete build

The public repository provides sources, configuration, and engineering records. A complete build additionally requires matching vision/KWS generated code and weights, the corresponding runtime, and required SDK dependencies. Raw recordings and prebuilt flash images are not included. Final deployment pointers, image roles, addresses, and available hashes are preserved in the documentation and evidence.

Compiler/tool versions and build entry points are in the [build notes](build.en.md). The [hardware demonstration video](https://youtu.be/m7wET9g5u6k) is available. Documentation retains existing results, with firmware behavior and original test data kept at their frozen versions.
