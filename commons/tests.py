from django.test import SimpleTestCase
from unittest.mock import patch, Mock

from commons.langchain import generate_answer_from_text


class LangchainCommunityImportTest(SimpleTestCase):
    """
    Unit test to ensure generate_answer_from_text works correctly
    with langchain community imports mocked.
    """

    @patch('commons.langchain.OpenAI')
    @patch('commons.langchain.RetrievalQA')
    @patch('commons.langchain.Chroma')
    @patch('commons.langchain.OpenAIEmbeddings')
    @patch('commons.langchain.TextLoader')
    def test_generate_answer_from_text_returns_answer(
        self,
        mock_text_loader,
        mock_embeddings,
        mock_chroma,
        mock_retrieval_qa,
        mock_openai,
    ):
        # -------- Arrange --------

        # Mock document loading
        mock_document = Mock()
        mock_document.page_content = "This is a test document."
        mock_document.metadata = {}

        mock_loader_instance = mock_text_loader.return_value
        mock_loader_instance.load.return_value = [mock_document]

        # Mock vector store & retriever
        mock_vector_store = Mock()
        mock_vector_store.as_retriever.return_value = Mock()
        mock_chroma.from_documents.return_value = mock_vector_store

        # Mock RetrievalQA chain
        mock_qa_instance = mock_retrieval_qa.from_chain_type.return_value
        mock_qa_instance.run.return_value = "This is the generated answer."

        # -------- Act --------
        result = generate_answer_from_text(
            text_path="dummy_path.txt",
            question="some question"
        )

        print(result)

        # -------- Assert --------
        self.assertEqual(result, "This is the generated answer.")

        mock_text_loader.assert_called_once_with(
            "dummy_path.txt",
            encoding="utf8"
        )
        mock_embeddings.assert_called_once()
        mock_chroma.from_documents.assert_called_once()
        mock_vector_store.as_retriever.assert_called_once()
        mock_retrieval_qa.from_chain_type.assert_called_once()
        mock_qa_instance.run.assert_called_once_with("some question")
