### Requirement: Message data model
The system SHALL represent messages as immutable objects with fields: message_id (str), sender_id (str), recipient (str or "broadcast"), node_id (str), text (str), sent_tick (int), delivered_tick (int = sent_tick + 1), and read (bool, default false). The message_id SHALL be deterministically generated as `msg_{tick}_{sequence}` where sequence is a per-tick counter.

#### Scenario: Create a private message
- **WHEN** an agent sends a targeted message to another agent
- **THEN** a Message object is created with recipient set to the target agent_id, node_id set to the sender's current location, sent_tick set to the current world tick, and delivered_tick set to sent_tick + 1

#### Scenario: Create a broadcast message
- **WHEN** an agent sends a broadcast message
- **THEN** a Message object is created with recipient set to "broadcast", node_id set to the sender's current location, sent_tick set to the current world tick, and delivered_tick set to sent_tick + 1

#### Scenario: Deterministic message IDs
- **WHEN** two messages are sent in the same tick
- **THEN** their message_ids SHALL be `msg_{tick}_0` and `msg_{tick}_1` respectively, ensuring deterministic ordering

### Requirement: Send private message
The system SHALL allow a living agent to send a text message to another specific living agent at the same node. The message text SHALL be truncated to `message_max_length` characters (default 500). The message SHALL be added to the pending queue for delivery next tick.

#### Scenario: Successful private message send
- **WHEN** agent_001 at node_A sends a message to agent_002 who is also at node_A and alive
- **THEN** a Message is created and added to pending_messages with sender_id="agent_001", recipient="agent_002", node_id="node_A"

#### Scenario: Reject message to agent at different node
- **WHEN** agent_001 at node_A attempts to send a message to agent_002 who is at node_B
- **THEN** the send operation SHALL fail (return None or raise) and no message is added to pending_messages

#### Scenario: Reject message from dead agent
- **WHEN** a dead agent attempts to send a message
- **THEN** the send operation SHALL fail and no message is added to pending_messages

#### Scenario: Reject message to dead agent
- **WHEN** an agent attempts to send a private message to a dead agent
- **THEN** the send operation SHALL fail and no message is added to pending_messages

#### Scenario: Truncate long message text
- **WHEN** an agent sends a message with text exceeding message_max_length characters
- **THEN** the text SHALL be truncated to message_max_length characters

