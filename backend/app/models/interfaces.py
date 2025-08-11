from pydantic import BaseModel, Field
from typing import List, Optional


class InterfaceStatus(BaseModel):
    name: str
    is_up: bool
    is_wireless: bool
    mac_address: Optional[str] = None
    ipv4_addresses: List[str] = Field(default_factory=list)
    role: Optional[str] = None  # "AP", "WAN", or None


class InterfacesResponse(BaseModel):
    interfaces: List[InterfaceStatus]


class AssignRoleRequest(BaseModel):
    interface_name: str
    role: str  # "AP" or "WAN"


