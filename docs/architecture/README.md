# CAIRN: Mine Operations Decision Fabric

## Architecture pack

**Status:** Draft v0.1  
**Date:** 2026-09-06  
**Primary hackathon track:** Professional Agents  
**Implementation direction:** Python, Strands Agents SDK, Amazon Bedrock  
**Initial wedge:** Compound-disruption recovery during an open-pit mine shift

CAIRN is a governed agentic operating layer that turns fragmented mine signals into accountable operational decisions. It coordinates specialist agents across dispatch, maintenance, processing, geotechnical risk, safety, and logistics, while keeping consequential actions behind policy and human approval.

This pack is deliberately split into a credible target architecture and a small vertical slice that can be built quickly with synthetic data. It is designed to be handed to Claude Code without requiring the architecture to be rediscovered.

## Read in this order

1. [Architecture Vision](01-architecture-vision.md) — problem, stakeholders, capabilities, principles, and scope.
2. [Target Architecture](02-target-architecture.md) — TOGAF-aligned business, data, application, technology, and deployment views.
3. [Strands Agent Design](03-strands-agent-design.md) — agent topology, graph orchestration, tools, state, hooks, and structured outputs.
4. [Security, Governance, and Safety](04-security-governance-and-safety.md) — mining-grade controls and action tiers.
5. [Interfaces and Data Contracts](05-interfaces-and-data-contracts.md) — stable API, event, plan, approval, and tool contracts.
6. [Delivery Roadmap and Evaluation](06-delivery-roadmap-and-evaluation.md) — compressed build plan, test scenarios, metrics, and demo script.
7. [Claude Code Handoff](07-claude-code-handoff.md) — implementation sequence and guardrails for the next agent.

## Architecture decisions

- [ADR-001: Python, Strands, and Bedrock](decisions/ADR-001-python-strands-bedrock.md)
- [ADR-002: Bounded graph orchestration](decisions/ADR-002-bounded-graph-orchestration.md)
- [ADR-003: Human-gated state changes](decisions/ADR-003-human-gated-actions.md)

## Non-goals for the first build

- Direct control of trucks, crushers, conveyors, PLCs, or safety interlocks.
- Automatic approval of permits, blast plans, isolations, or emergency decisions.
- Connection to live production credentials or proprietary mine systems.
- A generic chat assistant with no operational state, tool contracts, or audit trail.
- A production claim that the prototype has been safety-certified or regulatory-approved.

## Target architecture in one sentence

> A deterministic, auditable workflow of bounded Strands agents that observes a canonical mine event model, proposes evidence-backed recovery plans, obtains accountable approval, and records the resulting action and outcome.

## External references

- [The Open Group — TOGAF](https://www.opengroup.org/togaf)
- [Strands Agents — Quickstart and feature overview](https://strandsagents.com/docs/user-guide/quickstart/overview/)
- [Strands Agents — Graph multi-agent pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/)
- [Strands Agents — Hooks](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/)
- [Strands Agents — Session management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/)
- [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
- [AWS Prescriptive Guidance — security for generative AI data](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-data-considerations-gen-ai/security.html)
