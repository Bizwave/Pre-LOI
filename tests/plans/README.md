# Packet gates

One file per packet: `test_YYYY_MM_DD_p<n>_<topic>.py`, written before the packet's code and committed on
its own. It carries the packet's regression duty (CLAUDE.md section 6, step 4). It is never edited to make
it pass; the only legitimate change is one covered by a `## Spec amendment` in the packet plan.

The whole suite (`pytest`) runs these together with the module tests in `tests/`.
