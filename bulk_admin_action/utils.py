


from datetime import datetime
import os
import zipfile

import requests
from django.conf import settings
from bulk_admin_action.scenario_creator.function import get_candidate_type, scenario_create
from settings import BACKEND

base_url = BACKEND

def validate_file(df):
  required_columns = [
    "Test Type", "Objective", "Industry", "Department", "Asker", "Responder",
    "Situation", "Targeted Skills", "Iterations", "Pesonality Model",
    "start with user", "Is single select", "Skill Domain", "Generate Video Script", "Video Script"
  ]
  missing = [col for col in required_columns if col not in df.columns]
  if missing:
      print("❌ Missing required columns:\n")
      for m in missing:
          print(f"• {m}")
      print("\n⚠ Please re-upload a valid CSV with all required fields.")
      return False
  return True


def create_scenario_view(llm_type, uploaded_df):
    try:
        df = uploaded_df.get('df')
        file_name = uploaded_df.get('filename')
        results = []
        if 'Status' not in df.columns:
            df['Status'] = ''
        if 'Errors' not in df.columns:
            df['Errors'] = ''
        df['Status'] = df['Status'].astype(str)
        df['Errors'] = df['Errors'].astype(str)

        for i, row in df.iterrows():
            row = row.to_dict()
            print(f"Processing row {i + 1}: {row}")

            try:
                objective = row.get('Objective', '')
                industry = row.get('Industry', '')
                department = row.get('Department', '')
                asker = row.get('Asker', '')
                responder = row.get('Responder', '')
                situation = row.get('Situation', '')
                targeted_skills = row.get('Targeted Skills') or ''
                skill_domain = row.get('Skill Domain', '')
                generate_video_script = str(row.get('Generate Video Script')).lower() == 'true'
                video_script = row.get('Video Script', '')
                scenario_type = row.get('Test Type', '')
                personality_model = row.get('Pesonality Model') or None
                start_with_user = row.get('start with user')
                is_single_select = row.get('Is single select')

                try:
                    iterations = int(row.get('Iterations', 1))
                except:
                    iterations = 1

                question_type = ""
                if "game" in scenario_type:
                    if not is_single_select:
                        print(f"Row {i+1}: Missing 'Is single select' for game scenario.")
                        df.at[i, 'Status'] = 'Failed'
                        df.at[i, 'Errors'] = "'Is single select' required for game scenario."
                        continue
                    question_type = 'single' if is_single_select else "multiple"

                if scenario_type == "dynamic_start_with_user":
                    if not start_with_user:
                        print(f"Row {i+1}: Missing 'start with user' for dynamic scenario.")
                        df.at[i, 'Status'] = 'Failed'
                        df.at[i, 'Errors'] = "'start with user' required for dynamic scenario."
                        continue

                startwithuser_type = start_with_user if scenario_type == "dynamic_start_with_user" else ""
                candidate_type = get_candidate_type(start_with_user) if scenario_type == "dynamic_start_with_user" else "Manager"

                success, errors = scenario_create(
                    llm_type=llm_type,
                    scenario_type=scenario_type,
                    question_count=6,
                    iterations=iterations,
                    skill_count=2,
                    question_type=question_type,
                    personality_model=personality_model,
                    startwithuser_type=startwithuser_type,
                    candidate_type=candidate_type,
                    objective=objective,
                    industry=industry,
                    department=department,
                    responder=responder,
                    asker=asker,
                    situation=situation,
                    targeted_skills=targeted_skills,
                    custom_information="",
                    skill_domain=skill_domain,
                    generate_video_script=generate_video_script,
                    video_script=video_script,
                    file_name=None,
                    folder_path='media/scenario_creator'
                )

                df.at[i, 'Status'] = 'Success' if success else 'Failed'
                df.at[i, 'Errors'] = errors if errors else ''

            except Exception as row_error:
                print(f"❌ Error processing row {i + 1}: {row_error}")
                df.at[i, 'Status'] = 'Failed'
                df.at[i, 'Errors'] = str(row_error)

        # Create zip from generated scenarios
        print("📦 Creating ZIP file from generated scenarios...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"media/scenario_creator/Scenario_Creator_bundle_{timestamp}.zip"

        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for root, _, files in os.walk('media/scenario_creator'):
                for file in files:
                    print(f"Adding file to ZIP: {file}")
                    file_path = os.path.join(root, file)
                    # avoid including the zip file itself
                    if file_path != zip_filename:
                        arcname = os.path.relpath(file_path, 'media/scenario_creator')
                        zipf.write(file_path, arcname=arcname)

            print(f"📄 CSV saved: {file_name}")

        print(f"📦 ZIP created: {zip_filename}")
        zip_filename = os.path.relpath(zip_filename, start=settings.BASE_DIR)
        return zip_filename

    except Exception as e:
        print(f"❌ Error in create_scenario_view: {e}")
        raise 

def get_dynamic_csv(
    test_type,
    interaction_mode,
    scenario_case,
    num_questions,
    candidate_type,
    test_codes,
    page_name,
    competency_skills,
    tab_category,
    auth,
    bots,
    is_start_with_user
):
    url = f"{base_url}/api/v1/tests/get_group_discussion_test_csv/"
    params = {}

    if test_type:
        params['test_type'] = test_type
    if interaction_mode:
        params['interaction_mode'] = interaction_mode
    if scenario_case:
        params['scenario_case'] = scenario_case
    if num_questions:
        params['num_questions'] = num_questions
    if candidate_type:
        params['candidate_type'] = candidate_type
    if bots:
        params['bots'] = bots
    if is_start_with_user:
        params['is_start_with_user'] = is_start_with_user
    if test_codes:
        params['test_codes'] = test_codes
    if page_name:
        params['page_name'] = page_name
    if competency_skills:
        params['competency_skills'] = competency_skills
    if tab_category:
        params['tab_category'] = tab_category

    headers = {
        'Content-Type': 'application/json',
        'Authorization': auth
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print('Failed API request:', response.status_code, response.text)
            raise Exception(f"API request failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print('Exception in API request:', str(e))
        raise e


class CleanupFileStream:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file = open(file_path, 'rb')

    def read(self, size=-1):
        return self.file.read(size)

    def close(self):
        try:
            self.file.close()
        finally:
            try:
                if os.path.exists(self.file_path):
                    os.remove(self.file_path)
                    print(f"🧹 Deleted file: {self.file_path}")
            except Exception as e:
                print(f"❗ File delete error: {e}")

    def __iter__(self):
        return iter(self.file)