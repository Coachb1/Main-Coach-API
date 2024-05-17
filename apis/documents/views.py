from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apis.documents.serializer import DocumentViewSerializer, DocumentCreateSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from documents.helpers import create_document, get_document_url
from documents.models import Document
from rest_framework import mixins
from commons.langchain import download_and_transcribe_audio
from documents.utils import get_summary
from commons.youtube_utils import get_youtube_transcript, repidapi_stt
from commons.anthropic import anthropic_completion
from commons.cloudinary import upload_image
import logging

logger = logging.getLogger("main")


class DocumentViewSet(ApiViewSet,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin):
    """
    A viewset for handling document operations including listing, retrieving, uploading, and fetching document URLs and summaries.

    This viewset extends `ApiViewSet` and includes mixins for listing and retrieving models. It uses `Document` model objects, filtered to exclude deleted documents, and employs `DocumentViewSerializer` for serialization. Access is restricted to authenticated clients only.

    Methods:
        get_queryset(self):
            Filters the documents to include only those belonging to the tenant associated with the current request.

        upload_document_view(self, request, *args, **kwargs):
            Handles document upload. Validates and deserializes input data using `DocumentCreateSerializer`, creates a new document using the validated data, and returns the newly created document data.

        get_doc_url_view(self, request, *args, **kwargs):
            Retrieves the URL of a document based on its unique identifier.

        get_summary(self, request, *args, **kwargs):
            Fetches or generates a transcript from a YouTube link provided in the request, generates a summary of the transcript, and returns it. The summary length can be specified ('short' or 'long').

        get_prompt_response(self, request, *args, **kwargs):
            Generates a response from the Anthropic API based on a prompt provided in the request and returns it.

    Input:
        - For uploading documents: A multipart form data containing fields specified in `DocumentCreateSerializer`.
        - For fetching document URL: A `uid` parameter in the URL path.
        - For getting a summary: `youtube_link` and optional `choice` ('short' or 'long') in the query parameters.
        - For getting a prompt response: `prompt` in the query parameters.

    Output:
        - For document listing and retrieval: JSON representation of document data.
        - For document upload: JSON representation of the newly created document.
        - For fetching document URL: JSON object containing the document URL.
        - For getting a summary: JSON object containing the summary text.
        - For getting a prompt response: JSON object containing the response text from the Anthropic API.

    Example:
        POST /documents/upload/:
            Request: Multipart form data with document details.
            Response: {"uid": "123", "display_name": "example.pdf", ...}

        GET /documents/{uid}/url/:
            Response: {"url": "http://example.com/doc/123"}

        GET /documents/get-summary/?youtube_link=<YOUTUBE_URL>&choice=short:
            Response: {"summary": "This is a short summary of the video content."}

        GET /documents/get-prompt-response/?prompt=Hello%20world:
            Response: {"response_text": "Hello, how can I assist you today?"}
    """
    queryset = Document.objects.filter(deleted=0)
    serializer_class = DocumentViewSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    @action(methods=["POST"], detail=False, parser_classes=(MultiPartParser, ), url_path="upload")
    def upload_document_view(self, request, *args, **kwargs):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc = create_document(
            tenant=request.tenant,
            **serializer.validated_data
        )

        return Response(self.serializer_class(instance=doc).data, status=status.HTTP_201_CREATED)

    @action(methods=["GET"], detail=True, url_path="url")
    def get_doc_url_view(self, request, *args, **kwargs):
        doc = self.get_object()
        url = get_document_url(doc)
        return Response({"url": url})

    @action(methods=["GET"], detail=False, url_path="get-summary")
    def get_summary(self, request, *args, **kwargs):
        youtube_link = request.query_params.get("youtube_link")
        if youtube_link is None or youtube_link == "":
            return Response({"error": "Youtube link is required"}, status=status.HTTP_400_BAD_REQUEST)

        choice = request.query_params.get("choice")

        for i in range(2):
            transcript = get_youtube_transcript(youtube_link)
            if transcript is not None:
                break

        if transcript is None:
            transcript = repidapi_stt(youtube_link)
            
        if transcript is None:
            transcript = download_and_transcribe_audio(youtube_link)

        summary = get_summary(transcript,choice)
        return Response({"summary": summary})


    @action(methods=["GET"], detail=False, url_path="get-prompt-response")
    def get_prompt_response(self, request, *args, **kwargs):
        prompt = request.query_params.get("prompt")
        response_text = anthropic_completion(prompt, 500)
        return Response({"response_text": response_text})
    
    
    @action(methods=["POST"], detail=False,parser_classes = [MultiPartParser], url_path="upload-image")
    def _upload_image(self, request, *args, **kwargs):
        try:
            image_file = request.data.get('image_file')
            logger.info(f"<<<<<<<<<<<<<<<< image_file : {image_file} >>>>>>>>>>>>>>>>")
            image_url = upload_image(image_file).get('secure_url')
            logger.info(f"<<<<<<<<<<<<<<<<< image_url : {image_url} >>>>>>>>>>>>>>>>>>>>")
            return Response({"image_url": image_url})
        except Exception as e:
            logger.exception("!!!!!!!!!!!!!!!!!!! Error in uploading image !!!!!!!!!!!!!!!!!",e)
            return Response({"Error":e.args}, status=status.HTTP_400_BAD_REQUEST)