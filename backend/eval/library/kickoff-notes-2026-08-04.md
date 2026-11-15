# Campus Library app: kickoff
Date: 2026-08-04
Author: Dr. Sen
Attendees: Dr. Sen, Meera, Arun, Kavya

## Scope
- Decision: we use PostgreSQL on the college server because the IT department only supports Postgres backups.
- Meera owns the book-search API and the catalogue import scripts.
- Arun owns the nightly database backup job.
- Late-return fines are disabled during the pilot semester so students can get used to the app.

## Risks
- Do not rename columns in the loans table before December. The library's barcode kiosk reads it directly.
- The college firewall blocks outgoing SMTP, so email reminders cannot be sent from the server yet.

## Ideas
- We might move book search to Elasticsearch next year if the catalogue grows. Nothing decided.
