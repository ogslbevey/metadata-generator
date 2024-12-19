from pydantic import BaseModel, Field
from typing import List, Dict, Optional

# 1. Base Model for Translated Text


class TranslatedText(BaseModel):
    en: str
    fr: str
    translations: Dict[str, 'Translation']  # Reusable class for translations


class Translation(BaseModel):
    message: str
    verified: bool

# 2. Use the TranslatedText for Common Fields


class SummaryTranslated(BaseModel):
    en: str


class LimitationsWithTranslations(TranslatedText):
    pass


class TitleWithTranslations(TranslatedText):
    pass


class DescriptionWithTranslations(TranslatedText):
    pass


class DistributionDescription(TranslatedText):
    pass


class AdditionalDocumentationTitle(TranslatedText):
    pass


class HistorySourceDescription(TranslatedText):
    pass


class HistorySourceTitle(TranslatedText):
    pass


class InstrumentDescription(TranslatedText):
    pass


class InstrumentType(TranslatedText):
    pass

# 3. Models that Reuse the Common Translated Fields


class MapDescription(BaseModel):
    description: DescriptionWithTranslations
    east: Optional[str]
    north: Optional[str]
    polygon: Optional[str]
    south: Optional[str]
    west: Optional[str]


class AssociatedResourceTitle(TranslatedText):
    pass


class AssociatedResource(BaseModel):
    association_type: str
    association_type_iso: str
    authority: str
    code: str
    title: AssociatedResourceTitle


class Contact(BaseModel):
    givenNames: str
    inCitation: bool
    indEmail: str
    indOrcid: str
    indPosition: str
    lastName: str
    orgAdress: str
    orgCity: str
    orgCountry: str
    orgEmail: str
    orgName: str
    orgRor: str
    orgURL: str
    role: List[str]


class Distribution(BaseModel):
    description: DistributionDescription
    name: DistributionDescription
    url: str


class AdditionalDocumentation(BaseModel):
    authority: str
    code: str
    title: AdditionalDocumentationTitle


class HistorySource(BaseModel):
    authority: str
    code: str
    description: HistorySourceDescription
    title: HistorySourceTitle


class HistoryStatement(TranslatedText):
    pass


class History(BaseModel):
    additionalDocumentation: List[AdditionalDocumentation]
    scope: str
    source: List[HistorySource]
    statement: HistoryStatement


class Instrument(BaseModel):
    description: InstrumentDescription
    id: str
    manufacturer: str
    type: InstrumentType
    version: str

# 4. Keywords Model Simplified


class Keywords(BaseModel):
    en: List[str]
    fr: List[str]

# 5. Metadata Schema Models


class MetadataSchemaCIOOS(BaseModel):
    title: str
    resource_type: str
    theme: str
    title_translated: str
    auteurs: List[str]
    summary: str
    summary_translated: SummaryTranslated
    mots_cles: Keywords
    langue: str
    date_debut: str
    date_fin: str
    spatial: str


class FullMetadataSchema(BaseModel):
    abstract: DescriptionWithTranslations
    associated_resources: List[AssociatedResource]
    category: str
    comment: str
    contacts: List[Contact]
    created: str
    datasetIdentifier: str
    dateEnd: str
    datePublished: str
    dateRevised: str
    dateStart: str
    distribution: List[Distribution]
    doiCreationStatus: str
    edition: str
    eov: List[str]
    filename: str
    history: List[History]
    identifier: str
    instruments: List[Instrument]
    keywords: Keywords
    language: str
    lastEditedBy: Dict[str, str]
    license: str
    limitations: LimitationsWithTranslations
    map: MapDescription
    metadataScope: str
    noPlatform: bool
    noTaxa: bool
    noVerticalExtent: bool
    organization: str
    progress: str
    recordID: str
    region: str
    resourceType: List[str]
    sharedWith: Dict[str, bool]
    status: str
    timeFirstPublished: str
    title: TitleWithTranslations
    userID: str
    verticalExtentDirection: str
    verticalExtentEPSG: str
    verticalExtentMax: str
    verticalExtentMin: str
