from bulk_admin_action.automated_scenario import  AutomatedScenarios
import json
import os
import re

import pandas as pd

from bulk_admin_action.automated_scenario import append_to_csv, initialize_csv
from bulk_admin_action.scenario_creator.prompts import feedback_video_script_template, format_game_custom_prompt, get_game_prompt, get_scenario_prompt, video_script_prompt
from commons.anthropic import anthropic_completion
from commons.google_apis import gemini_completion


def clean_text(input_text):
    # Remove all types of brackets except quotation marks
    return re.sub(r'[\[\]\(\)\{\}<>]', '', input_text).strip()

def remove_url_garbage_char(text):
    # Remove URLs
    text = clean_text(text)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Remove common encoding garbage characters
    garbage_chars = [
        'â€“', 'â€™', 'â€œ', 'â€', 'â€˜', 'â€', 'â€¢', 'Â', '€', '™', ' '
    ]
    for char in garbage_chars:
        text = text.replace(char, '')

    # Optionally remove any leftover non-ASCII characters
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def generate_video_script_via(objective, prompt= None):
  if not prompt:
    prompt = video_script_prompt(objective)
  print('prompt', prompt)
  result = gemini_completion(prompt)

  result = remove_url_garbage_char(result)
  return result

def create_csv(scenario_data,question_count,iteration,scenario_type,information,file_name=None,folder_path=None):
      try:
        print('create_csv', scenario_data)
        response = {}

        response['Error'] = scenario_data.get('error')
        response['Intake Information'] = information
        response['Scenario Prompt Type'] = scenario_type
        response['Title'] = scenario_data.get('title')
        response['Test description'] = scenario_data.get('description')


        # Add extra columns
        const_columns = "Skill Domain,Candidate Type,Email Address List,Interaction Mode,Test Type,Scenario Case,Area/Domain,Certificate Title,Client Name,Personality Model,"

        optional = "Script Video Link,Video Script,Feedback Video Link,Feedback Video Script,Test Snippet Link,Max Test Allowed,Description Media,is learner path,Ted talks and HBR Case,is checkin type,is_email_type,Send only to email,Email Candidate,Certificate Description,source,image_url,rating,is_game_type,Competency Skill,Goals,Course,Industry,Experience Level,Background,Title UI,Description UI,is_micro,is_logged_in,Is Immersive,Is Transcript Only,is_pitch,Current news,Bot Name,User ID,Tab Category,Visual Tags,Page Name,"

        # if scenario_data.get('personality_model', None):
        #   const_columns += "Personality Model,"

        const_columns_list = const_columns.split(',')

        for col_name in const_columns_list:
            if len(col_name) == 0:
              continue
            response[col_name] = None

        response['Certificate Title'] = scenario_data.get('title')
        response['Email Address List'] = 'mail@coachbots.com'
        response['Interaction Mode'] = 'any'
        response['Test Type'] = 'test'
        response['Scenario Case'] = "role_play" if 'role_play' in scenario_type  else "simulation"
        response['Area/Domain'] = 'General'


        if scenario_data.get('personality_model', None):
          print(scenario_data.get('personality_model'),'personality_model')
          response['Personality Model'] = scenario_data.get('personality_model')


        if scenario_data.get('skill_domain'):
          response['Skill Domain'] = scenario_data.get('skill_domain')

        if scenario_data.get('candidate_type'):
          response['Candidate Type'] = scenario_data.get('candidate_type')


        print('Title: ', response['Title'])
        print('Test description: ', response['Test description'])

        questions = [que.get('question') for que in scenario_data.get('question_info')]
        prompts = [que.get('gpt_prompt_override') for que in scenario_data.get('question_info')]
        takeaways = [que.get('key_learning_point') for que in scenario_data.get('question_info')]
        skills_match = [que.get('key_learning_skills') for que in scenario_data.get('question_info')]

        if len(questions) > question_count:
          questions = questions[:question_count]

        if len(prompts) > question_count:
          prompts = prompts[:question_count]

        if len(takeaways) > question_count:
          takeaways = takeaways[:question_count]

        if len(skills_match) > question_count:
          skills_match = skills_match[:question_count]

        print('questions :', questions)
        print('prompts :', prompts)
        print('takeaways :', takeaways)
        print('skills_match :', skills_match)

        # Store the extracted information in the response dictionary
        for i in range(len(questions)):
            response[f'Question {i+1}'] = questions[i]
            response[f'Custom Prompt {i+1}'] = prompts[i]
            response[f'KLP {i+1}'] = takeaways[i]
            try:
                response[f'KLS {i+1}'] = skills_match[i].replace(' and', ',')
            except:
                response[f'KLS {i+1}'] = ""





        # adding optional fields
        for opt in optional.split(','):
          if len(opt) == 0:
              continue
          response[opt] = None

        print('video_script', scenario_data.get('video_script'))
        if scenario_data.get('video_script',None):
          print('video_script2', scenario_data.get('video_script'))

          response['Video Script'] = scenario_data.get('video_script')
        if scenario_data.get('script_video_link'):
          response['Script Video Link'] = scenario_data.get('script_video_link')
        if scenario_data.get('feedback_video_link'):
          response['Feedback Video Link'] = scenario_data.get('feedback_video_link')
        if scenario_data.get('feedback_script'):
          response['Feedback Video Script'] = scenario_data.get('feedback_script')


        print("REsponse to create csv", response)
        df = pd.DataFrame([response])
        file_path =file_name if file_name else f'bulk_static_{question_count}_que-{file_name}.csv'
        if folder_path:
          file_path=f"{folder_path}/{file_path}"
        my_string = ""
        if not os.path.isfile(file_path):

            with open(file_path, 'a') as file:
                my_string = 'Error,Intake Information,Scenario Prompt Type,Title,Test description,' + const_columns
                for cnt in range(1, question_count+1):
                  my_string += f"Question {cnt},Custom Prompt {cnt},KLP {cnt},KLS {cnt},"

                my_string += optional
                my_string = my_string[:len(my_string)-1] + "\n"

                file.write(my_string)
                my_string = my_string

        else:
            with open(file_path, 'r') as file:
                my_string = file.read().split('\n')[0]

        print(df.columns)
        print(len(df.columns))
        print('&'*100)

        print(my_string)
        print(len(my_string.split(',')))
        print('*'*100)
        if (len(df.columns) == (len(my_string.split(',')))):
            df.to_csv(file_path, mode='a', index=False, header=False)
            print(f'Saved {iteration} scenarios in the csv.\n\n')
        else:
            print(f'Error in iterations {iteration}. could not save to csv')
            print("Error: Number of columns in the row doesn't match the table.\n\n")
      except Exception as e:
        print('*'*100)
        print(f'[Got Error Skipping this test]: {e}')
        raise e



