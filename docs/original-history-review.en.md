# Engineering evidence from the original development conversations

[繁體中文](original-history-review.md) | [English](original-history-review.en.md)

This page records the 2026-11-20 review of the original development conversations and attachments. It restores the implementation and debugging work between audio capture, training, deployment, and the final dual-model revision. It complements the [engineering workflow](engineering-workflow.en.md), [code tour](code-tour.en.md), and [results](results.en.md); the final successful figures do not replace the work that preceded them.

## Materials and evidence levels

Each conversation contains 137 captured turn nodes. They share 135 inherited nodes, giving 139 distinct turns in total. This does not mean 274 independent pieces of content, and user and assistant messages are not counted separately. The available text, code blocks, expanded content, and eight user-supplied text attachments were reviewed.

Two source archives were also safely opened and their key implementations checked. The vision ZIP contains 2,041 files and is an early snapshot of a separate vision project; its model hash begins with 312ea458, unlike this dual-model project's 331673. The other RAR contains 8,249 entries, including 7,722 regular files, and holds the upstream Runtime1100 hand framework. These materials distinguish sources and revisions; work in that earlier vision project is not counted as a new contribution here. Checking key implementations does not mean reading every line of the third-party libraries.

The 12 distinctly named historical assistant-provided attachments were also retrieved and read: two integration ZIPs and ten source files. Nine standalone text files match code embedded in the conversations byte for byte; the ZIPs and an early PC recording program supply content that was not fully embedded. Both ZIPs explicitly require further compilation or board checks and are early proposals, not successful final KWS object-finder records. The attachments were read only; none of their programs were executed during this review.

The evidence here consists of terminal output pasted into conversations, source code printed at the time, and downloaded text attachments. **Conversation excerpts are not complete logs from the original computer.** Some command echoes are truncated or interleaved; some turns have no visible assistant response; other passages contain proposed commands only. The short excerpts below preserve observed values while omitting personal paths, accounts, and device identifiers. They are not full original logs and cannot revalidate binary payloads that are not included.

Four evidence levels are kept separate:

- **Observed result:** tool output, board output, or an operator report supplied by the user.
- **Preserved implementation:** printed source and published code establish that an implementation exists; a success message inside source code does not establish that it ran.
- **Proposal or repair command:** an intended action, requiring subsequent observed output before it is marked complete.
- **Evidence gap:** missing output, archive contents not yet checked, or a test that cannot support a broader claim.

Private conversation transcripts, conversation identifiers, and sign-in information are not published. Existing public artifacts and their provenance are linked in the [evidence index](evidence/development-history/README.en.md).

## Stages from audio capture to the final revision

