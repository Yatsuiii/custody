# Gate 2 cost model

This is a planning estimate only. No API key was read and no model/API call
occurred.

## Frozen route and prices

The dataset adaptation uses `gpt-4o-mini-2024-07-18` through the OpenAI text
API for both target and judge. The exact snapshot and route are frozen before
execution; the paper's GPT-OSS-120B route is not publicly specified and is not
treated as reproduced. The current model page lists `$0.15 / 1M` input tokens
and `$0.60 / 1M` output tokens: <https://developers.openai.com/api/docs/models/gpt-4o-mini>.
No tool calls, search calls, or hosted files are used.

## Call-count formula

The full pinned adaptation uses 3,239 adversarial ASR-eligible rows and 2,999
benign rows. Five seeds and four baselines are frozen. Write output is shared
across baselines for each case/seed; retrieval and judging remain
baseline-specific.

| Call family | Formula | Worst-case calls |
|---|---:|---:|
| shared target write | (3,239 + 2,999) × 5 | 31,190 |
| target retrieval | (2,997 adversarial with query + 2,999 benign) × 5 × 4 | 119,920 |
| ASR judge | 3,239 × 5 × 4 | 64,780 |
| RSR judge | 2,997 × 5 × 4 (all retrievals ASR-positive) | 59,940 |
| **total upper bound** |  | **275,830** |

Rows without `retrieval_query` are not imputed into RSR. A provider failure is
a blocked trial and is not retried, so this table is not a license to increase
the call count.

## Token estimate

The estimate uses the pinned corpus character totals, a documented 4-character
per-token planning conversion, fixed prompt overhead, and a 128-token output
cap:

| Family | Estimated input tokens | Estimated output tokens |
|---|---:|---:|
| shared write | 25.95M | 3.99M |
| retrieval | 40.01M | 15.35M |
| ASR judge | 21.06M | 1.04M |
| RSR judge | 23.38M | 0.96M |
| **total** | **110.39M** | **21.34M** |

Estimated API cost:

```text
110.39 × $0.15 + 21.34 × $0.60 = $29.36
```

The frozen planning ceiling is **$35.00**. The full pinned adaptation fits
that ceiling on token estimate, so no smoke slice is authorized merely to
reduce cost. A future execution still requires a separate user authorization,
an API key, and a check that the provider's current pricing/snapshot remains
the frozen route. There is no execution authorization in this commit.

## Resource and failure boundary

The estimate excludes local orchestration CPU/storage and assumes ordinary
text tokenization. It does not assume cached-input discounts. No retries,
fallback model, prompt shortening, seed reduction, or post-result resampling
is permitted. If the ceiling or model route cannot be honored, classify the
run `BLOCKED` before treatment.
