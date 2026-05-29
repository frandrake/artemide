"""Service-layer errors. Transports translate these to status codes."""
from __future__ import annotations


class ServiceError(Exception):
    """Base for all service-layer errors."""


class NotFoundError(ServiceError):
    """Requested entity does not exist."""


class ConflictError(ServiceError):
    """Mutation would violate a business invariant (e.g. duplicate contact)."""


class InvalidStateTransitionError(ServiceError):
    """A relationship_state change does not follow the allowed graph."""


class ValidationError(ServiceError):
    """Caller-supplied data failed validation."""


class ForbiddenRoleError(ServiceError):
    """The authenticated role lacks scope for this operation (Rule 18)."""