## extracter


def extract_text_only(input_text):
    # Remove digits from the text
    text_without_digits = re.sub(r'\d', '', input_text)

    # Remove extra whitespaces
    cleaned_text = ' '.join([st.replace("-","").strip().capitalize()  for st in text_without_digits.replace("."," ").strip().split()])

    return cleaned_text



def extract_information_static(text,iteration,question_count,scenario_type,candidate_type,is_pitch=False,personality_model=None,intake={},generate_video_script=False,video_script=None):
    """
    Extract information from a given text containing details about a scenario.

    Parameters:
    - text (str): The text containing information about a scenario.

    Returns:
    - tuple: A tuple containing title, description, question_info, skill_to_evaluate, and rating.

    Example:
    >>> extract_information('Title: Test\nDescription: Test Description\nQuestion: What is your approach to leadership?\nPrompt: Provide your leadership style.\nTakeaway: Effective communication is key.\nSkills: Communication, Leadership\nRating: 5')
    # Returns a tuple with extracted information from the scenario text.
    """
    # Regular expressions for extracting title, description, questions, prompts, takeaways, and skills
    try:
      text = text.replace("KLS", "Skills")
      text = text.replace("KLP", "Takeaway")
      text = text.replace("Custom prompt", "Prompt")
      text = text.replace("*","")

      title_pattern = re.compile(r'Title\s*:\s*(.+)')
      description_pattern = re.compile(r'Description\s*:\s*(.+)')
      statement_pattern = re.compile(r'Statement\s*:\s*(.+)')
      # background_pattern = re.compile(r'Background\s*:\s*(.+)')

      question_pattern = re.compile(r'Question\s*(\d*)\s*:\s*(.+)')
      prompt_pattern = re.compile(r'Prompt\s*(\d*)\s*:\s*(.+)')
      takeaway_pattern = re.compile(r'Takeaway\s*(\d*)\s*:\s*(.+)')
      skills_pattern = re.compile(r'Skills\s*(\d*)\s*:\s*(.+)')
      rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')

      # Extracting information using regular expressions
      title_match = title_pattern.search(text)
      description_match = description_pattern.search(text)
      rating_match = rating_pattern.search(text)
      statement_match = statement_pattern.search(text)
      # background_match = background_pattern.search(text)




      # If title_pattern doesn't match, try to find the title as the first line before the description
      if not title_match:
          pattern = re.compile(r'^(?:Title\s*:\s*)?(?:"(.?)"|([^"\n]))\n*Description\s*:')
          title_match = pattern.search(text)
          if not title_match:
              # Extract title (first quoted string or first line before description)
              title_match = re.search(r'^"([^"]+)"', text)
              title = title_match.group(1) if title_match else None
              if not title:
                raise ValueError("Invalid format. Unable to extract the title.")

      if not (title_match and statement_match and description_match and  question_pattern.findall(text) and prompt_pattern.findall(text) and takeaway_pattern.findall(text) and skills_pattern.findall(text)):
          invalid_fields = []

          if not title_match:
              invalid_fields.append("title")

          if not description_match:
              invalid_fields.append("description")
          if not question_pattern.findall(text):
              invalid_fields.append("question pattern")
          if not prompt_pattern.findall(text):
              invalid_fields.append("prompt pattern")
          if not takeaway_pattern.findall(text):
              invalid_fields.append("takeaway pattern")
          if not skills_pattern.findall(text):
              invalid_fields.append("skills pattern")
          if not statement_match:
              invalid_fields.append("statement pattern")
          # if not background_match:
          #     invalid_fields.append("background pattern")

          raise ValueError(f"Invalid format. Unable to extract necessary information. Invalid fields: {', '.join(invalid_fields)}")

      title = title_match.group(1) if title_match.group(1) else title_match.group()
      description = f'{clean_text(description_match.group(1))}'
      if statement_match:
          description += f"\nStatement: {clean_text(statement_match.group(1))}"
      # if background_match:
      #     description += f'\nBackground: {background_match.group(1)}'

      rating = int(rating_match.group(1)) if rating_match else 0
      questions = []
      for match in question_pattern.finditer(text):
          question_number = match.group(1) if match.group(1) else len(questions) + 1
          question_text = clean_text(match.group(2))
          prompt_match = prompt_pattern.search(text, match.end())
          takeaway_match = takeaway_pattern.search(text, prompt_match.end())
          skills_match = skills_pattern.search(text, takeaway_match.end())
          print(skills_match)

          prompt_text = clean_text(prompt_match.group(2))
          takeaway_text = clean_text(takeaway_match.group(2))
          skills_text = clean_text(skills_match.group(2))
          question_data = {
              'text': question_text,
              'prompt': prompt_text,
              'takeaway': takeaway_text,
              'skills': skills_text
          }
          questions.append(question_data)

      informations = {
          'title': title,
          'description': description,
          'rating': rating,
          'questions': questions
      }

      title = informations['title']

      question_info = []
      skill_to_evaluate = set()
      klps = []

      for que in informations['questions']:
          question_info.append({
              "question": que["text"],
              "question_type": "subjective",
              "gpt_prompt_override": clean_text(que["prompt"]),
              "subjective_answer": "",
              "key_learning_point": extract_text_only(que['takeaway']),
              "key_learning_skills": extract_text_only(que['skills'])
          })
          klps.append(extract_text_only(que['takeaway']))

          for skill in que['skills'].split(','):
              skill_to_evaluate.add(extract_text_only(skill.strip().capitalize()))

      if len(skill_to_evaluate) < 6 and not is_pitch:
          raise ValueError(f"Skills must have at least 6. Got:  {len(skill_to_evaluate)}, {skill_to_evaluate}")


      skill_to_evaluate = ', '.join(list(skill_to_evaluate)[:8])

      infomation = {
          'title': title,
          'description': description,
          'question_info': question_info,
          'skill_to_evaluate': skill_to_evaluate,
          'rating': rating,
          'personality_model': personality_model,
          'candidate_type': candidate_type,
          'skill_domain': intake.get('Skill Domain', "")
      }
      feedback_script = feedback_video_script_template(intake.get('Responder'),
                                                      intake.get('Asker'),
                                                      intake.get('Department'),
                                                      intake.get('Industry'),
                                                      intake.get('Objective'),
                                                      intake.get('Domain Skill'),
                                                      '\n\n'.join(klps),
                                                      )
      infomation['feedback_script'] = feedback_script
      if video_script:
          infomation['video_script'] = video_script
      elif generate_video_script:
        infomation['video_script'] = generate_video_script_via(description)

      print(f'scenario info: {infomation}')
      return infomation, True

    except Exception as e:
      question_info = []
      for i in range(question_count):
        question_info.append(
            {
                "question": "Error",
                "question_type": "subjective",
                "gpt_prompt_override": "Error",
                "subjective_answer": "",
                "key_learning_point": "Error",
                "key_learning_skills": "Error"
            }
        )
      return {'error': str(e), 'question_info': question_info}, False



