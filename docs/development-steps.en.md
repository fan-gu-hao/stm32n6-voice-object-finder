# Dual-model voice object finder: 32 complete development steps

[繁體中文](development-steps.md) | [English](development-steps.en.md) | [Back to the homepage](../README.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](toolchain-compatibility.en.md).

This project implements an MCU-level embedded AI system combining voice and vision on the STM32N6570-DK. The steps below cover requirements, model deployment, data and training, real-time firmware, memory, numerical debugging, and delivery. Each step links to implementation, configuration, or development records. Numbering follows engineering dependencies; data iteration and debugging overlapped during development.

Alongside firmware and training sources, the [development host workflows](../tools/development-history/README.en.md) preserve packaging diagnostics, fixed comparisons, live collection, generation, deployment, and observation programs from the original operation blocks. Each file records its source, dependencies, and execution status at that stage.

## Phase 1: requirements, project setup, and vision deployment (1–5)

<a id="step-01"></a>
### 1. Define the dual-model demonstration and interaction

- Run speech and image inference on the STM32N6570-DK, using the board's digital microphone, camera, and LCD as the operating interface.
- Say `cup`, `bottle`, or `phone` to select a search target through the speech model. Camera capture and YOLOv8 instance segmentation run continuously and search for the selected object.
- Display the target, searching/found state, bounding box, and segmentation mask on the LCD.

**Implementation:** `finder_voice_poll`, `finder_select_target`, `nn_thread_fct`, and `dp_thread_fct` in [app.c](../firmware/Src/app.c); [system architecture](architecture.en.md).

<a id="step-02"></a>
### 2. Establish the application project and pin the environment

- Create the dual-model project, separating the vision reference application, main firmware, and speech data/training tools into `vision/`, `firmware/`, and `kws/`.
- Use the startup, camera, display, FreeRTOS, and NPU framework from ST's dual-model hand example as the platform foundation. Replace its models and add this project's data workflow, speech model, search logic, and display behavior.
- Pin source revisions and tools: GCC 14.3.1, ST Edge AI Core 4.0.1, Neural-ART 1.1.3-275, and STM32CubeIDE 2.2.0, together with inference-runtime versions.
- Track dependencies between generated models, runtime components, and build sources so changes remain traceable to their corresponding versions.

**Implementation:** [source versions](source-provenance.json), [build environment](build.en.md), [platform initialization in main.c](../firmware/Src/main.c), and [application Makefile](../firmware/Makefile).

**Original host workflow:** [Vision-project setup source](../tools/development-history/vision_01_prepare_vision.sh).

<a id="step-03"></a>
### 3. Export, quantize, and generate the YOLO model for N6

- Use Python/PyTorch tools to load the original YOLOv8n-seg `.pt` model, configure a 256×256 input, export ONNX, and convert it to TensorFlow SavedModel with `onnx2tf`.
- Personally configure and execute per-channel INT8 quantization with calibration images, image rescaling, and INT8 input/output settings, producing TFLite.
- Compare original, floating-point, and INT8 models on the PC; check I/O shapes, types, quantization scales, zero points, and postprocessing interfaces.
- Run ST Edge AI/Neural-ART generation to produce N6 network code, model interfaces, weights, and execution commands; retain generation settings and memory-pool configuration.
- Compile, link, and package the reference application, then move the generated artifacts into the dual-model firmware and adapt its runtime and build.
- Retain code, configuration, successful logs, and per-stage model fingerprints for the complete export → quantization → generation → integration workflow.

**Implementation and records:** [Complete vision conversion workflow](../vision/deployment/README.en.md), [generation script reference](../vision/deployment/upstream-reference/generate-n6-model_STM32N6570-DK.sh), [Neural-ART settings](../vision/deployment/upstream-reference/user_neuralart_STM32N6570-DK.json), [recorded N6 input fingerprint](../sources.txt), [integration workflow](engineering-workflow.en.md).

**Original host workflow:** [N6 generation and application build](../tools/development-history/vision_03_generate_and_build_vision.sh). Python export and quantization settings, logs, and validation programs are linked in the complete vision workflow above.

<a id="step-04"></a>
### 4. Match generated models to the inference runtime

