import dataclasses


@dataclasses.dataclass
class UserCreateContextDto:
    name: str
    role: str
    password: str


@dataclasses.dataclass
class IdentityCreateContextDto:
    identity_type: str
    value: str
