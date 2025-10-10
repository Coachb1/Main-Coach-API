from bulk_admin_action.scenario_creator.function import create_upload_test_scenario, get_candidate_type


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

def process_create_upload_test(uploaded_df, llm_type,email, password, domain, auth):
    logs= []
    if uploaded_df.get('df') is not None:
      df = uploaded_df['df']
      filename = uploaded_df['filename'].replace('.csv','')

      print("✅ CSV contains all required fields. Processing rows...\n")
      for index, row in df.iterrows():
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

          success, errors = create_upload_test_scenario(
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
              asker=asker,
              responder=responder,
              situation=situation,
              targeted_skills=targeted_skills,
              custom_information=custom_information,
              skill_domain=skill_domain,
              generate_video_script=generate_video_script,
              video_script=video_script,
              file_name =filename,
              email=email,
              password=password,
              domain=domain,
              auth=auth
          )
          print(errors)
          if len(errors)>0:
            error_msg = "<br>".join(errors)
            logs.append(f"Got error in row {index}: {error_msg}.")
          
    a = filename.split('.csv')
    new_file_name = "".join(a[:-1] ) + "_report" + '.csv'     

    return logs, new_file_name
