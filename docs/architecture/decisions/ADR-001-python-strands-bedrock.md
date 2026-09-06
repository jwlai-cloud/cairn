# ADR-001: Use Python, Strands Agents SDK, and Amazon Bedrock

## Status

Accepted for the first vertical slice

## Date

2026-09-06

## Context

CAIRN needs an agent runtime that supports structured outputs, multi-agent orchestration, lifecycle hooks, sessions, model-provider flexibility, and a credible AWS deployment path. The build window is short, so the architecture must support a working local demo before cloud hardening.

## Decision

Use Python with the Strands Agents SDK and Amazon Bedrock as the default model provider.

Keep domain models, policy, audit, integrations, and action gateways independent from Strands-specific objects. Strands is the agent implementation layer, not the enterprise control plane.

## Alternatives considered

### TypeScript and the Strands TypeScript SDK

Viable because Strands supports both Python and TypeScript. Rejected for the first slice because Python is the faster path for data fixtures, simulation, validation, and evaluation in this project. Revisit if the product surface becomes primarily Node.js.

### LangGraph or another orchestration framework

Rejected for this implementation because the requested architecture is based on Strands and the first workflow can be expressed as a bounded Strands Graph.

### Direct model-provider SDK calls

Rejected because they would require rebuilding agent lifecycle, multi-agent, structured-output, session, and hook patterns and would create unnecessary provider coupling.

## Consequences

### Positive

- AWS-native Bedrock path with provider substitution available through Strands.
- Fast local implementation and testability.
- Clear separation between agent reasoning and enterprise controls.
- Direct alignment with the official Strands documentation and examples.

### Negative

- Strands API versions must be pinned and verified.
- AWS model access and credentials are still required for Bedrock runs.
- Python service packaging and async integration require deliberate structure.

## Guardrails

- Pin dependencies and record versions in the implementation README.
- Use a mock model or deterministic adapter for contract and safety tests.
- Never place authorization logic only in prompts or callbacks.
