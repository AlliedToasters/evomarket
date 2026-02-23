# Proposal: Communication System

## Change ID
`communication-system`

## Summary
Implement the message passing system: agent-to-agent and broadcast messages with one-tick delivery latency, node-local scope, and message history.

## Motivation
Natural language communication is what differentiates this from a standard multi-agent simulation. Messages enable negotiation, deception, reputation building, and information trading. In Phase 0 with heuristic agents, messages will be simple strings, but the infrastructure must support the rich text that LLM agents will produce in Phase 1.

## What's Changing

### New Files
- `evomarket/engine/communication.py` — Message handling, delivery, history
- `tests/test_communication.py`

### Data Models

**Message:**
- `message_id: str`
- `sender_id: str`
- `recipient: str | Literal["broadcast"]` (agent_id or "broadcast" for all at node)
- `node_id: str` (where the message was sent)
- `text: str`
- `sent_tick: int`
- `delivered_tick: int` (sent_tick + 1)
- `read: bool`

**MessageQueue (on WorldState):**
- `pending_messages: list[Message]` — sent this tick, to be delivered next tick
- `delivered_messages: dict[str, list[Message]]` — keyed by recipient agent_id, messages available this tick

### Operations

`send_message(world: WorldState, sender_id: str, action: SendMessageAction) -> Message`
- Verify sender is alive and at a node
- If targeted: verify recipient is at the same node and alive
- If broadcast: message goes to all agents at the same node (except sender)
- Create message with sent_tick = current tick
- Add to pending_messages queue
- Return the message object

`deliver_pending_messages(world: WorldState) -> int`
- Called during RECEIVE phase of next tick
- Move all pending_messages to delivered_messages, keyed by recipient
- For broadcasts: create a copy for each recipient at the node at time of sending
- Agents who moved away between send and deliver still receive (message was "in transit")
- Agents who died between send and deliver: message is dropped
- Returns count of messages delivered

`get_messages_for_agent(world: WorldState, agent_id: str) -> list[Message]`
- Returns all delivered messages for an agent this tick
- Used during OBSERVE phase to build the agent's context

`get_message_history(world: WorldState, node_id: str, limit: int) -> list[Message]`
- Returns recent broadcast messages at a node (not private messages)
- Provides a sense of "what's been discussed here"

### Death Cleanup

`clear_messages_for_agent(world: WorldState, agent_id: str) -> None`
- Remove any pending messages from the dead agent
- Remove any undelivered messages to the dead agent

### Configuration

| Parameter | Description | Default |
|---|---|---|
| `message_max_length` | Max characters per message | 500 |
| `broadcast_history_limit` | How many broadcast messages to keep per node | 20 |
| `private_message_history_limit` | How many private messages to keep per agent | 50 |

## Acceptance Criteria
- Messages have exactly one-tick delivery latency
- Messages are node-local (can only message agents at same node)
- Broadcast messages go to all agents at the node except sender
- Private messages are only visible to sender and recipient
- Messages to dead agents are dropped
- Message history is bounded (old messages pruned)
- Messages from dead agents in the pending queue are dropped

## Dependencies
- `core-data-models`

## Estimated Complexity
Low-medium. ~200-300 lines of communication code, ~200-300 lines of tests.
