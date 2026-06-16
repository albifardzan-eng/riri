from pydantic import BaseModel


class StatusResponse(BaseModel):
    name: str
    version: str
    status: str