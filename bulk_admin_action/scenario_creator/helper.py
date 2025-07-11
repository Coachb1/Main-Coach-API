import os
import io
import pandas as pd
import zipfile
import shutil
from datetime import datetime
from string import Template
from docx import Document

from coachbots_app.utils.llm import anthropic_completion, gemini_completion

