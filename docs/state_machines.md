# AMS State Machines

This document defines all valid state transitions for core domain entities. Invalid transitions must be rejected at the backend service level.

All enums are defined in [domain_model.md](domain_model.md).

---

## 1. Asset State Machine

### States

`idle` · `reserved` · `launching` · `transiting` · `on_task` · `returning` · `landing` · `charging` · `offline` · `degraded` · `lost` · `maintenance`

### Transition Table

| From | To | Trigger |
|------|----|---------|
| `idle` | `reserved` | Assigned to a mission |
| `reserved` | `launching` | Launch command dispatched |
| `reserved` | `idle` | Mission cancelled before launch |
| `launching` | `transiting` | Airborne, en route |
| `transiting` | `on_task` | Arrived at task location |
| `transiting` | `returning` | Abort / redirect command |
| `on_task` | `returning` | Task completed or aborted |
| `on_task` | `transiting` | Redirected to new task |
| `returning` | `landing` | Arrived at base |
| `landing` | `charging` | Landed, begin charge |
| `landing` | `idle` | Landed, no charge needed |
| `charging` | `idle` | Charge complete |
| `charging` | `maintenance` | Maintenance required |
| `maintenance` | `idle` | Maintenance complete |
| `offline` | `idle` | Connection restored |
| `degraded` | `idle` | Issue resolved |
| `degraded` | `maintenance` | Requires maintenance |
| `lost` | `idle` | Recovered |
| `lost` | `offline` | Confirmed offline |
| *any* | `degraded` | Health warning detected |
| *any* | `lost` | Communication timeout exceeded |
| *any* | `offline` | Explicit shutdown / disconnect |

### Diagram

```
                    ┌──────────────┐
              ┌────►│  maintenance │◄───┐
              │     └──────┬───────┘    │
              │            │ complete   │
              │            ▼            │
   ┌──────┐  │     ┌──────────┐     ┌──────────┐
   │offline│──┘ ┌──►│   idle   │◄────│ charging │
   └──────┘    │   └────┬─────┘     └────▲─────┘
      ▲        │        │ assign         │
      │        │        ▼                │ land
   ┌──────┐   │  ┌──────────┐     ┌─────┴─────┐
   │ lost │   │  │ reserved │     │  landing   │
   └──────┘   │  └────┬─────┘     └─────▲─────┘
      ▲       │       │ launch           │ arrive
      │       │       ▼                  │
  (any state) │ ┌──────────┐     ┌──────┴──────┐
              │ │launching │     │  returning   │
              │ └────┬─────┘     └──────▲──────┘
              │      │ airborne         │ complete/abort
              │      ▼                  │
              │ ┌──────────┐     ┌──────┴──────┐
              └─┤transiting├────►│   on_task    │
                └──────────┘     └─────────────┘
```

---

## 2. Mission State Machine

### States

`draft` · `proposed` · `approved` · `queued` · `active` · `paused` · `completed` · `aborted` · `failed` · `archived`

### Transition Table

| From | To | Trigger |
|------|----|---------|
| `draft` | `proposed` | Operator submits for review |
| `proposed` | `approved` | Reviewer approves |
| `proposed` | `draft` | Reviewer returns for edits |
| `approved` | `queued` | Awaiting resource availability |
| `queued` | `active` | Resources available, execution begins |
| `active` | `paused` | Operator pauses |
| `paused` | `active` | Operator resumes |
| `active` | `completed` | All tasks finished successfully |
| `active` | `aborted` | Operator manually aborts |
| `active` | `failed` | Unrecoverable error during execution |
| `paused` | `aborted` | Operator aborts while paused |
| `completed` | `archived` | Moved to archive |
| `aborted` | `archived` | Moved to archive |
| `failed` | `archived` | Moved to archive |

### Diagram

```
┌───────┐    submit    ┌──────────┐   approve   ┌──────────┐
│ draft │─────────────►│ proposed │────────────►│ approved │
└───────┘   ◄──────────└──────────┘             └────┬─────┘
             return                                   │ queue
                                                      ▼
                                                ┌──────────┐
                                    ┌──────────►│  queued   │
                                    │           └────┬─────┘
                                    │                │ start
                                    │                ▼
┌──────────┐          ┌─────────┐  │         ┌──────────┐
│ archived │◄─────────│ aborted │◄─┼─────────│  active  │
└──────────┘          └─────────┘  │  abort  └──┬───┬───┘
     ▲                     ▲       │     pause │   │ complete/fail
     ├─────────────────────┘       │           ▼   │
     │   ┌──────────┐             │    ┌────────┐ │
     ├───┤  failed  │◄────────────┘    │ paused │ │
     │   └──────────┘                  └───┬────┘ │
     │                                resume│     │
     │                                     └──►   │
     │   ┌───────────┐                           │
     └───┤ completed │◄──────────────────────────┘
         └───────────┘
```

---

## 3. Task State Machine

### States

`waiting` · `ready` · `assigned` · `transit` · `active` · `blocked` · `completed` · `failed` · `cancelled`

### Transition Table