- Update the vision reference application's runtime from 1200 to 1201 and the main hand-example foundation from 1100 to 1201.
- Pair the headers, libraries, and NPU support sources in `Inc`, `Lib`, and `Npu`, linking `NetworkRuntime1201_CM55_GCC.a`.
- Retain the FreeRTOS operating-system abstraction and asynchronous inference mechanism. Handle wait events through the corresponding waiting interface and reset state for the next execution after completion.
- Compare the official revisions used during development, documenting the differences between generation tools, README baselines, and build lists, along with the project's alignment changes.

**Implementation:** [ai.mk](../firmware/mks/ai.mk), [app.c](../firmware/Src/app.c), and [finder_kws.c](../firmware/Src/finder_kws.c); [official baselines and project runtime pairing](toolchain-compatibility.en.md).

**Original host workflow:** [Reference runtime pairing](../tools/development-history/vision_02_match_vision_runtime.py), [Application runtime pairing](../tools/development-history/vision_06_match_main_runtime.py).

<a id="step-05"></a>
### 5. Convert the hand-model application into a YOLO application

- Remove the palm-detection, hand-landmark, and related old-model build entries. Add this project's YOLO network, STAI interface, weights, and execution commands.
- Revise model and postprocessing build lists so the application links the intended sources and inference runtime.
- Adapt initialization and input/output buffer interfaces to obtain tensor pointers.
- Check input/output counts, dimensions, data types, sizes, and quantization information so capture, inference, and postprocessing use consistent interfaces.

**Implementation:** [Makefile](../firmware/Makefile), [ai.mk](../firmware/mks/ai.mk), [main.c](../firmware/Src/main.c), and [app.c](../firmware/Src/app.c); [migration steps and artifact names](engineering-workflow.en.md).

**Original host workflow:** [Six-artifact migration](../tools/development-history/vision_05_copy_vision_artifacts.sh), [Model build replacement](../tools/development-history/vision_07_update_model_build_list.py).


## Phase 2: visual search, display, and memory (6–11)

<a id="step-06"></a>
### 6. Configure camera input and display geometry

- Configure the digital camera interface pixel pipeline (DCMIPP) for display and neural-network input.
- Take a central square from the LCD field of view as the recognition region.
- Resize that region to the model's **256×256 RGB UINT8** input.
- Use consistent geometry between model input and the LCD recognition region for subsequent box and mask mapping.

**Implementation:** `DCMIPP_PipeInitNn` in [app_cam.c](../firmware/Src/app_cam.c); `Display_NetworkOutput` in [app.c](../firmware/Src/app.c).

<a id="step-07"></a>
### 7. Port vision postprocessing and model-output interfaces

- Integrate ST's instance-segmentation postprocessing core and YOLOv8 wrapper, connecting the INT8 detection and mask-prototype tensors.
- The detection output is `1×116×1344`, comprising 4 box parameters, 80 classes, and 32 mask coefficients; mask prototypes are `1×64×64×32`.
- Configure **80 classes, 1,344 candidate positions, and 32 mask prototypes of 64×64**, including each output's quantization scale and zero point.
- Integrate box decoding, non-maximum suppression (NMS), and mask reconstruction. Set confidence to **0.50**, NMS intersection over union (IoU) to **0.40**, and retain at most **10** results.
- The postprocessing core retains ST attribution; this project adapts the model interface, parameters, build, and search/display data flow.

**Implementation:** [YOLOv8 postprocessing wrapper](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c), [ai.mk](../firmware/mks/ai.mk), and [app.c](../firmware/Src/app.c).

**Original host workflow:** [Postprocessing migration source](../tools/development-history/vision_08_import_postprocessing.py).

<a id="step-08"></a>
### 8. Implement target-specific search and stable confirmation

- Map the three commands to COCO classes: cup `41`, bottle `39`, and cell phone `67`.
- Filter each inference result for the selected target and choose the highest-confidence box when multiple objects of that class are present.
- Require hits in **two consecutive frames** with box IoU of at least **0.30** before publishing FOUND.
- Clear the previous target's found state and accumulated hits whenever the target changes.
- Complete the vision-search functionality and retain board records for the vision version before adding speech.

