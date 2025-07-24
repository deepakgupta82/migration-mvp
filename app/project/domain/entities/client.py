"""Client domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid

from ....common.exceptions import ValidationError


class ClientType(Enum):
    """Client type enumeration."""
    ENTERPRISE = "enterprise"
    SMB = "smb"
    STARTUP = "startup"
    GOVERNMENT = "government"
    NON_PROFIT = "non_profit"


class ClientStatus(Enum):
    """Client status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROSPECT = "prospect"
    ARCHIVED = "archived"


@dataclass
class Client:
    """
    Client domain entity representing a client organization.
    
    Contains all business logic and rules for client management.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: ClientType = ClientType.ENTERPRISE
    status: ClientStatus = ClientStatus.PROSPECT
    industry: str = ""
    size_employees: Optional[int] = None
    annual_revenue: Optional[float] = None
    primary_contact_name: str = ""
    primary_contact_email: str = ""
    primary_contact_phone: Optional[str] = None
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    postal_code: str = ""
    website: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate entity after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """
        Validate the client entity.
        
        Raises:
            ValidationError: If validation fails
        """
        if not self.name or not self.name.strip():
            raise ValidationError("Client name is required", field_name="name")
        
        if len(self.name) > 200:
            raise ValidationError(
                "Client name must be 200 characters or less",
                field_name="name",
                field_value=self.name
            )
        
        if not self.primary_contact_name or not self.primary_contact_name.strip():
            raise ValidationError(
                "Primary contact name is required",
                field_name="primary_contact_name"
            )
        
        if not self.primary_contact_email or not self.primary_contact_email.strip():
            raise ValidationError(
                "Primary contact email is required",
                field_name="primary_contact_email"
            )
        
        # Basic email validation
        if "@" not in self.primary_contact_email or "." not in self.primary_contact_email:
            raise ValidationError(
                "Invalid email format",
                field_name="primary_contact_email",
                field_value=self.primary_contact_email
            )
        
        if self.size_employees is not None and self.size_employees < 0:
            raise ValidationError(
                "Employee count cannot be negative",
                field_name="size_employees",
                field_value=self.size_employees
            )
        
        if self.annual_revenue is not None and self.annual_revenue < 0:
            raise ValidationError(
                "Annual revenue cannot be negative",
                field_name="annual_revenue",
                field_value=self.annual_revenue
            )
    
    def update_contact_info(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None
    ) -> None:
        """
        Update primary contact information.
        
        Args:
            name: Contact name
            email: Contact email
            phone: Optional contact phone
            
        Raises:
            ValidationError: If contact info is invalid
        """
        if not name or not name.strip():
            raise ValidationError("Contact name is required")
        
        if not email or not email.strip():
            raise ValidationError("Contact email is required")
        
        if "@" not in email or "." not in email:
            raise ValidationError("Invalid email format")
        
        self.primary_contact_name = name.strip()
        self.primary_contact_email = email.strip()
        self.primary_contact_phone = phone
        self.updated_at = datetime.utcnow()
    
    def update_address(
        self,
        address: str,
        city: str,
        state: str,
        country: str,
        postal_code: str
    ) -> None:
        """
        Update client address.
        
        Args:
            address: Street address
            city: City
            state: State/province
            country: Country
            postal_code: Postal/ZIP code
        """
        self.address = address
        self.city = city
        self.state = state
        self.country = country
        self.postal_code = postal_code
        self.updated_at = datetime.utcnow()
    
    def activate(self) -> None:
        """Activate the client."""
        self.status = ClientStatus.ACTIVE
        self.updated_at = datetime.utcnow()
    
    def deactivate(self) -> None:
        """Deactivate the client."""
        self.status = ClientStatus.INACTIVE
        self.updated_at = datetime.utcnow()
    
    def archive(self) -> None:
        """Archive the client."""
        self.status = ClientStatus.ARCHIVED
        self.updated_at = datetime.utcnow()
    
    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the client.
        
        Args:
            tag: Tag to add
        """
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()
    
    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from the client.
        
        Args:
            tag: Tag to remove
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.utcnow()
    
    def update_metadata(self, key: str, value: any) -> None:
        """
        Update client metadata.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if client is active."""
        return self.status == ClientStatus.ACTIVE
