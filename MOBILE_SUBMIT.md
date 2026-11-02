# Submitting from a phone (no laptop)

## The notebook

**https://www.kaggle.com/code/comfyops/gemma-submit-mobile-ca5**

| property | value |
|---|---|
| ref | `comfyops/gemma-submit-mobile-ca5` (id_no 142223605) |
| visibility | private |
| competition attached | `gemma-4-developer-agent` ✅ (required for the submit button) |
| last run | COMPLETE — output exists |
| accelerator | none (CPU only, ~20 s) |
| internet | off |
| output | `submission.zip`, 4,763 B |

The notebook builds the **ca5 31B pack** from text embedded in the notebook itself. It reads
nothing from `/kaggle/input`, so it works regardless of what is attached apart from the
competition.

## How to submit (phone)

1. Open the notebook link above in the Kaggle mobile browser or app.
2. **Do not re-run it.** The output from the last completed run is already the correct artifact.
   Re-running creates a new version and you would have to wait for it to finish before submitting.
3. Tap **Submit to Competition** (top of the notebook page, or in the ⋯ menu). Kaggle uses the
   output of the latest completed run.
4. Pick `submission.zip` if prompted.
5. The daily limit applies: **1 submission per day**, and the button will fail with a 400 if the
   slot is spent.

## Verifying you submitted the right thing

After submitting, the description should read:

> ca5: pre-edit anchor-grep rule, no sub-agents, v10 config

## What the notebook produces (verified 2026-11-02)

Contents are **byte-identical** to the pack that scored 0.20 (ref 57760641) and 0.18 (ref 57847285):

| member | sha1 |
|---|---|
| `agent.yaml` | `b1663033e726` |
| `configs/sampling.yaml` | `8f61024c4e81` |
| `eval_config.yaml` | `4a6b044ec65c` |
| `prompts/system.md` | `b08b32a2438d` |

The outer zip sha256 differs from the 0.20 file (`e38bb015…` vs `1ee9b506…`) **only because of zip
entry timestamps** — every member's content hash matches. Kaggle unpacks the archive, so this does
not affect scoring.

`agent.yaml` declares `model: gemma-4-31b-it-qat-w4a16-ct` (main track) with caps
`8 min / 28 calls / 120 turns / 300 s`, temp 0.2, top_p 0.95, thinking_budget 4096.

## If you need a different variant

The notebook has three code cells: constants, the file bodies, and the zip writer. Edit the text
constants in cell 1, re-run, wait for COMPLETE, then submit. The previous known-good kernel
(`comfyops/gemma-submission-packager-ca5-anchor`) is untouched and still holds the original 0.20
output if you ever need to compare.

## Resubmission expectations (measured)

Two draws of this artifact scored 12/58 and 11/58, so the centre is ~11.5/58 = 0.198 and the
grader's sigma is **1 task**. Auto-selection keeps your **best 2**, so an extra draw can only help
or be neutral. P(a new draw ≥ 0.20) ≈ 31%. Expect either no change or 0.21 — it is not a route to a
bigger score.