def get_skills(candidate_type):

    MANAGER = [

        "Communication skills",

        "Objection handling",

        "Problem solving",

        "Social skills",

        "Collaboration",

        "Accountable",

        "Improve lives around you",

        "Negotiation",

        "Get the best from others",

        "Flexible",

        "Coaching",

        "Methodical approach",

        "Empathy",

        "Decisiveness",

        "Self assurance",

        "Clarity and concision"

    ]



    SALES_MANAGER = [

        "Communication skills",

        "Presence",

        "Ability to inspire",

        "Persuasive",

        "Strategic thinking",

        "Negotiation",

        "Presentation skills",

        "Problem solving",

        "Methodical approach",

        "Time management",

        "Storytelling",

        "Standards",

        "Tenacity",

        "Patience",

        "Curiosity",

        "Passionate"

    ]



    CUSTOMER_SERVICES = [

        "Communication skills",

        "Presence",

        "Social skills",

        "Coaching",

        "Flexible",

        "Ability to confront others",

        "Collaboration",

        "Ability to pivot",

        "Problem solving",

        "Accountable",

        "Clarity and concision",

        "Focused",

        "Empathy",

        "Proactive",

        "Willingness to learn",

        "Decisiveness"

    ]



    EMPLOYEE = [

        "Communication skills",

        "Objection handling",

        "Problem solving",

        "Social skills",

        "Collaboration",

        "Accountable",

        "Improve lives around you",

        "Negotiation",

        "Get the best from others",

        "Flexible",

        "Coaching",

        "Methodical approach",

        "Empathy",

        "Decisiveness",

        "Self assurance",

        "Clarity and concision"

    ]





    if candidate_type == 'Manager':

      skills_list = MANAGER

    elif candidate_type == 'Sales Manager':

      skills_list = SALES_MANAGER

    elif candidate_type == 'Customer Service':

      skills_list = CUSTOMER_SERVICES

    elif candidate_type == 'Employee':

        skills_list = EMPLOYEE

    else:

      skills_list = []





    skills_to_evalute = set()

    for skills in skills_list:

      skills_to_evalute.add(skills.strip().capitalize())



    return skills_to_evalute


