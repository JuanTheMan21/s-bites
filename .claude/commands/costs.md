---
description: Report Azure spend against the trial credit
---

Report current Azure spend for this project.

Use the Azure MCP server if connected; otherwise `az consumption usage list` or
`az costmanagement query`. Break down by service so it is clear where the money went — Foundry
tokens, Speech, Storage, Container Apps.

Context for interpreting the number: the subscription is Pay-As-You-Go with a $200 / 30-day credit,
and **no budget alerts are configured** — this command is the only spend check, so state clearly
how much credit remains and how many days are left.

Expected shape at POC volume: roughly $0.12 per 7-minute video, Speech free under the F0 tier's
500k characters/month, Container Apps inside its free monthly grant. If actual spend is materially
above that, say so and identify which service is responsible rather than just reporting the total.
