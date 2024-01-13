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
from django.conf import settings
import os

from commons.langchain import generate_answer, generate_summary, generate_answer_from_text


class DocumentViewSet(ApiViewSet,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin):
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


    @action(methods=["GET"], detail=False, url_path="ltest")
    def ltest(self, request, *args, **kwargs):
        import PyPDF2
        pdf = open('sample3.pdf', 'rb')
        pdfReader = PyPDF2.PdfReader(pdf)
        text_data = ""
        for i in range(pdfReader.numPages):
            page = pdfReader.getPage(i)
            text = page.extractText()
            text_data += " ".join(text.split("\t"))

        transcript_filepath = f"tmp/pdftext.txt"

        file_path = "sample3.pdf"

        # Get the size of the file in bytes
        file_size = os.path.getsize(file_path)

        # Convert bytes to megabytes
        file_size_in_mb = file_size / (1024 * 1024)

        # Check if the file size is less than 25 MB
        if file_size_in_mb < 25:
            with open(file_path, "rb") as audio_file:
                
                # Writing the content of transcript into a txt file
                with open(transcript_filepath, 'w') as transcript_file:
                    transcript_file.write(text_data)
        # print("#"*100,text_data,'#'*100)
            
        # answer = generate_answer(settings.OPENAI_API_KEY,"https://www.youtube.com/watch?v=_v_fgW2SkkQ","what is langchain")
        # answer = generate_answer(settings.OPENAI_API_KEY,"https://www.youtube.com/watch?v=9JUAPgtkKpI","what is langchain")
        answer = generate_answer_from_text(transcript_filepath,"git push")
        
        return Response({"response": answer})