**Implementation:** `finder_select_target`, `box_iou`, `FINDER_CONFIRM_FRAMES`, and `nn_thread_fct` in [app.c](../firmware/Src/app.c); [vision-version operation log](evidence/development-history/finder_vision_20261004.log).

<a id="step-09"></a>
### 9. Display boxes, segmentation masks, and search state

- Transform model coordinates into the LCD's central recognition region and overlay the box, mask, and current search state.
- Preserve inference results as a snapshot, separating postprocessing workspace lifetime from display-data lifetime.
- Let the display task obtain its own drawing snapshot while holding the mutex, then render outside the lock to shorten shared-data lock duration.
- Separate result-mask and drawing-mask storage so subsequent postprocessing cannot overwrite the data currently being displayed.

**Implementation:** `result_mask`, `drawing_mask`, `Display_NetworkOutput`, and `dp_thread_fct` in [app.c](../firmware/Src/app.c); [data-handoff architecture](architecture.en.md).

<a id="step-10"></a>
### 10. Coordinate camera, interrupt, and inference data handoffs

- Use image-buffer queues and counting semaphores to coordinate camera capture and inference.
- Correct the interrupt path in `bqueue_get_free`, using `xSemaphoreTakeFromISR` to acquire a free buffer and `portYIELD_FROM_ISR` when a task switch is required.
- Retain ordinary semaphore operations in task context and select the FreeRTOS interface appropriate to each caller.
- Maintain cache coherence after acquiring an image, copy it into the model input, and return the camera buffer only after input cache maintenance completes.
- Separate the next camera capture from the current inference input to prevent premature reuse of shared buffers.

**Implementation:** `bqueue_get_free`, `nn_input_queue`, and `nn_thread_fct` in [app.c](../firmware/Src/app.c); [interrupt and buffer changes](engineering-workflow.en.md).

**Original host workflow:** [Application/interrupt integration source](../tools/development-history/vision_12_integrate_vision_application.py).

<a id="step-11"></a>
### 11. Reconfigure vision memory and image sections

- Reduce application SRAM from **1,535 KiB** to **1,023 KiB**, covering `0x34000400–0x34100000` and avoiding the vision workspace.
- Collect vision commands from `.flash_blob` into `.flash_section`, located at external Flash **`0x71380000`** with **2 MiB** reserved.
- Place large display and postprocessing buffers in external PSRAM; collect `.psram_bss` into `.psram_section (NOLOAD)`.
- Modify the linker script and build-section definitions so code, workspaces, weights, and commands occupy their assigned regions.
- Extract the application and vision commands separately from one ELF to avoid binary expansion across address gaps. Later KWS integration reserves its own region at the end of the PSRAM window.

**Implementation:** [linker script](../firmware/Gcc/STM32N657xx.ld), [Makefile](../firmware/Makefile), and [vision memory-pool reference](../vision/deployment/upstream-reference/my_mpools/stm32n6-app2_STM32N6570-DK.mpool); [complete memory map and image boundaries](memory-deployment.en.md).

**Original host workflow:** [Camera/memory change source](../tools/development-history/vision_13_configure_camera_and_memory.py).


## Phase 3: speech data, model development, and quantization (12–16)

<a id="step-12"></a>
### 12. Build the speech-data collection workflow

- Define five classes: `cup`, `bottle`, `phone`, `unknown`, and `silence`. Record through the actual board microphone so the data includes device-specific capture characteristics.
- Capture five seconds per recording in **16 kHz, 16-bit, mono** format, totaling **80,000** samples.
- Record **12** takes for each command, **8** for unknown words, and **3** for silence: **47** original recordings.
- Capture five seconds into RAM before transmission from the main loop. Launch the recorder with the GDB RAM-loading tool; the host receiver handles handshakes, deadlines, length, format, and CRC32 checks.
- Retain source/session metadata, validate completed recordings, and resume unfinished collection after interruption.

**Implementation:** [collect_n6.py](../kws/collect_n6.py), [standalone recorder main.c](../kws/recording_firmware/FSBL/Src/main.c), [RAM-launch tool](../kws/recording_tools/n6_mic_start_and_record.sh), and [WAV receiver](../kws/recording_tools/n6_receive_wav.py).

<a id="step-13"></a>
### 13. Convert original recordings into one-second training clips

