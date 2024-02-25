import json
import logging
import tempfile

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.image as mpimg
import matplotlib.patheffects as pe
import networkx as nx
from django.conf import settings
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url_from_doc_id
from tenants.helpers import tenant_from_tenant_id
from tests.db_helpers import get_test_questions_from_test
from tests.models import Test

logger = logging.getLogger(__name__)


def add_line_breaks(text, max_length=10):
    """
    This function breaks a given text into multiple lines with a specified maximum length. 

    The function works by splitting the input text into words and then iteratively adding these words to a line until the maximum length is reached. If a word itself is longer than the maximum length, it is broken into parts with hyphens. The last part does not have a trailing hyphen. 

    Parameters:
    text (str): The input text that needs to be broken into lines. It should be a string.
    max_length (int, optional): The maximum length of a line. It defaults to 10.

    Returns:
    str: The input text broken into lines with a maximum length of 'max_length'. Each line is separated by a newline character.

    Example:
    >>> add_line_breaks("This is a test", 5)
    'This \nis a \ntest'
    >>> add_line_breaks("Supercalifragilisticexpialidocious", 5)
    'Super-\ncalif-\nragil-\nistice-\nxpial-\nidoci-\nous'
    """
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(word) > max_length:
            # Break the word into multiple parts with hyphens
            parts = [word[i:i + max_length] +
                     "-" for i in range(0, len(word), max_length)]
            # Remove trailing hyphen from the last part
            parts[-1] = parts[-1].rstrip("-")
            lines.extend(parts)
        elif len(current_line) + len(word) + 1 <= max_length:  # Consider space after each word
            current_line += word + " "
        else:
            lines.append(current_line.strip())
            current_line = word + " "
    if current_line:
        lines.append(current_line.strip())
    return '\n'.join(lines)


def get_mindmap_url_from_test(test: Test, only_data=False):
    """
    This function retrieves the URL of the mindmap document associated with a given test.

    The function first checks if the 'only_data' flag is set to True. If it is, the function returns the mindmap document ID 
    associated with the test by calling the 'get_mindmap_doc_id_from_test' function. 

    If the 'only_data' flag is set to False, the function retrieves the mindmap document ID associated with the test, and then 
    retrieves the URL of the document by calling the 'get_document_url_from_doc_id' function.

    Args:
        test (Test): The test object for which the mindmap document URL is to be retrieved.
        only_data (bool, optional): A flag that determines whether to return only the mindmap document ID or the URL. 
                                     Defaults to False.

    Returns:
        str: If 'only_data' is True, returns the mindmap document ID associated with the test.
             If 'only_data' is False, returns the URL of the mindmap document associated with the test.

    Example:
        >>> test = Test.objects.get(id=1)
        >>> get_mindmap_url_from_test(test)
        'http://example.com/document/1234'
        >>> get_mindmap_url_from_test(test, only_data=True)
        '1234'
    """
    if only_data:
        return get_mindmap_doc_id_from_test(test, only_data=only_data)

    else:
        mindmap_doc_id = get_mindmap_doc_id_from_test(
            test, only_data=only_data)
        return get_document_url_from_doc_id(mindmap_doc_id)


def get_mindmap_doc_id_from_test(test: Test, only_data=False):
    """
    Retrieves or generates a mindmap document ID for a given test.

    This function checks if a mindmap document ID already exists for the test. If it does and `only_data` is False, it returns the existing ID. If not, it generates a new mindmap document.

    The mindmap document is created as follows:
    - It retrieves the tenant from the test's tenant ID.
    - It retrieves the test's title and questions.
    - It constructs a data dictionary containing the test's name and content (questions, ideal answers, and learnings).
    - If `only_data` is True, it returns this data dictionary.
    - If `only_data` is False, it creates a temporary PDF file and generates a mindmap using the data dictionary.
    - It then creates a new document in the database using the temporary PDF file and updates the test's mindmap document ID.

    Args:
        test (Test): The test object for which the mindmap document ID is to be retrieved or generated.
        only_data (bool, optional): If True, the function will return the data dictionary instead of the mindmap document ID. Defaults to False.

    Returns:
        str or dict: If `only_data` is False, it returns the mindmap document ID (str). If `only_data` is True, it returns the data dictionary (dict).

    Example:
        >>> test = Test.objects.get(uid='test_uid')
        >>> get_mindmap_doc_id_from_test(test)
        'mindmap_doc_id'
        >>> get_mindmap_doc_id_from_test(test, only_data=True)
        {
            "test_name": "Test 1",
            "content": [
                {
                    "question": "What is the capital of France?",
                    "ideal_answer": "The capital of France is Paris.",
                    "learnings": ["France", "Paris", "capital"]
                },
                ...
            ]
        }
    """
    
    if test.mindmap_doc_id and not only_data:
        return test.mindmap_doc_id

    tenant = tenant_from_tenant_id(test.tenant_id)

    test_title = test.title

    test_question_list = get_test_questions_from_test(test)

    content = []

    for question in test_question_list:
        content.append(
            {
                "question": question.question,
                "ideal_answer": question.key_learning_point,
                "learnings": question.key_learning_skills.split(",")
            }
        )

    data = {
        "test_name": test_title,
        "content": content
    }

    if only_data:
        return data

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_mindmap:
        create_mindmap(data, temp_mindmap)

        temp_mindmap.content_type = "application/pdf"
        temp_mindmap.size = 0

        doc = create_document(
            tenant=tenant,
            owner_type=DocOwnerTypeChoice.system,
            owner_id=tenant.uid,
            display_name=f"mindmap_{test.uid}.pdf",
            doc_type=DocTypeChoice.MIND_MAP,
            file=temp_mindmap
        )

    test.mindmap_doc_id = doc.uid
    test.save(update_fields=["mindmap_doc_id", "updated"])

    return test.mindmap_doc_id


