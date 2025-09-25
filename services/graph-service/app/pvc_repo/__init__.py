"""PVC repository package (lazy-loaded).

Provides Postgres-backed persistence for Type Registry and Proposals.

Note: This package is imported lazily only when PVC_STORE=postgres to avoid
introducing new runtime dependencies for default Redis-backed operation.
"""
