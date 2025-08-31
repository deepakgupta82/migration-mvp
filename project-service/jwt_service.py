#!/usr/bin/env python3
"""
Backward-compatible re-export of the shared JWT service.
This keeps existing imports working: `from jwt_service import jwt_service, ServiceRole, TokenType`.
"""


from nagarro_ascent_common.auth.jwt_service import (
    jwt_service,
    JWTService,
    JWTConfig,
    TokenType,
    ServiceRole,
)

