# Standalone recording firmware: original data-collection implementation

[繁體中文](README.md) | [English](README.en.md)

This directory preserves the standalone five-second recorder used for keyword-spotting dataset collection. It captures board audio into RAM before transmitting it to the PC from the main loop, providing recording control, length checks, and CRC32 integrity checks. Interrupts collect samples; the main loop handles serial transmission.

## Base and modifications

This version was first used in `course15_n6_mic_test` and later for this project's keyword-spotting dataset collection. The retained C/H files, startup code, and project settings come directly from the local originals. Content hashes are in the [supplementary provenance record](../../docs/evidence/development-history/source_provenance.json).

The base is `Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder` from [STM32CubeN6](https://github.com/STMicroelectronics/STM32CubeN6/tree/1fc803683e03b0ce78e64523441d31acd0db2829), with local Git base commit `1fc803683e03b0ce78e64523441d31acd0db2829`.

The recording input is the board's digital microphone through MDF. This version retains MDF and DMA initialization, captures samples into RAM, and transmits them to the PC from the main loop. The official example originally played recorded audio through SAI/WM8904. That playback code remains in the file, but the current `main()` does not call `Playback_Init()`; WM8904 belongs to this playback path.

The [original diff](upstream_changes.patch) records enabling BSP COM and HAL UART, replacing the main loop and MDF callbacks, and adding UART drivers to the IDE project.

| Code entry | Implementation |
| --- | --- |
| `MicRecord` in [main.c](FSBL/Src/main.c) | Nominal 16 kHz, mono, 16-bit, 80,000 samples; capture five seconds before sending 160,000 bytes |
| `MicCopy` and MDF half/full callbacks | A 2,048-sample DMA buffer split into two halves; copy at most 1,024 samples each time, skip two initial warm-up blocks, and limit the last copy to the remaining length |
| `MicActive` / `MicFailed` / `MicCount` | Recording state shared by interrupts and the main loop; publish completed samples with a memory barrier and stop DMA from the main loop |
| `MicRecord` / `HAL_MDF_ErrorCallback` | A 12-second capture timeout, start/stop errors, and insufficient-sample checks; saturation is counted by the receiver, while other MDF/DMA errors abort recording |
| `MicTx` / `MicCrc32` | Chunked serial transmission, length, and CRC32 in the main loop; interrupt callbacks do not transmit serial data |
| `main` | `?` queries readiness and `R` starts recording; the green LED indicates recording, while errors are reported through the red LED and protocol |
| [stm32n6xx_hal_msp.c](FSBL/Src/stm32n6xx_hal_msp.c) / [interrupt entries](FSBL/Src/stm32n6xx_it.c) | Official base configuration for MDF pins, clocks, GPDMA links, and interrupts |
| `MPU_Config` / [linker settings](STM32CubeIDE/FSBL/STM32N657X0HXQ_AXISRAM2_fsbl.ld) | Place DMA-related buffers in a non-cacheable region; this is preserved separately from the later dual-model firmware's cache-maintenance strategy |

## Transfer protocol and later integration

The ready message is `N6MIC_READY,1,16000,1,16,80000`. After recording, the firmware sends an `N6MIC_DATA` header containing format/length/CRC32, the PCM bytes, and an `N6MIC_DONE` trailer. The [host receiver](../recording_tools/n6_receive_wav.py) checks those fields, exact length, and CRC32 before creating a WAV. The [collection program](../collect_n6.py) organizes recordings into five classes.

This stage records first and transmits afterward. The dual-model [continuous capture module](../../firmware/Src/finder_mic.c) instead uses circular DMA, a ring buffer, and one-second sliding windows. Both stages retain their implementations; later driver parameters are not retroactively assigned to this snapshot.

## Snapshot and build dependencies

This directory includes FSBL sources, CubeIDE projects, startup code, linker settings, and the original `.ioc`, rather than the complete STM32CubeN6 SDK. HAL, BSP, CMSIS, and other dependencies must come from the pinned base above. IDE source links preserve the original environment, including local absolute paths for two UART sources; on another machine, map them to the SDK's `Drivers/STM32N6xx_HAL_Driver/Src/`.

The `.ioc` and [UPSTREAM_README.md](UPSTREAM_README.md) remain in their original upstream form and describe the original example. The modified C code and diff define this version's five-second recording behavior; regenerating from the `.ioc` alone does not reproduce those modifications. Original ELF/BIN files are not included. The archival operation only preserved sources; it did not rebuild, connect to a board, or run acceptance tests.

Original copyright headers and the [SDK license index](LICENSE.md) are retained. The index lists examples under BSD 3-Clause; other SDK components follow their respective terms.
