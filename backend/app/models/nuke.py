from pydantic import BaseModel


class NukeRequest(BaseModel):
    confirmation: str
    full_device: bool = False


class NukeResponse(BaseModel):
    started: bool
    message: str