def dynamic_create_csv(scenario_data,question_count,iteration,scenario_type,is_game=False,information=None,file_name=None,folder_path=None):
      try:
        response = {}
        response['Error'] = scenario_data.get('error')
        response['Intake Information'] = information
        response['Scenario Prompt Type'] = scenario_type
        response['Title'] = scenario_data.get('title')
        response['Context'] = scenario_data.get('description')

        # Add extra columns
        if is_game:
          const_columns = "Test Custum Prompt,is_dynamic_thread,Email Address List,Scenario Case,Is Single Select,"
          optional = ""
        else:
          const_columns = "Script Video Link,Video Script,Feedback Video Link,Feedback Video Script,Skill Domain,Candidate Type,Email Address List,Scenario Case,Area/Domain,Certificate Title,Client Name,is_dynamic_thread,Asker UI,start with user,Skills_list,"
          # if scenario_data.get('start_with_user') != None:
          #   const_columns += "start with user,"

          print(scenario_data.get('skills_list'), 'skills_list')
          # if scenario_data.get('skills_list'):
          #   const_columns += 'Skills_list,'


          optional = "Test Snippet Link,Max Test Allowed,Description Media,is learner path,Ted talks and HBR Case,is checkin type,is_email_type,Send only to email,Email Candidate,Certificate Description,source,image_url,rating,is_game_type,Competency Skill,Goals,Course,Industry,Experience Level,Background,Title UI,Description UI,is_micro,is_logged_in,Is Immersive,Is Transcript Only,is_pitch,Current news,Bot Name,User ID,Tab Category,Visual Tags,Page Name,"

        const_columns_list = const_columns.split(',')

        for col_name in const_columns_list:
            if len(col_name) == 0:
              continue
            response[col_name] = None


        extraa_fields = ""
        for index, initial_question in enumerate(scenario_data.get('orchestrated_conversation_details',{}).get('initial_messages',[])):
          response[f'Person {index}'] = initial_question
          extraa_fields += f'Person {index},'

        for index,question in enumerate(scenario_data.get('question_info', {})):
          response[str(index)] = question.get('question')
          extraa_fields += f'{index},'




        response['Scenario Case'] = "game" if is_game else 'dynamic_discussion'
        response['is_dynamic_thread'] = True
        if is_game:
          print(isinstance(scenario_data.get('game_questions'), list))
          try:
            response['Test Custum Prompt'] = format_game_custom_prompt(is_single_select=scenario_data.get('is_single_select'),
                                                                      questions=scenario_data.get('game_questions'),
                                                                      title=scenario_data.get('title'),
                                                                      description=scenario_data.get('description'),
                                                                      num_of_questions=question_count,
                                                                      static= True if scenario_type == 'static_game' else False
                                                                  )
          except Exception as e:
            print("failed to custom prompt", e)
            raise e

          if scenario_data.get('is_single_select') != None:
            response['Is Single Select'] = scenario_data.get('is_single_select')

        if scenario_data.get('skill_domain'):
          response['Skill Domain'] = scenario_data.get('skill_domain')

        if 'Candidate Type' in response and scenario_data.get('candidate_type'):
          response['Candidate Type'] = scenario_data.get('candidate_type')
        if 'Email Address List' in response and scenario_data.get('email_list'):
          response['Email Address List'] = scenario_data.get('email_list')
        if 'Area/Domain' in response:
          response['Area/Domain'] = scenario_data.get('area_domain') if scenario_data.get('area_domain') else 'General'
        if 'Certificate Title' in response and scenario_data.get('certificate_title'):
          response['Certificate Title'] = scenario_data.get('certificate_title')
        if 'Description Media' in response and scenario_data.get('description_media'):
          response['Description Media'] = scenario_data.get('description_media')
        print("scenario_data.get('start_with_user')", scenario_data.get('start_with_user'))
        if 'start with user' in response and scenario_data.get('start_with_user') != None :
          response['start with user'] = scenario_data.get('start_with_user')
        if 'Asker UI' in response and scenario_data.get('responder'):
          response['Asker UI'] = scenario_data.get('responder')
        if 'Skills_list' in response and scenario_data.get('skills_list'):
          response['Skills_list'] = scenario_data.get('skills_list')

        response['Email Address List'] = 'mail@coachbots.com'



        # adding optional fields
        for opt in optional.split(','):
          if len(opt) == 0:
              continue
          response[opt] = None

        if scenario_data.get('video_script'):
          response['Video Script'] = scenario_data.get('video_script')
        if scenario_data.get('script_video_link'):
          response['Script Video Link'] = scenario_data.get('script_video_link')
        if scenario_data.get('feedback_video_link'):
          response['Feedback Video Link'] = scenario_data.get('feedback_video_link')

        if scenario_data.get('feedback_script'):
          response['Feedback Video Script'] = scenario_data.get('feedback_script')



        df = pd.DataFrame([response])
        file_path = file_name if file_name else (f'bulk_game_{question_count}que.csv' if is_game else f'bulk_dynamic{question_count}_que.csv')
        if folder_path:
           file_path=f"{folder_path}/{file_path}"
        my_string = ""
        if not os.path.isfile(file_path):

            with open(file_path, 'a') as file:
                my_string = 'Error,Intake Information,Scenario Prompt Type,Title,Context,' + const_columns
                my_string += extraa_fields
                my_string += optional
                my_string = my_string[:len(my_string)-1] + "\n"


                file.write(my_string)
                my_string = my_string

        else:
            with open(file_path, 'r') as file:
                my_string = file.read().split('\n')[0]

        print(df.columns)
        print(len(df.columns))
        print('&'*100)

        print(my_string)
        print(len(my_string.split(',')))
        print('='*100)
        if (len(df.columns) == (len(my_string.split(',')))):
            df.to_csv(file_path, mode='a', index=False, header=False)
            print(f'Saved {iteration} scenarios in the csv.\n\n')
        else:
            print(f'Error in iterations {iteration}. could not save to csv')
            print("Error: Number of columns in the row doesn't match the table.\n\n")
      except Exception as e:
        print('*'*100)
        print(f'[Got Error Skipping this test]: {e}')
        raise e

