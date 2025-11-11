# tests_csv_export.py
import io
import csv
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Optional
from datetime import datetime

from django.utils import timezone
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from identities.models import Identity
from tests.choices import ScenarioCaseChoices, TestTypeChoices
from tests.models import Test, TestQuestion


# ----------------------------
# Request params container
# ----------------------------
@dataclass
class CSVRequestParams:
    tenant_id: Optional[str]
    test_type: Optional[str]
    scenario_case: Optional[str]
    title: Optional[str]
    test_codes: List[str]
    candidate_type: Optional[str]
    client_name: Optional[str]
    creator_email: Optional[str]
    download: bool
    creator_user_id: Optional[int] = None

    @classmethod
    def from_request(cls, request) -> "CSVRequestParams":
        tenant_id = getattr(request.tenant, "uid", None)
        raw_codes = request.query_params.get("test_codes")
        test_codes = [c.strip() for c in raw_codes.split(",")] if raw_codes else []

        creator_email = request.query_params.get("creator_email")
        creator_user_id = None
        if creator_email:
            identity = Identity.objects.filter(value=creator_email).last()
            creator_user_id = identity.user_id if identity else None

        return cls(
            tenant_id=tenant_id,
            test_type=request.query_params.get("test_type"),
            scenario_case=request.query_params.get("scenario_case"),
            title=request.query_params.get("title"),
            test_codes=test_codes,
            candidate_type=request.query_params.get("candidate_type"),
            client_name=request.query_params.get("client_name"),
            creator_email=creator_email,
            download=request.query_params.get("download", "false").lower() == "true",
            creator_user_id=creator_user_id,
        )

# ----------------------------
# Filtering service
# ----------------------------
class TestFilterService:
    def filter_tests(self, params: CSVRequestParams) -> Iterable[Test]:
        qs = Test.objects.filter(deleted=0)

        # If explicit test codes requested -> use only that set
        if params.test_codes:
            return qs.filter(test_code__in=params.test_codes)

        filters = {}
        if params.tenant_id:
            filters["tenant_id"] = params.tenant_id
        if params.test_type:
            filters["test_type"] = params.test_type
        if params.scenario_case:
            filters["scenario_case"] = params.scenario_case
        if params.title:
            filters["title"] = params.title
        if params.candidate_type:
            filters["candidate_type"] = params.candidate_type
        if params.client_name:
            filters["client_name"] = params.client_name
        if params.creator_user_id:
            filters["creator_user_id"] = params.creator_user_id

        if filters:
            qs = qs.filter(**filters)
        return qs

