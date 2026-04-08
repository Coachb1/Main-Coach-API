

TEST_ALL_TYPES_SCHEMA = {
    'type': 'object',
    'properties': {
        # --- 1. PRIMITIVES ---
        'page_title': {
            'type': 'string',
            'label': 'Page Title (String)',
            'default': 'Welcome to the Dashboard', # Test Default String
            'help_text': 'This should pre-fill with "Welcome..."'
        },
        'refresh_rate': {
            'type': 'number',
            'label': 'Refresh Rate (Number)',
            'default': 30, # Test Default Number
        },
        'enable_feature': {
            'type': 'boolean',
            'label': 'Enable Feature (Boolean)',
            'default': True, # Test Default Boolean = Checked
        },

        # --- 2. DROPDOWNS ---
        'theme_color': {
            'type': 'select',
            'label': 'Theme (Select)',
            'default': 'dark', # Test Default Selection
            'choices': [
                ('light', 'Light Mode'),
                ('dark', 'Dark Mode'),
                ('auto', 'System Default')
            ]
        },

        # --- 3. MULTI-SELECTS ---
        'user_roles_string': {
            'type': 'multiselect',
            'label': 'Roles (Saves as String)',
            'output_type': 'string',
            # Test Default: Should pre-select Admin and Editor
            'default': 'Admin, Editor', 
            'choices': [
                ('Admin', 'Admin'),
                ('Editor', 'Editor'),
                ('Viewer', 'Viewer'),
                ('Audit', 'Audit')
            ]
        },
        'permissions_list': {
            'type': 'multiselect',
            'label': 'Permissions (Saves as Array)',
            'output_type': 'array',
            # Test Default: Should pre-select Read and Write
            'default': ['Read', 'Write'], 
            'choices': [
                ('Read', 'Read Data'),
                ('Write', 'Write Data'),
                ('Delete', 'Delete Data'),
                ('Execute', 'Execute Scripts')
            ]
        },

        # --- 4. NESTED STRUCTURES ---
        'social_links': {
            'type': 'array',
            'label': 'Social Links (Array of Objects)',
            'items': {
                'type': 'object',
                'properties': {
                    'platform': {
                        'type': 'select', 
                        'label': 'Platform',
                        'choices': [('fb', 'Facebook'), ('li', 'LinkedIn')]
                    },
                    'url': {'type': 'string', 'label': 'URL'}
                }
            }
        },
        'advanced_settings': {
            'type': 'object',
            'label': 'Advanced Settings (Group)',
            'properties': {
                'api_key': {'type': 'string', 'label': 'API Key'},
                'debug_mode': {'type': 'boolean', 'label': 'Debug Mode', 'default': False}
            }
        }
    }
}


# Define the structure of 'action_tab_info'
ACTION_TAB_SCHEMA = {
    'type': 'object',
    'properties': {
        # 1. Simple fields at the top level
        'id': {
            'type': 'string', 
            'label': 'Tab ID',
            'help_text': 'Unique identifier'
        },
        'title': {
            'type': 'string',
            'label': 'Tab Title'
        },
        'description': {
            'type': 'string',
            'label': 'Tab Description'
        },
        'icon': {
            'type': 'string',
            'label': 'Icon (SVG or reference)'
        },
        'type': {
            'type': 'select',
            'label': 'Tab Type',
            'choices': [('normal', 'Normal'), ('system', 'System'), ('both', 'Both')],
            'default': 'normal'
        },
        # 2. The nested array of buttons
        'buttons': {
            'type': 'array',
            'label': 'Action Buttons',
            'items': {
                'type': 'object', # Each item is an object
                'properties': {
                    'label': {'type': 'string', 'label': 'Button Label'},
                    'action': {'type': 'string', 'label': 'Action Name'},
                    'type': {
                        'type': 'select', 
                        'label': 'Type',
                        'choices': [('normal', 'Normal'), ('jobaid', 'Job Aid'),('iframe', 'Only Iframe')]
                    },
                    'heading': {'type': 'string', 'label': 'Button Section Header'},
                    
                    # 3. Deeply nested object (or array)
                    'iframe_table_panel': {
                        'type': 'array',
                        'label': 'Iframe Panels',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'enable': {
                                    'type': 'boolean', 
                                    'label': 'Enable', 
                                    'default': True
                                },
                                'iframe_link': {
                                    'type': 'string', 
                                    'label': 'Image/Iframe URL'
                                },
                                'iframe_title': {
                                    'type': 'string', 
                                    'label': 'Title'
                                },
                                'iframe_subtitle': {
                                    'type': 'string', 
                                    'label': 'Subtitle'
                                }
                            }
                        }
                    }
                }
            }
        },
        'iframe_config': {  
            'type': 'object',
            'label': 'Iframe Settings',
            'properties': {
                'show_iframe_panel': {'type': 'boolean', 'label': 'Show iframe panel', 'default': True},
                'use_default_iframe': {'type': 'boolean', 'label': 'Use default iframe', 'default': True}
            }
        }
    }
}

