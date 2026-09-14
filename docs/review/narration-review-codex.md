# CAIRN demo narration review and final revision

> Outside review of `captures/narration.md`, received 2026-09-07. Kept verbatim as the
> provenance of the shipped script. Where the shipped script departs from this, the
> reason is recorded in `captures/narration.md` under "Where this version came from".

## Overall direction

The current script has a strong product argument and an unusually credible safety story. Its main weakness is voice: it often sounds like an architecture review being read aloud. A good marketing narrator should let the audience feel the operational problem first, then reveal why the architecture earns trust.

The revised voice should be:

- confident, calm, and observant
- concrete before technical
- explanatory without sounding defensive
- focused on the supervisor's decision, not the framework's features
- careful with numbers, using them only when they make the situation visible

The central message should be repeated in different forms:

> CAIRN helps people make a better operational decision when the important facts are spread across different systems.

## Specific comments on the current version

### Opening: 0:00-0:40

The situation is strong, but "decision fabric" is abstract before the audience understands the problem. Start with the pressure of a shift and define CAIRN as a decision layer in plain language. Keep the crusher, truck, and weather facts; they give the story immediate stakes.

"The gap is the product" is memorable but sounds like a slogan. Explain the consequence instead: each system knows one fact, but no system sees the combined decision.

### Decision spine: 0:40-0:56

The left-hand spine is an excellent visual thesis. Keep it. However, "five stages where a model thinks and three that say no model" feels like an implementation diagram being narrated. Translate it into the more meaningful boundary: agents interpret evidence, while policy, approval, execution, and verification remain controlled.

### Strands explanation: 1:06-2:00

This section contains the right proof, but it has too many engineering terms close together: graph, node budget, timeout, typed results, evidence IDs, and evaluation cases. Explain Strands through two audience-friendly ideas:

1. specialists can work in parallel rather than waiting through a long chain of hand-offs;
2. each specialist passes a structured, evidence-backed finding to the next stage.

"Strands earns its place" sounds defensive. "We chose Strands because..." sounds deliberate and professional.

### Refusal and safety: 2:00-3:20

This is the strongest part of the original. Keep the stale data, conflicting weather, denied interlock, human approval, timeout, and reconciliation. They show enterprise value better than a generic "AI is helpful" claim.

Remove internal identifiers such as `T4-prohibited-interlock`. The audience needs to understand the control, not remember the rule name. Keep "deterministic policy service" once, then explain its consequence in plain English.

The timeout sequence is especially good. Frame it as a practical operational risk: a duplicate action can be more dangerous than a slow answer. Introduce "unknown, then reconcile, then close" as a clear behaviour rather than an implementation state machine.

### TOGAF: 3:30-4:30

The current TOGAF section arrives too late and becomes acronym-heavy. Mention earlier that the spine is a deliberate architecture, then use this section as the payoff: TOGAF connects a stakeholder concern to a principle, requirement, building block, and test.

Do not lead with "ADM cycle" or internal artefact codes. Judges outside mining can understand TOGAF if it is described as a traceability discipline: it prevents the demo from becoming a clever chatbot whose safety claims cannot be proven.

The example about the inconsistent shift target is valuable because it shows the method changed the build. Keep it, but describe it as an inconsistency in the synthetic scenario so it cannot be mistaken for a real mine statistic.

### Close: 4:30-4:48

The final line is excellent: "It recommends. It does not authorise." Keep it. The list of 110 tests, 13 of 13 cases, zero prohibited actions, and zero bypassed approvals is too much for the final breath. Use one compact proof statement, then land on the human and enterprise value.

## Final revision

**Approximate runtime:** 4:45-4:55 at a calm control-room pace. Verify against the existing narration tool before recording.

### 0:00-0:22 - A shift, not a dashboard

**Visual:** Normal shift. Trucks move through the pit. CAIRN is visible but quiet.

**Narration:**

This is CAIRN. In a mine shift, the difficult decisions rarely come from one alarm. They happen when several changes arrive together, across different systems, and no one has time to assemble the whole picture. CAIRN brings those signals together, tests the options, and helps a supervisor recover the shift safely.

### 0:22-0:43 - The decision window

**Visual:** Crusher, truck, and weather events appear. The timeline begins.

**Narration:**

Everything in this demo is synthetic, but the situation is familiar. The crusher is running at seventy-five percent. A haul truck has stopped. Rain will close the main ramp in forty-two minutes. Each source knows one fact. CAIRN sees one operational problem-and a decision window that is already closing.

### 0:43-1:02 - The design in one glance

**Visual:** Highlight the decision spine on the left.

**Narration:**