### Requirement: Send broadcast message
The system SHALL allow a living agent to send a broadcast message to all other living agents at the same node. At send time, the system SHALL resolve the recipient list (all alive agents at the sender's node, excluding the sender) and create one pending message per recipient.

#### Scenario: Broadcast to multiple agents at node
- **WHEN** agent_001 broadcasts at node_A where agent_002 and agent_003 are also present and alive
- **THEN** two pending messages are created: one with recipient="agent_002" and one with recipient="agent_003", both with node_id="node_A"

#### Scenario: Broadcast at node with no other agents
- **WHEN** agent_001 broadcasts at node_A where no other living agents are present
- **THEN** no pending messages are created (broadcast is a no-op)

#### Scenario: Broadcast excludes dead agents at node
- **WHEN** agent_001 broadcasts at node_A where agent_002 (alive) and agent_003 (dead) are located
- **THEN** only one pending message is created for agent_002

### Requirement: One-tick delivery latency
Messages sent in tick T SHALL be delivered to recipients during the RECEIVE phase of tick T+1. Messages SHALL NOT be available to recipients on the tick they are sent.

#### Scenario: Message delivered next tick
- **WHEN** agent_001 sends a message during tick 5
- **THEN** the message is in pending_messages during tick 5 and moved to delivered_messages for the recipient during tick 6's RECEIVE phase

#### Scenario: Message not available same tick
- **WHEN** agent_001 sends a message to agent_002 during tick 5 and agent_002 queries messages during tick 5
- **THEN** the message from agent_001 SHALL NOT be in agent_002's delivered messages

### Requirement: Deliver pending messages
The system SHALL provide a `deliver_pending_messages` function that moves all pending messages to the delivered_messages dict keyed by recipient agent_id. Messages to dead agents SHALL be dropped. Messages to agents who moved to a different node between send and deliver SHALL still be delivered (message was "in transit").

#### Scenario: Standard delivery
- **WHEN** deliver_pending_messages is called and there are 3 pending messages for 2 different recipients
- **THEN** each recipient's delivered_messages list receives their messages, and pending_messages is cleared

#### Scenario: Drop messages to dead agents
- **WHEN** deliver_pending_messages is called and a pending message's recipient died between send and deliver
- **THEN** that message is dropped and not added to delivered_messages

#### Scenario: Deliver to agent who moved
- **WHEN** agent_002 was at node_A when agent_001 sent a message, but agent_002 moved to node_B before delivery
- **THEN** the message SHALL still be delivered to agent_002's delivered_messages

### Requirement: Query messages for agent
The system SHALL provide a `get_messages_for_agent` function that returns all messages delivered to a specific agent this tick, ordered by message_id.

#### Scenario: Retrieve delivered messages
- **WHEN** agent_002 has 3 delivered messages this tick
- **THEN** get_messages_for_agent returns all 3 messages ordered by message_id

#### Scenario: No messages
- **WHEN** agent_002 has no delivered messages this tick
- **THEN** get_messages_for_agent returns an empty list

### Requirement: Broadcast message history
The system SHALL maintain a bounded history of broadcast messages per node. The history SHALL store at most `broadcast_history_limit` (default 20) recent broadcast messages per node. The `get_message_history` function SHALL return broadcast messages for a given node, most recent first.

#### Scenario: Query broadcast history
- **WHEN** 5 broadcasts have been sent at node_A and get_message_history is called for node_A
- **THEN** all 5 messages are returned, most recent first

#### Scenario: History bounded by limit
- **WHEN** 25 broadcasts have been sent at node_A with broadcast_history_limit=20
- **THEN** get_message_history returns only the 20 most recent broadcasts

### Requirement: Private message history pruning
The system SHALL prune each agent's delivered message buffer to at most `private_message_history_limit` (default 50) messages, keeping the most recent. Pruning SHALL occur after delivery.

#### Scenario: Prune old private messages
- **WHEN** agent_002 accumulates 60 delivered messages with private_message_history_limit=50
- **THEN** the oldest 10 messages are removed, leaving the 50 most recent

### Requirement: Death cleanup
The system SHALL provide a `clear_messages_for_agent` function that removes: (1) any pending messages sent by the dead agent, and (2) any pending messages addressed to the dead agent. This SHALL be called during the DEATH phase.

#### Scenario: Clear pending messages from dead sender
- **WHEN** agent_001 dies and has 2 pending messages in the queue that agent_001 sent
- **THEN** those 2 messages are removed from pending_messages

#### Scenario: Clear pending messages to dead recipient
- **WHEN** agent_002 dies and has 1 pending message addressed to agent_002
- **THEN** that message is removed from pending_messages

#### Scenario: Delivered messages remain after death
- **WHEN** agent_001 dies and agent_002 previously received messages from agent_001
- **THEN** those already-delivered messages SHALL remain in agent_002's history (they were already received)

### Requirement: Communication configuration
The system SHALL support configurable parameters: `message_max_length` (default 500), `broadcast_history_limit` (default 20), and `private_message_history_limit` (default 50). These SHALL be part of the world configuration.

#### Scenario: Custom message length limit
- **WHEN** message_max_length is configured to 200 and an agent sends a 300-character message
- **THEN** the message text is truncated to 200 characters

#### Scenario: Custom broadcast history limit
- **WHEN** broadcast_history_limit is configured to 10 and 15 broadcasts are sent at a node
- **THEN** only the 10 most recent broadcasts are retained in history