LIBRARY_SCHEMA = {
    'type': 'object',
    'properties': {
        'heading': {
            'type': 'string',
            'label': 'Page Heading'
        },
        'show_filters': {
            'type': 'multiselect',       # <--- New Type
            'label': 'Filters (visible in UI)',
            'output_type': 'string',     # <--- Saves as "A, B, C"
            'default': 'Industry, Function, Start Up',
            'choices': [
                ('Industry', 'Industry'),
                ('Function', 'Function'),
                ('Business Outcome', 'Business Outcome'),
                ('Unexpected Outcomes', 'Unexpected Outcomes'),
                ('Implementation Complexity', 'Implementation Complexity'),
                ('Emerging Players', 'Emerging Players'),
                ('Start Up', 'Start Up'),
            ]
        },
        'show_lists': {'type': 'boolean', 'label': 'Show Lists', 'default': False},
        'show_search': {'type': 'boolean', 'label': 'Show Search', 'default': True}
    }
}


# admin.py

TRANSFORM_IQ_SCHEMA = {
    # ROOT LEVEL: A Dictionary where Keys are Section Names ("General", "Thermax")
    'type': 'dictionary', 
    'label': 'Analysis Sections',
    'item_label': 'Section Name', # Label for the Key Input
    'item_schema': {
        # THE VALUE: An object containing Overview + Roles
        'type': 'object',
        'properties': {
            'overview': {
                'type': 'textarea', 
                'label': 'Overview',
                'help_text': 'Markdown summary'
            },
            # NESTED DICTIONARY: Keys are Role Names ("Tech Lead"), Values are Strings
            'roles': {
                'type': 'dictionary',
                'label': 'Roles',
                'item_label': 'Role Title', # Label for the Key Input (e.g. "Tech Lead")
                'item_schema': {
                    'type': 'textarea', # The value is just the text content
                    'label': 'Analysis Content'
                }
            }
        }
    }
}


BUTTON_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        # --- Description Config ---
        'description': {
            'type': 'object',
            'label': 'Description Button',
            'properties': {
                'show': {
                    'type': 'boolean',
                    'label': 'Show Button',
                    'default': True
                },
                'label': {
                    'type': 'string',
                    'label': 'Button Label',
                    'default': 'TransformIQ'
                }
            }
        },

        # --- Report Config ---
        'report': {
            'type': 'object',
            'label': 'Report Button',
            'properties': {
                'show': {
                    'type': 'boolean',
                    'label': 'Show Button',
                    'default': True
                },
                'label': {
                    'type': 'string',
                    'label': 'Button Label',
                    'default': 'Report'
                }
            }
        },

        # --- Audio Config ---
        'audio_button': {
            'type': 'object',
            'label': 'Audio Button',
            'properties': {
                'show': {
                    'type': 'boolean',
                    'label': 'Show Button',
                    'default': True
                },
                'label': {
                    'type': 'string',
                    'label': 'Button Label',
                    'default': ''
                }
            }
        },

        # --- Like Button Config ---
        'like_button': {
            'type': 'object',
            'label': 'Like Button',
            'help_text': 'To on/off the like button in our platform',
            'properties': {
                'show': {
                    'type': 'boolean',
                    'label': 'Show Button',
                    'default': True
                },
                'label': {
                    'type': 'string',
                    'label': 'Button Label',
                    'default': ''
                }
            }
        }
    }
}