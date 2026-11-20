# System architecture

[繁體中文](architecture.md) | [English](architecture.en.md)

The system integrates continuous audio capture, KWS command recognition, YOLO vision inference, and LCD rendering in one firmware application. Speech updates the search target while vision continuously looks for that object class. The two models use the shared NPU sequentially, with separate tasks handling display and image signal processor (ISP) updates.

See [dual-model memory and deployment](memory-deployment.en.md) for the full runtime/storage address map, and [toolchain compatibility](toolchain-compatibility.en.md) for pinned upstream versions, actual build commands, and packaging changes.

This description is based on the local frozen-version records. Model, output, and log paths below describe the complete local project; not all of those files are included in the public repository.

| Path | Role |
| --- | --- |
| `firmware/Src/main.c` | Clock, NPU, cache, external RAM/Flash, UART, and FreeRTOS initialization |
| `firmware/Src/app.c` | KWS command acceptance, target selection, YOLO inference, display, and task coordination |
| `firmware/Src/finder_mic.c` | MDF1/GPDMA capture, ring buffer, and one-second PCM snapshots |
| `firmware/Src/finder_kws.c` | CPU MFCC frontend, quantization, and STAI KWS inference |
| `firmware/Inc/finder_kws_tables.h` | Frontend coefficients and quantization parameters matching the current KWS model |
| `firmware/Src/app_cam.c` | Official Camera Middleware/DCMIPP display and model-input pipelines |
| `firmware/Model/`, `firmware/Model/kws/st_ai_output/` | Vision and KWS generated code compiled into the firmware |
| `firmware/Lib/AI_Runtime/` | Official STAI/ATON runtime and CPU software operators |
| `firmware/Lib/ai-postprocessing-wrapper/`, `firmware/Lib/lib_vision_models_pp/` | Official YOLOv8 instance-segmentation postprocessing |
| `firmware/Makefile`, `firmware/mks/`, `firmware/Gcc/STM32N657xx.ld` | Actual GCC build entry and memory layout |
| `vision/` | Official instance-segmentation example and source of the vision model/generated code, retaining existing modifications and history |
| `kws/` | Existing capture, dataset-preparation and training scripts, data, models, and evaluation reports |
| `output/`, `logs/` | Historical outputs and test records; not every historical output is the final version |

MDF captures one second, or 16,000 audio samples, at a nominal 16 kHz, providing a new window approximately every 200 ms. Historical board logs report approximately 16,009 Hz. The MFCC pipeline removes the mean, applies a 480-sample periodic Hann window with a 320-sample hop, runs a 512-point FFT, 40 HTK Mel filters, a natural logarithm, and a 13-dimensional orthonormal DCT, then normalizes with the model coefficients, clips to ±6, and quantizes to `49×13×1 int8`. Output order is cup, bottle, phone, unknown, silence.

KWS uses a depthwise-separable CNN with work divided between NPU and CPU; the final Softmax is a CPU operator. Before the CPU writes new input, the NPU cache is cleaned and invalidated, followed by invalidation of the CPU's stale copy. After writing, the CPU cache is cleaned so the NPU can read the input. Command acceptance requires peak amplitude of at least 2500, a top score of at least 0.90, a margin of at least 0.25 over the runner-up, two consecutive matching windows, and at least 1200 ms between commands. After acceptance, two quiet windows re-arm the state machine.

Camera Pipe 1 supplies the LCD image. Pipe 2 takes a central square and scales it to `256×256 RGB uint8`. YOLO has two int8 outputs: `116×1344` detection data and `64×64×32` mask prototypes. Official postprocessing identifies output order by tensor size and performs decoding, NMS, and mask generation, using confidence threshold 0.50, NMS IoU 0.40, and at most 10 results. The application filters COCO cup=41, bottle=39, and cell phone=67; FOUND requires two consecutive frames with box IoU of at least 0.30.

A single `nn_thread_fct()` polls KWS and runs YOLO sequentially on the shared NPU; the two models do not execute simultaneously. Voice switches the search target while YOLO continues running. Separate tasks update the LCD and ISP. UART is 115200, 8N1.

| Memory region | Base/capacity | Usage in the existing successful build |
| --- | --- | ---: |
| Application SRAM | `0x34000400` / 1023 KiB | 535,544 bytes |
| Vision command Flash | `0x71380000` / 2 MiB | 230,528 bytes |
| Application/display PSRAM | `0x91000000` / 16,128 KiB | 8,949,920 bytes |
| Dedicated KWS RAM | `0x91FC0000` / 256 KiB | About 17.03 KiB allocated by generated code |

Dedicated KWS RAM uses absolute addresses in the generated code, so a linker usage of 0 B does not mean it is unused. YOLO activation pools are also allocated by generated code; the linker report alone is insufficient.
