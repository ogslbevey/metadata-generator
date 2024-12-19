from app.schemas.metadata import (
    MetadataSchemaCIOOS, FullMetadataSchema,
    DescriptionWithTranslations, Translation
)


def transform_metadata_to_full(metadata: MetadataSchemaCIOOS) -> FullMetadataSchema:
    return FullMetadataSchema(
        abstract=DescriptionWithTranslations(
            en=metadata.summary_translated.en,
            fr=metadata.summary,
            translations={
                "fr": Translation(
                    message=metadata.summary,
                    verified=False
                )
            }
        ),
        associated_resources=[],
        category="",
        comment="",
        contacts=[],
        created="",
        datasetIdentifier="",
        dateEnd=metadata.date_fin,
        datePublished="",
        dateRevised="",
        dateStart=metadata.date_debut,
        distribution=[],
        doiCreationStatus="",
        edition="",
        eov=[""],
        filename="",
        history=[],
        identifier="",
        instruments=[],
        keywords=metadata.mots_cles,
        language=metadata.langue,
        lastEditedBy={"displayName": "", "email": ""},
        license="",
        limitations=DescriptionWithTranslations(
            en="",
            fr="",
            translations={
                "fr": Translation(
                    message="",
                    verified=True
                )
            }
        ),
        map={
            "description": {
                "en": "",
                "fr": "",
                "translations": {
                    "fr": {
                        "message": "",
                        "verified": False
                    }
                }
            },
            "east": "",
            "north": "",
            "polygon": "",
            "south": "",
            "west": ""
        },
        metadataScope="",
        noPlatform=True,
        noTaxa=True,
        noVerticalExtent=False,
        organization="",
        progress="",
        recordID="",
        region="",
        resourceType=[metadata.resource_type],
        sharedWith={"": True, "": True},
        status="",
        timeFirstPublished="",
        title={
            "en": metadata.title_translated,
            "fr": metadata.title,
            "translations": {
                "fr": {
                    "message": metadata.title,
                    "verified": False
                }
            }
        },
        userID="",
        verticalExtentDirection="",
        verticalExtentEPSG="",
        verticalExtentMax="",
        verticalExtentMin=""
    )
