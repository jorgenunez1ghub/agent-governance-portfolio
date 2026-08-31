from pydantic import BaseModel, ConfigDict, Field


class CreateActionItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    owner: str = Field(min_length=1, max_length=80)


class LookupPolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=160)


class SendExternalMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    message: str = Field(min_length=1, max_length=1000)
    channel: str = Field(default="email", pattern=r"^(email|slack)$")
