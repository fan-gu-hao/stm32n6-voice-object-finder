# Engineering evidence from the original development conversations

[繁體中文](original-history-review.md) | [English](original-history-review.en.md)

> **Version notation:** `Runtime1100`, `Runtime1200`, and `Runtime1201` mean versions **11.0.0, 12.0.0, and 12.0.1** of ST's **Network Runtime library**. This library is linked into the firmware to provide execution support required by generated model code. Updating the code-generation tools also requires matching library, header, and NPU support versions. These identifiers are separate from the ST Edge AI tool's own version number. [Version alignment details](toolchain-compatibility.en.md).

This page records the 2026-11-20 review of the original development conversations and attachments. It reconstructs the implementation and debugging work between audio capture, training, deployment, and the final dual-model revision. It complements the [engineering workflow](engineering-workflow.en.md), [code tour](code-tour.en.md), and [results](results.en.md), presenting each stage's problems, diagnostic methods, changes, and outcomes.

## Materials and evidence levels

Each conversation contains 137 captured turn nodes, for 274 nodes before deduplication. They share 135 inherited nodes, giving 139 distinct turns in total. User and assistant messages are counted together within each turn. The available text, code blocks, expanded content, and eight user-supplied text attachments were reviewed.

Two source archives were also safely opened and their key implementations checked. The vision ZIP contains 2,041 files and is an early snapshot of a separate vision project; its model hash begins with 312ea458, unlike this dual-model project's 331673. The other RAR contains 8,249 entries, including 7,722 regular files, and holds the upstream Runtime1100 hand framework. These materials establish provenance and revisions, with the earlier vision work and the formal dual-model project recorded separately. Archive review focused on versions and key implementations; a line-by-line review of all third-party libraries was outside its scope.

The 12 distinctly named historical assistant-provided attachments were also retrieved and read: two integration ZIPs and ten source files. Nine standalone text files match code embedded in the conversations byte for byte; the ZIPs and an early PC recording program supply content that was not fully embedded. Both ZIPs explicitly require further compilation or board checks, so they are recorded as early proposals with completion status separate from the final KWS object-finder revision. The attachments were read only; none of their programs were executed during this review.

The evidence here consists of terminal output pasted into conversations, source code printed at the time, and downloaded text attachments. The conversations preserve log excerpts: some command echoes are truncated or interleaved, some turns have no visible assistant response, and other passages contain proposed commands awaiting execution. The short excerpts below preserve observed values while omitting personal paths, accounts, and device identifiers. Recovering complete logs or revalidating omitted binary payloads would require the corresponding original files.

Four evidence levels are kept separate:

- **Observed result:** tool output, board output, or an operator report supplied by the user.
- **Preserved implementation:** printed source and published code establish the implementation; execution status is recorded separately through tool or board output.
- **Proposal or repair command:** an intended action, requiring subsequent observed output before it is marked complete.
- **Evidence gap:** missing output, archive contents not yet checked, or a test that cannot support a broader claim.

Private conversation transcripts, conversation identifiers, and sign-in information are not published. Existing public artifacts and their provenance are linked in the [evidence index](evidence/development-history/README.en.md).

## Stages from audio capture to the final revision

