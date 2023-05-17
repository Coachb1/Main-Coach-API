import uuid

from django.utils import timezone

from commons.s3_get_url import get_url
from commons.s3_upload import s3_upload
from documents.models import Document
from tenants.models import Tenant


def create_document(tenant: Tenant,
                    owner_type: str,
                    owner_id: str,
                    display_name: str,
                    doc_type: str,
                    file) -> Document:
    file_extension = display_name.rsplit(".", 1)[-1]
    date_str = timezone.now().date().isoformat()
    object_id = f"{tenant.uid}/{owner_type}/{owner_id}/{doc_type}/{date_str}/{str(uuid.uuid4())}.{file_extension}"
    bucket_name = tenant.document_storage_bucket_name or "coachbot-documents-v1-ind"
    region_name = "ap-south-1"

    s3_upload(
        file=file,
        bucket_name=bucket_name,
        s3_file_name=object_id,
        region_name=region_name
    )

    doc = Document.objects.create(
        tenant_id=tenant.uid,
        display_name=display_name,
        object_id=object_id,
        bucket_name=bucket_name,
        region_name=region_name,
        doc_type=doc_type,
        content_type=file.content_type,
        size=file.size,
        owner_type=owner_type,
        owner_id=owner_id,
        doc_status="saved"
    )

    return doc


def get_document_url_from_doc_id(doc_uid: str) -> str:
    doc = Document.objects.get(uid=doc_uid)
    return get_document_url(doc)


def get_document_url(doc: Document) -> str:
    return get_url(doc.region_name, doc.bucket_name, doc.object_id)
