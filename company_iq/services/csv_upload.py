import csv
from io import TextIOWrapper
import json
import re
from string import Template
import chardet
from django.core.exceptions import ValidationError
from commons.utils import generic_completion, sanitize_text
from company_iq.models import CompanyIQ

import logging

from company_iq.prompts import company_iq_prompts

logger = logging.getLogger("main")

MAX_CSV_ROWS = 50

def get_existing_company_iq(company_name, industry=None, hq=None):
    company_iq = CompanyIQ.objects.filter(
            company_normalized=company_name.strip().lower(),
            deleted=False
        )
    
    if industry:
        company_iq = company_iq.filter(industry=industry.strip())
    if hq:
        company_iq = company_iq.filter(hq=hq.strip())

    return company_iq.first()

CSV_FIELD_MAP = {
    "Company": "company",
    "Industry": "industry",
    "HQ": "hq",
    "Revenue (US Millions)": "revenue_us_millions",
    "Employees (Full-Time)": "employees_full_time",
    "Use LLM": "use_llm",
    "Approved": "approved",

    "AI/Cloud Leadership Roles": "ai_cloud_leadership_roles",
    "AI / Digital Initiatives": "ai_digital_initiatives",
    "Cloud / Tech Stack Signals": "cloud_tech_stack_signals",
    "AI Use Cases": "ai_use_cases",
    "Tranformation IQ - Outlook": "transformation_iq_outlook",
}


LLM_REQUIRED_FIELDS = [
    "Company",
    "Use LLM",
]
CSV_REQUIRED_FIELDS = [
    "Use LLM",
    "Company",
    "Industry",
    "HQ",
    "Revenue (US Millions)",
    "Employees (Full-Time)",
    "AI/Cloud Leadership Roles",
    "AI / Digital Initiatives",
    "Cloud / Tech Stack Signals",
    "AI Use Cases",
]

def normalize_csv_row(row):
    def parse_int_field(value, field_name):
        """
        Accepts numbers like:
        6200
        6,200
        6,200.00
        6200.0

        Returns int or raises ValidationError
        """
        if value is None or value == "":
            raise ValidationError(f"{field_name} is required")

        try:
            cleaned = value.replace(",", "").strip()
            return int(float(cleaned))
        except ValueError:
            raise ValidationError(
                f"Invalid integer for {field_name}: {value}"
            )

    normalized = {}

    for csv_key, model_key in CSV_FIELD_MAP.items():
        raw = row.get(csv_key)
        if raw is None:
            continue

        value = sanitize_text(raw.strip())

        if model_key in ("use_llm", "approved"):
            normalized[model_key] = value.lower() == "true" if value else False
        elif model_key in ("revenue_us_millions", "employees_full_time"):
            try:
                normalized[model_key] = parse_int_field(value, model_key)
            except ValueError:
                raise ValidationError(f"Invalid integer for {model_key}: {value}")
        else:
            normalized[model_key] = value

    return normalized


def parse_list(value):
    if not value:
        return []

    # Case 1: list with a single giant string
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        value = value[0]

    items = []

    # Case 2: string input
    if isinstance(value, str):
        lines = re.split(r"[\n\r]+", value)
        items.extend(lines)

    # Case 3: list input
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                items.extend(re.split(r"[\n\r]+", item))

    else:
        raise ValidationError(
            "Expected a list of strings or a newline-separated string."
        )

    cleaned = []
    for line in items:
        line = line.strip()

        # remove bullets: *, -, •, 1., 1)
        line = re.sub(r"^(\s*[\*\-\•]|\s*\d+[\.\)])\s*", "", line)

        if line:
            cleaned.append(line)

    # deduplicate while preserving order
    return list(dict.fromkeys(cleaned))



def validate_row(row, required_fields):
    missing = [f for f in required_fields if not row.get(f)]
    if missing:
        raise ValidationError(f"Missing required fields: {missing}")


def upsert_companyiq(existing_obj, data, source, approved=False):
    """
    Update only if NOT approved.
    Approved records are immutable.
    """
    if existing_obj:
        # if existing_obj.approved :
        #     return "skipped_approved"

        for field, value in data.items():
            setattr(existing_obj, field, value)

        existing_obj.source = source
        existing_obj.approved = approved
        existing_obj.save()
        return "updated"

    CompanyIQ.objects.create(
        **data,
        source=source,
        approved=approved,
    )
    return "created"

