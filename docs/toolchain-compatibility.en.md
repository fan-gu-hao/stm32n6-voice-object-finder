# Toolchain compatibility, build differences, and deployment fixes

[繁體中文](toolchain-compatibility.md) | [English](toolchain-compatibility.en.md)

This project brings two official applications built around different tool versions into one GCC 14.3.1, ST Edge AI 4.0.1, and Runtime1201 build. The work includes identifying generation/runtime version differences, transferring memory-section settings, extracting separate images, and diagnosing a packaging problem that prevented startup despite successful Flash verification.

## Pinned sources and version alignment

| Application/stage | Original settings at the pinned official revision | Integration in this project |
| --- | --- | --- |
| Vision reference | Instance-segmentation example `42f7d645f1ed61967a922defa4aa97b95d390b16`; README specifies ST Edge AI 4.0.0 and Makefile links Runtime1200 | Regenerate in this project's `vision/` tree with ST Edge AI 4.0.1 and update to GCC Runtime1201 |
| Main application framework | Hand dual-model example `6c313001f69d3ddb1ffa7bd700aba74f9c11037b` (v2.2.0); README specifies ST Edge AI 3.0.0 and `mks/ai.mk` links Runtime1100 | Replace the models with YOLO/KWS and align GCC Runtime1201, retaining the FreeRTOS abstraction and asynchronous execution mode |
| Environment actually used | STM32CubeIDE 2.2.0, GCC 14.3.1, ST Edge AI Core 4.0.1-20581, Neural-ART/ATON 1.1.3-275, CubeProgrammer/Signing Tool 2.23.0 | Match generated models, headers, libraries, NPU support sources, and linker settings together |

The original settings are directly inspectable in the segmentation [README lines 112–116][v-tools] and [Makefile line 219][v-runtime], and the hand-example [README lines 59–63][h-tools] and [`ai.mk` lines 46–47][h-runtime]. Both READMEs describe the possible `Possible mismatch in ll_aton library used` error when changing ST Edge AI versions and direct users to update the runtime ([segmentation][v-migration], [hand example][h-migration]).

Runtime1200/1100 are not inherently incorrect in their original version combinations; they differ from the newer generation environment selected for this project. The course17 record shows the difference being identified and the components updated before successful builds. It does not present the potential error documented upstream as an error actually observed during this migration.

## Generation command and runtime updates

Line 5 of the pinned [official vision-generation script][v-generate] invokes `stedgeai` from PATH without pinning its version inside the script. Lines 7–11 copy the network code, STAI interface, execution commands, and weights. Line 12 separately invokes `arm-none-eabi-objcopy` from PATH to produce weight HEX data at its external-Flash address.

This project placed ST Edge AI 4.0.1 and the selected GCC tools on PATH before generation. Alignment involved more than changing a library name:

1. Update `Middlewares/stedgeai-lib/Inc`, `Lib`, and `Npu` in the vision reference, and change the GCC library from Runtime1200 to Runtime1201.
2. Update `firmware/Lib/AI_Runtime/Inc`, `Lib`, and `Npu` in the main application, and change its `firmware/mks/ai.mk` GCC library from Runtime1100 to `NetworkRuntime1201_CM55_GCC.a`.
3. Import the generated YOLO network and weights into `firmware/Model/`, update build lists and model calls, then generate KWS under a distinct network name with the same toolchain and link both models.

The original 2026-10-04 terminal record confirms vision generation, runtime updates, and successful builds. The 2026-10-08 [KWS generation report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt) also directly records tool 4.0.1, compiler 1.1.3-275, and `NetworkRuntime1201_CM55_GCC.a`. See the [vision deployment notes](../vision/deployment/README.en.md) for vision sources and generation entry points.

## Build entry points and memory sections

| Difference in the pinned official sources | Integration change | Engineering implication |
| --- | --- | --- |
| The segmentation CubeIDE `ModelZoo` configuration defines `.flash_blob`/`.psram_bss` placement ([lines 136 and 163–164][v-cproject]); the standalone Makefile at the same revision does not include those two definitions | Explicitly add `ECBLOB_CONST_SECTION` and `POSTPROCESS_WRAPPER_SECTION` to the project's Makefile, placing vision commands in Flash and postprocessing buffers in PSRAM | Separate build configurations do not automatically inherit each other's memory-placement options |
| The segmentation linker script already has `.flash_section` and PSRAM sections ([lines 152–164][v-sections]); the hand base has 1535 KiB of application SRAM and its existing PSRAM section ([lines 14–19][h-memory]) | Reduce the main application's SRAM to 1023 KiB, add the vision-command region at `0x71380000`/2 MiB, and use the existing PSRAM section for the integrated postprocessing allocation | Coordinate model pools and the complete application linker layout so application memory does not extend into vision activations |
| Original Makefiles convert the whole ELF directly to BIN ([segmentation lines 264–265][v-binary], [hand example lines 198–199][h-binary]) | Exclude/extract only `.flash_section` to produce separate application and `vision_commands.bin` files | Adding a separate external-Flash section also requires updating binary extraction to avoid a large address-gap-filled image |