- Locate utterances using short-time energy and constrain neighboring-word boundaries to avoid including the next word.
- Pad clips to one second while retaining their original recording and utterance start/end positions.
- Split the original five-second recordings into training/validation groups before segmentation, keeping related clips from one source in the same partition.
- Produce **142 training clips and 49 validation clips** in the initial dataset, tracking the 47 recordings separately from the 191 derived clips.

**Implementation:** `speech_regions`, `extract_word`, and grouping in [prepare_dataset.py](../kws/prepare_dataset.py); [training-version history](../kws/training_history/README.en.md).

<a id="step-14"></a>
### 14. Implement the PC speech-feature pipeline

- Remove the mean from a one-second, **16,000-sample** waveform and analyze it with a **480-sample** periodic Hann window and **320-sample** hop.
- Run a **512-point** fast Fourier transform (FFT) and calculate the power spectrum.
- Apply **40 Mel filters**, the natural logarithm, and an orthonormal discrete cosine transform (DCT).
- Retain **13 Mel-frequency cepstral coefficients (MFCC)** per frame, producing a **49×13×1** input.
- Derive normalization from training data, clip features, and preserve the window, filter, DCT, and normalization coefficients for use on the board.

**Implementation:** `features` and coefficient construction in the [final train_kws.py](../kws/training_snapshot/train_kws.py); [board coefficient tables](../firmware/Inc/finder_kws_tables.h).

<a id="step-15"></a>
### 15. Design and train the five-class KWS model

- Design a compact keyword-spotting (KWS) network using MFCC inputs, convolutions, and depthwise-separable convolutions to control compute and model size.
- Include batch normalization, activation functions, global average pooling, and dropout, producing five class scores.
- Use class weights to account for data distribution and augment audio with gain, background noise, and time shifts.
- Retain training history, models, coefficients, and evaluation results. Initial offline validation was **48/49** for both float and INT8.
- Iterate data and training from board behavior, retaining the initial, live-data, and final grouped-training source versions.

**Implementation:** [initial training script](../kws/training_history/20261005_baseline/train_kws.py); `build_model` and `augment` in the [final network/augmentation source](../kws/training_snapshot/train_kws.py); [training history](../kws/training_history/README.en.md).

<a id="step-16"></a>
### 16. Quantize and export the custom speech model

- Export the trained network as TensorFlow SavedModel and calibrate quantization with representative training data.
- Convert to **INT8 TFLite** and check input/output shapes, types, scales, and zero points.
- Compare float and quantized classifications, retaining models, quantization parameters, and evaluation reports.
- Export feature coefficients alongside the model so board preprocessing and the speech model use the same version.

**Implementation:** `export_int8` in [train_kws_groupcv.py](../kws/training_snapshot/train_kws_groupcv.py); [training snapshot](../kws/training_snapshot/README.en.md) and [final held-out-audio report](evidence/kws-int8-holdout.json).

## Phase 4: second-model and real-time firmware integration (17–21)

<a id="step-17"></a>
### 17. Give KWS independent generation and RAM/Flash allocation

- Assign KWS a separate network name and context to avoid generated-symbol and interface collisions with YOLO.
- Reserve **256 KiB at PSRAM `0x91FC0000`** for KWS activations and input/output, and **64 KiB at Flash `0x70700000`** for speech weights.
- Run ST Edge AI through its internal ONNX and quantization metadata stages, followed by Neural-ART compilation; integrate the speech network, interfaces, and weights into the application.
- The final configuration contains **11 NPU hardware stages and 1 CPU Softmax stage**, with **11,409 B** of weight allocation and **17,440 B** of activation allocation.
- The CPU executes the tool-generated C control flow. This configuration does not enable the epoch controller and has no separate KWS EC blob.
- KWS uses generated absolute addresses for its workspace, so the linker reports 0 B in `KWS_RAM`; the generation report tracks the actual model allocation.

**Implementation:** [kws.mpool](../kws/deployment/kws.mpool), [kws_neuralart.json](../kws/deployment/kws_neuralart.json), [kws.mk](../firmware/mks/kws.mk), [original generation command](evidence/development-history/codegen_20261008/command.json), and [compiler report](evidence/development-history/codegen_20261008/kws_network_generate_report.txt).

