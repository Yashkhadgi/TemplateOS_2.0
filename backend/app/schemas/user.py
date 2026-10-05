from pydantic import BaseModel, ConfigDict, EmailStr


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class ProfilePreferences(BaseModel):
    default_document_format: str = "docx"
    email_notifications: bool = False


class UserProfileRead(UserRead):
    department: str | None = None
    organization: str | None = None
    job_title: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    signature_path: str | None = None
    preferences: ProfilePreferences | None = None