def fetch_json_from_string(text):
    """
    Extracts and parses the first valid JSON object from a given string.

    :param text: str - A string that contains JSON data mixed with other text.
    :return: dict or None - Extracted JSON data or None if parsing fails.
    """
    try:
        # Regular expression to find JSON-like structures
        json_match = re.search(r'\{.*\}', text, re.DOTALL)

        if json_match:
            json_string = json_match.group(0)  # Extract JSON substring
            return json.loads(json_string)  # Parse JSON
        else:
            print("No valid JSON found in the text.")
            return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

def extract_information_dynamic_scenario(text,scenario_type,candidate_type="Manager",num_questions=3,targeted_skills=None,intake={},generate_video_script=False,video_script=None):

    """

    Extract information from a dynamic scenario text.



    Parameters:

    - text (str): The dynamic scenario text to extract information from.

    - is_dynamic (bool): Indicates whether the scenario is dynamic.

    - candidate_type (str): Type of candidate (e.g., 'Manager', 'Team Member').



    Returns:

    - tuple: A tuple containing title, description, question_info, rating, evaluation_skill_list, and orchestrated_conversation_details.



    Example:

    >>> extract_information_dynamic_scenario('Title: Test Title\nDescription: Test Description\nQuestion: What is your approach to leadership?\nRating: 5', is_dynamic=True, candidate_type='Manager')

    # Returns a tuple with extracted information from the dynamic scenario text.

    """

    if not text:
        raise ValueError("Invalid format. Text is empty.")

    try:


      data = fetch_json_from_string(text)


      if data:
        print('data', data)
        question_info = []
        manager_name = data['Person 0'].split(':')[0].strip()
        title = data['Title']
        description = data['Context']

        # for key, value in data.items():
        #   if key.isdigit():
        #     question_info.append({
        #       "question": value,
        #       "question_type": "subjective",
        #       "gpt_prompt_override": "",
        #       "subjective_answer": "",
        #       'question_for': manager_name
        #     })

        for i in range(1,2*num_questions):
              question = {
                      "question_type": "subjective",
                      "gpt_prompt_override": "",
                      "subjective_answer": ""
                  }
              if i % 2 == 0:
                  question['question'] = f"Respond as {manager_name}"
                  question['question_for'] = manager_name
              else:
                  question['question'] = "Please respond in order to continue"
                  question['question_for'] = 'user'
              if i == (2*num_questions-1):
                  question['question'] = "Conclude the discussion as a participant."



              question_info.append(question)

        test_main_context = description + data['Person 0']

        orchestrated_conversation_details = {
              "test_main_context": test_main_context,
              "test_user_persona": data['Candidate Type'].capitalize(),
              "objective": description,
              "initial_messages": [data['Person 0']]

          }


        infomation = {
          'title': title,
          'description': clean_text(description),
          'question_info': question_info,
          "candidate_type": data['Candidate Type'].capitalize(),
          'area_domain': "General",
          'certificate_title': data['Certificate Title'],
          'email_list': data['Email Address List'],
          'responder': data['Responder'],
          'orchestrated_conversation_details': orchestrated_conversation_details,
          'skill_domain': intake.get('Skill Domain', "")
        }


        if data.get('start with user') != "None":
          infomation['start_with_user'] = data['start with user']

        if data.get('skill_list'):
          infomation['skills_list'] = data['skill_list']

        infomation['feedback_script'] = feedback_video_script_template(
                                                        intake.get('Responder'),
                                                        intake.get('Asker'),
                                                        intake.get('Department'),
                                                        intake.get('Industry'),
                                                        intake.get('Objective'),
                                                        intake.get('Domain Skill'),
                                                        '',
                                                        True
                                                        )


        if video_script:
          infomation['video_script'] = video_script
        elif generate_video_script:
          infomation['video_script'] = generate_video_script_via(description)


        from pprint import pprint

        pprint(f'scenario info============================: {infomation}')


        return infomation, True


      text = text.replace('KLS', 'Skills')

      title_pattern = re.compile(r'Title\s*:\s*(.*?)\n', re.DOTALL)
      description_pattern = re.compile(r'Description\s*:\s*(.?)\nQuestions\s:', re.DOTALL)



      question_pattern = re.compile(r'Questions\s*:\s*(.+)')

      skill_pattern = re.compile(r'Skills:\s*(.+)')

      rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')

      if not description_pattern.findall(text):
        description_pattern = re.compile(r'Description\s*:\s*(.*?)\n', re.DOTALL)

      if not question_pattern.findall(text):

          question_pattern = re.compile(r'Question\s*:\s*(.+)')




      # Extracting information using regular expressions

      title_match = title_pattern.search(text)

      description_match = description_pattern.search(text)

      questions_match = question_pattern.search(text)

      rating_match = rating_pattern.search(text)
      skill_match = skill_pattern.search(text)



      # If title_pattern doesn't match, try to find the title as the lines before the description

      if not title_match:

          pattern = re.compile(r'^(?:Title\s*:\s*)?(?:"(.?)"|([^"\n]))\n*Description\s*:')

          title_match = pattern.search(text)

          if not title_match:

              raise ValueError("Invalid format. Unable to extract the title.")





      if not (title_match and description_match and question_pattern.findall(text)):

          raise ValueError("Invalid format. Unable to extract necessary information.")



      print('skill_match', skill_match)



      title = title_match.group(1).strip()

      description = clean_text(description_match.group(1).strip())

      questions = clean_text(questions_match.group(1).strip())

      rating = int(rating_match.group(1)) if rating_match else 0

      skill_list = clean_text(skill_match.group(1).strip()) if skill_match else None

      question_info = []



      test_main_context = description + questions

      orchestrated_conversation_details = {

              "test_main_context": test_main_context,

              "test_user_persona": candidate_type.capitalize(),

              "objective": description,

              "initial_messages": [questions]

          }



      skills_list_candidate = set()

      for item in get_skills(candidate_type.capitalize()):

              skills_list_candidate.add(item.capitalize())



      evaluation_skill_list = [skill.strip() for skill in sorted(skills_list_candidate)]



      if len(evaluation_skill_list) < 6:

          raise ValueError(f"Skills must have at least 4. Got:  {len(skills_list_candidate)}, {skills_list_candidate}")



      if len(evaluation_skill_list) > 8:


          evaluation_skill_list = evaluation_skill_list[:8]



      evaluation_skill_list = ','.join(evaluation_skill_list)



      manager_name = questions.split(':')[0].strip()

      for i in range(1,2*num_questions):

          question = {

                  "question_type": "subjective",

                  "gpt_prompt_override": "",

                  "subjective_answer": ""

              }



          if i % 2 == 0:

              question['question'] = f"Respond as {manager_name}"

              question['question_for'] = manager_name

          else:

              question['question'] = "Please respond in order to continue"

              question['question_for'] = 'user'



          if i == (2*num_questions-1):

              question['question'] = "Conclude the discussion as a participant."

          elif i == (2*num_questions-2):
                  question['question'] = f'Respond as {manager_name} with this exact statement, "Thats great! Can you please summarize and highlight any potential next step here. "'


          question_info.append(question)



      infomation = {

          'title': title,

          'description': description,

          'question_info': question_info,

          'skill_to_evaluate': evaluation_skill_list,

          'rating': rating,

          'orchestrated_conversation_details': orchestrated_conversation_details,
          'candidate_type': candidate_type,
          'responder': manager_name,
          'certificate_title': title,
          'email_list': 'mail@coachbots.com',
          'area_domain': 'General',
          'skill_domain': intake.get('Skill Domain', "")
      }

      if skill_list:
        infomation['skills_list'] = skill_list
      elif targeted_skills:
          infomation['skills_list'] = targeted_skills

      if video_script:
          infomation['video_script'] = video_script
      elif generate_video_script:
        infomation['video_script'] = generate_video_script_via(description)

      infomation['feedback_script'] = feedback_video_script_template(
                                                        intake.get('Responder'),
                                                        intake.get('Asker'),
                                                        intake.get('Department'),
                                                        intake.get('Industry'),
                                                        intake.get('Objective'),
                                                        intake.get('Domain Skill'),
                                                        '',
                                                        True
                                                        )

      from pprint import pprint

      pprint(f'scenario info============================: {infomation}')
      return infomation, True

    except Exception as e:
      question_info = []
      for i in range(1,2*num_questions):
              question = {
                      "question_type": "subjective",
                      "gpt_prompt_override": "",
                      "subjective_answer": ""
                  }
              if i % 2 == 0:
                  question['question'] = f"Error"
                  question['question_for'] = 'bot'
              else:
                  question['question'] = "Please respond in order to continue"
                  question['question_for'] = 'user'
              if i == (2*num_questions-1):
                  question['question'] = "Conclude the discussion as a participant."



              question_info.append(question)


      orchestrated_conversation_details = {
              "test_main_context": 'test_main_context',
              "test_user_persona": '',
              "objective": 'description',
              "initial_messages": ["person 0"]

          }

      return {'error': str(e), 'question_info': question_info, 'orchestrated_conversation_details': orchestrated_conversation_details}, False



