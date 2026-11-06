# 0003: Keep raw evidence local and state timing limits

Status: adopted, November 6, 2026.

The launcher supervises the existing Steam/Proton command, saves start/end and
monotonic elapsed time, forwards stop signals and records durable heartbeats.
It captures available error and journal evidence without collecting a full
environment or persisting Steam command arguments.

Elapsed time includes loading, menus and pauses; it is not an active-play
measurement. An incomplete session keeps its last saved lower bound and unknown
end time. Exit codes and error counters do not independently diagnose a crash.
Journal access can be unavailable and hard locks may prevent final writes.

Raw logs and Proton crash reports remain private. Reports export selected
structured fields only and still require review before sharing. No telemetry
or automatic upload is added.

The first gameplay review exposed two gaps: the journal helper rejected saved
UUID-form boot IDs, and the summary did not count a Wine assertion when the
wrapper returned zero. Normalize the boot ID for the helper, remove inherited
Steam loader injections for that helper only, and count assertion/dispatch
evidence independently of process exit status. Preserve original reports
privately before regenerating them; do not rewrite an uncertain event as a
confirmed gameplay or GPU crash.
