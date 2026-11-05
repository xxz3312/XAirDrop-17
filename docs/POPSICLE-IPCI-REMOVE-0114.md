# 0114 IPCI remove admission before synchronization unregister

Patch 0046 adds a preflight to the native `pld_ipci_remove()` callback after acquiring its PSOC transition and draining operations, while the device sync lookup is still registered. It checks the upper SSR gate, module-stop journal, exact HDD parent identities, host/runtime ownership and backend detach result before native unregister/remove/delete/destroy can run.

A refusal retains the lookup, HDD and transition. The journal is not consumed or reset and the native teardown is not entered. Empty private state preserves the native path, including absent PLD context and native transition acquisition failure. Backend unregister pending or failure retains its authority. This is a fail-closed admission guard; a void remove callback cannot promise that a bus or module loader will preserve external lifetimes after it returns. Full module unload, hardware disappearance, deferred retry and other bus removal paths remain uncoordinated. The radio backend stays disabled.

## Verification

Production source `4a6a4c648418ffc1031dfabcf4ce24772759dfdf`, verification source `51d1799635b7367b24cc7e3bdd316c8d8f661d43`; [Actions 41977591491](https://github.com/xxz3312/XAirDrop-17/actions/runs/41977591491) completed all seven jobs. Seventeen new remove scenarios and ten new mutation controls passed along with eighty inherited controls using ASan/UBSan and leak detection. The initial run failed because inherited source audits matched the newly added helper rather than the native function; the correction scopes those audits to native functions without changing production code.

The compact diagnostic archive and all six fast regression archives have verified SHA-256 digests. Full diagnostic and fast host reports match exactly. Reassembling the fixture from the locked WLAN revision plus patches reproduced its hash, production hashes and native remove function hashes. Existing whole-source restoration audits and patch 0046 reverse check passed. Full WLAN linking, selected structure layouts, recorded loader checks and required helper symbols passed. These retain their report-specific limits; the large diagnostic archive was not downloaded.

Locally, 53 Python tests and shell syntax passed. A separate management RX C fixture compiled but LeakSanitizer aborted under this host's ptrace environment; the remainder of that local C command chain did not execute. The native host fixture was only reassembled locally. Successful sanitizer execution is evidenced by Actions, not by a local C pass.

This completes stage 0114 offline acceptance, not physical removal or Apple interoperability certification. No phone execution, discovery, handshake or bidirectional transfer was performed. Next work must coordinate caller lifetime retention across remove/unload before activation.

See the [validation checkpoint](research/popsicle-ipci-remove-0114-validation.json).
