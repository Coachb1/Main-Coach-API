DEFAULT_FILTERS_SCHEMA = {
    'type': 'object',
    'label': 'Default Filter Selections',
    'properties': {
        'function': {
            'type': 'string',
            'label': 'Function',
            'default': ''
        },
        'industry': {
            'type': 'string',
            'label': 'Industry',
            'default': 'Banking'
        },
        'business_outcome': {
            'type': 'string',
            'label': 'Business Outcome',
            'default': ''
        },
        'emerging_players': {
            'type': 'string',
            'label': 'Emerging Players',
            'default': ''
        },
        'startup': {
            'type': 'string',
            'label': 'Startup',
            'default': ''
        },
        'unexpected_outcomes': {
            'type': 'string',
            'label': 'Unexpected Outcomes',
            'default': ''
        },
        'implementation_complexity': {
            'type': 'string',
            'label': 'Implementation Complexity',
            'default': ''
        }
    }
}

BOT_CONFIG_SCHEMA = {
    'type': 'object',
    'label': 'Bot Configuration',
    'properties': {
        'coaching': {
            'type': 'object',
            'label': 'Coaching Bot',
            'properties': {
                'show': {
                    'type': 'boolean',
                    'label': 'Enable Coaching',
                    'default': False
                },
                'bot_id': {
                    'type': 'string',
                    'label': 'Bot ID',
                    'default': ''
                }
            }
        },
        'simulation': {
            'type': 'object',
            'label': 'Simulation Bot',
            'properties': {
                'show': {
                    'type': 'boolean',
                    'label': 'Enable Simulation',
                    'default': False
                },
                'bot_id': {
                    'type': 'string',
                    'label': 'Bot ID',
                    'default': ''
                }
            }
        }
    }
}


FEATURE_BUTTON_SCHEMA = {
    'type': 'object',
    'label': 'Feature & Button Visibility',
    'properties': {
        'ai_pulse': {
            'type': 'object',
            'label': 'AI Pulse',
            'properties': {
                'show': {'type': 'boolean', 'label': 'Show', 'default': False},
                'label': {'type': 'string', 'label': 'Label', 'default': 'AI Pulse Report'}
            }
        },
        'metadata_filters': {
            'type': 'object',
            'label': 'Metadata Filters',
            'properties': {
                'show': {'type': 'boolean', 'label': 'Show', 'default': True},
                'label': {'type': 'string', 'label': 'Label', 'default': ''}
            }
        },
        'idea_board_button': {
            'type': 'object',
            'label': 'Idea Board Button',
            'properties': {
                'show': {'type': 'boolean', 'label': 'Show', 'default': True},
                'label': {'type': 'string', 'label': 'Label', 'default': 'Logs & Radar'}
            }
        },
        'leaderboard_button': {
            'type': 'object',
            'label': 'Leaderboard Button',
            'properties': {
                'show': {'type': 'boolean', 'label': 'Show', 'default': False},
                'label': {'type': 'string', 'label': 'Label', 'default': 'LeaderBoard'}
            }
        },
        'transform_iq_feature': {
            'type': 'object',
            'label': 'Transform IQ Feature',
            'properties': {
                'show': {'type': 'boolean', 'label': 'Show', 'default': True},
                'label': {'type': 'string', 'label': 'Label', 'default': 'Transform IQ'}
            }
        }
    }
}

FEATURE_BOX_SCHEMA = {
    'type': 'array',
    'label': 'Feature List',
    'items': {
        'type': 'string',
        'label': 'Feature Name'
    }
}

# Helper to avoid repetition for Heading/Subheading structure
_TEXT_LINK_STRUCTURE = {
    'type': 'object',
    'properties': {
        'text': {
            'type': 'string',
            'label': 'Display Text',
            'widget': 'string' # Optional: if text is long
        },
        'link': {
            'type': 'string',
            'label': 'URL Link',
            'default': ''
        },
        'link_text': {
            'type': 'string',
            'label': 'Link Anchor Text',
            'default': ''
        },
        'append_text': {
            'type': 'string',
            'label': 'Append Text (Optional)',
            'default': ''
        }
    }
}

ANNOUNCEMENT_SCHEMA = {
    'type': 'object',
    'label': 'Announcement Section',
    'properties': {
        'enabled': {
            'type': 'boolean',
            'label': 'Enable Announcement',
            'default': False
        },
        'heading': {
            **_TEXT_LINK_STRUCTURE, 
            'label': 'Main Heading'
        },
        'subheading': {
            **_TEXT_LINK_STRUCTURE, 
            'label': 'Sub Heading'
        }
    }
}

COMPANY_INFO_SCHEMA = {
    'type': 'object',
    'label': 'Company Information',
    'properties': {
        'company_name': {
            'type': 'string',
            'label': 'Company Name',
            'default': ''
        },
        'company_url': {
            'type': 'string',
            'label': 'Company URL',
            'default': ''
        }
    }
}        