# ----------------------------
# Base CSV Mapper (strategy)
# ----------------------------
class BaseCSVMapper(ABC):
    """
    Each subclass must provide:
      - required_columns: mapping csv-header -> model_attr_or_special_key
      - optional_columns: mapping csv-header -> model_attr_or_special_key
      - dynamic_columns: mapping csv-header -> model_attr_or_special_key (used per-question)
    """

    required_columns: Dict[str, str] = {}
    optional_columns: Dict[str, str] = {}
    dynamic_columns: Dict[str, str] = {}

    def build_row(self, test: Test) -> Tuple[Dict[str, str], List[str]]:
        """
        Build single CSV row for 'test' and return (row_dict, ordered_fieldnames)
        """
        row: Dict[str, str] = {}
        fieldnames: List[str] = []

        # required
        for header, attr in self.required_columns.items():
            row[header] = self._resolve_field(test, attr)
            fieldnames.append(header)

        # dynamic & question handling
        dynamic_fieldnames, dynamic_data = self._build_dynamic_data(test)
        for fname in dynamic_fieldnames:
            fieldnames.append(fname)
            row[fname] = dynamic_data.get(fname, "")

        # optional columns
        for header, attr in self.optional_columns.items():
            # append optional column headers after dynamic/question columns to resemble original order
            fieldnames.append(header)
            row[header] = self._resolve_field(test, attr)

        return row, fieldnames

    @abstractmethod
    def csv_name(self, test: Test, max_questions: int) -> str:
        """Return a file name for the csv for this test type"""
        raise NotImplementedError

    # ---------- Helper utilities ----------
    def _resolve_field(self, test: Test, attr: str) -> str:
        """
        Resolve special attribute names (certificate_details, psychometric_report_config, etc.)
        otherwise use getattr.
        Always return string for CSV safety.
        """
        try:
            if attr == "certificate_title":
                if getattr(test, "certificate_details", None):
                    return str(test.certificate_details.get("title", ""))
                return ""
            if attr == "certificate_description":
                if getattr(test, "certificate_details", None):
                    return str(test.certificate_details.get("description", ""))
                return ""
            if attr == "psychometric_report_config":
                if getattr(test, "psychometric_report_config", None):
                    return str(test.psychometric_report_config.name)
                return ""
            if attr == "psychometric":
                if getattr(test, "psychometric", None):
                    return str(test.psychometric.name)
                return ""
            if attr == "is_dynamic_discussion_thread":
                return str(test.test_type == TestTypeChoices.dynamic_discussion_thread)
            if attr == "title_ui":
                if getattr(test, "ui_information", None):
                    return str(test.ui_information.get("title", ""))
                return ""
            if attr == "description_ui":
                if getattr(test, "ui_information", None):
                    return str(test.ui_information.get("description", ""))
                return ""
            if attr == "background":
                orch = getattr(test, "orchestrated_conversation_details", None)
                if orch and isinstance(orch, dict):
                    return str(orch.get("background", ""))
                return ""
            # default: getattr
            return str(getattr(test, attr, ""))
        except Exception:
            # Defensive fallback; individual mappers/tests shouldn't crash CSV export
            return ""

    def _build_dynamic_data(self, test: Test) -> Tuple[List[str], Dict[str, str]]:
        """
        Returns (ordered_fieldnames_for_dynamic_content, mapping_fieldname_to_value)
        Handles question lists, person messages for orchestrated conversation, options, ranges etc.
        """
        fieldnames: List[str] = []
        data: Dict[str, str] = {}

        # Orchestrated conversation handling if present
        orch = getattr(test, "orchestrated_conversation_details", None)
        # For tests with "initial_messages" (dynamic)
        if isinstance(orch, dict):
            initial_msgs = orch.get("initial_messages", []) or []
            for idx, msg in enumerate(initial_msgs):
                key = f"Person {idx}"
                fieldnames.append(key)
                data[key] = str(msg)

            if orch.get("start_with_user", None) is not None:
                fieldnames.append("start with user")
                data["start with user"] = str(orch.get("start_with_user"))

            if orch.get("responder", None) is not None:
                fieldnames.append("Asker UI")
                data["Asker UI"] = str(orch.get("responder"))

        # Questions handling (by test questions)
        qs = TestQuestion.objects.filter(test_id=test.uid).order_by("question_number")
        if not qs.exists():
            return fieldnames, data
        
        

        # If the test mapper expects dynamic columns per question, create them.
        for q in qs:
            qn = str(getattr(q, "question_number", 1)-1)
            data[qn] = q.question
            fieldnames.append(qn)

            q_num_str = str(getattr(q, "question_number", 1))
            # For each dynamic_columns mapping, possibly produce multiple columns per question
            for dyn_header, dyn_model in self.dynamic_columns.items():
                # Special handling for option-type dynamic (MCQ options dictionary)
                if dyn_model == "option" and getattr(q, "mcq_options", None):
                    # expected dict like {"A": {"opt": "text"}, "B": {...}}
                    for opt_key, opt_val in q.mcq_options.items():
                        fname = f"{dyn_header} {q_num_str}{opt_key}"
                        fieldnames.append(fname)
                        data[fname] = str(opt_val.get("opt", "")) if isinstance(opt_val, dict) else str(opt_val)
                # Score range feedback is usually on test level (score_config)
                elif dyn_model == "range_feedback":
                    # test.score_config expected dict of range->feedback
                    if getattr(test, "score_config", None):
                        for idx, (range_label, feedback) in enumerate(test.score_config.items(), start=1):
                            fieldnames.append(f"Range {idx}")
                            data[f"Range {idx}"] = str(range_label)
                            fieldnames.append(f"Feedback {idx}")
                            # feedback might be dict with 'feedback' key
                            fb_val = feedback.get("feedback") if isinstance(feedback, dict) else feedback
                            data[f"Feedback {idx}"] = str(fb_val)
                else:
                    fname = f"{dyn_header} {q_num_str}"
                    fieldnames.append(fname)
                    
        return fieldnames, data

