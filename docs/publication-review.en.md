# Published contents, provenance, and build dependencies

[繁體中文](publication-review.md) | [English](publication-review.en.md)

This repository preserves the application, data processing, model training, firmware integration, and deployment records for the STM32N6 dual-model voice object finder. The main application is in `firmware/`; `vision/` retains the adopted official instance-segmentation reference sources; `kws/` contains the speech-data workflow, training code, and recording dependencies.

## What each part provides

| Part | Published contents | Reading entry |
| --- | --- | --- |
| Dual-model application | Sequential NPU use, voice acceptance, target changes, consecutive-frame confirmation, camera and LCD coordination | [app.c](../firmware/Src/app.c), [app_cam.c](../firmware/Src/app_cam.c) |
| Continuous audio and C frontend | MDF/circular DMA, ring-buffer windows, caches, MFCC, quantized interfaces, and layered comparisons | [finder_mic.c](../firmware/Src/finder_mic.c), [finder_kws.c](../firmware/Src/finder_kws.c) |
| Data-collection dependencies | Five-second recorder, RAM startup, serial reception, length and CRC32 checks | [Recording sources](../kws/recording_firmware/README.en.md), [host tools](../kws/recording_tools/README.en.md) |
| Data and training | Labeled recording, segmentation, source groups, features, augmentation, five-fold validation, and quantization | [collect_n6.py](../kws/collect_n6.py), [prepare_dataset.py](../kws/prepare_dataset.py), [training history](../kws/training_history/README.en.md), [final snapshot](../kws/training_snapshot/README.en.md) |
| Model deployment | Vision generation, runtime alignment, and postprocessing port; KWS network name, memory pools, generation command, internal ONNX stage, and compiler reports | [Vision/speech workflow](engineering-workflow.en.md), [KWS deployment settings](../kws/deployment/README.en.md), [generation records](evidence/development-history/README.en.md) |
| System build | Model/DSP build lists, memory regions, separate command image, and IDE entry | [Makefile](../firmware/Makefile), [kws.mk](../firmware/mks/kws.mk), [linker script](../firmware/Gcc/STM32N657xx.ld), [build notes](build.en.md) |
| Results and versions | Grouped evaluation, held-out audio, live comparisons, collection manifest, voice/vision logs, and write verification | [Results](results.en.md), [evidence index](evidence/README.en.md) |
| Development tools | IDE source synchronization, path checks, preview, backups, concurrency checks, and atomic replacement | [IDE tool](../tools/ide/README.en.md) |

## Sources and implementation scope

ST's hand dual-model example supplies the FreeRTOS, camera, display, and inference-runtime base. ST's instance-segmentation example supplies interfaces and postprocessing for the selected vision model. HAL, BSP, CMSIS-DSP, FreeRTOS, and STAI/ATON reuse upstream components. Versions, original file headers, and license indexes are retained in [third-party notices](../THIRD_PARTY_NOTICES.en.md), [model sources](../sources.txt), and [source versions](source-provenance.json).

Project implementation covers the five-class speech dataset and model, live-data iteration, Python/C frontend port, continuous audio capture, quantization-interface checks, CPU/DMA/NPU cache handling, vision generation and runtime alignment, camera interrupt-queue adaptation, joint model build, search state and inter-task data handoffs, memory layout, and deployment verification. The [code tour](code-tour.en.md) maps these to functions and files.

The standalone recorder used by labeled collection originally lived in `course15_n6_mic_test`. It is retained here as a data-collection dependency with its original version and upstream diff. Training and recording-IDE snapshots also retain their original path and environment assumptions, documented in each directory.

## Source materials and hashes

The [project source-material inventory](evidence/development-history/review_inventory.json) covers 25 dual-model materials and 23 recording-dependency materials. It traces sources and public locations; it is not the total repository file count. [Supplementary provenance](evidence/development-history/source_provenance.json) retains original/public hashes, path substitutions, and excerpt methods. [Evaluation provenance](evidence/provenance.json) traces final training and evaluation files.

Model comparisons, voice acceptance, and vision records are presented against their respective versions. Fixed PC reference JSON, board comparison code, and original serial logs are distinct materials; see [test records](results.en.md) for interpretation.

A turn-by-turn review of both original development conversations and their attachments on 2026-11-20 adds recording startup, vision generation, image alignment, fixed five-class comparisons, and model iteration. The [review](original-history-review.en.md) distinguishes actual terminal output, proposed steps, and steps without reported results. Published material is an engineering summary with necessary de-identified output excerpts; private conversation transcripts and early source archives are not uploaded to this repository. The existing 48-item inventory still describes the original file review, not the complete conversation attachment set.

## Materials required for a complete build

The public repository provides sources, configuration, and engineering records. A complete build additionally requires matching vision/KWS generated code and weights, the corresponding runtime, and required SDK dependencies. Raw recordings and prebuilt flash images are not included. Final deployment pointers, image roles, addresses, and available hashes are preserved in the documentation and evidence.

Compiler/tool versions and build entry points are in the [build notes](build.en.md). The demonstration video is pending. Documentation retains existing results, with firmware behavior and original test data kept at their frozen versions.