| Stage | Work and observed results | Supported scope |
| --- | --- | --- |
| Official audio example and build | The ST MDF recording/playback example was adapted for serial monitoring and host capture. Early linking failed on HAL_UART_Transmit and HAL_UART_Init. After adding UART and UART_EX build links, the actual build reported zero errors and one unused playback-function warning; both objects existed and were linked. | Completed UART build dependencies and integrated the capture workflow on the ST HAL/BSP. See the [recording firmware](../kws/recording_firmware/README.en.md). |
| Microphone data and RAM startup | Continuous audio blocks and changing amplitudes were observed. The five-second recorder then passed download verification but failed the handshake. PC, vector-table, and UART reads showed that execution was still in Boot ROM. GDB RAM loading and explicit vector/core setup subsequently reached main, MicLine, and the READY message. | Confirmed execution state and restored recorder startup. The earlier return to Boot ROM remained unresolved; debugger frequency was changed at the same time, without isolating its individual effect. |
| Host reception and playback | Automated loading followed by debugger detach completed the handshake, fixed-length transfer, CRC32 check, WAV save, and host playback. One complete successful record contained 80,000 samples at 16 kHz, 16-bit mono, lasting five seconds, with zero clipped samples; the user confirmed hearing their own voice. | Verified recording and transfer after RAM loading; standalone-power and cold-boot status for the dual-model system is tracked separately. See the [host tools](../kws/recording_tools/README.en.md). |
| 47 source recordings and dataset preparation | Five-second recordings were collected for cup, bottle, and phone, 12 each, plus eight unknown and three silence recordings. Speech was located and cut into one-second clips, preserving source and speech boundaries. Grouping by original recording produced 142 training and 49 validation clips. | The counting units are 47 source recordings and their 191 derived clips; distinct-speaker counts are not included. See [collection](../kws/collect_n6.py) and [preparation](../kws/prepare_dataset.py). |
| Vision framework and model integration | The ST dual-model FreeRTOS/camera framework was adapted to the project's vision model, build dependencies, postprocessing, target classes, and display. Audio was then connected to the same inference task. | The project implements model integration, search logic, and real-time system adaptation. Framework, generation, and postprocessing sources are documented in the [workflow](engineering-workflow.en.md). |
| Baseline KWS training and quantization | A five-class network using 49×13 features was built, with coefficients, models, and results saved. Float and INT8 validation both reached 48/49. Early augmentation used fixed time shifts and training-set background noise. | Completed offline validation; continuous-listening performance was examined in subsequent board tests. See the [training history](../kws/training_history/README.en.md). |
| N6 generation, linking, and startup | KWS-generated code, CMSIS-DSP, memory pools, and the two model interfaces were integrated. Early application and KWS-weight writes both passed verification, but no application serial output appeared and the user reported a black screen. The payload was later found at offset 0x240 instead of the required 0x400. | Generation, build, packaging, write verification, and actual execution are recorded separately to localize the problem. |
| Cache handoff and fixed comparisons | Five frontend tables were checked; reproducing the C formulas on the host still gave 48/49. NPU/CPU input handoff was added. An initial monitor captured only comparison instructions; an actual reset later produced five-class INPUT and PCM comparisons. | Five fixed samples verify numerical consistency after porting; recognition accuracy and live operation are evaluated separately. |
| Live-window diagnosis | The same one-second PCM window, 637 INT8 features, and five outputs were returned with packet ordering, length, and CRC32 checks, then compared with two host inference paths. Four samples were received and played; the user confirmed that the bottle utterance was complete. | Separates captured content, preprocessing, and classification. Silence→phone and a low bottle score are retained as failures. |
| Acceptance rules and field retraining | An amplitude gate, quiet rearming, and last-accepted-command display were added; four field recordings and background noise were included in retraining. Offline validation remained 48/49, but a free-form trial still showed no accepted bottle command; a later labeled test accepted only two of six commands. | Acceptance rules and model data were adjusted separately, with missed field commands guiding the next collection and training cycle. |
| 48 samples and grouped final training | Collection completed with 32 training and 16 held-out samples. The user's requests for more epochs, stronger bottle/silence augmentation, and K-fold evaluation led to grouped five-fold training. Development validation reached 224/227; final training used the median best epoch, 66; float and INT8 held-out evaluation both reached 15/16. | Development/epoch selection, held-out single-window evaluation, and board operation remain separate. An intermediate version-three script is preserved, but no independent completion output was found. |
| Final deployment and voice operation | Generated-file discovery was corrected; model, frontend, quantization interface, and diagnostic mode were synchronized. Existing records show successful verification of two image writes. Cup, bottle, and phone were each correctly accepted twice; hello and two quiet intervals were not accepted. | Voice operation passed 6/6 in that session; every vision record in the same session was found=0. This record verifies voice acceptance, while complete three-object finding performance is assessed through the demonstration separately. |

On 2026-10-04, this project ran generate-n6-model_STM32N6570-DK.sh in the newly created vision/Model/ directory; the tools reported ST Edge AI Core 4.0.1-20581 and STM32CubeAI 12.0.1-RC2, followed by completed generation, ELF linking, and image packaging. To match those artifacts, the vision reference application moved from Runtime1200 to Runtime1201, while the main hand-framework base moved from Runtime1100 to NetworkRuntime1201_CM55_GCC.a, updating headers, libraries, and NPU support sources together. Model/STAI-generated code, weights, and official postprocessing were then integrated. This record confirms the vision generation and integration carried out in course17; see the [engineering workflow](engineering-workflow.en.md) for the detailed mapping.

## Startup failure: correct contents at the wrong offset

Black-screen diagnosis recorded a HardFault state, with return-address analysis landing near assertion handling. A specific null pointer, GPU2D callback, or KWS initialization step was not isolated as the fault cause. The diagnostic command also had two problems: it jumped to a default address instead of resuming in place, and its parser missed PC/LR values that had already been printed. These diagnostic-tool problems occurred after the existing fault and were corrected and recorded separately.

Comparing the compiled raw program with the boot image then produced these observed excerpts. The original Chinese output is retained:

```text
原始程式在簽章映像中的偏移： 0x240
簽章映像內的程式內容完全一致： True

檢查通過：程式起始偏移為 0x400。
檢查通過：程式內容與原始編譯結果完全一致。
```

These lines report an original payload offset of 0x240 with identical contents, followed by a successful 0x400 offset and content check. Repackaging added -align while retaining -nk, -of 0x80000000, -t ssbl, and -hv 2.3. After the first successful packaging check, replacement stopped at an interactive prompt for a read-only file. File replacement and reflashing were completed subsequently, followed by actual KWS/FINDER execution.

The confirmed repair is **moving the payload from 0x240 to 0x400 and checking that its full contents were unchanged**. The project uses no-key boot-header packaging without a cryptographic signature; signed follows the tool and artifact naming. Later packaging retained vector, size, section, and payload-alignment checks, with the application and vision-command section extracted separately.

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