That is the idea behind the spine on the left. It is the decision loop: understand the situation, work out the choices, check the risks, then decide and verify. You can also see where AI stops. Agents help interpret evidence; policy, approval, and execution remain deterministic and accountable.

### 1:02-1:27 - Why Strands

**Visual:** Four source signals arrive. The Strands graph begins. Specialist nodes run in parallel.

**Narration:**

Five signals arrive from four source systems. CAIRN correlates them into one incident and starts a bounded Strands workflow. Operations, reliability, risk, and scenario planning can work in parallel, so the decision does not wait on hand-offs. The graph gives the work clear limits and a clear result.

We chose Strands because it gives us a practical way to compose these specialists without creating an uninspectable swarm. Each specialist returns a structured finding, not just a paragraph of text. Evidence, assumptions, and uncertainty travel with that finding into the next stage. That makes the reasoning testable and easier to trust.

### 1:27-2:05 - Honest evidence

**Visual:** Agent cards complete. Stale truck telemetry and conflicting weather sources are highlighted.

**Narration:**

CAIRN also refuses to make messy data look clean. This truck signal is fifteen minutes old, so it is marked stale. The weather sources disagree, so both readings remain visible. It can reason, but it cannot turn uncertainty into fact.

### 2:05-2:31 - Options, not a magic answer

**Visual:** Three scenario cards appear. Select the preferred recovery option and animate its route.

**Narration:**

Here are the recovery choices. One protects safety and accepts lower production. One recovers more tonnes by using the stockpile buffer and rerouting the fleet. The third protects the crusher and gives maintenance room to work. The point is not a clever answer; it is a visible trade-off with evidence behind it.

### 2:31-2:53 - Where the system draws the line

**Visual:** Attempt the interlock override. Hold the policy-denied message.

**Narration:**

Now we reach the boundary between intelligence and authority. I will ask for an interlock override. The request is denied by a deterministic policy service before it can become an action. The model may explain a situation or suggest a plan; it does not get to waive a safety control.

### 2:53-3:15 - Human approval

**Visual:** Approval request appears. Show the named role, plan version, and scoped assets. Approve.

**Narration:**

For an allowed recovery plan, the system still asks for a person. The approval is tied to the named role, the selected assets, and this exact plan version. It expires, it can be used once, and it leaves a record. That is how a recommendation becomes an accountable operational decision.

### 3:15-3:39 - When the world misbehaves

**Visual:** Simulate a dispatch timeout. Show the unknown state, then reconciliation.

**Narration:**

Then the external world behaves the way it sometimes does: dispatch times out after the call may already have applied. CAIRN does not blindly try again. It marks the result unknown and reconciles it against authoritative state. Only when the outcome is confirmed does the workflow close. Avoiding a duplicate action can matter as much as producing the original recommendation.

### 3:39-4:02 - What TOGAF changed

**Visual:** Show the TOGAF ADM view, then move to the traceability chain.

**Narration:**

TOGAF is what helped us turn these controls into an architecture instead of a collection of prompts. We started with stakeholder concerns, turned them into principles and requirements, mapped those requirements to building blocks, and connected each one to a test. For a judge outside mining, it is a chain of accountability from the question someone asks to the behaviour the system must prove.

### 4:02-4:29 - One requirement, carried through

**Visual:** Animate the safety question through the stakeholder, principle, requirement, policy service, and test views.

**Narration:**

Take the safety question on screen: can CAIRN waive a safety control? The answer becomes a principle-no direct control path to operational technology. That becomes a requirement-high-consequence actions are denied for every role. It becomes a policy service in the architecture, and it becomes a test that fails if a model is ever consulted. TOGAF gives us the trace; the implementation gives us the evidence.

That discipline even caught an inconsistency in our own synthetic scenario: the shift target did not line up with the fleet capacity we had declared. We corrected it before it became a misleading demo.

### 4:29-4:55 - Close

**Visual:** Reset to the situation room. Show the complete audit trail, then return to the quiet mine view.

**Narration:**

CAIRN does not replace fleet management, plant control, or the systems a mine already trusts. It connects them when the decision crosses boundaries. It brings the evidence together, makes the trade-offs visible, keeps authority with people, and leaves a record of what happened. It recommends. It does not authorise. And when the shift changes, it can show us whether the decision actually worked.

## Recording guidance

Speak as someone showing a capable product to another professional, not as someone defending a thesis. Let the visual state change before explaining it. Pause briefly after the interlock denial and after "It recommends. It does not authorise." Those are the two lines the audience should remember.

Keep "Strands," "TOGAF," "deterministic policy," and "structured finding" in the script, but explain each in ordinary language immediately. Avoid reading component names, rule identifiers, test IDs, or internal implementation labels aloud.