# ----------------------------
# Concrete mapper implementations
# ----------------------------
class PsychometricCSVMapper(BaseCSVMapper):
    required_columns = {
        "Category": "category",
        "Title": "title",
        "Test description": "description",
        "Skill Domain": "skill_domain",
        "Candidate Type": "candidate_type",
        "Email Address List": "email_address_list",
        "Interaction Mode": "interaction_mode",
        "Test Type": "test_type",
        "Scenario Case": "scenario_case",
        "Area/Domain": "area_domain",
        "Certificate Title": "certificate_title",
        "Send only to email": "send_only_to_email",
        "Email Candidate": "email_candidate",
        "Report Description": "report_description",
        "Psychometric Set": "psychometric",
        "Psychometric Report Config": "psychometric_report_config",
    }
    optional_columns = {}  # left empty as original
    dynamic_columns = {
        "Question": "question",
        "Custom Prompt": "gpt_prompt_override",
    }

    def csv_name(self, test: Test, max_questions: int) -> str:
        return f"psychometric-{max_questions}-export-{timezone.now().isoformat()}.csv"


class StaticCSVMapper(BaseCSVMapper):
    required_columns = {
        "Title": "title",
        "Test description": "description",
        "Skill Domain": "skill_domain",
        "Candidate Type": "candidate_type",
        "Email Address List": "email_address_list",
        "Interaction Mode": "interaction_mode",
        "Test Type": "test_type",
        "Scenario Case": "scenario_case",
        "Certificate Title": "certificate_title",
        "Personality Model": "personality_model",
    }
    optional_columns = {
        "Explanation Visible": "explanation_visible",
        "Score Visible": "score_visible",
        "Time Limit": "time_limit",
        "Scenario Prompt Type": "creator_prompt_type",
        "Description Media": "description_media",
        "Instruction Media": "instruction_media_link",
        "Area/Domain": "area_domain",
        "Client Name": "client_name",
        "Personality Model": "personality_model",
        "Script Video Link": "script_video_link",
        "Video Script": "video_script",
        "Feedback Video Link": "feedback_script_video_link",
        "Feedback Video Script": "feedback_video_script_template",
        "Test Snippet Link": "snippet_url",
        "is learner path": "is_learner_path",
        "Ted talks and HBR Case": "tedtalk_and_hbr_case",
        "is checkin type": "is_checkin_type",
        "is_email_type": "is_email_type",
        "Send only to email": "send_only_to_email",
        "Email Candidate": "email_candidate",
        "Certificate Description": "certificate_description",
        "source": "source",
        "image_url": "image_url",
        "rating": "rating",
        "is_game_type": "is_game_type",
        "Competency Skill": "competency_group",
        "Goals": "goals",
        "Course": "course",
        "Industry": "industry",
        "Experience Level": "exp_level",
        "Title UI": "title_ui",
        "Description UI": "description_ui",
        "Is Transcript Only": "is_transcript_only",
        "Current news": "web_page_url",
        "User ID": "creator_user_id",
        "Calculate Culture": "calculate_culture",
        "Visual Tags": "visual_tags",
    }
    dynamic_columns = {
        "Question": "question",
        "Custom Prompt": "gpt_prompt_override",
        "KLP": "key_learning_point",
        "KLS": "key_learning_skills",
        "Que Media": "media_link",
    }

    def csv_name(self, test: Test, max_questions: int) -> str:
        return f"static-{max_questions}-export-{timezone.now().isoformat()}.csv"


