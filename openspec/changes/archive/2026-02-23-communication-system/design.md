## Context

EvoMarket's core data models and economy primitives are implemented (`core/` module). The engine module exists but has no phase implementations yet. The tick pipeline defines 10 phases (RECEIVE → OBSERVE → DECIDE → VALIDATE → RESOLVE → TAX → DEATH → SPAWN → REPLENISH → LOG), and the communication system integrates with RECEIVE (delivery), OBSERVE (reading), and DEATH (cleanup).

`WorldState` is the root state container — not a Pydantic model (holds `random.Random`), but all sub-objects (Agent, Node) are Pydantic models. Messages must fit this pattern.

## Goals / Non-Goals

**Goals:**
- Implement node-local message passing with one-tick delivery latency
- Support both targeted (private) and broadcast messages
- Bounded message history to prevent unbounded memory growth
- Clean integration points for future tick pipeline phases
- Deterministic message ordering for reproducibility

**Non-Goals:**
- Cross-node messaging (out of scope — agents must be co-located)
- Message costs (no credit cost for sending messages in Phase 0)
- Message content analysis or moderation
- Encryption or message privacy enforcement beyond delivery targeting
- Rich message types (attachments, structured data) — text only for now

## Decisions

### 1. Message model as a frozen Pydantic BaseModel

Messages are immutable after creation. Use a frozen Pydantic model consistent with the project's data modeling conventions. The `message_id` is deterministically generated as `msg_{tick}_{sequence}` using a per-tick counter on WorldState to ensure reproducibility.

**Alternative considered:** Dataclass — rejected because all other models use Pydantic, and we need JSON serialization for checkpoints.

### 2. MessageQueue as a plain container on WorldState

Add `pending_messages` (list) and `delivered_messages` (dict keyed by agent_id) directly as attributes on `WorldState.__init__`. Also add `broadcast_history` (dict keyed by node_id, each a bounded deque) for node-local broadcast history.

**Alternative considered:** Separate MessageQueue Pydantic model — rejected because WorldState itself is not a Pydantic model, and adding a non-Pydantic container keeps the pattern consistent. The queue is simple enough to not need its own class.

### 3. Broadcast fan-out at send time, delivery at receive time

When a broadcast is sent, immediately resolve the recipient list (all alive agents at the sender's node, excluding sender) and create one pending message per recipient. This captures the "who was there when the message was sent" semantics. Delivery happens next tick during RECEIVE phase.

**Alternative considered:** Fan-out at delivery time — rejected because agents may move between ticks, and the proposal specifies that "agents who moved away between send and deliver still receive."

### 4. Message history pruning via bounded deques

Use `collections.deque(maxlen=N)` for broadcast history per node. Private message history uses a list with explicit truncation after delivery (keep last N). This is simple, O(1) per append, and automatically handles bounds.

**Alternative considered:** Periodic sweep — unnecessary complexity for a bounded buffer.

### 5. SendMessageAction as a standalone Pydantic model

Define `SendMessageAction` in `evomarket/engine/communication.py` alongside the message processing functions. This keeps the communication system self-contained. When the action system is built later, it can import from here.

**Alternative considered:** Add to a central `actions.py` — premature since actions.py doesn't exist yet and would create a dependency on unbuilt infrastructure.

## Risks / Trade-offs

- **Memory growth from message history** → Mitigated by bounded deques and configurable limits. Default 20 broadcasts/node, 50 private/agent.
- **Broadcast fan-out with many agents at one node** → O(N) copies per broadcast where N = agents at node. Acceptable for population_size=20. If populations grow much larger, consider a shared-reference approach.
- **Message ordering determinism** → Mitigated by deterministic `message_id` generation using tick + sequence counter, and list ordering preserved through the pipeline.
- **No tick pipeline yet** → Communication functions are designed as standalone functions that take WorldState, so they can be called from the tick pipeline when it's built, or directly in tests.