INPUT uses host-computed quantized features directly; PCM additionally tests the board frontend. All five classes matched in both paths, and all 637 input values matched for each PCM case. Output differences are quantized integer steps: at most one for silence and zero for the other classes. The comparison confirms numerical consistency after the changes for this sample set; causal links between cache behavior and earlier recognition failures remain case-specific. The host reference is preserved separately in the [fixed-reference JSON](evidence/development-history/fixed_reference_20261007.json).

## From numerical agreement to reliable field operation

The early implementation already required score 0.90, margin 0.25, two consecutive windows, and a 1200 ms interval. However, amplitude was calculated only after the acceptance decision and printed for diagnostics, while the display updated on every candidate. This low-amplitude acceptance line appears in the actual pasted output:

```text
KWS,class=CUP,score=91,accept=1,peak=954,mfcc_ms=8,nn_ms=1
```

This line records acceptance of a low-amplitude window, without an utterance label for that instant. A separate prompted test accepted PHONE again during its ending quiet interval and missed cup/bottle, providing a field-problem record with labeled context.

The four live-window comparisons were:

| Prompt | Board / host using board features / host recomputing PCM | INT8 input differences | Maximum integer output difference |
| --- | --- | --- | --- |
| Silence | phone / phone / phone | 0 | 0 |
| cup | cup / cup / cup | 0 | 0 |
| bottle | bottle / bottle / bottle | 0 | 3 |
| phone | phone / phone / phone | 0 | 1 |

The [comparison report](evidence/development-history/live_comparison_20261007.json) preserves the values. Bottle ranked first but scored about 41% on the board, below acceptance. The quiet recording was classified as phone on all three paths. With a quiet peak of 1748 and all three utterances above 8800 in this collection, acceptance version two used 2500 as an initial amplitude threshold, rearmed after two quiet windows, and displayed only the last accepted command. This threshold was selected from those collection conditions; its applicability across environments remains unevaluated.

Sampling also changed across revisions. The four-case diagnostic deliberately selected the most command-like quiet window and the highest-energy speech windows. The later 48-sample collector selected by energy for every class and entered capture before the normal amplitude gate. The two datasets use different targeted sampling strategies and are interpreted according to their respective purposes.

After retraining with four field samples, a free-form trial still showed no accepted bottle command and included a peak of 32767. This prompted the addition of per-window class scores, margin, hit count, and full-scale sample counts. A text-replacement patch initially stopped because formatting differed; it was revised to locate a unique print statement. That was a patching-tool problem, not a separate NPU fault. The subsequent labeled six-command test already included these detailed fields; it accepted only two commands, with all clipping counts zero in that trial. Those findings then led to 48-sample collection and grouped retraining. The earlier full-scale peak raised a clipping concern but did not establish that clipping caused the missed commands.

## Retraining, artifact synchronization, and final results

Grouped training combined the original 142 training clips, 49 validation clips, four field samples, and 32 new training samples into a 227-clip development pool. The original 49 clips were therefore no longer the final independent test set. Identical PCM samples were grouped together, contradictory labels and development/holdout overlap were rejected, and each fold's statistics, noise, and quantization calibration came only from its training portion.

The epoch limit increased to 300, with early stopping eligible after an 80-epoch warmup and patience 50. Bottle and silence received more augmentation and higher class-loss priority. The five best epochs were 82, 28, 66, 9, and 79; their median, 66, determined final training. The downloaded original training attachment begins late in fold five and continues through all 66 final-training epochs and the held-out results.

The [five-fold report](evidence/kws-groupcv.json), 224/227, and [held-out report](evidence/kws-int8-holdout.json), 15/16, match that attachment. The sole held-out classification error was cup→phone. Its phone score was about 60.9%, below the 90% single-window threshold, so this score condition would reject it.

After final code generation completed, a recursive file search counted same-named files in both the formal output and tool workspace, causing the artifact check to stop. Restricting discovery to the formal output confirmed the artifacts, with the Neural-ART compilation results remaining valid. Installation synchronized the model, coefficients, and quantization parameters: the input zero point changed from 8 to 7, and collection mode was disabled. The existing acceptance threshold remained unchanged.

In the final board session, cup, bottle, and phone were each accepted twice; hello and two quiet intervals were not accepted. Quiet intervals had no KWS inference rows, recording successful amplitude gating with no model silence-classification results for those intervals. The test covers that operation session; cross-speaker, cross-environment, and long-term false-acceptance performance await separate evaluation.

Each stage's completion status follows its retained records: the intermediate version-three script is preserved but lacks independent completion output; the end of fold five, final retraining, generation, flashing, and board trial have corresponding execution records. Archive review covered provenance, revisions, and key implementations; a line-by-line review of all third-party libraries was outside its scope. The voice operation and earlier vision results are recorded separately here. Demonstration content is available in the [hardware video](https://youtu.be/m7wET9g5u6k); passing standalone-power and cold-boot records remain unavailable.

