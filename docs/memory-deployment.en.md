# Dual-model memory layout and deployment

[繁體中文](memory-deployment.md) | [English](memory-deployment.en.md)

This project assigns **CPU application memory, YOLO workspaces, KWS workspaces, display buffers, model weights, and NPU execution commands** separately, then coordinates model generation, firmware linking, and flash placement. Both models use one NPU sequentially in the same inference task, with separate model contexts and I/O, and explicit CPU/DMA/NPU cache handoffs.

All address intervals below include the start and exclude the end. KiB = 1,024 bytes; MiB = 1,048,576 bytes. **Reserved capacity, linked section usage, model compiler allocation, and image file size are distinct measurements.**

## Three configuration layers define the deployed system

| Layer | Responsibility | Project implementation |
| --- | --- | --- |
| Model memory pools (`.mpool`) | Regions available to the model compiler for weights, activations, and I/O, including access properties | The vision pool source is pinned and retained as an upstream reference; the [KWS pools](../kws/deployment/kws.mpool) specify separate audio RAM and Flash locations |
| Firmware linker script and section attributes | CPU code, shared runtime, global data, stack, display buffers, and vision commands | [Linker script](../firmware/Gcc/STM32N657xx.ld) together with [build definitions and image extraction rules](../firmware/Makefile) |
| Image packaging and programming configuration | Images actually written to Flash, their addresses, headers, and contents | Application, two weight images, vision commands, and FSBL; [final programming manifest](evidence/development-history/deployment_20261008/flash_manifest.json) |

A model pool describes a compiler allocation range, not the entire firmware layout or an amount already occupied. Execution and boot-storage addresses also differ: the application image is programmed at `0x70100000`, while the application is linked to execute in internal SRAM starting at `0x34000400`.

## Runtime RAM: application, models, and display

| Purpose | Address / allocation range | Reserved capacity | Saved allocation or usage |
| --- | --- | ---: | --- |
| Main application, FreeRTOS, peripheral drivers, shared AI runtime, model CPU control code, and ordinary data | `0x34000400–0x34100000` | 1,023 KiB | Final linker usage: **535,544 B** |
| Microphone DMA/ring buffers, CPU preprocessing workspace, and model contexts | Same application SRAM, in ordinary static data sections | Included in the application reservation above | The audio ring contains 32,768 16-bit samples; static MFCC arrays are separate from model activations |
| YOLO internal workspace | Internal SRAM/NPU RAM pools starting at `0x34100000` | Per-pool configuration below | Actual usage requires the corresponding vision generation report |
| YOLO external workspace pool | `0x90000000–0x91000000` | 16 MiB available in the upstream pool | Available capacity, not actual model usage |
| Camera input, LCD frames, post-processing, and mask snapshots | `0x91000000–0x91FC0000` | 16,128 KiB (15.75 MiB) | Final `.psram_section` usage: **8,949,920 B** |
| KWS activations, including model I/O | `0x91FC0000–0x92000000` | 256 KiB | Final model allocation: **17,440 B**; used envelope ends at `0x91FC4420` |

Application and display figures come from the [final build log](evidence/development-history/deployment_20261008/build.log); KWS figures come from the [final generation report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt). They are not a measured whole-system runtime memory peak.

The linker reports **0 B** for `KWS_RAM` because generated model code uses absolute addresses in that reservation rather than placing ordinary linked sections there. The model report records the 17,440 B activation allocation. **A zero in the linker report does not mean that KWS uses no RAM.**

### Available pools in the upstream vision configuration

The [pinned upstream pool file](https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Model/my_mpools/stm32n6-app2_STM32N6570-DK.mpool) corresponding to this project's pinned vision source defines the following regions. This table describes compiler configuration; it does not substitute measurements from another vision project.

| Pool | Start | Configured capacity |
| --- | --- | ---: |
| `cpuRAM2` | `0x34100000` | 1,024 KiB |
| `npuRAM3` | `0x34200000` | 448 KiB |
| `npuRAM4` | `0x34270000` | 448 KiB |
| `npuRAM5` | `0x342E0000` | 448 KiB |
| `npuRAM6` | `0x34350000` | 448 KiB |
| `hyperRAM` | `0x90000000` | 16 MiB |

The same configuration gives `flexMEM` and `cpuRAM1` zero capacity. The application linker limits CPU application memory to addresses below `0x34100000`, keeping ordinary code and data out of the region needed by the vision model.

## Storage and boot: five deployment images

| Image / data | Flash storage location | Capacity or saved size | Runtime role |
| --- | --- | --- | --- |
| First-stage bootloader (FSBL), `ai_fsbl.hex` | Addresses embedded in the HEX records | Parse the actual HEX file for its address ranges | Initialize the boot environment and load the application |
| Application image, `finder_signed.bin` | Starting at `0x70100000` | Check the corresponding packaged artifact | CPU code is linked to internal SRAM; shared runtime and both models' CPU control code are included |
| Vision weights, `vision_weights.bin` | Starting at `0x70380000` | Original development output records **3,474,865 B** | YOLO weights |
| Audio weights, `kws_weights.bin` | `0x70700000–0x70710000` | 64 KiB reserved; model report allocates **11,409 B** of weights | KWS weights |
| Vision commands, `vision_commands.bin` | `0x71380000–0x71580000` | 2 MiB reserved; linked section size **230,528 B** | YOLO epoch-controller commands (EC blob) |

