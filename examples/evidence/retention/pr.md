Propose retention for dev/app.

Retention days: 7 → 3. Reviewed module supplies encryption, public-access blocks and lifecycle expiration.

Adapter: fixture; live AI: False. No cloud execution performed.

Assumptions:
- Public demonstration configuration; bucket name requires global uniqueness before live use.

Validation required: Python checks, Terraform fmt/validate and mocked-provider tests. New resources require infrastructure review. Reducing expiration may delete existing objects earlier.

Proposal digest: `9a6911074a7a911f68171c9cbb8da5f7b10f4f30d24f6a1ea75e19c24a4d28dc`. Execute only an explicitly reviewed, merged revision.
