from pydantic import BaseModel
from typing import Optional, List


# ---------------------------------
# Email
# ---------------------------------
class EmailAddressModel(BaseModel):
    EmailAddress: Optional[str] = None
    IsDefaultEmailAddress: Optional[bool] = True


# ---------------------------------
# Phone
# ---------------------------------
class PhoneNumberModel(BaseModel):
    PhoneNumber: Optional[str] = None
    IsDefaultPhoneNumber: Optional[bool] = True


# ---------------------------------
# Address
# ---------------------------------
class BusinessPartnerAddressModel(BaseModel):
    Country: Optional[str] = None
    CityName: Optional[str] = None
    PostalCode: Optional[str] = None
    StreetName: Optional[str] = None
    HouseNumber: Optional[str] = None

    to_EmailAddress: Optional[
        List[EmailAddressModel]
    ] = None

    to_PhoneNumber: Optional[
        List[PhoneNumberModel]
    ] = None


# ---------------------------------
# Role
# ---------------------------------
class BusinessPartnerRoleModel(BaseModel):
    BusinessPartnerRole: Optional[str] = None


# ---------------------------------
# Tax
# ---------------------------------
class BusinessPartnerTaxModel(BaseModel):
    BPTaxType: Optional[str] = None
    BPTaxNumber: Optional[str] = None


# ---------------------------------
# External Reference
# ---------------------------------
class ExternalReferenceModel(BaseModel):
    SourceSystem: Optional[str] = None
    SourceCustomerID: Optional[str] = None


# ---------------------------------
# Contact Person
# ---------------------------------
class ContactPersonModel(BaseModel):
    FirstName: Optional[str] = None
    LastName: Optional[str] = None
    EmailAddress: Optional[str] = None
    PhoneNumber: Optional[str] = None


# ---------------------------------
# Main Business Partner Data
# ---------------------------------
class BusinessPartnerDataModel(BaseModel):

    # Basic Information
    BusinessPartnerCategory: Optional[str] = None
    OrganizationBPName1: Optional[str] = None

    SearchTerm1: Optional[str] = None
    Language: Optional[str] = None

    # Additional Fields
    BusinessPartnerGrouping: Optional[str] = None
    CorrespondenceLanguage: Optional[str] = None
    Industry: Optional[str] = None
    WebsiteURL: Optional[str] = None

    # Address
    to_BusinessPartnerAddress: Optional[
        List[BusinessPartnerAddressModel]
    ] = None

    # Roles
    to_BusinessPartnerRole: Optional[
        List[BusinessPartnerRoleModel]
    ] = None

    # Tax
    to_BusinessPartnerTax: Optional[
        List[BusinessPartnerTaxModel]
    ] = None

    # External Reference
    ExternalReference: Optional[
        ExternalReferenceModel
    ] = None

    # Contact Person
    ContactPerson: Optional[
        ContactPersonModel
    ] = None


# ---------------------------------
# Final Request Wrapper
# ---------------------------------
class BusinessPartnerRequestModel(BaseModel):
    BusinessPartner: BusinessPartnerDataModel


# ---------------------------------
# Generic Mapping Request
# ---------------------------------
class MappingRequest(BaseModel):
    source: dict
    target_schema: str = "BusinessPartner"