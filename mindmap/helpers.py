import json
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
import matplotlib.font_manager as fm

def add_line_breaks(text, max_length=10):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) <= max_length:
            current_line += word + " "
        else:
            lines.append(current_line.strip())
            current_line = word + " "
    if current_line:
        lines.append(current_line.strip())
    return '\n'.join(lines)


def create_mindmap(json_data, filepath):
    
    try:
        data = json.loads(json_data)

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
        test_name = add_line_breaks(data['test_name'])
        graph.add_node(test_name, shape='circle', color='none', style='filled', fillcolor=test_node_color)

        # Create question nodes and edges from test node
        for content in data['content']:
            question = add_line_breaks(content['question'], max_length=18)
            graph.add_node(question, shape='box', color='none', style='filled', fillcolor=question_node_color)
            graph.add_edge(test_name, question, color=test_question_edge_color, arrowhead='vee')

            # Create ideal answer nodes and edges from question nodes
            ideal_answer = add_line_breaks(content['ideal_answer'], max_length=30)
            graph.add_node(ideal_answer, shape='box', color='none', style='filled', fillcolor=ideal_answer_node_color)
            graph.add_edge(question, ideal_answer, color=question_ideal_answer_edge_color, arrowhead='vee')

            # Create learning nodes and edges from ideal answer nodes
            for learning in content['learnings']:
                learning = add_line_breaks(learning, max_length=20)
                graph.add_node(learning, shape='box', color='none', style='filled', fillcolor=learning_node_color)
                graph.add_edge(ideal_answer, learning, color=ideal_answer_learning_edge_color, arrowhead='vee')

        # Set node labels
        node_labels = {node: node.replace('\n', '\n') for node in graph.nodes()}

        # Set node sizes based on label lengths
        node_sizes = [300 + len(node) * 300 for node in graph.nodes()]

        # Set node and edge colors
        node_colors = [graph.nodes[node]['fillcolor'] for node in graph.nodes()]
        edge_colors = [graph.edges[edge]['color'] for edge in graph.edges()]

        # Set node positions using the 'neato' layout / shell layout
        pos = nx.nx_agraph.graphviz_layout(graph, prog='neato')

        # Increase gap between nodes
        pos = {node: (x, y + 1) for node, (x, y) in pos.items()}

        # Increase figure size based on the number of nodes
        fig_width = max(10, len(graph.nodes) * 1.2)
        fig_height = max(6, len(graph.nodes) * 1.2)

        # Border
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        fig.patch.set_edgecolor('#00c091')  # Set border color
        fig.patch.set_linewidth(50)  # Set border thickness

        # Draw the graph with networkx and graphviz (Graphviz needs to be installed in the system)
        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_shape='o', node_size=node_sizes)
        nx.draw_networkx_edges(graph, pos, edge_color=edge_colors, arrowsize=10)
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_color=default_font_color, font_size=10)

        # Remove axis
        ax.axis('off')

        # Title
        font_path = './static/Poppins-Regular.ttf'
        fm.fontManager.addfont(font_path)
        title = 'Programming Test'
        ax.set_title(title, y=1.0, pad=-60, size=30, weight='bold', fontfamily='Poppins')

        # Logo
        image_path = './static/coachbot-1.png' 
        image = mpimg.imread(image_path)
        imagebox = OffsetImage(image, zoom=0.15)
        imagebox.image.axes = ax
        ab = AnnotationBbox(imagebox, (1, 1), xybox=(-70, -70), xycoords='axes fraction', boxcoords="offset points", frameon=False)
        ax.add_artist(ab)

        # Displaying and saving the graph
        plt.tight_layout()
        fig.savefig('Draft.png', bbox_inches='tight')
        return True
    
    except Exception as e:
        print(f"Error in create_mindmap: {str(e)}")
        return False