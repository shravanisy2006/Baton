# GitHub export — club/eventapp (synthetic)

## Pull request #87 — Remove Razorpay checkout from registration flow
Author: riya-dev
Date: 2026-09-14

Dropping Razorpay for now. The sponsor asked us to pause payments until the MoU is signed. Keep the payment code behind the PAYMENTS_ENABLED flag so we can switch it back on later.

## Issue #92 — Excel export breaks above 500 rows (reopened)
Author: anika
Date: 2026-10-02

Reopening this. The attendee Excel export works for small events, but above 500 rows it times out and the downloaded file is corrupted. This task is not done.

## Comment on issue #92
Author: riya-dev
Date: 2026-10-03

Confirmed the export fails above 500 rows. The fix is to write rows in chunks instead of building the whole sheet in memory. I have not started the fix yet.

## Commit 4f2a9c1
Author: riya-dev
Date: 2026-09-14

Add PAYMENTS_ENABLED flag (default false) and hide the checkout button when it is off.
