# CAIRN technical visual plan

> Outside review of `docs/review/visual-parts-draft.md`, received 2026-09-07. Kept
> verbatim. What was done about each item is recorded at the end of this file.

This plan adds no narration and does not extend the 4:48 video. It fills the narration that already exists with technically credible visuals.

The production rule is simple: every technical claim shown on screen must be either implemented and verified, clearly labelled as a design target, or moved to documentation. Do not present planned artefacts as shipped evidence.

Use these status labels:

- **Design:** defined in the architecture pack
- **Build for video:** required before recording
- **Documentation only:** useful in the README or Devpost, but not needed in the five-minute cut
- **Verified:** implemented, tested, and safe to show as evidence

Final visual timing must be aligned with the actual `beats.json` or edit timeline. Do not maintain a second, conflicting timing system in this document.

## A. TOGAF ADM lens

**Video placement:** Act 4, the TOGAF explanation.

**Status:** Build for video.

The visual should show the full TOGAF ADM ring quietly in the background, with Requirements Management at the centre. The ring provides context, but it must not become an acronym slide.

Highlight the work that this prototype actually demonstrates:

- Architecture Vision
- Business, data, application, and technology architecture
- Delivery and governance constraints
- Requirements traceability

Show the remaining phases in a neutral state unless the project has explicitly documented and implemented them. Do not imply that the prototype completed a full enterprise ADM cycle.

Add a small caption:

```text
TOGAF ADM lens applied to the prototype
Prototype coverage - not a claim of full ADM execution
```

The main visual focus should remain the four moves named in the narration:

```text
stakeholder concern
        v
principle
        v
requirement
        v
building block and test
```

Keep the narration unchanged.

## B. Traceability chain

**Video placement:** Immediately after the ADM view.

**Status:** Build for video.

Reveal one link at a time: concern, principle, requirement, building block, implementation, verification.

Use plain-language labels on screen. Do not read internal file names aloud.

A short verification label may appear only after the test exists.

Do not show a green "PASS" badge for an unimplemented test. Before recording, the test must use a model-call spy or forbidden-model stub so that the build fails if the policy path invokes an LLM.

Keep the narration unchanged.

## C. Requirements table and corrected scenario

**Video placement:** The beat about the inconsistency found during architecture review.

**Status:** Build for video.

The table and the narration must describe the same thing. Use a split beat:

- First show the requirements table for approximately six seconds.
- Highlight the safety requirement traced in the previous scene.
- Then show the corrected shift target beside the declared fleet capacity for the remaining time.

The corrected figures should be labelled as synthetic scenario data.

Do not display a table for the entire beat while the voice talks only about the corrected figures.

If the requirements table has fifteen rows, show the total honestly. If the final architecture contains a different number, use the committed count rather than preserving the planned number.

## D. Strands topology overlay

**Video placement:** During the existing Strands explanation in Act 2.

**Status:** Build for video.

Use a three- to four-second overlay inside the live decision-room interface. Do not replace the live spine with a separate technical slide.

Show four specialists running in parallel and handing structured findings to the scenario planner. Label the edges with the actual domain objects.

The visual must make three things obvious: the specialists run in parallel, the planner waits for their findings, and the findings are structured evidence rather than informal chat messages.

Do not overcrowd the frame with node budgets, timeout values, or SDK internals. The live spine and the narration already communicate bounded execution.

## E. Sequence flow

**Status:** Documentation only.

Build a sequence diagram for the README and Devpost technical section, but keep it out of the video.

The implementation must claim the idempotency key before making the external call. If the call times out, the system must enter `UNKNOWN` and reconcile authoritative state before retrying. It must never blindly send a second state-changing request.

## Final build priority

1. TOGAF ADM lens with honest prototype coverage
2. Traceability chain
3. Requirements table and corrected synthetic figures
4. Strands fan-in overlay
5. Sequence diagram for documentation

The video should only display an artefact as verified after it has been implemented, the relevant test run, and the visible result confirmed to match the narration.

## Recording order (from the same review)

1. Normal shift and mine context
2. Crusher, truck, and weather disruption
3. CAIRN correlates the signals into one incident
4. Strands specialists run in parallel
5. Stale and conflicting evidence appears
6. Three recovery scenarios are compared
7. Unsafe interlock request is denied
8. Supervisor approves the safe plan
9. Dispatch timeout enters UNKNOWN, then reconciles
10. TOGAF ADM view and traceability chain
11. Corrected synthetic requirement/target figures
12. Final audit trail and closing message

Keep the technical visuals silent where possible. Let the narration carry the story, while the screen proves the claims.

The two most important visual moments are the policy denial, where the model can suggest but cannot authorise, and the final audit trail, where CAIRN connects evidence, decision, approval, action and outcome.

The recording should feel like a product demonstration for an executive audience, not a source-code walkthrough.

---

## What was done

| Item | Action |
|---|---|
| B, no PASS badge without a real guard | **Fixed, and it found a real fault.** The slide credited `test_tier_four_is_denied_for_every_role` with failing the build if a model is consulted. That test asserts denial and tier only. The no-model guard lives in `test_policy_denial_does_not_touch_the_agent_layer`, and it patched one seam, `run_graph`. It now patches three, including model construction, and was verified to fail when policy is made to construct a model. The slide names the guard that actually makes the claim. |
| A, honest prototype coverage | Applied. The ring is quiet, the four narrated moves carry the focus, and the caption states prototype coverage rather than a completed enterprise cycle. |
| C, split beat | Applied. Table first, then the correction, rather than both for the whole beat. Figures labelled as synthetic scenario data. |
| C, honest row count | Already correct, and the review prompted a re-check: the table has 17 rows. `docs/architecture/10-demo-video-plan.md` had claimed fifteen. Corrected. |
| D, overlay not a slide | Adopted, including edge labels from the real contract types and dropping node budget and timeout from the frame. |
| E, sequence flow | Not built. Dropped from scope by the project owner, video and documentation both. |
| Recording order | Adopted. The audit trail becomes an explicit closing beat rather than a screen note inside the close. |