**Original host workflow:** [KWS host generation workflow](../tools/development-history/generate_groupcv_model.py).

<a id="step-18"></a>
### 18. Integrate the standalone recorder as continuous audio input

- Integrate the multifunction digital filter (MDF) and general-purpose DMA (GPDMA), configuring microphone pins, clock division, filtering, decimation, and peripheral access attributes.
- Preserve the image system's shared PLL2 and configure the microphone's IC8 divider so audio and vision coexist.
- Use circular DMA and half/full callbacks to process audio blocks, skip warm-up, and write into a **32,768-sample ring buffer**.
- Take the latest **16,000 samples** as a one-second window. Require at least **3,200 new samples** before another window becomes eligible, nominally about **200 ms**; DMA block delivery and task scheduling determine the actual interval.
- Handle ring wraparound and discard snapshots if copying is delayed long enough for their source data to be overwritten.

**Implementation:** `finder_mic_start`, `receive_block`, `finder_mic_take`, and MDF callbacks in [finder_mic.c](../firmware/Src/finder_mic.c); [audio interface](../firmware/Inc/finder_mic.h).

<a id="step-19"></a>
### 19. Port the Python feature pipeline to C

- Use the CMSIS-DSP real FFT, followed by power-spectrum calculation, Mel filtering, logarithms, and DCT.
- Handle the real FFT's special DC/Nyquist storage layout to preserve the Python feature definition.
- Normalize, clip, and quantize with the training-exported coefficients, producing **637 INT8 features**.
- Allocate FFT, spectrum, power, and feature workspaces statically and restrict them to one inference task, reducing task-stack usage.
- Check input/output shapes, types, scales, and zero points at compile time and initialization to catch model/coefficient version mismatches early.

**Implementation:** `encode_mfcc`, `finder_kws_init`, and `finder_kws_classify` in [finder_kws.c](../firmware/Src/finder_kws.c); [feature coefficients](../firmware/Inc/finder_kws_tables.h) and [DSP build fragment](../firmware/mks/kws.mk).

<a id="step-20"></a>
### 20. Maintain CPU, DMA, and NPU cache coherence

- Align DMA descriptors and audio buffers to **64 and 32 bytes**, respectively.
- Maintain CPU cache after DMA writes so processing sees fresh audio. Complete the handoff with a memory barrier before publishing a new ring-buffer write position.
- Before the CPU updates a KWS input, clean and invalidate old NPU cache contents, then invalidate the CPU's old copies.
- Clean CPU cache after writing new features so the NPU reads current data; wait for asynchronous inference completion and prepare the next execution state.
- Read outputs according to where they are produced. The final KWS Softmax runs on the CPU, so its quantized output is read from the CPU-produced result.

**Implementation:** cache/ring-buffer handling in [finder_mic.c](../firmware/Src/finder_mic.c); `kws_begin_input_update`, `prepare_input_cache`, and `finder_kws_classify` in [finder_kws.c](../firmware/Src/finder_kws.c); [data lifetimes](memory-deployment.en.md).

<a id="step-21"></a>
### 21. Implement shared-NPU scheduling and cross-task state

- Initialize the inference runtime once while keeping separate YOLO and KWS contexts and input/output buffers.
- Poll KWS and run YOLO sequentially within `nn_thread_fct` on the shared NPU. Display and image signal processing (ISP) use two other cooperating FreeRTOS tasks.
- Update the search class through the voice target-selection interface. Increment a target-generation number on each change and recheck it after inference to discard results for an old target.
- Runtime speech capture/classification errors disable voice and display an error while retaining the vision code path. This isolation design has not undergone a separate fault-injection test.

**Implementation:** `nn_thread_fct`, `dp_thread_fct`, `isp_thread_fct`, `finder_select_target`, and `finder_voice_poll` in [app.c](../firmware/Src/app.c); [task/state architecture](architecture.en.md).

## Phase 5: builds, numerical debugging, and voice acceptance (22–25)

<a id="step-22"></a>
### 22. Integrate the build and correct startup/image packaging

