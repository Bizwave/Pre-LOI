# YYYY-MM-DD — P<n> <packet name>

Status: draft | signed off (date) | building | verifying | reviewing | closed
Branch: `p<n>-<topic>` · Gate: `tests/plans/test_YYYY_MM_DD_p<n>_<topic>.py` · Budget: <hours> (tech plan §9)

## Goal
<One paragraph in plain words. What exists after this packet that did not before.>

**Done when:** <observable result, e.g. "`bw intake` on a synthetic folder records 3 documents and 11 pages">

## Scope
In: <bullets>
Out: <bullets, including tempting things deliberately left for later packets>

## Data contract
Exact names, types and example values for every interface this packet creates or changes.

```
<function signatures, table columns with types and nullability, JSON shapes, CLI arguments>
```

## Sub-packets
- [ ] P<n>.1 <small, committable step>
- [ ] P<n>.2 ...
- [ ] P<n>.3 ...

## Gate tests (written first)
| Test | Asserts (real values) |
|---|---|
| `test_...` | ... |

## Depends on
Decisions: <D-numbers from docs/decisions.md, or none> · Packets: <earlier packets>

## Risks and rollback
<what could go wrong; how to undo (e.g. alembic downgrade -1, revert branch)>

## Lessons applied
<Every lesson in tasks/lessons.md that bears on this packet (promoted ones first) and how this plan applies it.>
- [<packet>] <lesson> → <how this plan applies it>

## Revision log
| Date | What changed | Stopped for Chan |
|---|---|---|
| YYYY-MM-DD HH:MM | Plan written | yes |

## Reviewer Note
<Chan writes here. Claude answers each point below it, adds a Revision log row, and stops again.>

## Gate — first run
<per-test first-run result: each test fails for its own reason (the behaviour it checks); mark any test that
passed before the code as a preservation check and say why>

## Spec amendment
<only if the gate proved the plan wrong: what changed, why, date, Chan's OK>

## Results
<what changed, gate and suite counts, deviations, review verdict and rounds, hours>

## Master-plan change proposal
<optional>