| Stage | Work and observed results | Supported scope |
| --- | --- | --- |
| Official audio example and build | The ST MDF recording/playback example was adapted for serial monitoring and host capture. Early linking failed on HAL_UART_Transmit and HAL_UART_Init. After adding UART and UART_EX build links, the actual build reported zero errors and one unused playback-function warning; both objects existed and were linked. | A build-dependency repair, not a rewrite of the HAL or BSP. See the [recording firmware](../kws/recording_firmware/README.en.md). |
| Microphone data and RAM startup | Continuous audio blocks and changing amplitudes were observed. The five-second recorder then passed download verification but failed the handshake. PC, vector-table, and UART reads showed that execution was still in Boot ROM. GDB RAM loading and explicit vector/core setup subsequently reached main, MicLine, and the READY message. | Execution state and startup were checked. The earlier return to Boot ROM was not isolated to one cause; a simultaneous debugger-frequency change cannot be credited as the sole fix. |
| Host reception and playback | Automated loading followed by debugger detach completed the handshake, fixed-length transfer, CRC32 check, WAV save, and host playback. One complete successful record contained 80,000 samples at 16 kHz, 16-bit mono, lasting five seconds, with zero clipped samples; the user confirmed hearing their own voice. | A RAM-loaded recording test, not a standalone-power or cold-boot test of the dual-model system. See the [host tools](../kws/recording_tools/README.en.md). |
| 47 source recordings and dataset preparation | Five-second recordings were collected for cup, bottle, and phone, 12 each, plus eight unknown and three silence recordings. Speech was located and cut into one-second clips, preserving source and speech boundaries. Grouping by original recording produced 142 training and 49 validation clips. | The 47 source recordings and 191 derived clips are different counts; neither establishes different speakers. See [collection](../kws/collect_n6.py) and [preparation](../kws/prepare_dataset.py). |
| Vision framework and model integration | The ST dual-model FreeRTOS/camera framework was adapted to the project's vision model, build dependencies, postprocessing, target classes, and display. Audio was then connected to the same inference task. | Upstream mechanisms and project adaptations retain separate attribution. Vision generation and postprocessing provenance are described in the [workflow](engineering-workflow.en.md); unrelated projects are not counted as this implementation. |
| Baseline KWS training and quantization | A five-class network using 49×13 features was built, with coefficients, models, and results saved. Float and INT8 validation both reached 48/49. Early augmentation used fixed time shifts and training-set background noise. | Offline validation did not establish reliable continuous listening. See the [training history](../kws/training_history/README.en.md). |
| N6 generation, linking, and startup | KWS-generated code, CMSIS-DSP, memory pools, and the two model interfaces were integrated. Early application and KWS-weight writes both passed verification, but no application serial output appeared and the user reported a black screen. The payload was later found at offset 0x240 instead of the required 0x400. | Generation, build, packaging, write verification, and actual execution are separate milestones. |
| Cache handoff and fixed comparisons | Five frontend tables were checked; reproducing the C formulas on the host still gave 48/49. NPU/CPU input handoff was added. An initial monitor captured only comparison instructions; an actual reset later produced five-class INPUT and PCM comparisons. | Numerical consistency for five fixed samples, not a new recognition-accuracy estimate or complete live-system validation. |
| Live-window diagnosis | The same one-second PCM window, 637 INT8 features, and five outputs were returned with packet ordering, length, and CRC32 checks, then compared with two host inference paths. Four samples were received and played; the user confirmed that the bottle utterance was complete. | Separates captured content, preprocessing, and classification. Silence→phone and a low bottle score are retained as failures. |
| Acceptance rules and field retraining | An amplitude gate, quiet rearming, and last-accepted-command display were added; four field recordings and background noise were included in retraining. Offline validation remained 48/49, but a free-form trial still showed no accepted bottle command; a later labeled test accepted only two of six commands. | Rule changes and model changes are distinct work. High offline scores do not erase live failures. |
| 48 samples and grouped final training | Collection completed with 32 training and 16 held-out samples. The user's requests for more epochs, stronger bottle/silence augmentation, and K-fold evaluation led to grouped five-fold training. Development validation reached 224/227; final training used the median best epoch, 66; float and INT8 held-out evaluation both reached 15/16. | Development/epoch selection, held-out single-window evaluation, and board operation remain separate. An intermediate version-three script is preserved, but no independent completion output was found. |
| Final deployment and voice operation | Generated-file discovery was corrected; model, frontend, quantization interface, and diagnostic mode were synchronized. Existing records show successful verification of two image writes. Cup, bottle, and phone were each correctly accepted twice; hello and two quiet intervals were not accepted. | Voice operation passed 6/6 in that session. Every vision record in the same session was found=0, so it is not a completed three-object finding demonstration. |

Vision generation in this project also has observed execution evidence. On 2026-10-04, generate-n6-model_STM32N6570-DK.sh ran in the newly created vision/Model/ directory; the tools reported ST Edge AI Core 4.0.1-20581 and STM32CubeAI 12.0.1-RC2, followed by completed generation, ELF linking, and image packaging. To match those artifacts, the vision reference application moved from Runtime1200 to Runtime1201, while the main hand-framework base moved from Runtime1100 to NetworkRuntime1201_CM55_GCC.a, updating headers, libraries, and NPU support sources together. Model/STAI-generated code, weights, and official postprocessing were then integrated. This is course17's own generation and integration workflow, not a substitute from an earlier vision project; see the [engineering workflow](engineering-workflow.en.md) for the detailed mapping.