- Build both models, postprocessing, MDF, CMSIS-DSP, and the shared runtime together, using consistent compiler settings for FFT and preprocessing.
- Check linked sections, capacity, and separately extracted images against deployment addresses.
- Investigate a version that passed programming verification but produced no display or serial output, comparing the original application and packaged contents byte by byte.
- After confirming identical program contents but a different payload offset, correct **`0x240` to `0x400`**, recheck alignment/content, and complete the subsequent deployment.
- Compare the official segmentation README and Makefile packaging options, preserving the alignment method adopted in this project and its successful records.

**Implementation and records:** [Makefile](../firmware/Makefile), [kws.mk](../firmware/mks/kws.mk), [packaging failure and correction](original-history-review.en.md), [official settings and build commands](toolchain-compatibility.en.md), and [final build log](evidence/development-history/deployment_20261008/build.log).

**Host workflows:** [payload contents/offset inspection](../tools/development-history/inspect_boot_payload.py), [alignment and programming](../tools/development-history/realign_and_flash_application.sh), and [subsequent programming retry](../tools/development-history/retry_aligned_application_flash.sh).

<a id="step-23"></a>
### 23. Build layered PC/board numerical comparisons

- First inject fixed INT8 features to test model deployment; then pass identical PCM through C preprocessing and inference.
- Add a third path that returns live audio, actual features, and model outputs for recomputation on the PC using the same window.
- One fixed sample per class matches the PC classification on both INPUT and PCM paths; **all 637 features per PCM sample match element by element**.
- The maximum output difference on either fixed-sample path is **one quantized integer unit**: zero for four classes and one for silence.
- Use these comparisons to separate model-interface, preprocessing, and data-handoff issues. Classification performance is evaluated separately on the dataset associated with each model version.

**Implementation and records:** `finder_kws_compare` and `finder_kws_live_capture` in [finder_kws.c](../firmware/Src/finder_kws.c); [comparison switches](../firmware/Inc/finder_kws_compare.h), [fixed reference data](../firmware/Inc/finder_kws_compare_data.h), [PC reference JSON](evidence/development-history/fixed_reference_20261007.json), and [original comparison results](original-history-review.en.md).

**Host workflows:** [export fixed references](../tools/development-history/export_fixed_reference.py), [install the comparison revision](../tools/development-history/install_fixed_comparison.py), and [build/deploy the comparison revision](../tools/development-history/build_flash_fixed_comparison.py).

**Original host workflow:** [Live reception and PC recomputation](../tools/development-history/compare_live_windows.py).

<a id="step-24"></a>
### 24. Diagnose live misclassifications and missed commands

- Capture PCM, 637 features, five outputs, and amplitude from the same window, returning chunked data with CRC32.
- For four live windows, INT8 features match exactly. Maximum output integer differences for silence, cup, bottle, and phone are **0, 0, 3, and 1**.
- The silence case is classified as phone on the board, with PC feature input, and through the complete PC frontend. Bottle ranks first in another case but remains below the acceptance threshold.
- Add top score, runner-up margin, consecutive hits, and clipping statistics; matching numerical inputs with wrong classifications focuses the investigation on data and model behavior.
- Add four initial live recordings, increasing training clips from 142 to 146 while retaining 49 validation clips. Offline performance remains 48/49, but a later six-command session accepts only two, prompting further live-data collection and training changes.

**Implementation and records:** `finder_kws_live_capture` and `live_send` in [finder_kws.c](../firmware/Src/finder_kws.c); speech diagnostics in [app.c](../firmware/Src/app.c); [live comparison report](evidence/development-history/live_comparison_20261007.json), [iteration history](original-history-review.en.md), and [live-data training version](../kws/train_kws_live_v3.py).

**Host workflows:** [install live comparison](../tools/development-history/install_live_comparison.py), [build/deploy live comparison](../tools/development-history/build_flash_live_comparison.py), [receive windows and recompute on the PC](../tools/development-history/compare_live_windows.py), and [record voice diagnostics](../tools/development-history/record_voice_diagnostics.py).

<a id="step-25"></a>
### 25. Implement the voice-command acceptance state machine