def extract_game_type(text,scenario_type,candidate_type="Manager",num_questions=3,intake=None,video_script=None):
  data = fetch_json_from_string(text)
  if not data:
    raise ValueError("Invalid format. Unable to extract necessary information.")
  print(data['is_single_select'].strip().lower())
  information = {
      "title": data['title'],
      "description": data['description'],
      "game_questions": data['questions'],
      "is_single_select": data['is_single_select'].strip().lower() == 'true',
      "email_list": "mail@coachbots.com"
  }

  from pprint import pprint

  pprint(f'scenario info============================: {information}')

  return information, True


def scenario_create(llm_type,
                    scenario_type,
                    question_count,
                    iterations,
                    skill_count,
                    question_type,
                    personality_model,
                    startwithuser_type,
                    candidate_type,
                    objective,
                    industry,
                    department,
                    responder,
                    asker,
                    situation,
                    targeted_skills,
                    custom_information,
                    skill_domain,
                    generate_video_script,
                    video_script = None,
                    file_name=None,
                    folder_path=None):
                    
  is_pitch = False
  if scenario_type == 'pitch':
      question_count = 1
      scenario_type = 'normal_static'
      is_pitch = True

  if question_count <=3 and skill_count <2:
    skill_count = 2


  personality_model = None if personality_model == 'none' else personality_model
  scenario_types = [scenario_type]



  intake = {
      'Skill Domain': skill_domain,
      'Targeted Skills': targeted_skills,
      'Objective': objective,
      'Industry': industry,
      'Department': department,
      'Asker': asker,
      'Responder': responder,
      'Situation': situation
  }


  information = f"""
  Situation: {situation}\n
  Objective: {objective}\n
  Industry: {industry}\n
  Department: {department}\n
  Skill Domain: {skill_domain}\n
  Responder: {responder}\n
  Asker: {asker}\n
  Targeted Skills: {targeted_skills}\n
  """
  if scenario_type == 'dynamic_start_with_user':
    information = f"{information}\nStart with user: {startwithuser_type}\n CandidateType: {candidate_type}"

  if len(custom_information.strip()) > 0:
    information = custom_information

  print("="*100)
  print("Information:  \n",information)

  errors = []
  all_failed = False
  for iteration in range(iterations):
    if 'game' in scenario_type:
      prompt = get_game_prompt(
          industry=industry,
          informatioquestion_countn=information,
          num_of_questions=1 if scenario_type == 'dynamic_game' else question_count,
          question_type=question_type,
          candidate_type=candidate_type
      )
    else:
      prompt = get_scenario_prompt(scenario_type, information, skill_count, question_count,create_skill=len(targeted_skills)>0)
    print(f"iteration: {iteration + 1}, prompt_type: {scenario_type} Starts")
    print("="*100)
    print(f"prompt: {prompt}")
    print("="*100)
    for index in range(3):
      if llm_type == 'gemini':
        raw_scenario = gemini_completion(prompt)
      else:
        raw_scenario = anthropic_completion(prompt)

      print(f"raw_scenario: {raw_scenario}")

      try:
        scenario_information_data = {}
        if 'game' in scenario_type:
          scenario_information_data, success = extract_game_type(text=raw_scenario,scenario_type=scenario_type,num_questions=question_count,intake=intake,generate_video_script=generate_video_script,video_script=video_script)
          if not success:
            raise ValueError(f"Got error: {scenario_information_data.get('error')}")
          
          if file_name:
            dynamic_create_csv(
                scenario_data=scenario_information_data,
                question_count=question_count,
                iteration=iteration,
                scenario_type=scenario_type,
                is_game=True,
                information=intake,
                file_name=file_name,
                folder_path= folder_path
            )
          else:
            dynamic_create_csv(
                scenario_data=scenario_information_data,
                question_count=question_count,
                iteration=iteration,
                scenario_type=scenario_type,
                is_game=True,
                information=intake,
                folder_path= folder_path
            )
        elif "static" in scenario_type:
          scenario_information_data, success = extract_information_static(raw_scenario,
                                     iteration+1,
                                     question_count,
                                     scenario_type,
                                     candidate_type,
                                     is_pitch=is_pitch,
                                     personality_model=personality_model,
                                     intake=intake,generate_video_script=generate_video_script,
                                     video_script=video_script
                                      )
          if not success:
            raise ValueError(f"Got error: {scenario_information_data.get('error')}")

          if file_name:
            create_csv(scenario_information_data,question_count,iteration,scenario_type,information=intake,file_name=file_name,folder_path=folder_path)
          else:
            create_csv(scenario_information_data,question_count,iteration,scenario_type,information=intake,file_name=None,folder_path=folder_path)

        else:
          scenario_information_data,success = extract_information_dynamic_scenario(text=raw_scenario,
                                               scenario_type=scenario_type,
                                               num_questions=question_count,
                                               targeted_skills=targeted_skills if len(targeted_skills)>0 else None,
                                               intake=intake,
                                               generate_video_script=generate_video_script,
                                               video_script=video_script)


          if not success:
            raise ValueError(f"Got error: {scenario_information_data.get('error')}")

          if file_name:
            dynamic_create_csv(scenario_information_data,question_count,iteration,scenario_type,information=intake,file_name=file_name,folder_path=folder_path)
          else:
            dynamic_create_csv(scenario_information_data,question_count,iteration,scenario_type,information=intake,folder_path=folder_path)

        print(f"iteration: {iteration+1} Ends")
        print("="*100)
        break
      except Exception as e:
            # raise e
            print('*'*100)
            print(f'[Got Error Skipping this test for {index+1}]: {e}')
            if index+1 == 3:
              errors.append(f"Failed to create iter {iteration+1} for retry {index+1}, error: {e}  info: {information}")
              all_failed = True
              if "static" in scenario_type:
                if file_name:
                  create_csv(scenario_information_data,question_count,iteration,scenario_type,information=intake,file_name=file_name,folder_path= folder_path)
                else:
                  create_csv(scenario_information_data,question_count,iteration,scenario_type,information=intake,file_name=None,folder_path= folder_path)

              else:
                if file_name:
                  dynamic_create_csv(scenario_information_data,question_count,iteration,scenario_type,file_name=file_name,information=intake,folder_path= folder_path)
                else:
                  dynamic_create_csv(scenario_information_data,question_count,iteration,scenario_type,file_name=None,information=intake,folder_path= folder_path)

            initialize_csv('Failed Scenarios.csv', ['information', 'raw Scenario', 'error'])
            append_to_csv('Failed Scenarios.csv', [information, raw_scenario, f"Failed to create iter {iteration+1} for retry {index+1}, error: {e}"])

  return True if len(errors) == 0 else False, errors