## Startup failure: correct contents at the wrong offset

Black-screen diagnosis recorded a HardFault state. Return-address analysis landed near assertion handling, but **the evidence does not identify a particular null pointer, GPU2D callback, or KWS initialization step as the sole fault cause**. The diagnostic command also had two problems: it jumped to a default address instead of resuming in place, and its parser missed PC/LR values that had already been printed. Those tool errors must not be confused with the pre-existing fault.

Comparing the compiled raw program with the boot image then produced these observed excerpts. The original Chinese output is retained:

```text
原始程式在簽章映像中的偏移： 0x240
簽章映像內的程式內容完全一致： True

檢查通過：程式起始偏移為 0x400。
檢查通過：程式內容與原始編譯結果完全一致。
```

These lines report an original payload offset of 0x240 with identical contents, followed by a successful 0x400 offset and content check. Repackaging added -align while retaining -nk, -of 0x80000000, -t ssbl, and -hv 2.3. The first replacement then stopped at an interactive prompt for a read-only file. Passing the packaging checks therefore did not yet mean that reflashing had completed. Subsequent completion was followed by actual KWS/FINDER execution.

The confirmed repair is **moving the payload from 0x240 to 0x400 and checking that its full contents were unchanged**. The project uses a no-key boot-header package; signed in a tool or filename does not establish cryptographic signing. Later packaging retained vector, size, section, and payload-alignment checks, with the application and vision-command section extracted separately.

## CPU/NPU handoff and two fixed-data paths

The early KWS source handled CPU cache only, while its work area enabled NPU cache. The current [finder_kws.c](../firmware/Src/finder_kws.c) cleans and invalidates the relevant 64-byte NPU cache lines before the CPU writes new features, invalidates the CPU's old copy, and applies a barrier. It then cleans CPU cache after writing and starts inference. The two models retain separate contexts and use the NPU sequentially in one inference task; they do not run on the NPU simultaneously.

These are actual comparison rows pasted into the conversation on 2026-10-07, excerpted without the surrounding log:

```text
CMP,case=cup,path=INPUT,pc=cup,n6=cup,input_diff=0,input_max=0,output_max=0
CMP,case=bottle,path=INPUT,pc=bottle,n6=bottle,input_diff=0,input_max=0,output_max=0
CMP,case=phone,path=INPUT,pc=phone,n6=phone,input_diff=0,input_max=0,output_max=0
CMP,case=unknown,path=INPUT,pc=unknown,n6=unknown,input_diff=0,input_max=0,output_max=0
CMP,case=silence,path=INPUT,pc=silence,n6=silence,input_diff=0,input_max=0,output_max=1
CMP,case=cup,path=PCM,pc=cup,n6=cup,input_diff=0,input_max=0,output_max=0
CMP,case=bottle,path=PCM,pc=bottle,n6=bottle,input_diff=0,input_max=0,output_max=0
CMP,case=phone,path=PCM,pc=phone,n6=phone,input_diff=0,input_max=0,output_max=0
CMP,case=unknown,path=PCM,pc=unknown,n6=unknown,input_diff=0,input_max=0,output_max=0
CMP,case=silence,path=PCM,pc=silence,n6=silence,input_diff=0,input_max=0,output_max=1
```

INPUT uses host-computed quantized features directly; PCM additionally tests the board frontend. All five classes matched in both paths, and all 637 input values matched for each PCM case. Output differences are quantized integer steps: at most one for silence and zero for the other classes. This supports the corrected implementation on those samples; **it does not establish that cache was the sole cause of every earlier recognition failure**. The host reference is preserved separately in the [fixed-reference JSON](evidence/development-history/fixed_reference_20261007.json).

## From numerical agreement to reliable field operation

The early implementation already required score 0.90, margin 0.25, two consecutive windows, and a 1200 ms interval. However, amplitude was calculated only after the acceptance decision and printed for diagnostics, while the display updated on every candidate. This low-amplitude acceptance line appears in the actual pasted output:

```text
KWS,class=CUP,score=91,accept=1,peak=954,mfcc_ms=8,nn_ms=1
```