- Require peak amplitude of at least **2,500**, top-class probability of at least **90%**, and a lead of at least **25 percentage points** over the runner-up.
- Require **two consecutive windows** to qualify and at least **1,200 ms** between accepted commands.
- Disarm after acceptance and require **two quiet windows** before re-arming, preventing repeated acceptance of one sustained utterance.
- Display the last accepted command to reduce flicker from changing per-window candidates.
- Keep these acceptance conditions in the final version while improving recognition through additional data, training, and synchronized deployment.

**Implementation:** `finder_voice_poll`, `hits`, `quiet_windows`, `armed`, and speech thresholds in [app.c](../firmware/Src/app.c); [final voice-operation log](evidence/development-history/voice_groupcv_20261008.log).

## Phase 6: data iteration, final training, and deployment (26–30)

<a id="step-26"></a>
### 26. Expand live data and reorganize development/holdout sets

- Collect **48 live audio clips** from the application board: **32** for development and **16** held out for evaluation.
- Combine the original 142 training clips, 49 validation clips, four earlier live clips, and 32 new development clips into a **227-clip development pool**.
- Retain each clip's label, purpose, source, and PCM hash, improving coverage of actual board-captured speech and background noise.
- Constrain time shifts using utterance energy and boundaries so augmentation does not truncate the word.
- After moving the original 49 validation clips into development, evaluate the final model on the separate 16-clip holdout.

**Implementation and records:** [live collection plan](../kws/live_collection_plan.json), [48-clip manifest](evidence/development-history/live_dataset_manifest_20261008.json), [features and augmentation](../kws/training_snapshot/train_kws.py), and [development-data loading](../kws/training_snapshot/train_kws_groupcv.py).

**Host workflows:** [prepare the collection revision](../tools/development-history/prepare_live_collection.py), [build/deploy collection firmware](../tools/development-history/build_flash_live_collection.py), [collect the live dataset](../tools/development-history/collect_live_dataset.py), and [check the dataset](../tools/development-history/check_live_dataset.py).

<a id="step-27"></a>
### 27. Implement leakage-resistant grouped validation and final training

- Group by original recording and merge source groups with identical PCM hashes, keeping related clips in one fold.
- Check conflicting labels, overlapping groups, class coverage per fold, exactly one validation occurrence per sample, and development/holdout duplication.
- Derive normalization, background noise, and quantization-calibration data only from the training partition of each fold.
- Complete stratified grouped five-fold validation with an aggregate INT8 result of **224/227, 98.68%**.
- The best epochs are **82, 28, 66, 9, and 79**. Select their median, **66 epochs**, and train the final model on all 227 development clips.

**Implementation and records:** `load_development`, `make_splits`, `make_training`, `fit_model`, and `export_int8` in [train_kws_groupcv.py](../kws/training_snapshot/train_kws_groupcv.py); [five-fold report](evidence/kws-groupcv.json) and [training history](../kws/training_history/README.en.md).

<a id="step-28"></a>
### 28. Evaluate the final model and synchronize board artifacts

- Evaluate float and INT8 models on the **16 held-out clips**; both score **15/16, 93.75%**.
- Preserve the only misclassified cup sample and its scores. It is classified as phone at approximately **60.9%**, below the **90%** command-score threshold.
- Regenerate N6 artifacts for the final INT8 model and update model code, weights, preprocessing coefficients, scales, and zero points together.
- Change input zero point from **8 to 7**, disable development live-collection/comparison switches, and build the final firmware.
- Retain model hashes and generation settings to connect offline evaluation, generated artifacts, and the deployed board version.
- After generation completed, recursive discovery also found same-named files in the tool's working directories, stopping artifact validation. A follow-up check restricted discovery to the formal output before installation and building continued.

**Implementation and records:** [held-out-audio report](evidence/kws-int8-holdout.json), [final generation log](evidence/development-history/codegen_20261008/codegen.log), [model SHA-256](evidence/development-history/codegen_20261008/model_sha256.txt), [preprocessing coefficients](../firmware/Inc/finder_kws_tables.h), and [development comparison settings](../firmware/Inc/finder_kws_compare.h).

**Host workflows:** [final generation and original artifact check](../tools/development-history/generate_groupcv_model.py), [formal-output inspection](../tools/development-history/inspect_groupcv_codegen.py), and [synchronized installation/build](../tools/development-history/install_build_groupcv.py).