def create_mindmap(data, file_ptr):
    """
    Creates a mindmap from the given data and saves it as a PDF file.

    This function takes a dictionary of test data and a file pointer. It uses the NetworkX and Matplotlib libraries to create a directed graph (mindmap) based on the test data. The mindmap is then saved as a PDF file using the provided file pointer.

    The mindmap is created as follows:
    - A central node is created for the test.
    - For each question in the test, an ideal answer node is created and connected to the test node.
    - For each learning point in the ideal answer, a learning node is created and connected to the ideal answer node.
    - The nodes are color-coded based on their type (test, question, ideal answer, learning).
    - The edges are color-coded based on their source node type.
    - The node labels are set to the content of the nodes, with line breaks added for readability.
    - The node sizes are set based on the length of the labels.
    - The node positions are set using the 'neato' layout from Graphviz.
    - The figure size is set based on the number of nodes.
    - A title and a logo are added to the figure.

    Args:
        data (dict): A dictionary containing the test data. The dictionary should have the following structure:
            {
                "test_name": str,  # The name of the test
                "content": [  # A list of dictionaries, each representing a question
                    {
                        "question": str,  # The question text
                        "ideal_answer": str,  # The ideal answer text
                        "learnings": list  # A list of learning points
                    },
                    ...
                ]
            }
        file_ptr (file object): A file pointer to which the mindmap PDF will be saved.

    Returns:
        bool: True if the mindmap was successfully created and saved, False otherwise.

    Raises:
        Exception: If an error occurs during the creation or saving of the mindmap.

    Example:
        data = {
            "test_name": "Test 1",
            "content": [
                {
                    "question": "What is the capital of France?",
                    "ideal_answer": "The capital of France is Paris.",
                    "learnings": ["France", "Paris", "capital"]
                },
                ...
            ]
        }
        with open("mindmap.pdf", "wb") as f:
            create_mindmap(data, f)
    """

    try:
        graph = nx.DiGraph()

        # Set edge colors for font, test name, questions, and ideal answers
        default_font_color = 'black'
        test_question_edge_color = 'red'
        question_ideal_answer_edge_color = 'blue'
        ideal_answer_learning_edge_color = 'green'

        # Set node colors for test name, questions, ideal answers, and learnings
        test_node_color = '#D0EDC6'
        question_node_color = '#B0E0A0'
        ideal_answer_node_color = '#90D27B'
        learning_node_color = '#71C456'

        # Create central test node
        test_name = add_line_breaks(f"0.0 " + data['test_name'], max_length=11)
        graph.add_node(test_name, shape='circle', color='none',
                       style='filled', fillcolor=test_node_color)

        # Create question nodes and edges from test node
        for i, content in enumerate(data['content']):
            # Create question nodes and edges from test node (commented out) if needed in future

            # question = add_line_breaks(content['question'], max_length=17)
            # graph.add_node(question, shape='box', color='none', style='filled', fillcolor=question_node_color)
            # graph.add_edge(test_name, question, color=test_question_edge_color, arrowhead='vee')

            # Create ideal answer nodes and edges from question nodes
            max_length_ideal_answer = 17
            len_ideal_answer = len(content['ideal_answer'])
            if len_ideal_answer < 200:
                max_length_ideal_answer = 17
            elif len_ideal_answer < 300:
                max_length_ideal_answer = 30
            elif len_ideal_answer < 600:
                max_length_ideal_answer = 40
            else:
                max_length_ideal_answer = 45

            ideal_answer = add_line_breaks(
                f"{i}.{i} " + content['ideal_answer'], max_length=max_length_ideal_answer)
            graph.add_node(ideal_answer, shape='box', color='none',
                           style='filled', fillcolor=ideal_answer_node_color)
            graph.add_edge(test_name, ideal_answer,
                           color=question_ideal_answer_edge_color, arrowhead='vee')

            # Create learning nodes and edges from ideal answer nodes
            for j, learning in enumerate(content['learnings']):
                max_length_learning = 17
                len_learrning = len(learning)
                if len_learrning < 30:
                    max_length_learning = 17
                elif len_learrning < 50:
                    max_length_learning = 20
                else:
                    max_length_learning = 25

                learning = add_line_breaks(
                    f"{i}.{j} " + learning, max_length=max_length_learning)
                graph.add_node(learning, shape='box', color='none',
                               style='filled', fillcolor=learning_node_color)
                graph.add_edge(
                    ideal_answer, learning, color=ideal_answer_learning_edge_color, arrowhead='vee')

        # Set node labels
        node_labels = {node: node.replace(
            '\n', '\n')[4:] for node in graph.nodes()}

        # Set node sizes based on label lengths
        node_sizes = []
        for node in graph.nodes():
            label_length = len(node)
            node_type = graph.nodes[node]['fillcolor']

            # Set different multipliers based on node types
            if node_type == test_node_color:
                multiplier = 450
            elif node_type == question_node_color:
                multiplier = 350
            elif node_type == ideal_answer_node_color:
                multiplier = 400
            elif node_type == learning_node_color:
                multiplier = 620
            else:
                multiplier = 300

            node_size = 300 + label_length * multiplier * 1.6
            node_sizes.append(node_size)

        # Set node and edge colors
        node_colors = [graph.nodes[node]['fillcolor']
                       for node in graph.nodes()]
        edge_colors = [graph.edges[edge]['color'] for edge in graph.edges()]

        # Set node positions using the 'neato' layout / shell layout
        pos = nx.nx_agraph.graphviz_layout(graph, prog='neato')

        # Increase gap between nodes
        pos = {node: (x, y + 1) for node, (x, y) in pos.items()}

        # Increase figure size based on the number of nodes
        fig_width = 35.0
        fig_height = 25.0

        num_primary_content = len(data['content'])

        if num_primary_content == 1:
            fig_width = 35.0
            fig_height = 25.0

        elif num_primary_content == 2:
            fig_width = max(45.0, len(graph.nodes) * 1.2)
            fig_height = max(45.0, len(graph.nodes) * 1.2)

        elif num_primary_content == 3:
            fig_width = max(50.0, len(graph.nodes) * 1.2)
            fig_height = max(50.0, len(graph.nodes) * 1.2)
        else:
            fig_width = max(60.0, len(graph.nodes) * 1.2)
            fig_height = max(60.0, len(graph.nodes) * 1.2)

        multiplier_factor = 0.55

        if num_primary_content >= 7:
            multiplier_factor = 0.65

        # Border
        fig, ax = plt.subplots(
            figsize=(fig_width * multiplier_factor, fig_height * multiplier_factor))
        fig.patch.set_edgecolor('#00c091')  # Set border color
        fig.patch.set_linewidth(50)  # Set border thickness

        # Draw the graph with networkx and graphviz (Graphviz needs to be installed in the system)
        nx.draw_networkx_nodes(
            graph, pos, node_color=node_colors, node_shape='o', node_size=node_sizes)
        nx.draw_networkx_edges(
            graph, pos, edge_color=edge_colors, arrowsize=10)
        nx.draw_networkx_labels(
            graph, pos, labels=node_labels, font_color=default_font_color, font_size=17)

        # Remove axis
        ax.axis('off')

        # Title
        font_path = settings.TEMPLATES_DIR.joinpath(
            "mindmap").joinpath("Poppins-Regular.ttf")

        fm.fontManager.addfont(font_path)
        title_text = data['test_name']
        title = ax.set_title(title_text, y=1.0, pad=-60,
                             size=34, weight='bold', fontfamily='Poppins')
        title.set_color('#dc143c')
        title.set_path_effects(
            [pe.withStroke(linewidth=2, foreground='#dc143c')])

        # Logo
        image_path = settings.TEMPLATES_DIR.joinpath(
            "mindmap").joinpath("coachbot-1.png")
        image = mpimg.imread(image_path)
        imagebox = OffsetImage(image, zoom=0.15)
        imagebox.image.axes = ax
        ab = AnnotationBbox(imagebox, (1, 1), xybox=(-70, -70), xycoords='axes fraction', boxcoords="offset points",
                            frameon=False)
        ax.add_artist(ab)

        # Displaying and saving the graph
        plt.tight_layout()
        plt.savefig(file_ptr, format='pdf', bbox_inches='tight')
        return True

    except Exception as e:
        logger.exception(f"Error in create_mindmap: {str(e)}")
        raise e
