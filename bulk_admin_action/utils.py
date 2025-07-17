


from datetime import datetime
import os
import zipfile

import requests

from bulk_admin_action.scenario_creator.function import get_candidate_type, scenario_create

base_url = "https://coach-api-gke-dev.coachbots.com"

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
                for index, row in df.iterrows():
                    print(row)
                    index = index + 1
                    # Simulate processing for each row
                    row = row.to_dict()
                    print(f"Processing row {index}: {row}")
                    objective = row['Objective']
                    industry = row['Industry']
                    department = row['Department']
                    asker = row['Asker']
                    responder = row['Responder']
                    situation = row['Situation']
                    targeted_skills = row['Targeted Skills'] if row['Targeted Skills'] else ""
                    skill_domain = row['Skill Domain']
                    generate_video_script = str(row.get('Generate Video Script')).lower() == 'true' if row.get('Generate Video Script') else False

                    video_script = row['Video Script']
                    custom_information = ""
                    scenario_type = row['Test Type']
                    question_count = 6
                    try:
                        iterations = int(row['Iterations']) if row['Iterations'] else 1
                    except:
                        iterations = 1
                    question_type = ""
                    skill_count = 2

                    # if targeted_skills and len(targeted_skills.split(',')) < 8:
                    #   message_label.value += f"<span style='color:red;'>Row {index}: Skills must have at least 8. Got:  {len(targeted_skills.split(','))}, {targeted_skills}</span><br>"
                    #   continue
                    personality_model = row['Pesonality Model'] if row['Pesonality Model'] else None

                    if scenario_type == "dynamic_start_with_user":
                        if not row['start with user']:
                        # message_label.value += f"<span style='color:red;'>Row {index}: For {scenario_type}, field 'start with user' required.</span><br>"
                            print(f"Row {index}: For {scenario_type}, field 'start with user required.")
                            continue
                    if "game" in scenario_type:
                        if not row['Is single select']:
                        # message_label.value += f"<span style='color:red;'>Row {index}: For {scenario_type}, field 'Is single select' required.</span><br>"
                            print(f"Row {index}: For {scenario_type}, field 'Is single select' required.")
                            continue
                        question_type = 'single' if row['Is single select'] else "multiple"

                    startwithuser_type = row['start with user'] if scenario_type == "dynamic_start_with_user" else ""
                    candidate_type = get_candidate_type(row['start with user']) if scenario_type == "dynamic_start_with_user" else "Manager"
                    success, errors = scenario_create(
                        llm_type=llm_type,
                        scenario_type=scenario_type,
                        question_count=question_count,
                        iterations=iterations,
                        skill_count=skill_count,
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
                        custom_information=custom_information,
                        skill_domain=skill_domain,
                        generate_video_script=generate_video_script,
                        video_script = video_script,
                        file_name=None,
                        folder_path= 'media\scenario_creator'
                    )
                    df.at[index, 'Status'] = 'Success' if success else 'Failed'
                    df.at[index, 'Errors'] = errors if errors else ''
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_filename = f"Scenario Creator_bundle_{timestamp}.zip"
                    with zipfile.ZipFile(zip_filename, 'w') as zipf:
                        for root, _, files_list in os.walk('media\scenario_creator'):
                            for file in files_list:
                                file_path = os.path.join(root, file)
                                zipf.write(file_path, arcname=file)
                    print(f"📦 ZIP created: {zip_filename}")                   
                    return zip_filename

            except Exception as e:
                print(f"error: {e}")


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