class DynamicCSVMapper(BaseCSVMapper):
    required_columns = {
        "Title": "title",
        "Context": "description",
        "Skill Domain": "skill_domain",
        "Candidate Type": "candidate_type",
        "Email Address List": "email_address_list",
        "Scenario Case": "scenario_case",
        "Certificate Title": "certificate_title",
        "Skills_list": "skills_to_evaluate",
        "is_dynamic_thread": "is_dynamic_discussion_thread",
    }
    optional_columns = {
        "Scenario Prompt Type": "creator_prompt_type",
        "Description Media": "description_media",
        "Instruction Media": "instruction_media_link",
        "Area/Domain": "area_domain",
        "Client Name": "client_name",
        "Script Video Link": "script_video_link",
        "Video Script": "video_script",
        "Feedback Video Link": "feedback_script_video_link",
        "Feedback Video Script": "feedback_video_script_template",
        "Test Snippet Link": "snippet_url",
        "is learner path": "is_learner_path",
        "Ted talks and HBR Case": "tedtalk_and_hbr_case",
        "is checkin type": "is_checkin_type",
        "Send only to email": "send_only_to_email",
        "Email Candidate": "email_candidate",
        "Certificate Description": "certificate_description",
        "Competency Skill": "competency_group",
        "Goals": "goals",
        "Course": "course",
        "Industry": "industry",
        "Experience Level": "exp_level",
        "Background": "background",
        "Title UI": "title_ui",
        "Description UI": "description_ui",
        "Is Transcript Only": "is_transcript_only",
        "Current news": "web_page_url",
        "User ID": "creator_user_id",
        "Visual Tags": "visual_tags",
        "Time Limit": "time_limit",
    }
    dynamic_columns = {
        # "Person": "orch.initialmessage",
    }

    def csv_name(self, test: Test, max_questions: int) -> str:
        return f"dynamic-{max_questions}-export-{timezone.now().isoformat()}.csv"


class GameDynamicCSVMapper(BaseCSVMapper):
    required_columns = {
        "Title": "title",
        "Context": "description",
        "Test Custom Prompt": "gpt_prompt_override",
        "is_dynamic_thread": "is_dynamic_discussion_thread",
        "Email Address List": "email_address_list",
        "Scenario Case": "scenario_case",
        "Is Single Select": "is_single_select",
    }
    optional_columns = {}
    dynamic_columns = {}

    def csv_name(self, test: Test, max_questions: int) -> str:
        return f"game_dynamic-{max_questions}-export-{timezone.now().isoformat()}.csv"


class StaticGameCSVMapper(BaseCSVMapper):
    required_columns = {
        "Title": "title",
        "Test description": "description",
        "Skill Domain": "skill_domain",
        "Candidate Type": "candidate_type",
        "Email Address List": "email_address_list",
        "Interaction Mode": "interaction_mode",
        "Test Type": "test_type",
        "Scenario Case": "scenario_case",
        "Certificate Title": "certificate_title",
        "Score Visible": "score_visible",
        "Explanation Visible": "explanation_visible",
        "Is Single Select": "is_single_select",
    }
    optional_columns = {}
    dynamic_columns = {
        "Range and feedback": "range_feedback",
        "Question": "question",
        "Q Explanation": "que_explanation",
        "Correct answer": "mcq_answer",
        "Que Media": "media_link",
        "Option": "option",
    }

    def csv_name(self, test: Test, max_questions: int) -> str:
        return f"static_game-{max_questions}-export-{timezone.now().isoformat()}.csv"

# ----------------------------
# Mapper resolver (factory)
# ----------------------------
class TestTypeConfig:
    _MAPPERS = {
        "psychometric": PsychometricCSVMapper(),
        "static": StaticCSVMapper(),
        "dynamic": DynamicCSVMapper(),
        "game_dynamic": GameDynamicCSVMapper(),
        "static_game": StaticGameCSVMapper(),
    }

    @classmethod
    def get_mapper_for_test(cls, test: Test) -> BaseCSVMapper:
        # replicate your selection logic
        if test.is_game_type and test.test_type in [
            TestTypeChoices.dynamic_discussion, 
            TestTypeChoices.dynamic_discussion_thread,
        ]:
            return cls._MAPPERS["game_dynamic"]

        if test.test_type in [
            TestTypeChoices.dynamic_discussion,
            TestTypeChoices.dynamic_discussion_thread,
            TestTypeChoices.orchestrated_conversation,
        ]:
            return cls._MAPPERS["dynamic"]

        if test.is_game_type and test.test_type == TestTypeChoices.test:
            return cls._MAPPERS["static_game"]

        if test.scenario_case == ScenarioCaseChoices.psychometric:
            return cls._MAPPERS["psychometric"]

        return cls._MAPPERS["static"]