<a id="step-29"></a>
### 29. Organize five deployment images and install the final update

- Separate delivery into first-stage bootloader (FSBL), application, vision weights, KWS weights, and vision execution commands, recording addresses, capacities, and hashes.
- Program FSBL at addresses embedded in its HEX file. Store the application at **`0x70100000`**, vision weights at **`0x70380000`**, KWS weights at **`0x70700000`**, and vision commands at **`0x71380000`**.
- Distinguish storage from execution addresses: the application image resides in Flash while its linked execution location is internal SRAM.
- The final update writes and verifies the application and KWS weights, retaining the other configured images. Preserve the successful records for these two writes.
- Check actual vision-weight length against the KWS start address, connecting generated allocation, linked sections, and deployed contents.

**Implementation and records:** [image manifest](evidence/development-history/deployment_20261008/flash_manifest.json), [write-verification summary](evidence/development-history/deployment_20261008/flash_verified.json), [application programming log](evidence/development-history/deployment_20261008/flash_finder_signed.bin.log), [KWS-weight programming log](evidence/development-history/deployment_20261008/flash_kws_weights.bin.log), and [addresses and boundaries](memory-deployment.en.md).

**Host workflow:** [final-image checks, programming, and verification](../tools/development-history/flash_groupcv.py).

<a id="step-30"></a>
### 30. Preserve final board operation and version-specific results

- Issue cup, bottle, and phone twice each. **All six voice commands are correctly accepted**, with the selected target matching each accepted command.
- Preserve the non-command and two quiet intervals with no accepted command. Quiet-period behavior records amplitude gating separately from single-window model classification.
- Vision messages in that final session have `found=0`; the session measures voice acceptance and target selection. Earlier CUP/PHONE `found=1` records belong to a separate vision version.
- Distinguish offline classification, command acceptance, visual detections, and demonstration video by model version, method, and log.

**Records:** [final voice session](evidence/development-history/voice_groupcv_20261008.log), [line-by-line observation summary](evidence/development-history/observations.json), [earlier vision log](evidence/development-history/finder_vision_20261004.log), and [results/version mapping](results.en.md).

**Host workflow:** [final board observation and log capture](../tools/development-history/record_voice_groupcv.py).

## Phase 7: engineering preservation and hardware demonstration (31–32)

<a id="step-31"></a>
### 31. Prepare IDE integration, project preservation, and GitHub publication

- Synchronize IDE source/header browsing entries with the actual project, retaining previews, backups, hash-race checks, and atomic configuration replacement.
- Resolve build paths relative to the project, support `GCC_PATH`, and check **GCC 14.3.1**.
- Preserve the main application, recording firmware and host tools, data preparation, training versions/final snapshot, model configurations, source versions, model hashes, and deployment records.
- Provide Chinese/English homepages, complete steps, architecture, model workflows, code tours, memory maps, build instructions, and results, with direct links from technical descriptions to source.
- Save the project in Git and publish on GitHub while retaining component copyrights and licenses. Publication/build notes separately describe the scope of weights, raw audio, generated model code, and prebuilt images.

**Implementation:** [IDE synchronization script](../tools/ide/sync_cubeide_sources.py), [IDE usage](../tools/ide/README.en.md), [build entry](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh), [publication inventory](publication-review.en.md), [build dependencies](build.en.md), and [third-party sources](../THIRD_PARTY_NOTICES.en.md).

<a id="step-32"></a>
### 32. Publish the demonstration and track standalone operation

- The hardware video is complete and prominently linked on the homepage: [watch the dual-model voice object finder](https://youtu.be/m7wET9g5u6k).
- Present the video alongside implementation, model evaluation, board logs, and deployment records as the operating demonstration.
- Standalone power and power-cycle startup are separate boot/operation checks. A verified completion record is not currently available, so their test status remains explicit.

**Reading:** [homepage demonstration](../README.en.md), [video](https://youtu.be/m7wET9g5u6k), [demonstration/test scope](results.en.md), and [boot-image layout](memory-deployment.en.md).

---

See the [code tour](code-tour.en.md) for function-level detail, the [implementation index](development-coverage.en.md) for work/material mapping, and [results](results.en.md) for measurements and versions.
