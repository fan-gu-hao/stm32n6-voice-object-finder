# Build and external dependencies

[繁體中文](build.md) | [English](build.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](toolchain-compatibility.en.md).

The environment used was GCC 14.3.1, ST Edge AI 4.0.1, ATON 1.1.3-275, `NetworkRuntime1201_CM55_GCC.a`, HAL 1.3.0, and FreeRTOS 10.6.2, with STM32CubeIDE 2.2.0.

**The project completed upstream-version alignment, memory allocation, and boot-image payload alignment corrections.** [Toolchain compatibility](toolchain-compatibility.en.md) connects pinned official settings and build-path differences to the recorded successful build, programming, and board operation. [Dual-model memory and deployment](memory-deployment.en.md) distinguishes model pools, linked sections, storage addresses, and execution addresses.

The checked build path is GCC: the vision reference's Runtime1200 and the hand-framework base's Runtime1100 were aligned to GCC Runtime1201 during integration. The retained IAR configuration in `ai.mk` still points to Runtime1100 and is not listed as a completed build path for this project. Vision generation, memory sections, and image packaging are traced in the [engineering workflow](engineering-workflow.en.md) and [original-history review](original-history-review.en.md).

The public repository retains application sources, build settings, and training scripts. Models and prebuilt images are outside the publication scope. A complete build still requires matching generated model code and runtime dependencies.

Model locations in the complete local project are `firmware/Model/` and `firmware/Model/kws/st_ai_output/`. The actual compilation lists are defined in `firmware/mks/ai.mk` and `firmware/mks/kws.mk`.

From the project root with all dependencies available, the existing build targets are:

```bash
bash firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh \
  build_finder_ide/Project.elf \
  build_finder_ide/Project.bin \
  build_finder_ide/vision_commands.bin
```

| Output | Purpose |
| --- | --- |
| `firmware/build_finder_ide/Project.elf` | Complete linked image for section, symbol, and memory-allocation checks |
| `firmware/build_finder_ide/Project.bin` | Application binary excluding `.flash_section`; still requires boot-header packaging |
| `firmware/build_finder_ide/vision_commands.bin` | Only `.flash_section`, programmed at `0x71380000` |

The Makefile's `TX_MAX_PARALLEL_NETWORKS=1` limits simultaneous execution. Both YOLO and KWS are linked and use the NPU sequentially within one inference task. This compilation entry point does not automatically package or program images.

The build script accepts a compiler directory through `GCC_PATH`, or searches for GCC 14.3.1 in a local STM32CubeIDE installation. IDE build paths are resolved relative to the project location.

The [vision-generation source guide](../vision/deployment/README.en.md) provides the script/configuration entry point; speech generation is covered by the [KWS configuration](../kws/deployment/README.en.md). Regenerated models require matching runtime components, synchronized KWS feature/quantization coefficients, and memory checks against actual image ranges. The upstream vision Flash candidate pool includes this project's KWS weight address, so its capacity is not a safe dual-model weight budget.

The recording host tools are in `kws/recording_tools/`, and the corresponding [FSBL sources and IDE snapshot](../kws/recording_firmware/README.en.md) are also published. Rebuilding requires the pinned STM32CubeN6 SDK and adjustment of original development paths in the snapshot. The host tools require matching ELF/BIN files; prebuilt images are not included.

[Final code-generation and deployment records](evidence/development-history/README.en.md) retain commands, the tool's internal ONNX stage, memory/execution-stage reports, build output, and successful write verification for tracing the existing workflow.
