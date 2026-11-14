# KWS model code-generation configuration

[繁體中文](README.md) | [English](README.en.md)

These two configuration files were copied directly from the final model's generation workspace without content changes.

| File | Purpose |
| --- | --- |
| [kws_neuralart.json](kws_neuralart.json) | Neural-ART configuration selecting the `kws` profile and `kws.mpool` |
| [kws.mpool](kws.mpool) | KWS memory regions, access attributes, and capacities |

| Region | Base address | Capacity |
| --- | --- | --- |
| KWS working memory | `0x91FC0000` | 256 KiB |
| KWS weights | `0x70700000` | 64 KiB |

The matching environment is ST Edge AI 4.0.1. The generation command in the existing final-version records is shown below; the working directory must contain both configuration files and the matching model:

    stedgeai generate --model kws_int8.tflite --target stm32n6 --name kws_network --st-neural-art kws@kws_neuralart.json --input-data-type int8 --output-data-type int8

Matching model SHA-256: `bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b`.

This directory provides configuration and the recorded command, not model weights, and does not automatically generate code. Frontend and quantization coefficients are in [`finder_kws_tables.h`](../../firmware/Inc/finder_kws_tables.h).

## Original generation and deployment records

The [original command record](../../docs/evidence/development-history/codegen_20261008/command.json), [generation log](../../docs/evidence/development-history/codegen_20261008/codegen.log), and [text report](../../docs/evidence/development-history/codegen_20261008/kws_network_generate_report.txt) are retained.

ST Edge AI first converts INT8 TFLite into internal ONNX and quantization JSON, then invokes Neural-ART; the workflow includes the ONNX intermediate representation. The report records 11 hardware stages and 1 software Softmax stage, with no epoch-controller command blob. Allocations are 11,409 bytes for weights and 17,440 bytes for activations. Full configuration information is in [kws_network_c_info.json](../../docs/evidence/development-history/codegen_20261008/kws_network_c_info.json).

The [deployment image manifest](../../docs/evidence/development-history/deployment_20261008/flash_manifest.json) and [verification record](../../docs/evidence/development-history/deployment_20261008/flash_verified.json) retain addresses, hashes, and successful write results for the KWS weights and application image at that time. All figures come from existing records.