These five images form a two-model deployment. This KWS version has no separate EC blob: the official tool's generated C control code is linked into the application. The CPU runs that control flow, the NPU executes 11 hardware epochs, and the final Softmax epoch executes on the CPU.

`finder_signed.bin` is the historical filename. Packaging uses the no-key option (`-nk`) to add a boot header; this is not presented as a cryptographic signature. FSBL Flash placement comes from HEX records, not from the linker's `_fsbl_start_address = 0x34180000`, which is a RAM address.

### Boundary between vision and KWS weights

The upstream vision `octoFlash` pool offers 16 MiB at `0x70380000–0x71380000`. **That available allocation range includes the later KWS weight address, `0x70700000`.** Different pool names alone therefore do not establish disjoint address ranges.

The original development output records a 3,474,865 B vision weight image, giving these content boundaries:

| Recorded artifact | Content start | Exclusive content end | Relationship to the next region |
| --- | --- | --- | --- |
| Vision weights | `0x70380000` | `0x706D05B1` | **195,151 B** remain before the KWS start |
| Reserved KWS weight region | `0x70700000` | `0x70710000` | Separate 64 KiB reservation |

The vision size comes from the [user's terminal-output excerpt](evidence/development-history/vision_image_layout_20261004.txt) for the formal vision application on 2026-10-04, which records weight and command lengths and addresses. Its application size belongs to the vision stage before KWS integration. See the [original development review](original-history-review.en.md) for the workflow and version context. These boundaries are calculated from the recorded size; this review does not claim to have reread the unpublished weight binary.

The recorded content ends before KWS. **Replacing or regenerating the vision model requires another boundary check:** compare the weight start plus file length, the compiler's used ranges, and the programming regions. The upstream 16 MiB pool is not a safe weight-size limit for the integrated two-model layout. If the new content crosses `0x70700000`, update pool configuration, weight placement, and deployment manifests consistently, then regenerate and rebuild.

## Adapting the official examples to this layout

| Item | Pinned official source | Project integration |
| --- | --- | --- |
| CPU application SRAM | Hand example `6c313001…`: 1,535 KiB; instance-segmentation example `42f7d645…`: 1,023 KiB | Reduced the hand-based application to 1,023 KiB to match the vision workspace boundary |
| Vision commands | The segmentation linker already provides `.flash_section` at `0x71380000`, with 2 MiB | Brought that placement into the formal application and used section definitions to collect generated `.flash_blob` data |
| Uninitialized PSRAM buffers | Both official examples already contain `.psram_section (NOLOAD)` | Reused the mechanism for this application's display, camera, post-processing, and mask snapshots |
| Dedicated KWS RAM | The hand base originally offers 16 MiB of general PSRAM | Reduced it to 15.75 MiB and reserved the final 256 KiB as `KWS_RAM`, using the same address in the KWS pool |
| Image extraction | Generated commands and CPU code occupy distant address regions | Extracted application and vision commands separately from the same ELF, avoiding binary expansion across address gaps |

Official comparisons: [hand-example linker](https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/Gcc/STM32N657xx.ld), [instance-segmentation linker](https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/STM32CubeIDE/STM32N657xx.ld). These are adaptations made while combining examples and adding a second model; each original example's configuration served its own models.

## Sections, caches, and data lifetimes

`NOLOAD` keeps PSRAM workspace contents out of the programmed load image. The application explicitly initializes the frame buffers that require it. Generated code separately allocates KWS workspace, outside general application PSRAM.

| Handoff | Implementation |
| --- | --- |
| Camera → CPU → YOLO | Acquire the capture buffer, invalidate stale CPU cache, copy into model input, complete cache maintenance, then release the capture buffer |
| Microphone DMA → CPU | Align DMA descriptors to 64 B and audio buffers to 32 B; process cache state before writing the ring buffer, then publish the position with a memory barrier |
| CPU features → KWS NPU | Handle old NPU 64 B cache lines and stale CPU copies before updating input; clean CPU cache after the write and before inference |
| Final KWS output → CPU | The final Softmax runs on the CPU; read the quantized results written by the CPU |
| Post-processing → display task | Save result and mask snapshots; the display task copies under a mutex and renders outside it, preventing the next inference from overwriting data in use |

Source: [system and image handoffs](../firmware/Src/app.c), [continuous audio capture](../firmware/Src/finder_mic.c), [features and model cache handoffs](../firmware/Src/finder_kws.c). One inference task serializes NPU access; model workspaces and display data remain separately managed.

## Build and deployment evidence

- [Final link results](evidence/development-history/deployment_20261008/build.log): application SRAM, vision-command Flash, and PSRAM section usage.
- [KWS generation report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt): pools, used ranges, weights, activations, and hardware/software epochs.
- [Final image manifest](evidence/development-history/deployment_20261008/flash_manifest.json) and [programming verification](evidence/development-history/deployment_20261008/flash_verified.json): addresses, hashes, and successful verification for the application and KWS weights.
- [Original development review](original-history-review.en.md): vision generation, framework porting, the packaged payload correction from `0x240` to `0x400`, and board operation records.
- [Build and version compatibility](build.en.md): tools, official-example runtime matching, and the existing build entry point.

The final update directly records successful programming of the application and KWS weight images; the other three images retain their existing contents. Together with the final board operation log, these records support that the integrated version was deployed and running. Demonstration-video and standalone-power/cold-boot status are tracked separately in [results and version scope](results.en.md).