# ----------------------------
# CSV builder service
# ----------------------------
class CSVExportService:
    def generate_csv_mapping(self, tests: Iterable[Test]) -> Dict[str, List[Dict[str, str]]]:
        """
        Returns mapping: {csv_filename: [row_dicts...]}
        """
        mapping: Dict[str, List[Dict[str, str]]] = {}
        # compute max questions across tests (used for file naming in your original code)
        max_questions_overall = 0

        # We may need per-test max questions to pick a name; compute on the fly
        for test in tests:
            qs = TestQuestion.objects.filter(test_id=test.uid)
            if qs.exists():
                highest = qs.order_by("-question_number").first().question_number
                if highest > max_questions_overall:
                    max_questions_overall = highest

        # build rows
        for test in tests:
            mapper = TestTypeConfig.get_mapper_for_test(test)
            # Let mapper take care of building row
            row, fieldnames = mapper.build_row(test)
            csv_name = mapper.csv_name(test, max_questions_overall)
            # include fieldnames as first row (header) - but we will use DictWriter to produce CSV when needed
            if csv_name not in mapping:
                mapping[csv_name] = []
            mapping[csv_name].append(row)

        return mapping

    def mapping_to_single_csv_bytes(self, filename: str, rows: List[Dict[str, str]]) -> bytes:
        """
        Convert rows (list of dicts) to CSV bytes.
        Fieldnames are taken from union of keys in rows preserving insertion order of first row.
        """
        if not rows:
            return b""

        # Determine final fieldnames: union of all keys preserving order from first row then others
        fieldnames = []
        seen = set()
        for r in rows:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")



