"""Phase 5 application agent: a semi-autonomous, human-supervised form filler.

The agent opens a job's application page in a headed, persistent browser, fills
what it safely can from profile.yaml, attaches the prepared PDFs, advances
through multi-step flows, and STOPS at the final review step. It never submits.
Safety invariants are enforced in code (app.agent.safety + the browser click
helper), not merely in prompts.
"""
