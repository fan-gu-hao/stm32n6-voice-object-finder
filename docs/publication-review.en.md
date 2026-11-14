# Engineering results and publication inventory

[繁體中文](publication-review.md) | [English](publication-review.en.md)

A subsequent review added the [work and evidence map from setup to freeze](development-coverage.en.md). The 67 items below form a disposition list of supplied materials, not an exhaustive master list of all STM32N6 project conversations and files. Explicit historical gaps remain for early environment setup, course13, and temporary terminal programs.

Preparation date: 2026-11-13. The 67-item source/evidence report supplied by the user was checked against published dual-model version 988aeb31f35e358c7c75bc898e52a201da4b9298 and vision version c044d7d4230eb2438340255e51df5c88162a3fda. The original project and frozen firmware were left intact.

## Published entry points by stage

| Engineering stage | Preserved implementation and evidence | Public entry |
| --- | --- | --- |
| Earlier models and tool environment | Original model, ONNX, onnx2tf/SavedModel, ST INT8, tool versions, and successful logs | [Complete vision work index](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md) |
| Model Zoo postprocessing adaptation | Detection/mask output identification, quantized interface and header-generation patches; local Neural-ART argument and image-alignment fixes | [Vision engineering guide](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| Vision validation and experiments | A1 sources, A2 numerics/boxes/masks, A3 performance, A4 memory, A5 reliability | [Vision project](https://github.com/fan-gu-hao/stm32n6-instance-segmentation) |
| Historical serial-interrupt experiment | Queue, interrupt callbacks, HAL dependencies, two installers, deployment and rollback, with experimental-version boundaries | [Experiment source snapshot](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/docs/publication_supplement_20261113/uart_it/source_snapshot) |
| Standalone recording firmware | Five-second recording, DMA callbacks, warm-up, timeout, errors and CRC32; complete FSBL sources, IDE snapshot, and upstream diff | [Recording firmware](../kws/recording_firmware/README.en.md) |
| Host loading and data collection | Vector-table/RAM startup, serial handshake, exact length and CRC32, WAV, labeling, and segmentation | [Host tools](../kws/recording_tools/README.en.md), [dataset preparation](../kws/prepare_dataset.py) |
| Training evolution | Initial MFCC/depthwise-separable model and INT8 export, live-data versions 2/3, final grouped version | [Training history](../kws/training_history/README.en.md), [final snapshot](../kws/training_snapshot/README.en.md) |
| Deployment debugging | Fixed INPUT/PCM comparison code, live raw-window/feature return, and CPU/NPU cache corrections | [Board code](../firmware/Src/finder_kws.c), [comparison reports](evidence/development-history/README.en.md) |
| Live data and evaluation | 48-clip manifest, usage and PCM hashes; five-fold and held-out evaluation | [Dataset manifest](evidence/development-history/live_dataset_manifest_20261008.json), [evaluation reports](evidence/README.en.md) |
| Final generation and deployment | Commands, internal ONNX/quantization metadata, execution stages, memory, build, and successful write verification | [Generation and deployment evidence](evidence/development-history/README.en.md) |
| Live voice and vision | Six final-version command acceptances and non-command results; earlier FOUND vision records, each labeled by version | [Results](results.en.md) |
| Tasks and memory integration | MDF/DMA, caches, one NPU inference task, display and ISP, target generations, linking, and build | [Engineering workflow](engineering-workflow.en.md), [code tour](code-tour.en.md) |
| IDE source synchronization | Original tool, path checks, preview, backups, hash-based concurrency checks, and atomic replacement | [Synchronization tool](../tools/ide/README.en.md) |

## Disposition of the 67 materials

The [itemized inventory](evidence/development-history/review_inventory.json) records each original path, hash, publication location, and disposition. The [provenance record](evidence/development-history/source_provenance.json) additionally records original/public hashes and transformations for the files added in that preparation.

- Fourteen UART patch/deployment/rollback materials already published in the vision repository were verified against the supplied originals using Git object hashes. Readable C/H sources, the main program, and two installer versions were then added.
- Recording firmware, early training, IDE synchronization, comparison/live-data reports, and final generation/deployment records were added to their corresponding directories.
- Existing host recording, collection, and segmentation tools retain their public versions with adjusted paths. Differences from original local paths are not counted again as missing uploads.
- SDK startup files for other toolchains are indexed through the pinned upstream version. This repository adds CubeIDE source/configuration snapshots while preserving file copyrights and license indexes.

The 107 content differences in an earlier hash inventory included backups, official SDK files, generated code, and build files; they are not 107 original programs. The additions preserve actual engineering sources and evidence item by item.

## Known material scope

- The fixed five-class PC reference report is public, but original line-by-line board CMP logs for INPUT/PCM are not in the supplied report. Code and the existing development-result summary are retained with their evidence level identified.
- The specified course13 custom-tool directories were absent from the collection results. Environment inheritance and successful course14 conversions are supported by evidence; failure to collect a standalone script is not described as failure to perform that work.
- Receiver, coefficient-generation, or analysis programs executed temporarily in a terminal and not saved as files cannot be reconstructed verbatim from this report. Existing functions, settings, reports, and development steps have entry points; newly written programs are not passed off as historical originals.
- Raw recordings, model weights, generated model code, and the complete local frozen five-image package retain the established publication scope. Their roles, versions, and available hashes are documented separately.
- The demonstration video remains pending. Preparation added no training, builds, flashing, or hardware acceptance tests.

The completeness scope of this inventory is the supplied material and evidence accessible in the two repositories. It does not claim access to every file on the user's computer or every historical conversation.