def get_test_export_list(tests):
    # -------------------------
    # 🧱 Required Columns
    # -------------------------
    required_columns = {
        "psychometric": {
            "Category": "category",
            "Title": "title",
            "Test description": "description",
            "Skill Domain": "skill_domain",
            "Candidate Type": "candidate_type",
            "Email Address List": "email_address_list",
            "Interaction Mode": "interaction_mode",
            "Test Type": "test_type",
            "Scenario Case": "scenario_case",
            "Area/Domain": "area_domain",
            "Certificate Title": "certificate_title",
            "Send only to email": "send_only_to_email",
            "Email Candidate": "email_candidate",
            "Report Description": "report_description",
            "Psychometric Set": "psychometric",
            "Psychometric Report Config": "psychometric_report_config"
        },

        "static": {
            "Title": "title",
            "Test description": "description",
            "Skill Domain": "skill_domain",
            "Candidate Type": "candidate_type",
            "Email Address List": "email_address_list",
            "Interaction Mode": "interaction_mode",
            "Test Type": "test_type",
            "Scenario Case": "scenario_case",
            "Certificate Title": "certificate_title",
            "Personality Model": "personality_model"
        },

        "dynamic": {
            "Title": "title",
            "Context": "description",
            "Skill Domain": "skill_domain",
            "Candidate Type": "candidate_type",
            "Email Address List": "email_address_list",
            "Scenario Case": "scenario_case",
            "Certificate Title": "certificate_title",
            "Skills_list": "skills_to_evaluate",
            "is_dynamic_thread": "is_dynamic_discussion_thread",

        },

        "game_dynamic": {
            "Title": "title",
            "Context": "description",
            "Test Custom Prompt": "gpt_prompt_override",
            "is_dynamic_thread": "is_dynamic_discussion_thread",
            "Email Address List": "email_address_list",
            "Scenario Case": "scenario_case",
            "Is Single Select": "is_single_select"
        },

        "static_game": {
            "Title": "title",
            "Test description": "description",
            "Skill Domain": "skill_domain",
            "Candidate Type": "candidate_type",
            "Email Address List": "email_address_list",
            "Interaction Mode": "interaction_mode",
            "Test Type": "test_type",
            "Scenario Case": "scenario_case",
            "Certificate Title": "certificate_title",
            "Score Visible": "score_visible",
            "Explanation Visible": "explanation_visible",
            "Is Single Select": "is_single_select",
            
        }
    }

    # -------------------------
    # 🧩 Optional Columns (mapped)
    # -------------------------
    optional_columns = {
        "psychometric": {},

        "static": {
            "Explanation Visible": "explanation_visible",
            "Score Visible": "score_visible",
            "Time Limit": "time_limit",
            "Scenario Prompt Type": "creator_prompt_type",
            "Description Media": "description_media",
            "Instruction Media": "instruction_media_link",
            "Area/Domain": "area_domain",
            "Client Name": "client_name",
            "Personality Model": "personality_model",
            "Script Video Link": "script_video_link",
            "Video Script": "video_script",
            "Feedback Video Link": "feedback_script_video_link",
            "Feedback Video Script": "feedback_video_script_template",
            "Test Snippet Link": "snippet_url",
            "is learner path": "is_learner_path",
            "Ted talks and HBR Case": "tedtalk_and_hbr_case",
            "is checkin type": "is_checkin_type",
            "is_email_type": "is_email_type",
            "Send only to email": "send_only_to_email",
            "Email Candidate": "email_candidate",
            "Certificate Description": "certificate_description",
            "source": "source",
            "image_url": "image_url",
            "rating": "rating",
            "is_game_type": "is_game_type",
            "Competency Skill": "competency_group",
            "Goals": "goals",
            "Course": "course",
            "Industry": "industry",
            "Experience Level": "exp_level",
            "Title UI": "title_ui",
            "Description UI": "description_ui",
            "Is Transcript Only": "is_transcript_only",
            "Current news": "web_page_url",
            "User ID": "creator_user_id",
            "Calculate Culture": "calculate_culture",
            "Visual Tags": "visual_tags"
        },

        "dynamic": {
            "Scenario Prompt Type": "creator_prompt_type",
            "Description Media": "description_media",
            "Instruction Media": "instruction_media_link",
            "Area/Domain": "area_domain",
            "Client Name": "client_name",
            "Script Video Link": "script_video_link",
            "Video Script": "video_script",
            "Feedback Video Link": "feedback_script_video_link",
            "Feedback Video Script": "feedback_video_script_template",
            "Test Snippet Link": "snippet_url",
            "is learner path": "is_learner_path",
            "Ted talks and HBR Case": "tedtalk_and_hbr_case",
            "is checkin type": "is_checkin_type",
            "Send only to email": "send_only_to_email",
            "Email Candidate": "email_candidate",
            "Certificate Description": "certificate_description",
            "Competency Skill": "competency_group",
            "Goals": "goals",
            "Course": "course",
            "Industry": "industry",
            "Experience Level": "exp_level",
            "Background": "background",
            "Title UI": "title_ui",
            "Description UI": "description_ui",
            "Is Transcript Only": "is_transcript_only",
            "Current news": "web_page_url",
            "User ID": "creator_user_id",
            "Visual Tags": "visual_tags",
            "Time Limit": "time_limit",
            "Background": "background",

        },

        "game_dynamic": {},

        "static_game": {
            
        }
    }

    # -------------------------
    # 🔁 Dynamic Repeating Columns (mapped)
    # -------------------------
    dynamic_columns = {
        "psychometric": {
            "Question": "question",
            "Custom Prompt": "gpt_prompt_override",
            # "KLP": "key_learning_point",
            # "KLS": "key_learning_skills",
            # "QnA Insight": "question_insight",
            # "Que Media": "media_link",
        },

        "static": {
            "Question": "question",
            "Custom Prompt": "gpt_prompt_override",
            "KLP": "key_learning_point",
            "KLS": "key_learning_skills",
            # "QnA Insight": "question_insight",
            "Que Media": "media_link",
        },

        "dynamic": {
            "Person": "orch.initialmessage",
        },

        "game_dynamic": {},

        "static_game": {
            "Range and feedback": "range_feedback",
            "Question": "question",
            'Q Explanation': "que_explanation",
            "Correct answer": "mcq_answer",
            "Que Media": "media_link",
            "Option": "option"
        }
    }


    # --- Dynamic analysis: max persons, max questions ---
    max_questions = 0
    test_list = []


    test_lists_mapping = {} # {"q_num": [{}]}
    for test in tests:
        qs = TestQuestion.objects.filter(test_id=test.uid)
        if qs.exists():
            highest = qs.order_by('-question_number').first().question_number
            max_questions = highest
            
        # --- Determine applicable column setup ---

        test_key = 'static'
        if test.is_game_type and test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread]:
            test_key = 'game_dynamic'
        elif test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread, TestTypeChoices.orchestrated_conversation]:
            test_key = 'dynamic'
        elif test.is_game_type and test.test_type == TestTypeChoices.test:
            test_key = 'static_game'
        elif test.scenario_case == ScenarioCaseChoices.psychometric:
            test_key = 'psychometric'

        base_columns = required_columns.get(test_key, required_columns["static"])
        option_coulums_csv = optional_columns.get(test_key, optional_columns['static'])
        dynamic_columns_csv = dynamic_columns.get(test_key, dynamic_columns['static'])


        csv_columns = list(base_columns.keys())

        row = {}

        # --- Populate required fields ---
        for field_name, model_name in base_columns.items():

            if model_name == 'certificate_title' and test.certificate_details:
                row[field_name] = test.certificate_details.get('title',"")
            elif model_name == 'psychometric_report_config' and test.psychometric_report_config:
                row[field_name] = test.psychometric_report_config.name
            elif model_name == 'psychometric' and test.psychometric:
                row[field_name] = test.psychometric.name
            elif model_name == 'is_dynamic_discussion_thread':
                row[field_name] = test.test_type == TestTypeChoices.dynamic_discussion_thread
            else:
                row[field_name] = str(getattr(test, model_name, ""))

        

        # --- Fill dynamic person messages ---

        orch = getattr(test, "orchestrated_conversation_details", None)
        print('orch', orch, test.title)
        if 'dynamic' in test_key:
            if isinstance(orch, dict):
                initial_msgs = orch.get("initial_messages", []) or []
                print('msg', initial_msgs)
                for idx, msg in enumerate(initial_msgs):
                    key = f"Person {idx}"
                    csv_columns.append(key)
                    row[key] = msg
                
                if orch.get('start_with_user', None):
                    csv_columns.append('start with user')
                    row['start with user'] = orch.get('start_with_user')

                if orch.get('responder', None):
                    csv_columns.append('Asker UI')
                    row["Asker UI"] = orch.get('responder')

            qs = TestQuestion.objects.filter(test_id=test.uid).order_by('question_number')
            for q in qs:
                qn = str(getattr(q, "question_number", 1)-1)
                row[qn] = q.question
                csv_columns.append(qn)

        else:
            # --- Fill test questions ---
            qs = TestQuestion.objects.filter(test_id=test.uid).order_by('question_number')
            for q in qs:
                qn = str(getattr(q, "question_number", 1))
                for dyna_col, dyna_model in dynamic_columns_csv.items():
                    if dyna_model == 'option' and q.mcq_options:
                        for option, value in q.mcq_options.items():
                            row[f'{dyna_col} {qn}{option}'] = value.get('opt')

                    elif dyna_model in ['range_feedback'] and test.score_config:
                        for index, (rn, feedback) in enumerate(test.score_config.items()):
                            row[f"Range {index+1}"] = rn
                            row[f"Feedback {index+1}"] = feedback.get('feedback')
                    else:
                        row[f'{dyna_col} {qn}'] = str(getattr(q, dyna_model,""))
                    csv_columns.append(f'{dyna_col} {qn}')
        

        #--- now optional/const column:
        csv_columns += option_coulums_csv.keys()
        for f, m in option_coulums_csv.items():
            if m == 'certificate_description' and test.certificate_details:
                row[f] = test.certificate_details.get('description','')
            elif m == 'background' and orch and isinstance(orch, dict):
                row[f] = orch.get('background')
            elif m == 'title_ui':
                row[f] = test.ui_information.get('title') if test.ui_information else "None"
            elif m == 'description_ui':
                row[f] = test.ui_information.get('description') if test.ui_information else "None"
            else:
                row[f] = str(getattr(test, m, ""))

        csv_name = f"{test_key}-{max_questions}-export-{timezone.now()}.csv"
        if max_questions not in test_lists_mapping:
            test_lists_mapping[csv_name] = [row]
        else:
            test_lists_mapping[csv_name].append(row)
        test_list.append(row)
    return test_lists_mapping