def import_companyiq_csv(file, generate_score=False, generate_outlook=False):
    raw = file.read()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding") or "utf-8"

    file.seek(0)

    reader = csv.DictReader(
        TextIOWrapper(file, encoding=encoding, errors="replace")
    )
    rows = list(reader)
    # if len(rows) > MAX_CSV_ROWS:
    #     raise ValidationError(
    #         f"CSV row limit exceeded. Maximum allowed is {MAX_CSV_ROWS}, "
    #         f"but found {len(rows)} rows."
    #     )
    
    created = 0
    errors = []

    for line_no, row in enumerate(rows):
        try:
            logger.info(f"Processing line {line_no + 1}: {row.get('Company', 'Unknown')}")
            use_llm = row.get("Use LLM", "").strip().lower() == "true"

            validate_row(row, LLM_REQUIRED_FIELDS if use_llm else CSV_REQUIRED_FIELDS)
            data = normalize_csv_row(row)

            company_name = data["company"]
            industry = data.get('industry')
            hq = data.get('hq')

            existing = get_existing_company_iq(company_name)

            use_llm = data.get("use_llm", False)

            # --------------------
            # LLM FLOW
            # --------------------
            if use_llm:
                prompt = Template(company_iq_prompts.METADATAPROMPT).safe_substitute(company_name=company_name)
                company_info = generic_completion(
                    prompt
                )
                

                payload = {
                    "company": company_name,
                    "industry": company_info["industry"].strip(),
                    "hq": company_info["hq"].strip(),
                    "revenue_us_millions": int(company_info["revenue_us_millions"]),
                    "employees_full_time": int(company_info["employees_full_time"]),
                    "ai_cloud_leadership_roles": parse_list(company_info.get("ai_cloud_leadership_roles")),
                    "ai_digital_initiatives": parse_list(company_info.get("ai_digital_initiatives")),
                    "cloud_tech_stack_signals": parse_list(company_info.get("cloud_tech_stack_signals")),
                    "ai_use_cases": parse_list(company_info.get("ai_use_cases")),
                }
                if generate_outlook:
                    payload["transformation_iq_outlook"] = generic_completion(
                        Template(company_iq_prompts.OUTLOOKPROMPT).substitute(
                            input_data=company_info
                        )
                    )

                if generate_score:
                    score_prompt = Template(company_iq_prompts.SCOREGENERATIONPROMPT).safe_substitute(company_name=company_name, company_info=json.dumps(payload))
                    score_data = generic_completion(score_prompt)
                    payload["score"] = score_data

                result = upsert_companyiq(
                    existing,
                    payload,
                    source="LLM",
                    approved=False,  # LLM is NEVER auto-approved
                )

            # --------------------
            # CSV FLOW
            # --------------------
            else:
                payload = {
                    "company": company_name,
                    "industry": industry,
                    "hq": hq,
                    "revenue_us_millions": int(data["revenue_us_millions"]),
                    "employees_full_time": int(data["employees_full_time"]),
                    "ai_cloud_leadership_roles": parse_list(data.get("ai_cloud_leadership_roles")),
                    "ai_digital_initiatives": parse_list(data.get("ai_digital_initiatives")),
                    "cloud_tech_stack_signals": parse_list(data.get("cloud_tech_stack_signals")),
                    "ai_use_cases": parse_list(data.get("ai_use_cases")),
                }

                transformation_iq_outlook = data.get("transformation_iq_outlook", "").strip()
                if not transformation_iq_outlook and generate_outlook:
                    transformation_iq_outlook = generic_completion(
                            Template(company_iq_prompts.OUTLOOKPROMPT).substitute(
                                input_data=payload
                            )
                        )
                
                payload["transformation_iq_outlook"] = transformation_iq_outlook


                approved_flag = data.get("approved", False)

                result = upsert_companyiq(
                    existing,
                    payload,
                    source="CSV",
                    approved=approved_flag,
                )

            if result in ("created", "updated"):
                created += 1
            elif result == "skipped_approved":
                errors.append(
                    f"Line {line_no} ({company_name}): Skipped (already approved)"
                )

        except Exception as e:
            logger.exception(f"Error processing line {line_no+1}- {row.get('Company', 'Unknown')}: {e}")
            errors.append(
                f"Line {line_no+1} ({row.get('Company')}): {str(e)}"
            )

    return created, errors
