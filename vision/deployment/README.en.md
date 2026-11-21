# Vision-model export, quantization, N6 generation, and deployment

[繁體中文](README.md) | [English](README.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](../../docs/toolchain-compatibility.en.md).

The vision work starts with Python/PyTorch model processing and covers ONNX export, TensorFlow SavedModel conversion, per-channel INT8 quantization, interface validation, and ST Edge AI/Neural-ART generation. The author executes these stages and then integrates the network, interfaces, weights, and commands into the dual-model application, including runtime pairing, building, and image packaging.

This page corresponds to [development step 3: vision model conversion](../../docs/development-steps.en.md#step-03), covering generation inputs, tool processing, artifact roles, and firmware handoff. See [toolchain compatibility](../../docs/toolchain-compatibility.en.md) for version differences and [dual-model memory layout](../../docs/memory-deployment.en.md) for addresses and deployment images.

## The complete vision workflow from Python/PyTorch to N6

**Python/PyTorch (`.pt`) → ONNX → TensorFlow SavedModel → per-channel INT8 quantization (TFLite) → ST Edge AI / Neural-ART → N6 network/interfaces (C/H), weights (BIN), and execution commands.** The author personally performed model export, format conversion, quantization calibration, interface checks, and N6 generation before integrating vision into the dual-model firmware. Model-preparation implementations and records are retained in the vision repository; final firmware integration is retained here.

| Stage | Work performed by the author | Code, configuration, and successful execution records |
| --- | --- | --- |
| Python/PyTorch export | Load the local `yolov8n-seg.pt` with Python/Ultralytics tools, configure a 256×256 input, and export ONNX; the log records opset 19, graph simplification, and export success | [Model export log](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log) |
| ONNX to TensorFlow | Convert ONNX to TensorFlow SavedModel with `onnx2tf`, retain detection and mask-prototype outputs, and proceed to TFLite export | [ONNX/SavedModel success record](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log) |
| Execute INT8 quantization | Run ST's quantization tools on the local SavedModel and calibration images, configuring per-channel quantization, image rescaling, and INT8 inputs/outputs to produce quantized TFLite | [Quantization configuration](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/configs/yolov8n_seg_int8_int8.yaml), [successful quantization log](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/04_st_quantization_seg.log) |
| Check PC behavior and deployment interfaces | Compare original, floating-point, and INT8 models; check I/O shapes, tensor types, scales, zero points, and N6 postprocessing interfaces | [PC model comparison](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/scripts/check_seg_models_pc.sh), [N6 interface check](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/scripts/check_n6_seg_header.py) |
| Generate N6 artifacts and integrate firmware | Use ST Edge AI/Neural-ART to generate network code, STAI interfaces, weights, and vision execution commands; match the runtime library and adapt builds, memory, postprocessing, and display | [Vision deployment program](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/scripts/deploy_n6_seg.sh), [dual-model generation workflow](../../tools/development-history/vision_03_generate_and_build_vision.sh), [six-artifact handoff](../../tools/development-history/vision_05_copy_vision_artifacts.sh) |

Export, quantization, and dual-model integration retain separate stage-specific versions. The source table below records the input to a particular N6 generation run. The code, configuration, and success logs above trace the complete development work; per-run hashes identify the exact model and weight bytes.

## Three official reference files

These files are byte-for-byte snapshots from the official instance-segmentation example at commit `42f7d645f1ed61967a922defa4aa97b95d390b16`. They preserve the original commands and configuration. [upstream-reference.json](upstream-reference.json) records the source URLs, Git blob hashes, SHA-256 hashes and sizes.

| File | Purpose |
| --- | --- |
| [Generation script](upstream-reference/generate-n6-model_STM32N6570-DK.sh) | Calls `stedgeai generate`; copies the network, STAI interface, epoch-controller commands and weights; converts weights to an addressed HEX image |
| [Neural-ART configuration](upstream-reference/user_neuralart_STM32N6570-DK.json) | Selects the `default` profile, memory pool and compiler options, including cache maintenance and the epoch controller |
| [Memory pool](upstream-reference/my_mpools/stm32n6-app2_STM32N6570-DK.mpool) | Supplies candidate SRAM, external RAM and Flash addresses, capacities and access properties to the compiler |

These are **pinned official reference snapshots**. No byte-for-byte comparison against the historical local copies is available, so they are not presented as a complete reconstruction of the final local generation directory. Model weights, generated network code and prebuilt images are not included. These files belong to the upstream `Model` directory, listed under **SLA0044** in its component-license index; this directory does not relicense them. See [vision/LICENSE.md](../LICENSE.md) and [third-party notices](../../THIRD_PARTY_NOTICES.en.md).

## N6 generation and artifact handoff in the dual-model application

| Stage | Work performed in this project |
| --- | --- |
| Prepare generation inputs | Check the local TFLite model, Neural-ART configuration, and memory pools; select ST Edge AI Core `4.0.1-20581`, which also reports STM32CubeAI `12.0.1-RC2` |
| Convert for N6 deployment | Run the generation script in `vision/Model/` with `--target stm32n6`, the `default` profile, and `--input-data-type uint8` to generate an N6 interface matching camera input; configuration covers model memory allocation, cache maintenance, and the epoch controller |
| Collect network and data artifacts | Obtain `network.c/.h`, `stai_network.c/.h`, `network_ecblobs.h`, and `network_data.xSPI2.bin`, supplying network execution code, the STAI calling interface, execution commands, and weights |
| Match the runtime | Move the vision reference from Runtime1200 and the main application from Runtime1100 to `NetworkRuntime1201_CM55_GCC.a`, updating headers, libraries, and NPU support sources together |
| Integrate into main firmware | Copy the six artifacts into `firmware/Model/`, update build lists and model calls, and connect instance-segmentation postprocessing, camera input, target search, and display data flow |
| Build and extract images | Link the main application's ELF; extract vision commands from `.flash_section`, retain separate application/weight/command deployment locations, and package the application with its boot header |

After obtaining the model file, board deployment requires conversion, runtime configuration, firmware integration, and image preparation. Artifacts and completion records are retained for each stage.

### Original host workflows executed in this project

The [development-source directory](../../tools/development-history/README.en.md) contains 14 vision workflows covering project setup, model generation, runtime updates, postprocessing migration, camera/memory configuration, and application builds. These entry points expose the original operations and changes:

- [Run generation and the reference build](../../tools/development-history/vision_03_generate_and_build_vision.sh), [pair the vision runtime](../../tools/development-history/vision_02_match_vision_runtime.py).
- [Copy six model artifacts](../../tools/development-history/vision_05_copy_vision_artifacts.sh), [pair the application runtime](../../tools/development-history/vision_06_match_main_runtime.py).
- [Import postprocessing](../../tools/development-history/vision_08_import_postprocessing.py), [integrate search logic and interrupt interfaces](../../tools/development-history/vision_12_integrate_vision_application.py).
- [Configure camera and memory](../../tools/development-history/vision_13_configure_camera_and_memory.py), [build the application and images](../../tools/development-history/vision_14_build_main_vision.py).

These files preserve complete terminal code blocks from development. Per-file purposes, execution status, and original/public hashes are in the [provenance record](../../tools/development-history/source-provenance.json). Frozen firmware remains in `firmware/`, with historical workflows retained separately to show the implementation process.

With the model, tools and original reference-project directory structure in place, the historical entry point from `vision/Model/` was:

```bash
bash generate-n6-model_STM32N6570-DK.sh
```

Its core command is:

```bash
stedgeai generate --model yolov8n_256_quant_pc_ii_seg_coco-st.tflite --target stm32n6 --st-neural-art default@user_neuralart_STM32N6570-DK.json --input-data-type uint8
```

The original script resolves `stedgeai` and `arm-none-eabi-objcopy` through `PATH`; it does not pin their versions. The original text is retained here, so tool selection and dependent directories must be checked before use. `upstream-reference/` is a reading snapshot, not a self-contained model rebuild package.

The main firmware received six model artifacts: `network.c`, `network.h`, `network_ecblobs.h`, `stai_network.c`, `stai_network.h` and `network_data.xSPI2.bin`. This version of the official script does not include `network.h` in its copy list; the complete handoff must therefore check that header separately.

The official reference project's documented tool version and GCC runtime differed from the newer generator used here. This project paired the headers, libraries and NPU support sources in both the reference application and main firmware with GCC Runtime1201. [Toolchain compatibility](../../docs/toolchain-compatibility.en.md) identifies the official files, version differences, corrections and saved build/deployment evidence.

### Recorded completion on October 4, 2026

| Output stage | Retained results |
| --- | --- |
| `vision_20261004_181810` | Terminal output confirms successful model generation, reference-application ELF linking, and boot-image packaging: application SRAM 352,320 B, vision commands 230,528 B, PSRAM 2,404,512 B |
| Six-artifact handoff | Terminal output lists the network code, headers, STAI interface, commands, and weights copied from `vision/Model/STM32N6570-DK/` into `firmware/Model/` |
| `finder_vision_20261004_193031_265404` | Successful main-application build: application SRAM 351,240 B, vision commands 230,528 B, PSRAM 8,949,920 B. The 3,474,865 B vision-weight image is placed at `0x70380000`; vision commands are placed at `0x71380000` |

These builds correspond to the reference application and the ported vision application, both before KWS integration. The [original-history review](../../docs/original-history-review.en.md) records their execution order, and the [image-layout excerpt](../../docs/evidence/development-history/vision_image_layout_20261004.txt) retains the main vision application's image sizes and addresses. Later dual-model usage and deployment results are documented in [memory layout](../../docs/memory-deployment.en.md) and [results](../../docs/results.en.md).

### Source record for the October 4 generation input

[sources.txt](../../sources.txt) was created after obtaining the model by running `sha256sum` on the local file. It identifies the pinned source and content hash for that generation input:

| Field | Retained value |
| --- | --- |
| Model file | `yolov8n_256_quant_pc_ii_seg_coco-st.tflite` |
| Source revision | `stm32-hotspot/ultralytics` commit `176ecaa749b79a3f53ce077d2b14412fa45e81a0` |
| Local path | `vision/Model/yolov8n_256_quant_pc_ii_seg_coco-st.tflite` |
| SHA-256 | `3316733125a5fb85d66ed33993627b5d293b3baceb348b137132071ca365ebd6` |

The original retrieval procedure also checked the Git blob hash; the user's terminal output confirms a model size of 3,514,494 B. Subsequent generation, artifact copying, and main-application building correspond to the execution results above. Source records, generated artifacts, and deployment images are tracked separately to make this conversion and integration workflow traceable.

## Candidate pools versus the final dual-model layout

**A memory-pool file describes candidate ranges for the model compiler. It is neither the final allocated footprint nor a replacement for the application linker script.**

| Official candidate pool | Start | Capacity | Meaning in the dual-model project |
| --- | --- | --- | --- |
| `cpuRAM2` | `0x34100000` | 1,024 KiB | Candidate on-chip vision memory; the application SRAM range ends before this address |
| `npuRAM3–6` | `0x34200000`, `0x34270000`, `0x342E0000`, `0x34350000` | 448 KiB each | Actual use of each pool is determined by the corresponding generation results |
| `hyperRAM` | `0x90000000` | 16 MiB | Candidate external working-memory range for vision generation |
| `octoFlash` | `0x70380000` | 16 MiB | Weight range in the original single-vision reference configuration, not freely available capacity in the dual-model system |

The final system separately reserves KWS weights at `0x70700000`, inside the original `octoFlash` candidate range. **The gap between the YOLO weight start and the KWS start is only `0x380000`, or 3.5 MiB.** Regeneration or model replacement must check the actual weight image's address and size against this boundary; the original pool's 16 MiB capacity is not a valid non-overlap guarantee.

The [main linker script](../../firmware/Gcc/STM32N657xx.ld), [KWS memory pool](../../kws/deployment/kws.mpool) and deployment-image configuration jointly constrain application SRAM, display/post-processing PSRAM, dedicated KWS RAM and the vision-command region. See [dual-model memory layout](../../docs/memory-deployment.en.md) for addresses, reserved capacities, saved usage figures and the five deployment images.