def get_candidate_type(role_key):
    mapping = {
        "team-manager": "Employee",
        "sales-customer": "Sales Manager",
        "customer-sales": "Customer Service",
        "manager-team": "Manager"
    }
    return mapping.get(role_key, "Unknown")

# def initialize_csv(file_name, fields= ["Test Code","TEST TITLE","Client Name", "Test Type","Report Link", "Success" ,"Error"]):
#     # from google.colab import drive
#     # import os

#     # drive.mount('/content/drive')

#     # # Create a folder in Drive
#     # folder_path = '/content/drive/MyDrive/Collab Downloads'
#     # os.makedirs(folder_path, exist_ok=True)

#     # file_path = os.path.join(folder_path, file_name)

#     # Check if file already exists
#     file_exists = os.path.isfile(file_name)

#     # Open the file in append mode and write header if not exists
#     with open(file_name, mode='a', newline='') as file:
#         writer = csv.writer(file)
#         if not file_exists:
#             writer.writerow(fields)



# Function to append a row to the CSV file
# def append_to_csv(file_name, row):
#     folder_path = '/content/drive/MyDrive/Collab Downloads'

#     file_path = os.path.join(folder_path, file_name)
#     with open(file_name, mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(row)



def create_upload_test_scenario(llm_type,
                    scenario_type,
                    question_count,
                    iterations,
                    skill_count,
                    question_type,
                    personality_model,
                    startwithuser_type,
                    candidate_type,
                    objective,
                    industry,
                    department,
                    responder,
                    asker,
                    situation,
                    targeted_skills,
                    custom_information,
                    skill_domain,
                    generate_video_script,
                    file_name,
                    email,
                    password,
                    domain,
                    auth,
                    video_script = None,

                                ):

  # scenairo creation
  test_type = 'dynamic'
  report_file_name = f'Bulk Report Testing- {file_name}.csv'
  if 'static' in scenario_type:
    file_name = f'bulk_static_{question_count}_que-{file_name}.csv'
    test_type = 'static'

  elif 'game' in scenario_type:
    file_name = f'bulk_game_{question_count}_que-{file_name}.csv'
  else:
    file_name = f'bulk_dynamic_{question_count}_que-{file_name}.csv'


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
                    asker=asker,
                    responder=responder,
                    situation=situation,
                    targeted_skills=targeted_skills,
                    custom_information=custom_information,
                    skill_domain=skill_domain,
                    generate_video_script=generate_video_script,
                    video_script=video_script,
                    file_name=file_name
                )

  if len(errors)>0:
    return False, errors



  with open(file_name, 'rb') as f:
    try:
      automated_scenario = AutomatedScenarios(auth)
      automated_scenario.create_and_attempt_test(f,email, password, domain,test_type, report_file_name)
      
    except Exception as e:
      return False, [f'❌ Failed to Upload and test, Reason: {e}']

  try:
      os.remove(file_name)
  except OSError as e:
      # Optional: log or handle if deletion fails
      print(f"⚠ Failed to delete file {file_name}: {e}")

  return True, []
