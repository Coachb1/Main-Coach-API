import uuid

from django.db import transaction
from django.utils import timezone

from commons.s3_get_url import get_url
from commons.s3_upload import s3_upload
from commons.timeit import timeit
from documents.choices import DocActionTypeChoice, DocTypeChoice
from documents.models import Document
from external_apis.coach_whisper_api import coach_whisper_api
from tenants.models import Tenant
from commons.openai_gpt import gpt_wishper_api
from commons.gcp_upload import gcp_upload
from commons.ovh_s3 import upload_to_ovh_s3, get_ovh_url


def create_document(tenant: Tenant,
                    owner_type: str,
                    owner_id: str,
                    display_name: str,
                    doc_type: str,
                    file,
                    actions_pipeline: list = None) -> Document:
    """
    Creates a new document object in the database.

    Args:
        tenant (Tenant): The tenant object for which the document is being created.
        owner_type (str): The type of the document owner (e.g., "user", "organization").
        owner_id (str): The ID of the document owner.
        display_name (str): The display name of the document.
        doc_type (str): The type of the document (e.g., "pdf", "image").
        file (file object): The file to be uploaded.
        actions_pipeline (list, optional): A list of actions to be performed on the document.

    Returns:
        Document: The created document object in the database.
    """
    file.seek(0)

    file_extension = display_name.rsplit(".", 1)[-1]
    date_str = timezone.now().date().isoformat()
    object_id = f"{tenant.uid}/{owner_type}/{owner_id}/{doc_type}/{date_str}/{str(uuid.uuid4())}.{file_extension}"
    bucket_name = tenant.document_storage_bucket_name or "coachbot-documents-v1-ind"
    bucket_name = tenant.document_storage_bucket_name or "botsforslack"
    region_name = "ap-south-1"

    # s3_upload(
    #     file=file,
    #     bucket_name=bucket_name,
    #     s3_file_name=object_id,
    #     region_name=region_name
    # )

    # uploading file to gcp bucket

    gcp_upload(
        bucket_name,
        file,
        object_id
    )
    # upload_to_ovh_s3(file, object_id)

    # creating document objects in db

    with transaction.atomic():
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
            doc_status="saved",
            actions_pipeline=actions_pipeline
        )

        if actions_pipeline:
            transaction.on_commit(
                lambda: execute_actions_pipline(doc)
            )

    return doc


def get_document_url_from_doc_id(doc_uid: str) -> str:
    doc = Document.objects.get(uid=doc_uid)
    return get_document_url(doc)


def get_document_url(doc: Document) -> str:
    return get_url(doc.region_name, doc.bucket_name, doc.object_id)
    # return get_ovh_url(doc.object_id)


@timeit
def execute_actions_pipline(doc: Document):
    """
    Executes a pipeline of actions on a document object.

    Args:
        doc (Document): The document object on which the actions pipeline needs to be executed.

    Returns:
        None

    Summary:
    This function executes a pipeline of actions on a document object. 
    It checks if the document has an actions pipeline defined, and if so, it iterates through each action in the pipeline. 
    For each action, it updates the status of the action in the executed actions pipeline and performs the corresponding action based on the document type. 
    If the document type is an audio or video answer, it calls the `gpt_wishper_api` function to transcribe the audio or video and updates the transcript details of the document. 
    Finally, it saves the updated actions pipeline and document object in the database.
    """
    if not doc.actions_pipeline:
        return

    executed_actions_pipeline = []
    for item in doc.actions_pipeline:
        action = item["action"]
        context = item.get("context")
        status = "init"

        current_action = dict(
            action=action,
            context=context,
            status=status
        )

        executed_actions_pipeline.append(current_action)

        if action == DocActionTypeChoice.transcribe:
            current_action["status"] = "init"

            transcribed_text = ""
            if doc.doc_type == DocTypeChoice.AUDIO_ANSWER:
                # transcribed_text = coach_whisper_api.get_transcribe_from_audio(
                #     get_document_url(doc))
                transcribed_text = gpt_wishper_api(
                    get_document_url(doc))
                current_action["status"] = "success"

            elif doc.doc_type == DocTypeChoice.VIDEO_ANSWER:
                # transcribed_text = coach_whisper_api.get_transcribe_from_video(
                #     get_document_url(doc))
                transcribed_text = gpt_wishper_api(
                    get_document_url(doc))
                current_action["status"] = "success"

            doc.transcript_details = {
                "text": transcribed_text,
                "source": "gpt_wishper_api"
            }

        doc.actions_pipeline = executed_actions_pipeline

        doc.save()
