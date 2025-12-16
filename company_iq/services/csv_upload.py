import csv
from io import TextIOWrapper
import json
from string import Template
from django.core.exceptions import ValidationError
from pyparsing import line
from vine import transform
from commons.utils import generic_completion
from company_iq.models import CompanyIQ
from django.db import IntegrityError

import logging

logger = logging.getLogger(__name__)

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


REQUIRED_FIELDS = [
    "Company",
    "Industry",
    "HQ",
    "Revenue (US Millions)",
    "Employees (Full-Time)",
    "Use LLM",
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

        value = raw.strip()

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


def get_company_iq_prompt(type_of_prompt):
    if type_of_prompt == 'outlook':
        return '''Role & Stance
You are acting as an Enterprise AI Adoption Analyst advising C-suite leaders and cloud GTM teams.
Your task is not to summarize the past.
Your task is to predict the next 12 months of AI direction for a specific company, grounded in public signals, industry patterns, and adoption constraints.

You must be opinionated, selective, and falsifiable.


---

Inputs : ${input_data}




---

Output Requirements

Produce a 12-Month AI Outlook with the following structure.
Do not exceed 400–500 words.


---

1. Executive Prediction (Non-Obvious)

State one clear prediction about how this organization’s AI journey will evolve in the next 12 months.

This must be a directional bet, not a hedge

Use phrases like:

“The most likely outcome is…”

“The critical inflection will occur when…”

“The risk leadership is underestimating is…”



Avoid generic optimism.


---

2. What Will Move Forward (3 items max)

Identify up to three AI initiatives or themes that are most likely to progress meaningfully.

For each:

Why this and not others

What internal force supports it (regulatory, margin pressure, talent, customer behavior)



---

3. What Will Stall or Be Abandoned

Explicitly name:

At least one AI initiative that is likely to stall, pause, or fail

The real reason (political, operational, cultural — not “data quality”)


This is where credibility is built.


---

4. Cloud & Technology Implications

Describe how this outlook translates into actual cloud behavior:

Experimentation vs production

Spend concentration vs fragmentation

Central IT vs business-led motion


No vendor hype. No product names unless justified.


---

5. Executive Risk & Opportunity Window

Close with:

One risk leadership will face if they do nothing in the next 12 months

One opportunity that compounds if acted on early


This should read like advice someone would pay for.


---

Style Constraints

No marketing language

No buzzword stacking

No “AI will transform everything” statements

Write like a trusted internal strategist, not a vendor

'''
    elif type_of_prompt == 'meta_data':
        return '''
            For the company, "${company_name}", find the following metadata from publicly available resources and adhere strictly to the format and constraint guidelines below: 
**Constraint Guidelines:** 
* **Output Format:** 
Provide a direct, unadorned bulleted list. NO introductory or concluding sentences, NO descriptions, and NO symbols (e.g., $, %, etc.) unless specified.
 * **Revenue Constraint:** 
Must be the most recent *Annual* Revenue figure, expressed ONLY as an integer count in **US Millions**. If the figure is $5.2 Billion, render it as 5200. 
* **Employees Constraint:** 
Must be the *most recent full-time* employee count, expressed ONLY as a single integer count. Exclude seasonal or contract staff. 
* **Industry Constraint:** 
Select the single best fit from this standard, comprehensive list: **Technology, Finance, Healthcare, Manufacturing, Retail, Consumer Services, Energy, Transportation/Logistics, Telecommunications, Government/Defense.
** **Metadata Variables and Required Format must be in json:** 
{
  "company": "[Company registered Name]",
  "industry": "[Standard Industry from list above]",
  "hq": "[City, State or Country]",
  "revenue_us_millions": [Integer Count],
  "employees_full_time": [Integer Count],
  "ai_cloud_leadership_roles": [List up to 5 key title/leader names with their focus (e.g., CIO/Alan Lowden - Technology Strategy)],
  "ai_digital_initiatives": [List up to 5 major programs or strategies (e.g., Block Next Strategy, AI Tax Assist)],
  "cloud_tech_stack_signals": [List up to 5 core technologies (e.g., Primary Cloud/Azure, Data/Cosmos DB, Languages/.NET Core)],
  "ai_use_cases": [List up to 5 specific applications with their function (e.g., Predictive Maintenance - Reduces unplanned downtime)]

}
        '''


def parse_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split("|") if v.strip()]
    return value


def validate_row(row):
    missing = [f for f in REQUIRED_FIELDS if not row.get(f)]
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

def import_companyiq_csv(file):
    reader = csv.DictReader(TextIOWrapper(file, encoding="utf-8"))
    created = 0
    errors = []

    for line_no, row in enumerate(reader):
        try:
            validate_row(row)
            data = normalize_csv_row(row)

            company_name = data["company"]
            industry = data["industry"]
            hq = data["hq"]

            existing = get_existing_company_iq(company_name, industry, hq)

            use_llm = data.get("use_llm", False)

            # --------------------
            # LLM FLOW
            # --------------------
            if use_llm:
                prompt = get_company_iq_prompt("meta_data")
                prompt = Template(prompt).safe_substitute(company_name=company_name)
                company_info = generic_completion(
                    prompt
                )

                outlook = generic_completion(
                    Template(get_company_iq_prompt("outlook")).substitute(
                        input_data=company_info
                    )
                )

                payload = {
                    "company": company_info["company"].strip(),
                    "industry": company_info["industry"].strip(),
                    "hq": company_info["hq"].strip(),
                    "revenue_us_millions": int(company_info["revenue_us_millions"]),
                    "employees_full_time": int(company_info["employees_full_time"]),
                    "ai_cloud_leadership_roles": parse_list(company_info.get("ai_cloud_leadership_roles")),
                    "ai_digital_initiatives": parse_list(company_info.get("ai_digital_initiatives")),
                    "cloud_tech_stack_signals": parse_list(company_info.get("cloud_tech_stack_signals")),
                    "ai_use_cases": parse_list(company_info.get("ai_use_cases")),
                    "transformation_iq_outlook": outlook,
                }

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
                if not transformation_iq_outlook:
                    transformation_iq_outlook = generic_completion(
                            Template(get_company_iq_prompt("outlook")).substitute(
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
            logger.exception(f"Error processing line {line_no}: {e}")
            errors.append(
                f"Line {line_no} ({row.get('Company')}): {str(e)}"
            )

    return created, errors
