# Third-party sources and publication scope

[繁體中文](THIRD_PARTY_NOTICES.md) | [English](THIRD_PARTY_NOTICES.en.md)

This project contains components under multiple licenses. It does not apply a single MIT or Apache license to all contents. Existing copyright, license, and third-party notices in individual files remain applicable.

| Source | Purpose | Version or record |
| --- | --- | --- |
| [ST hand-recognition example](https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks) | Basis for the firmware framework and runtime | Base commit `6c31300`; full local provenance is recorded in `docs/source-provenance.json` |
| [ST instance-segmentation example](https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation) | Reference for vision integration | `42f7d645f1ed61967a922defa4aa97b95d390b16` |
| [YOLOv8 models for STM32](https://github.com/stm32-hotspot/ultralytics/tree/176ecaa749b79a3f53ce077d2b14412fa45e81a0/examples/YOLOv8-STEdgeAI) | Source of the quantized vision model used locally | `176ecaa749b79a3f53ce077d2b14412fa45e81a0` |
| [STM32CubeN6 recording example](https://github.com/STMicroelectronics/STM32CubeN6/tree/1fc803683e03b0ce78e64523441d31acd0db2829/Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder) | Base for the standalone recording firmware | Local Git base `1fc803683e03b0ce78e64523441d31acd0db2829`; [modified sources and diff](kws/recording_firmware/README.en.md) |

Component license indexes are in [`firmware/LICENSE.md`](firmware/LICENSE.md) and [`vision/LICENSE.md`](vision/LICENSE.md). The Google/Apache model entries in the original firmware index come from the upstream hand-recognition example and do not establish the license of the current YOLO model.

The upstream YOLO Notice describes distribution restrictions when AGPL-3.0-only and certain ST-licensed components are combined. This public version does not provide model weights, generated model code, or integrated flash images, and does not claim additional distribution rights. Third-party models must be obtained and used under their actual source terms.

Official components retain their original licenses. This project's additions and modifications are described in [`docs/code-tour.md`](docs/code-tour.en.md).

The standalone recorder retains the [STM32CubeN6 license index](kws/recording_firmware/LICENSE.md) and original file headers. The added KWS generation text/JSON files are tool reports and configuration metadata; they contain neither model weights nor generated model C code. The tool's [original license index](docs/evidence/development-history/codegen_20261008/STEdgeAI_LICENSE.txt) is also retained.
