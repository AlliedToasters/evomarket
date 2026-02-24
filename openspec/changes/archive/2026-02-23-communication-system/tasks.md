## 1. Data Models

- [x] 1.1 Add communication config fields to WorldConfig (message_max_length, broadcast_history_limit, private_message_history_limit)
- [x] 1.2 Create Message frozen Pydantic model in evomarket/engine/communication.py
- [x] 1.3 Create SendMessageAction Pydantic model (sender_id, recipient, text)
- [x] 1.4 Add message queue state to WorldState (pending_messages, delivered_messages, broadcast_history, next_message_seq)

## 2. Core Message Operations

- [x] 2.1 Implement send_message() — validate sender alive + at node, validate recipient (co-located + alive for private, resolve recipients for broadcast), truncate text, create Message, add to pending queue
- [x] 2.2 Implement deliver_pending_messages() — move pending to delivered_messages keyed by recipient, drop messages to dead agents, prune private history to limit, clear pending queue
- [x] 2.3 Implement get_messages_for_agent() — return delivered messages for agent ordered by message_id
- [x] 2.4 Implement get_message_history() — return bounded broadcast history for a node, most recent first

## 3. Death Cleanup

- [x] 3.1 Implement clear_messages_for_agent() — remove pending messages from and to dead agent

## 4. Serialization

- [x] 4.1 Add message queue state to WorldState.to_json() and WorldState.from_json()

## 5. Tests

- [x] 5.1 Test Message model creation and immutability
- [x] 5.2 Test send_message — private success, reject different node, reject dead sender, reject dead recipient, text truncation
- [x] 5.3 Test send_message — broadcast to multiple agents, broadcast with no others, broadcast excludes dead
- [x] 5.4 Test deliver_pending_messages — standard delivery, drop to dead, deliver to moved agent
- [x] 5.5 Test one-tick latency — message not available same tick, available next tick
- [x] 5.6 Test get_messages_for_agent — with messages, empty list
- [x] 5.7 Test broadcast history — query, bounded by limit
- [x] 5.8 Test private message history pruning
- [x] 5.9 Test clear_messages_for_agent — clear from dead sender, clear to dead recipient, delivered messages remain
- [x] 5.10 Test deterministic message IDs (msg_{tick}_{seq})
- [x] 5.11 Test WorldState serialization round-trip with message queue state