It proves that this low-amplitude window was accepted. Without an utterance label at that instant, the line alone does not prove that the user was silent. A separate prompted test accepted PHONE again during its ending quiet interval and missed cup/bottle, providing clearer evidence of a live problem.

The four live-window comparisons were:

| Prompt | Board / host using board features / host recomputing PCM | INT8 input differences | Maximum integer output difference |
| --- | --- | --- | --- |
| Silence | phone / phone / phone | 0 | 0 |
| cup | cup / cup / cup | 0 | 0 |
| bottle | bottle / bottle / bottle | 0 | 3 |
| phone | phone / phone / phone | 0 | 1 |

The [comparison report](evidence/development-history/live_comparison_20261007.json) preserves the values. Bottle ranked first but scored about 41% on the board, below acceptance. The quiet recording was classified as phone on all three paths. With a quiet peak of 1748 and all three utterances above 8800 in this collection, acceptance version two used 2500 as an initial amplitude threshold, rearmed after two quiet windows, and displayed only the last accepted command. This does not establish that one fixed threshold suits every environment.

Sampling also changed across revisions. The four-case diagnostic deliberately selected the most command-like quiet window and the highest-energy speech windows. The later 48-sample collector selected by energy for every class and entered capture before the normal amplitude gate. These are not equivalent random-sampling procedures.

After retraining with four field samples, a free-form trial still showed no accepted bottle command and included a peak of 32767. This prompted the addition of per-window class scores, margin, hit count, and full-scale sample counts. A text-replacement patch initially stopped because formatting differed; it was revised to locate a unique print statement. That was a patching-tool problem, not a separate NPU fault. The subsequent labeled six-command test already included these detailed fields; it accepted only two commands, with all clipping counts zero in that trial. Those findings then led to 48-sample collection and grouped retraining. The earlier full-scale peak raised a clipping concern but did not establish that clipping caused the missed commands.

## Retraining, artifact synchronization, and final results

Grouped training combined the original 142 training clips, 49 validation clips, four field samples, and 32 new training samples into a 227-clip development pool. The original 49 clips were therefore no longer the final independent test set. Identical PCM samples were grouped together, contradictory labels and development/holdout overlap were rejected, and each fold's statistics, noise, and quantization calibration came only from its training portion.

The epoch limit increased to 300, with early stopping eligible after an 80-epoch warmup and patience 50. Bottle and silence received more augmentation and higher class-loss priority. The five best epochs were 82, 28, 66, 9, and 79; their median, 66, determined final training. The downloaded original training attachment begins late in fold five and includes all 66 final-training epochs and held-out results; it is not a complete epoch-by-epoch log of all five folds.

The [five-fold report](evidence/kws-groupcv.json), 224/227, and [held-out report](evidence/kws-int8-holdout.json), 15/16, match that attachment. The sole held-out error was cup→phone. Its phone score was about 60.9%, below the 90% single-window threshold, so it cannot be described as an observed wrong command accepted by the board.

Final code generation completed, but a recursive file search then counted same-named files in both the formal output and tool workspace and stopped. Restricting discovery to the formal output confirmed the artifacts; this was an artifact-check failure, not a Neural-ART compilation failure. Installation synchronized the model, coefficients, and quantization parameters: the input zero point changed from 8 to 7, and collection mode was disabled. The final success was not achieved by lowering the existing acceptance threshold.

In the final board session, cup, bottle, and phone were each accepted twice; hello and two quiet intervals were not accepted. Quiet intervals had no KWS inference rows, supporting successful amplitude gating rather than correct silence classification by the model. This short trial does not establish cross-speaker, cross-environment, or long-term false-acceptance performance.

The intermediate version-three script, grouped training, final retraining, generation, flashing, and board trial retain separate evidence statuses. **A later successful final revision does not prove that every intermediate proposal was executed.** Archive review established provenance, revisions, and key implementations; it did not read every line of the third-party libraries. An integrated three-object demonstration, standalone power, and cold boot also cannot be inferred from these excerpts. The demonstration video remains pending.

