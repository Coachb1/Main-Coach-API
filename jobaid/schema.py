LABELS_SCHEMA = {
    'type': 'object',
    'label': 'Custom Labels',
    'properties': {
        'innovation_score': {
            'type': 'object',
            'label': 'Innovation Score',
            'properties': {
                'label': {
                    'type': 'string',
                    'label': 'Label',
                    'help_text': 'The display name for the label (e.g. "Align Priority")'
                },
                'info': {
                    'type': 'string',
                    'label': 'Info',
                    'help_text': 'Additional information or tooltip content for this label'
                }
            }
        }
    }

}
