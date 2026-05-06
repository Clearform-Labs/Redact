# Test log

Paste each `Input` block into a supported chat site (e.g. claude.ai) with the
extension loaded. Record what you observed in the `Result` column.

| ✓ = expected, ✗ = wrong, ~ = partial / over- or under-redacted |

---

## BLOCK tier — model

| # | Case | Input | Expected | Result |
|---|---|---|---|---|
| 1 | SSN dashed | `Customer SSN on file: 234-56-7890.` | One BLOCK modal, redacts `234-56-7890` | ✓ |
| 2 | Credit card (Luhn-valid) | `Charge card 4532-0151-1283-0366 exp 09/27` | One BLOCK modal, redacts `4532-0151-1283-0366` | ✓ |
| 3 | Generic password | `The DB password is hunter2-prod-2024 — rotated last week.` | One BLOCK modal, redacts only `hunter2-prod-2024` | ✓ |

## BLOCK tier — regex safety net

| # | Case | Input | Expected | Result |
|---|---|---|---|---|
| 4 | AWS access key | `AWS_ACCESS_KEY_ID=AKIA4F3JWPQ8N2ZX7V9B` | BLOCK, redacts only the key value | ~ redacted entire string |
| 5 | GitHub PAT | `ghp_xK9mN3pQrStUvWxYz0aBcDeFgHiJk2lMnOpQ` | BLOCK | ✓ |
| 6 | Anthropic API key | `sk-ant-api03-aBcDeFgHiJkLmNoPq...` | BLOCK | ✓ |
| 7 | JWT | `Bearer eyJhbGciOiJIUzI1NiJ9.eyJ...` | BLOCK | ~ 2 redactions, Bearer treated separately |
| 8 | DB connection string | `postgresql://app_user:s3cret_pass@db.prod.internal:5432/orders` | BLOCK, full URI redacted | ✓ |
| 9 | Private key header | `-----BEGIN OPENSSH PRIVATE KEY-----` | BLOCK | ~ |

## WARN tier

| # | Case | Input | Expected | Result |
|---|---|---|---|---|
| 10 | Email | `Customer reached out: jane.smith@example.com` | WARN banner, top-center | ✓ |
| 11 | Phone | `She's at +1-415-555-2891` | WARN banner | ✓ |
| 12 | IP address | `Server: 10.42.18.7` | WARN banner | ✗ |
| 13 | MAC address | `0a:1b:2c:3d:4e:5f` | WARN banner | ✗ |
| 14 | ETH wallet | `0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B` | WARN banner | ✗ |
| 15 | BTC wallet | `bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq` | WARN banner | ✗ |

## Negative cases (should NOT trigger)

| # | Case | Input | Expected | Result |
|---|---|---|---|---|
| 16 | Innocent code review | `Sarah will lead the backend redesign. Stack trace at line 42 of payments.py shows the same Postgres timeout.` | No detections | ✗ 42 redacted |
| 17 | Doc placeholders | `set OPENAI_API_KEY=<your-key-here> in your environment` | Ideally: no detection. Acceptable: only the placeholder (not the var name). | ✗ everything after set is redacted |
| 18 | Lookalike CC, fails Luhn | `Order ID 4532-0000-0000-0000` | No detection (Luhn override drops it) | ✓ |

## Combo / stress test

| # | Case | Input | Expected | Result |
|---|---|---|---|---|
| 19 | Stack trace + creds + customer info | (paste the multi-line combo from README) | One BLOCK modal listing 4-5 items, plus WARN for IP + email | |

---

## Notes on the v0.1 results above

- **Short pastes (#12, #13)** never trigger by design — there's a 20-char min in `content.ts` that filters trivial pastes. Real pastes are always longer.
- **Bare crypto wallets (#14, #15)** without surrounding context: the model over-predicts CREDENTIAL on long hex, so the regex WARN gets dropped on overlap. Embedded in real prose, they trigger correctly. (See realistic cases below.)
- **Over-redaction (#4, #7, #16, #17)** is a known model-quality issue — training data didn't teach tight value boundaries. Inference-time mitigations (edge trim, per-token score floor, connector split) reduce but don't eliminate it. Real fix is a v3 model with tighter span labels.

---

## Realistic test cases (longer, video-demo ready)

These mirror what an actual paste looks like — at least 100 chars, embedded in normal prose, triggering correctly per all the above rules. **Use these for the live demo in the video** and for any reproducible benchmark you want to cite.

### Demo A — `.env` snippet (the realistic "help me debug my deploy" paste)

```
trying to figure out why my prod deploy keeps timing out. here's my docker env:

AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
DATABASE_URL=postgresql://app_user:s3cret_pass@db.prod.internal:5432/orders
NODE_ENV=production

app starts up fine but every s3 upload fails with ETIMEDOUT. anyone hit this?
```
Expected: BLOCK modal with 2 items (AWS secret, DB URI).

### Demo B — Customer support handoff (mixed tier)

```
Hey team, picking up the ticket from Sarah.
Customer is jane.smith@example.com (phone +1-415-555-2891).
Charged her card 4532-0151-1283-0366 twice on Tuesday.
Refund needs SSN 234-56-7890 to verify.
Anyone want to take this over?
```
Expected: BLOCK modal (CC + SSN) plus WARN banner (email + phone).

### Demo C — GitHub PR comment with a leaked PAT

```
@team I accidentally committed my personal access token in commit 4f3a9d2.
The token is ghp_xK9mN3pQrStUvWxYz0aBcDeFgHiJk2lMnOpQ — already rotated on GitHub.
Please force-push to remove from history. Sorry about this.
```
Expected: BLOCK modal with the PAT. Single high-confidence detection.

### Demo D — Innocent code review (negative case)

```
The TypeError on the auth callback is happening because the middleware redirect handler isn't handling the OAuth state parameter when it comes back URL-encoded. I think we need to decode it before parsing. Anyone want to pair on this in the morning?
```
Expected: no detections, no interruption. Verifies the extension stays out of the way.


## What to verify in `Result`

- **Single span per entity** — not fragmented (`[CRED][CRED][CRED]`)
- **Tight boundaries** — variable names not swallowed
- **Final pasted text length** ≈ original minus value plus mask, not duplicated
- **Banner is visible** — top-center, dark, red stripe, doesn't disappear before you read it
