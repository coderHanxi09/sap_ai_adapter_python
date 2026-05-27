from pydantic import BaseModel
from typing import Optional, List


# Address structure
class Address(BaseModel):
    Country: Optional[str] = None
    CityName: Optional[str] = None
    PostalCode: Optional[str] = None
    StreetName: Optional[str] = None
    HouseNumber: Optional[str] = None


# Email structure
class EmailAddress(BaseModel):
    EmailAddress: Optional[str] = None
    IsDefault: Optional[bool] = True


# Phone structure
class PhoneNumber(BaseModel):
    PhoneNumber: Optional[str] = None
    IsDefault: Optional[bool] = True


# Role structure
class BusinessPartnerRole(BaseModel):
    BusinessPartnerRole: Optional[str] = None


# SAP Business Partner (main object)
class BusinessPartner(BaseModel):

    BusinessPartner: Optional[str] = None
    BusinessPartnerFullName: Optional[str] = None
    BusinessPartnerGrouping: Optional[str] = None

    FirstName: Optional[str] = None
    LastName: Optional[str] = None
    OrganizationName: Optional[str] = None

    Language: Optional[str] = None
    SearchTerm1: Optional[str] = None

    to_Address: Optional[List[Address]] = None
    to_EmailAddress: Optional[List[EmailAddress]] = None
    to_PhoneNumber: Optional[List[PhoneNumber]] = None
    to_Role: Optional[List[BusinessPartnerRole]] = None


# Request model (API input)
class MappingRequest(BaseModel):
    source: dict
    target_schema: str = "BusinessPartner"