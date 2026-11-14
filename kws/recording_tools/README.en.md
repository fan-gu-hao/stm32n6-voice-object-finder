# Recording and serial-transfer tools

[繁體中文](README.md) | [English](README.en.md)

These two host tools come from the existing `course15_n6_mic_test` project. The public copies adapt project paths, debugger serial number, and serial-port configuration while preserving the recording protocol, CRC32 checks, and GDB loading workflow.

| Program | Reading focus |
| --- | --- |
| [n6_receive_wav.py](n6_receive_wav.py) | Exclusive serial access, handshake, chunked reception, timeout handling, CRC32, and WAV storage |
| [n6_mic_start_and_record.sh](n6_mic_start_and_record.sh) | Tool discovery, vector-table checks, RAM loading, core-register setup, startup checkpoints, and process cleanup |

## External dependencies

The matching [FSBL sources, IDE settings, and upstream diff](../recording_firmware/README.en.md) are published. The host tools still require the two corresponding prebuilt files from the existing recording project. The complete STM32CubeN6 SDK and these ELF/BIN files are not included:

- `STM32CubeN6/Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder/STM32CubeIDE/FSBL/Debug/MDF_AudioRecorder_FSBL.elf`
- `MDF_AudioRecorder_FSBL.bin` in the same directory

These must be the five-second recording version supporting `N6MIC_READY,1,16000,1,16,80000`, not an arbitrary version of the official recording example. The host tools use STM32CubeIDE 2.2.0 debugging tools and Linux serial interfaces.

## Configuration and execution

| Environment variable | Purpose |
| --- | --- |
| `N6_MIC_ROOT` | Recording-project root; defaults to `STM32N6ai/course15_n6_mic_test` under the user's home directory |
| `N6_MIC_IDE` | CubeIDE installation; defaults to `/opt/st/stm32cubeide_2.2.0` |
| `N6_STLINK_SERIAL` | Actual ST-LINK debugger serial number; required |
| `N6_MIC_PORT` | Actual serial-port path under `/dev/serial/by-id/`; required |

After configuration, with the board in the development boot state required by the tool, run from this repository's root:

    python3 kws/collect_n6.py

The first recording loads and starts the recorder in RAM through GDB, then receives audio. This is not the startup command for the current dual-model demonstration firmware; it changes the program currently running on the board.

The received format is 16 kHz, mono, 16-bit, 80,000 samples, with serial baud rate 115200. Original WAVs are saved under `recordings/` in the recording project, and labeled data under this repository's `kws/data_raw/`. Neither is included in public commits.

Publication preparation only organized source code and checked syntax; it did not reconnect to a board or record audio. Training scripts additionally use NumPy, SciPy, scikit-learn, and TensorFlow. The public version does not yet provide a complete version-lock file for the training environment.
