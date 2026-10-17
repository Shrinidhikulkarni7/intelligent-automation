Propose create for dev/new-app.

Retention days: None → 7. Reviewed module supplies encryption, public-access blocks and lifecycle expiration.

Adapter: codex; live AI: True. No cloud execution performed.

Assumptions:
- The private_bucket module implements encryption, public access blocking, and lifecycle retention.

Validation required: Python checks, Terraform fmt/validate and mocked-provider tests. New resources require infrastructure review. Reducing expiration may delete existing objects earlier.

Proposal digest: `cfe06b259388241ee1777f77ad90f26072555b28b3f6a34afe1a870861b78cf0`. Execute only an explicitly reviewed, merged revision.
