## 1. Result Models

- [x] 1.1 Define `WillUpdateResult` Pydantic model (frozen) with success/error fields
- [x] 1.2 Define `WillTransfer` Pydantic model (frozen) — beneficiary_id, credits, commodities, will_percentage, alive
- [x] 1.3 Define `DeathResult` Pydantic model (frozen) — agent_id, estate totals, will distributions, unclaimed amounts, local share, treasury return, commodities destroyed

## 2. Will Management

- [x] 2.1 Implement `update_will(world, agent_id, distribution)` — validate beneficiary IDs exist in world, percentages non-negative and sum ≤ 1.0, replace agent's will
- [x] 2.2 Implement `get_will(world, agent_id)` — return agent's current will

## 3. Death Resolution Core

- [x] 3.1 Implement estate calculation — extract credit balance and commodity inventory from dying agent
- [x] 3.2 Implement will execution — iterate beneficiaries, transfer credits (floor division) and commodities (floor division) to living beneficiaries, accumulate unclaimed shares
- [x] 3.3 Implement unclaimed distribution — split credits between local agents (equal floor division) and treasury per config percentages, destroy unclaimed commodities, send rounding remainders to treasury
- [x] 3.4 Implement death cleanup — set `alive = False`, invoke optional cancel_orders_fn and clear_messages_fn callbacks
- [x] 3.5 Assemble `resolve_death(world, agent_id, cancel_orders_fn, clear_messages_fn)` combining steps 3.1-3.4, returning `DeathResult`

## 4. Batch Death Resolution

- [x] 4.1 Implement `resolve_deaths(world, dead_agent_ids, cancel_orders_fn, clear_messages_fn)` — sort by agent_id, process each sequentially, return list of DeathResult

## 5. Tests — Will Management

- [x] 5.1 Test valid will update replaces existing will
- [x] 5.2 Test will rejection: percentages exceed 1.0
- [x] 5.3 Test will rejection: negative percentage
- [x] 5.4 Test will rejection: non-existent beneficiary agent ID
- [x] 5.5 Test will accepts dead agent as beneficiary
- [x] 5.6 Test get_will returns current will

## 6. Tests — Death Resolution

- [x] 6.1 Test single death with 100% beneficiary alive — full transfer
- [x] 6.2 Test death with multiple beneficiaries at partial percentages — correct floor division
- [x] 6.3 Test death with dead beneficiary — share goes to unclaimed
- [x] 6.4 Test death with all beneficiaries dead — entire estate unclaimed
- [x] 6.5 Test death with empty will — entire estate unclaimed
- [x] 6.6 Test death with zero credits and empty inventory — no-op distribution
- [x] 6.7 Test unclaimed split: local agents receive equal share, treasury receives its portion plus rounding remainder
- [x] 6.8 Test unclaimed with no living agents at node — all goes to treasury
- [x] 6.9 Test unclaimed commodities are destroyed
- [x] 6.10 Test cleanup: agent marked `alive = False`, callbacks invoked

## 7. Tests — Batch Deaths and Invariant

- [x] 7.1 Test batch death ordering: earlier-ID agent processed first, later-ID agent receives inheritance then dies
- [x] 7.2 Test batch death: later-ID agent wills to earlier-ID agent who is already dead
- [x] 7.3 Test batch death: all agents at a node die simultaneously — local share goes to treasury
- [x] 7.4 Test invariant preserved after single death
- [x] 7.5 Test invariant preserved after batch deaths
- [x] 7.6 Property-based test: random death sequences with random wills preserve invariant
