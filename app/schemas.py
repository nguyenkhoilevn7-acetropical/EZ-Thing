from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator

Industry = Literal["fnb", "retail", "online", "services"]

class SignUp(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class Login(BaseModel):
    email: EmailStr
    password: str

class OnboardAnswers(BaseModel):
    industry: Industry
    need_tables: bool = True
    need_inventory: bool = True
    need_insights: bool = False
    need_branches: bool = False
    description: str = Field(default="", max_length=500)

class CreateBusiness(OnboardAnswers):
    selected_plan: Literal["BASIC", "PLUS", "PRO"] | None = None
    name: str = Field(min_length=2, max_length=140)

class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    sku: str = Field(min_length=1, max_length=80)
    category: str = Field(default="Khác", max_length=80)
    price_vnd: int = Field(ge=0, le=2_000_000_000)
    cost_vnd: int = Field(default=0, ge=0, le=2_000_000_000)
    stock: int = Field(default=0, ge=0, le=1_000_000_000)
    track_stock: bool = True

class TableCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    seats: int = Field(default=4, ge=1, le=50)
    branch_id: str | None = None

class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)

class OrderLine(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=1000)
    selected_options: list[str] = Field(default_factory=list, max_length=30)

class CreateOrder(BaseModel):
    branch_id: str | None = None
    table_id: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=80)
    lines: list[OrderLine] = Field(min_length=1, max_length=50)
    note: str = Field(default="", max_length=300)
    customer_id: str | None = None

class StockAdjust(BaseModel):
    branch_id: str | None = None
    delta: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=4, max_length=40)
    @field_validator("delta")
    @classmethod
    def non_zero(cls, v):
        if v == 0: raise ValueError("Delta must not be zero")
        return v

class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=300)

class ConfirmPayment(BaseModel):
    confirmed: Literal[True]