| From | To | Trigger |
|------|----|---------|
| `waiting` | `ready` | All dependency tasks completed |
| `ready` | `assigned` | Asset allocated |
| `assigned` | `transit` | Asset begins transit to target |
| `transit` | `active` | Asset arrives at target |
| `transit` | `blocked` | External block (e.g., geofence, weather) |
| `active` | `completed` | Task execution finished successfully |
| `active` | `failed` | Task execution error |
| `active` | `blocked` | External block during execution |
| `blocked` | `transit` | Block resolved, resume transit |
| `blocked` | `active` | Block resolved, resume execution |
| `blocked` | `cancelled` | Operator cancels blocked task |
| `ready` | `cancelled` | Operator cancels before assignment |
| `assigned` | `cancelled` | Operator cancels after assignment |
| `waiting` | `cancelled` | Parent mission aborted |

### Diagram

```
┌─────────┐  deps met  ┌───────┐  assign  ┌──────────┐
│ waiting │───────────►│ ready │─────────►│ assigned │
└────┬────┘            └───┬───┘          └────┬─────┘
     │                     │                    │ depart
     │ cancel              │ cancel             ▼
     │                     │              ┌─────────┐
     ▼                     ▼              │ transit │
┌───────────┐        ┌───────────┐       └──┬──┬───┘
│ cancelled │◄───────│ cancelled │          │  │
└───────────┘        └───────────┘   arrive │  │ block
                                            ▼  ▼
                     ┌───────────┐    ┌─────────┐
                     │ completed │◄───│ active  │
                     └───────────┘    └──┬──┬───┘
                     ┌───────────┐       │  │
                     │  failed   │◄──────┘  │ block
                     └───────────┘          ▼
                                      ┌─────────┐
                                      │ blocked │
                                      └─────────┘
```

---

## 4. Command State Machine

### States

`proposed` · `validated` · `rejected` · `approved` · `queued` · `sent` · `acknowledged` · `active` · `completed` · `failed` · `cancelled` · `expired`

### Transition Table

| From | To | Trigger |
|------|----|---------|
| `proposed` | `validated` | Passes validation checks |
| `proposed` | `rejected` | Fails validation |
| `validated` | `approved` | Approved (auto or manual) |
| `validated` | `rejected` | Denied by approver |
| `approved` | `queued` | Placed in execution queue |
| `queued` | `sent` | Dispatched to execution adapter |
| `sent` | `acknowledged` | Adapter confirms receipt |
| `acknowledged` | `active` | Execution started |
| `active` | `completed` | Execution finished successfully |
| `active` | `failed` | Execution error |
| `sent` | `failed` | Adapter reports send failure |
| `proposed` | `cancelled` | Operator cancels before validation |
| `validated` | `cancelled` | Operator cancels before approval |
| `approved` | `cancelled` | Operator cancels before dispatch |
| `queued` | `cancelled` | Operator cancels in queue |
| `sent` | `expired` | No acknowledgement within timeout |
| `acknowledged` | `expired` | No completion within timeout |

### Diagram

```
┌──────────┐  valid   ┌───────────┐  approve  ┌──────────┐
│ proposed │─────────►│ validated │──────────►│ approved │
└────┬─────┘         └─────┬─────┘           └────┬─────┘
     │ invalid              │ deny                  │ queue
     ▼                      ▼                       ▼
┌──────────┐          ┌──────────┐           ┌──────────┐
│ rejected │          │ rejected │           │  queued  │
└──────────┘          └──────────┘           └────┬─────┘
                                                   │ send
                                                   ▼
┌──────────┐                                ┌──────────┐
│ expired  │◄───────────────────────────────│   sent   │
└──────────┘         timeout                └────┬─────┘
     ▲                                           │ ack
     │              ┌──────────┐                 ▼
     └──────────────│  active  │◄──────── ┌────────────┐
        timeout     └──┬───┬──┘           │acknowledged│
                       │   │              └────────────┘
              complete │   │ error
                       ▼   ▼
              ┌──────────┐ ┌──────────┐
              │completed │ │  failed  │
              └──────────┘ └──────────┘

(cancelled reachable from: proposed, validated, approved, queued)
```

---

## 5. Alert State Machine

### States

`open` · `acknowledged` · `cleared`

### Transition Table

| From | To | Trigger |
|------|----|---------|
| `open` | `acknowledged` | Operator acknowledges |
| `open` | `cleared` | Condition auto-resolves |
| `acknowledged` | `cleared` | Condition resolves or operator clears |

### Diagram

```
┌──────┐   ack    ┌──────────────┐   clear   ┌─────────┐
│ open │─────────►│ acknowledged │──────────►│ cleared │
└──┬───┘          └──────────────┘           └─────────┘
   │                                              ▲
   │              auto-resolve                    │
   └──────────────────────────────────────────────┘
```

---

## 6. Enforcement Rules

1. **All transitions are validated at the backend service level.** The frontend cannot bypass state checks.
2. **Invalid transitions return an error** with the current state, attempted target state, and reason for rejection.
3. **Wildcard transitions** (e.g., any → `degraded`, any → `lost` for assets) take precedence and are always valid.
4. **Terminal states** (`archived` for missions, `rejected`/`completed`/`failed`/`expired`/`cancelled` for commands, `cleared` for alerts) have no outgoing transitions.
5. **Every transition emits a domain event** — see [event_catalog.md](event_catalog.md).

---

## 7. Cross-References

- Entity field definitions: [domain_model.md](domain_model.md)
- Events emitted on transitions: [event_catalog.md](event_catalog.md)
- API endpoints that trigger transitions: [api_contract.md](api_contract.md)
