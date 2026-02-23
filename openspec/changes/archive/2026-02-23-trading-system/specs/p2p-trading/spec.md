## ADDED Requirements

### Requirement: Agents can propose direct trades to co-located agents
The system SHALL allow an agent to propose a trade to another agent at the same node. The proposal specifies commodities and credits offered and requested. The proposer MUST have the offered items and credits at proposal time. The system SHALL reject the proposal if the proposer already has `max_pending_trades` pending proposals.

#### Scenario: Successful trade proposal
- **WHEN** agent_001 at node_hub_iron proposes to agent_002 (also at node_hub_iron): offer 3 IRON, request 2 WOOD + 1000 mc
- **THEN** a TradeProposal is created with status PENDING

#### Scenario: Proposal rejected — not co-located
- **WHEN** agent_001 at node_hub_iron proposes a trade to agent_003 at node_hub_wood
- **THEN** the proposal is rejected

#### Scenario: Proposal rejected — proposer lacks offered items
- **WHEN** agent_001 with 1 IRON proposes offering 3 IRON
- **THEN** the proposal is rejected

#### Scenario: Proposal rejected — pending trade limit reached
- **WHEN** agent_001 with 3 pending proposals proposes a new trade
- **THEN** the proposal is rejected

### Requirement: Target agent can accept or reject trade proposals
The system SHALL allow the target agent to accept a PENDING proposal directed at them. On acceptance, the system SHALL verify both agents are still co-located and both still have the required items and credits. The system SHALL also allow the target to reject a proposal, setting its status to REJECTED.

#### Scenario: Successful acceptance
- **WHEN** agent_002 accepts a pending proposal from agent_001, both are at node_hub_iron, and both have required items
- **THEN** the trade executes: offered items/credits transfer from proposer to target, requested items/credits transfer from target to proposer, and proposal status becomes ACCEPTED

#### Scenario: Acceptance fails — agents no longer co-located
- **WHEN** agent_002 accepts a proposal but agent_001 has moved to a different node
- **THEN** the acceptance fails, proposal status becomes INVALID

#### Scenario: Acceptance fails — proposer no longer has items
- **WHEN** agent_002 accepts but agent_001 no longer has the offered commodities
- **THEN** the acceptance fails, proposal status becomes INVALID

#### Scenario: Target rejects proposal
- **WHEN** agent_002 rejects a pending proposal
- **THEN** the proposal status becomes REJECTED

### Requirement: Trade proposals expire after a configurable number of ticks
The system SHALL expire PENDING proposals that are older than a configurable max age. Expired proposals SHALL have status EXPIRED and SHALL NOT be acceptable.

#### Scenario: Proposal expires after max age
- **WHEN** a proposal created at tick 10 reaches tick 15 with max_age=5
- **THEN** the proposal status becomes EXPIRED

#### Scenario: Proposal accepted before expiry
- **WHEN** a proposal created at tick 10 is accepted at tick 13 with max_age=5
- **THEN** the acceptance proceeds normally (proposal is not expired)

### Requirement: P2P trades support multi-item swaps with credits
The system SHALL support proposals that include any combination of: commodities offered, credits offered, commodities requested, and credits requested. A proposal MUST offer or request at least one non-zero item.

#### Scenario: Pure commodity swap
- **WHEN** agent_001 proposes: offer 5 IRON, request 3 WOOD
- **THEN** the proposal is valid with zero credit amounts

#### Scenario: Commodity for credits
- **WHEN** agent_001 proposes: offer 5 IRON, request 10000 mc
- **THEN** the proposal is valid

#### Scenario: Mixed swap
- **WHEN** agent_001 proposes: offer 3 IRON + 2000 mc, request 5 HERBS
- **THEN** the proposal is valid

#### Scenario: Empty proposal rejected
- **WHEN** agent_001 proposes with all zero quantities and credits
- **THEN** the proposal is rejected
