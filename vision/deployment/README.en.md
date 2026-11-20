# Vision code generation and configuration sources

[繁體中文](README.md) | [English](README.en.md)

This directory supplies the vision-generation entry point and configuration sources for the dual-model project. The October 4, 2026 development record confirms that the official script was run in this project's `vision/Model/` with ST Edge AI 4.0.1, generating the N6 network, weights and execution commands before building the reference application and integrating it into the main firmware. See [sources.txt](../../sources.txt) for the selected model source and hash.

## Three official reference files

These files are byte-for-byte snapshots from the official instance-segmentation example at commit `42f7d645f1ed61967a922defa4aa97b95d390b16`. They preserve the original commands and configuration. [upstream-reference.json](upstream-reference.json) records the source URLs, Git blob hashes, SHA-256 hashes and sizes.

| File | Purpose |
| --- | --- |
| [Generation script](upstream-reference/generate-n6-model_STM32N6570-DK.sh) | Calls `stedgeai generate`; copies the network, STAI interface, epoch-controller commands and weights; converts weights to an addressed HEX image |
| [Neural-ART configuration](upstream-reference/user_neuralart_STM32N6570-DK.json) | Selects the `default` profile, memory pool and compiler options, including cache maintenance and the epoch controller |
| [Memory pool](upstream-reference/my_mpools/stm32n6-app2_STM32N6570-DK.mpool) | Supplies candidate SRAM, external RAM and Flash addresses, capacities and access properties to the compiler |

These are **pinned official reference snapshots**. No byte-for-byte comparison against the historical local copies is available, so they are not presented as a complete reconstruction of the final local generation directory. Model weights, generated network code and prebuilt images are not included. These files belong to the upstream `Model` directory, listed under **SLA0044** in its component-license index; this directory does not relicense them. See [vision/LICENSE.md](../LICENSE.md) and [third-party notices](../../THIRD_PARTY_NOTICES.en.md).

## Entry point and generated-file handoff

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