These changes adapt specific build paths to the new models and memory layout. The formal course17 application builds successfully after configuration; the SRAM overflow from an earlier, separate audio/vision attempt is not presented as a failure of this formal application.

## Packaging inconsistency and startup correction

The pinned segmentation commit has a verifiable difference between packaging entry points: [README lines 297–306][v-align] distinguish CubeProgrammer versions before and after 2.21 and require `--align` for 2.21 onward, while the [Makefile rule at lines 267–268][v-sign] omits alignment. The hand-base [example at line 195][h-sign] also omits it, with that README listing CubeProgrammer 2.18.0. With this project's 2.23.0 tools, the packaging command must match the tool version instead of mixing instructions from different entry points.

The project's October 4 vision image already used `0x400` alignment successfully. When the local live-voice packaging command was assembled on October 6, the alignment option from that working configuration was omitted. This was a regression in this project's integration procedure, not an issue attributable entirely to the official sources.

| Actual observation/check | Correction and outcome |
| --- | --- |
| Application and KWS weights were written and verified, but the user reported a black screen without normal startup output | Inspect CPU state, ELF vectors/symbols, and the raw program's position in the packaged image, distinguishing correct Flash contents from a bootable image |
| The raw BIN begins at offset `0x240` in the packaged image; its bytes match the original program | Restore the established no-key packaging settings, including `-of 0x80000000` and `-align`; verify a `0x400` payload offset with bytes still identical to the raw BIN |
| KWS serial output appears after the correction, allowing subsequent dual-model debugging and operation | Retain this as a confirmed packaging defect and correction without extending it into a single explanation for every black screen, core fault, or recognition error |

Original execution results and chronology are covered in the [original-history review](original-history-review.en.md). `-nk` is no-key mode: this operation adds a boot header and alignment and is not described as a cryptographic signature.

## Current GCC build entry point

From the complete project root, with the matching generated models and runtime available, the current entry point is:

```bash
bash firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh \
  build_finder_ide/Project.elf \
  build_finder_ide/Project.bin \
  build_finder_ide/vision_commands.bin
```

[`cubeide_make.sh`](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) accepts `GCC_PATH` or finds GCC 14.3.1 in a local STM32CubeIDE installation, checks the version, and adds the compiler directory to PATH. It resolves the firmware directory relative to the script and invokes Make for the three targets above. This produces the ELF, raw application, and vision-command images; it does not automatically package or flash them. Dependencies and model locations are described in the [build notes](build.en.md).

GCC is the confirmed build path. The retained IAR setting in `ai.mk` still references Runtime1100 and is not listed as a validated path for this project.

## Retained build, deployment, and board results

| Stage | Direct evidence and result |
| --- | --- |
| Main vision application, 2026-10-04 | The original terminal record shows a successful build in `finder_vision_20261004_193031_265404`: SRAM 351,240 B, vision commands 230,528 B, PSRAM 8,949,920 B. Its [board log](evidence/development-history/finder_vision_20261004.log) retains early vision FOUND results |
| Final dual-model build, 2026-10-08 | The [original build log](evidence/development-history/deployment_20261008/build.log) records SRAM 535,544 B/1023 KiB, vision commands 230,528 B/2 MiB, and general PSRAM 8,949,920 B/16128 KiB. A linker-reported 0 B for `KWS_RAM` does not mean that the model's fixed-address activations use no memory |
| Final image update | The [deployment manifest](evidence/development-history/deployment_20261008/flash_manifest.json) and [verification record](evidence/development-history/deployment_20261008/flash_verified.json) confirm writing/verifying the application at `0x70100000` and KWS weights at `0x70700000` in this update; the remaining images retain their existing configuration |
| Final board operation | The [October 8 log](evidence/development-history/voice_groupcv_20261008.log) records two correctly accepted instances each of cup, bottle, and phone. All vision results in that run have found=0, so they remain separate from the October 4 vision FOUND evidence |

The current entry point was prepared for publication; the successful results above come from retained historical builds and hardware records, not a new build or flash run during this documentation update. The demonstration video and final dual-model standalone-power/cold-boot checks remain pending; see [results](results.en.md).

[v-tools]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/README.md#L112-L116
[v-runtime]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/Makefile#L219
[h-tools]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/README.md#L59-L63
[h-runtime]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/mks/ai.mk#L46-L47
[v-migration]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/README.md#L347-L354
[h-migration]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/README.md#L220-L227
[v-generate]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Model/generate-n6-model_STM32N6570-DK.sh#L3-L12
[v-cproject]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/STM32CubeIDE/.cproject#L136-L164
[v-sections]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/STM32CubeIDE/STM32N657xx.ld#L152-L164
[h-memory]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/Gcc/STM32N657xx.ld#L14-L19
[v-binary]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/Makefile#L264-L265
[h-binary]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/Makefile#L198-L199
[v-align]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/README.md#L297-L306
[v-sign]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/Makefile#L267-L268
[h-sign]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/README.md#L191-L196
