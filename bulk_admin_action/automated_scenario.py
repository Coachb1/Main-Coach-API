import base64
import csv
from enum import auto
from importlib.metadata import files
import json
import os
import random
import datetime
import time

from django.conf import settings
import requests
from settings import BACKEND

base_url = BACKEND


key = os.getenv("dev_key")
secret = os.getenv("dev_secret")
slack_webhook_url = os.getenv("SLACK_MESSAGE_WEBHOOK_URL")
user_uid = '52927aeb-854c-4573-90c2-bcaf09e6792f'

global_file_name = f'Bulk Report Testing - {datetime.datetime.today().strftime("%Y-%m-%d")}.csv'

sample_answers =  [
        "On-time completion of the new office building project. This was a complex project with a tight deadline, but I was able to successfully manage the team and ensure that the project was completed on time and on budget.",
        "Dealing with unexpected weather delays. We experienced a number of unexpected weather delays during the construction of the office building. I was able to manage these delays by adjusting the project schedule and resequencing tasks.",
        "Continue to focus on communication and teamwork. I will continue to focus on communicating effectively with my team members and working collaboratively to achieve our goals."
        ]


errors = []
messages = []


class AutomatedScenarios:
    def __init__(self, token):
      self.token = token
      self.base_url = base_url

    
    def generate_question_response(self,title,description,question,is_game=False, previous_conv=None):
        raw_question = question
        if is_game:
          if isinstance(question, str):
            question = json.loads(question)
            options = question['content']['options'].keys()
            resp = random.choice(list(options))
            print(f"Response for question - {raw_question} : ",resp)
            return resp

        else:
          instruction = f'''Title: {title}
                          Description: {description}
                          According to the information provided, please respond to the question below in "a minimum of 30 words and a maximum of 50 words". Maintain a professional tone and respond *directly and insightfully to the question, avoiding small talk or vague confirmations like “Okay” or “Please ask your questions. etc.”
                      '''
          print('previous conv', previous_conv)
          if previous_conv != None:
            question = f"Previous Conversation: {previous_conv}\n\n{question}"
          else:
            question = f"Question: {question}"

          for i in range(3):
            try:
              resp = requests.post(f'{self.base_url}/api/v1/documents/get-prompt-response/',data=json.dumps({
                          'prompt': question,
                          'instruction': instruction,
                      }), headers={
                'Content-Type': 'application/json'
              })
              # resp = requests.get(f'{base_url}/api/v1/documents/get-prompt-response/?prompt={question}&instruction={instruction}')
              print(resp.text)
              resp.raise_for_status()
              resp =  resp.json()
              print(f"Response for question - {raw_question} : ",resp['response_text'])
              return resp['response_text']
            except Exception as e:
              print(e)
              if i+1 == 3:
                raise e
              time.sleep(3)


    def upload_file(self):
      url = f"{self.base_url}/api/v1/documents/upload/"
      file_path = "response.mp3"
      user_id = user_uid

      # Construct the form data
      form_data = {
          "owner_type": "user",
          "owner_id": user_id,
          "display_name": "automated samplel response",
          "doc_type": "AUDIO_ANSWER",
          "actions_pipeline[0]action": "transcribe",
          "actions_pipeline[0]context": "null"
      }

      # Open the file and add it to the form data
      with open(file_path, 'rb') as file:
          files = {'file': (file.name, file, 'multipart/form-data')}
          response = requests.post(url,headers=self.get_quick_headers(), data=form_data, files=files)

      # Handle response
      if response.status_code == 201:
          print("File uploaded successfully")
          response = response.json()
          print(response)
          return response
      else:
          print("Error:", response.text)






    def get_doc_url(self,doc_id):
      url = f"{self.base_url}/api/v1/documents/{doc_id}/url"
      response = requests.post(url,headers=self.get_quick_headers())
      response = response.json()
      # print(response)
      return response


    def text_to_speech(self,text):
      doc = requests.get(f"{self.base_url}/api/v1/test-responses/get-text-to-speech/?text={text}")
      with open('response.mp3', 'wb') as f:
        f.write(doc.content)

    def get_text_audio_url(self,text):
      self.text_to_speech(text)


      doc = self.upload_file()
      doc_id = doc['uid']

      doc_url = self.get_doc_url(doc_id)['url']
      print('Doc URL :',doc_url)
      return doc_url


    def send_slack_message(self,data):
        url = slack_webhook_url

        # data.update({"message":"Testing slack webhook"})

        payload = json.dumps({
            "text": json.dumps(data, default=str)
        })

        headers = {
            'Content-type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        try:
            response.raise_for_status()
        except Exception as e:
            print("failed to send to slack data: %s, err: %s", data, str(e))


    def create_basic_auth_token(self,key: str, secret: str) -> str:
        return base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode()


    def get_headers(self, basic_auth_token):
            return {
                "Authorization": basic_auth_token
            }

    def get_quick_headers(self):
        return self.get_headers(self.token)

    def create_or_get_account(self):
        try:
            response = requests.post(self.base_url + '/api/v1/accounts/', json={
                    "user_context": {
                        "name": "test-user",
                        "role": "member",
                        "user_attributes": {
                            "tag": "deepchat_profile",
                            "attributes": {
                                    "username": "test-user611",
                                }
                        }
                    },
                    "identity_context": {
                        "identity_type": "deepchat_unique_id",
                        "value": f"test-user611"
                    }
                },
                headers=self.get_quick_headers()
            )

            response =  response.json()
            user_uid = response['uid']
            return response
        except Exception as e:
            errors.append("Error in creating account: " + str(e.args))


    def get_test_from_code(self,code='Q7JS0OL'):
        try:
            response = requests.get(self.base_url + f'/api/v1/tests/?test_code={code}', headers=self.get_quick_headers())
            if response.status_code == 200:
                messages.append("Got test from code successfully")
            else:
                errors.append("Error in getting test from code: ")
            print(response.json())
            return response.json()
        except Exception as e:
            errors.append("Error in getting test from code: " + str(e.args))
            return None

    def cancel_previous_session(self):
        try:
            response = requests.get(self.base_url + "/api/v1/test-attempt-sessions/cancel-test-sessions/", json={
                    "user_id": user_uid
                    },  headers=self.get_quick_headers()
            )

            if response.status_code == 200:
                messages.append("Cancelled previous session successfully")
            else:
                errors.append("Error in cancelling previous session: ")

            response =  response.json()
            print(response)
            return response
        except Exception as e:
            errors.append("Error in cancelling previous session: " + str(e.args))

    def create_test_session(self, test_id, participant_id):
        try:
            response = requests.post(self.base_url + f'/api/v1/test-attempt-sessions/', json={
                    "test_id": test_id,
                    "participant_id": participant_id
                },
                headers=self.get_quick_headers()
            )

            if response.status_code == 201:
                messages.append("Created test session successfully")
            else:
                errors.append("Error in creating test session: ")

            # print("create test session status code: ", response.status_code)

            response =  response.json()
            return response
        except Exception as e:
            print(e)
            errors.append("Error in creating test session: " + str(e.args))


    def submit_response(self, test_attempt_session_id, question_id, response_text, response_url):
        try:
            response = requests.post(self.base_url + f'/api/v1/test-responses/', json={
                    "test_attempt_session_id": test_attempt_session_id,
                    "question_id": question_id,
                    "response_text": response_text,
                    "response_file": response_url
                },
                headers=self.get_quick_headers()
            )

            if response.status_code == 201:
                messages.append("Submitted response successfully")
            else:
                errors.append("Error in submitting response: ")
            # print("submit response status code: ", response.status_code)

            response =  response.json()
            print(response)
            return response
        except Exception as e:
            print(e)
            errors.append("Error in submitting response: " + str(e.args))


    def get_report_url(self,session_id, interaction_id,report_type='interactionSessionReport'):
        try:
            response = requests.post(self.base_url + f'/api/v1/frontend-auth/get-report-url/', json={
                    "user_id": user_uid,
                    "report_type": report_type,
                    "session_id": session_id,
                    "interaction_id": interaction_id,
                    "test_attempt_session_id": session_id,
                },
                headers=self.get_quick_headers()
            )

            if response.status_code == 200:
                messages.append("Got Report url successfully")
            else:
                errors.append("Error in getting report url: ")

            response =  response.json()
            # print("GET REPORT URL RESPONSE : ",response)

            return response
        except Exception as e:
            errors.append("Error in getting report url: " + str(e.args))


    def send_report_email(self, test_attempt_session_id, report_url):
        try:
            response = requests.post(self.base_url + f'/api/v1/test-attempt-sessions/send-report-email/', params={
                    "test_attempt_session_id": test_attempt_session_id,
                    "report_url": report_url,
                    "is_whatsapp": False
                },
                headers=self.get_quick_headers()
            )

            if response.status_code == 200:
                messages.append("Sent report email successfully")
            else:
                errors.append("Error in sending report email: ")

            response =  response.json()
            print(response)
            return response
        except Exception as e:
            errors.append("Error in sending report email: " + str(e.args))

    # print(get_headers(create_basic_auth_token(key, secret)))

    def attempt_test(self,test, is_audio=False):
        self.create_or_get_account()

        # test = get_test_from_code(test_code)

        test_id = test['results'][0]['uid']
        questions = test['results'][0]['questions']
        no_of_questions = len(questions)

        self.cancel_previous_session()
        session = self.create_test_session(test_id, user_uid)
        print(session)
        session_id = session['uid']

        print('Session created with id: ', session_id)
        # session_id = '6679a137-58fd-4ca0-ab42-ffb2c7e6e1f5'

        start = time.time()
        for i in range(no_of_questions):
            # answer = sample_answers[i]
            answer = self.generate_question_response(test['results'][0]['title'],test['results'][0]['description'],questions[i]['question'])
            # if i + 1 == no_of_questions:
            file_url = ""
            if is_audio:
                file_url = self.get_text_audio_url(answer)
                answer = ""

            print(f"####### answer: {answer},,,, file_url: {file_url}")
            self.submit_response(session_id, questions[i]['uid'], answer, file_url)
            """ else:
                threading.Thread(target=submit_response, args=(session_id, questions[i]['uid'], answer, "")).start() """
        end = time.time()
        print(f"Time taken to submit all responses", end - start, " seconds")
        messages.append("Time taken to submit all responses " + ": " + str(end - start) + " seconds")

        report_type = "interactionSessionReport"
        if test['results'][0]['scenario_case'] == "psychometric":
          report_type = "personalityPsychomatricReport"
        report = self.get_report_url(session_id, test_id, report_type=report_type)
        print(f"Report URL: {report['url']}")
        messages.append("Report url: " + report['url'])

        # time.sleep(20)
        self.send_report_email(session_id, report['url'])
        return report['url'], session_id



    def attempt_dynamic_test(self,test, is_audio=False):
        self.create_or_get_account()

        if test['results'][0]['test_type'] not in ["orchestrated_conversation", "dynamic_discussion", "dynamic_discussion_thread"]:
          print("!!U!Un!Uns!Unsu!Unsup!Unsupp!Unsuppo!Unsuppor!Unsupport!Unsupporte!Unsupported!Unsupported Test type ")

        test_id = test['results'][0]['uid']
        questions = test['results'][0]['questions']
        no_of_questions = len(questions)

        print("No of questions: ", no_of_questions)
        print("Questions: ", questions)
        print("scenario_case", test['results'][0]['scenario_case'])


        self.cancel_previous_session()
        session = self.create_test_session(test_id, user_uid)
        session_id = session['uid']
        print('Session created with id: ', session_id, session)
        # session_id = '6679a137-58fd-4ca0-ab42-ffb2c7e6e1f5'

        question_text = ""

        start = time.time()
        previous_conv = ""

        if test['results'][0]['scenario_case'] == 'game':
          question_text = session['next_question_text']
          print(f'question_text game :  {question_text}')
          while True:
            answer = self.generate_question_response(test['results'][0]['title'],test['results'][0]['description'],question_text,is_game=True)
            resp = self.submit_response(session_id, "sdkfj", answer, "")
            print(f'resp:{resp}')
            question_text = resp['question_text']
            if 'end_message' in question_text:
              question_text = json.dumps(resp['question_text'])

              break
        else:
          question_text = questions[0]['question']

          orchestrated_conversation_details = test['results'][0]['orchestrated_conversation_details']
          print('orc conv', orchestrated_conversation_details)
          for i in range(no_of_questions):
              if i == 0:
                if orchestrated_conversation_details.get('start_with_user', None) == None:
                    question_text = "\n".join(orchestrated_conversation_details['initial_messages'])
                    previous_conv += f"{question_text}\n"

              if questions[i]['question_for'] == "user":

                  answer = self.generate_question_response(test['results'][0]['title'],test['results'][0]['description'],question_text,previous_conv=previous_conv)
                  file_url = ""
                  previous_conv += f"User: {answer}\n"
                  if is_audio:
                      file_url = self.get_text_audio_url(answer)
                      answer = ""
                  self.submit_response(session_id, questions[i]['uid'], answer, file_url)
              else:
                  resp = self.submit_response(session_id, questions[i]['uid'], "", "")
                  question_text = resp['response_text']
                  previous_conv += f"{questions[i]['question_for']}: {question_text}\n"

        end = time.time()
        print(f"Time taken to submit all responses", end - start, " seconds")
        messages.append("Time taken to submit all responses " + ": " + str(end - start) + " seconds")

        if test['results'][0]['scenario_case'] != 'game':
          test_type = test['results'][0]['test_type']
          report_type =  "dynamicDiscussionReport"

          if test_type == "orchestrated_conversation":
            report_type = "meetingAnalysisReport"
          report = self.get_report_url(session_id, test_id,report_type)

          print(f"Report URL: {report['url']}")
          messages.append("Report url: " + report['url'])

          # time.sleep(20)
          self.send_report_email(session_id, report['url'])
          return report['url'], session_id

        else:
          return question_text, session_id


    def to_batches(self, data, batch_size):
        batches = []
        for i in range(0, len(data), batch_size):
            batches.append(data[i:i + batch_size])
        return batches

    # Function to check if the CSV file exists and write header if not
   

    def get_test_by_filter(self, filter_params:dict):


        url = f"{self.base_url}/api/v1/tests/get-tests-by-filter/"
        headers=self.get_quick_headers()
        print(self.base_url)
        try:
          response = requests.request("GET",url , headers=headers, params=filter_params)
          print(response)
          print(f"get test by filter {response.json()}")
          return response.json()
        except Exception as e:
          print(f"failed to get test by filter: {e}")



    def simulate_scenarios(self, test_codes,report_csv, IS_AUDIO=True):
      for code in test_codes:
          test = self.get_test_from_code(code)
          print("GET TEST FROM CODE : ",test)

          test_data = []
          session_id = ''

          if test is None:
            print(f"!!!!!!!! EROOR: Invalid Test CODE : {code}")
            append_to_csv(report_csv,[code,"","","", "",False, "Invalid test code","", ""])
            continue
          if len(test['results']) == 0:
            print(f"!!!!!!!! EROOR: Invalid Test CODE : {code}")
            append_to_csv(report_csv,[code,"","","","", False, "Invalid test code","", ""])
            continue
          print("Test details : ",test)
          UNSUPPORTED_TEST_TYPES= ["mcq","dynamic_mcq","coaching"]
          if test['results'][0]['test_type'] in UNSUPPORTED_TEST_TYPES:
            print("!!!!! ERROR : Unsupported Test type.")
            append_to_csv(report_csv, [code,"","","","", False, "Unsupported test type","",""])
            continue

          test_data.append(code)
          test_data.append(test['results'][0]['title'])
          test_data.append(test['results'][0]['client_name'])
          test_data.append(test['results'][0]['test_type'])


          if test['results'][0]['test_type'] in ["orchestrated_conversation", "dynamic_discussion", "dynamic_discussion_thread"]:
              print(f'*************** Attempting TEST: {code} in TEXT MODE ***************')
              try:
                url, session_id = self.attempt_dynamic_test(test,IS_AUDIO)
                test_data.append(url)
              except Exception as e:
                print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
              print(f"",end="\n\n\n\n")

              # if test['results'][0]['interaction_mode'] == 'any':
              #   print(f'*************** Attempting TEST: {code} in AUDIO MODE ***************')
              #   try:
              #     url = attempt_dynamic_test(test,True)
              #     test_data.append(url)
              #   except Exception as e:
              #     print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
              #   print(f"",end="\n\n\n\n")
          else:
              print(f'****************** Attempting TEST: {code} in TEXT MODE ************************** ')
              try:
                url, session_id = self.attempt_test(test,IS_AUDIO)
                test_data.append(url)
              except Exception as e:
                print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
              print(f"",end='\n\n\n\n')

              # if test['results'][0]['interaction_mode'] == 'any':
              #   print(f'****************** Attempting TEST: {code} in AUDIO MODE ************************** ')
              #   try:
              #     url = attempt_test(test,True)
              #     test_data.append(url)
              #   except Exception as e:
              #     print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
              #   print(f"",end='\n\n\n\n')

          test_data.append(True)
          test_data.append(None)
          if test['results'][0]['test_type'] in ["orchestrated_conversation", "dynamic_discussion", "dynamic_discussion_thread"]:
            report = self.get_report(session_id, 'dynamic',report_only=True)
            test_data.append(report.get('feedback_video_script'))
            test_data.append(report.get('video_script'))
          else:
            report = self.get_report(session_id, 'test',report_only=True)
            test_data.append(report.get('feedback_video_script'))
            test_data.append(report.get('video_script'))
          print(test_data)
          append_to_csv(report_csv,test_data)


    def generate_test(self, TEST_CODES, IS_AUDIO, file_name):
      initialize_csv(file_name)
      UNSUPPORTED_TEST_TYPES= ["mcq","dynamic_mcq","coaching"]
      session_ids = []

      for code in TEST_CODES:
        test_data = []
        test = self.get_test_from_code(code)
        print(test)
        if test is None:
            print(f"!!!!!!!! EROOR: Invalid Test CODE : {code}")
            append_to_csv(file_name,[code,"","","", "", False, "Invalid test code", "",""])
            continue
        if len(test['results']) == 0:
          print(f"!!!!!!!! EROOR: Invalid Test CODE : {code}")
          append_to_csv(file_name,[code,"","","","", False, "Invalid test code", "", ""])
          continue
        print("Test details : ",test)

        if test['results'][0]['test_type'] in UNSUPPORTED_TEST_TYPES:
          print("!!!!! ERROR : Unsupported Test type.")
          append_to_csv(file_name, [code,"","","", "",False, "Unsupported test type","", ""])
          continue


        test_data.append(code)
        test_data.append(test['results'][0]['title'])
        test_data.append(test['results'][0]['client_name'])
        test_data.append(test['results'][0]['test_type'])

        session_id = ''
        if test['results'][0]['test_type'] in ["orchestrated_conversation", "dynamic_discussion", "dynamic_discussion_thread"]:
            print(f'*************** Attempting TEST: {code} in TEXT MODE ***************')
            try:
              url,session_id = self.attempt_dynamic_test(test,False)
              session_ids.append(session_id)
              test_data.append(url)
            except Exception as e:
              print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
              raise e
            print(f"",end="\n\n\n\n")

            # if (test['results'][0]['interaction_mode'] == 'any' and IS_AUDIO) and test['results'][0]['scenario_case'] != 'game':
            #   print(f'*************** Attempting TEST: {code} in AUDIO MODE ***************')
            #   try:
            #     url,session_id = attempt_dynamic_test(test,True)
            #     session_ids.append(session_id)

            #     test_data.append(url)
            #   except Exception as e:
            #     print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
            #   print(f"",end="\n\n\n\n")
            # else:
            #   test_data.append("")
        else:
            print(f'****************** Attempting TEST: {code} in TEXT MODE ************************** ')
            try:
              url, session_id = self.attempt_test(test,False)
              session_ids.append(session_id)
              test_data.append(url)
            except Exception as e:
              print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
              raise e
            print(f"",end='\n\n\n\n')
            # if test['results'][0]['interaction_mode'] == 'any' and IS_AUDIO:
            #   print(f'****************** Attempting TEST: {code} in AUDIO MODE ************************** ')
            #   try:
            #     url,session_id = attempt_test(test,True)
            #     session_ids.append(session_id)

            #     test_data.append(url)
            #   except Exception as e:
            #     print(f"!!!!!!!!!!!!!! Failed To attempt TEST: {code}, REASON: {e}")
            #   print(f"",end='\n\n\n\n')
            # else:
            #   test_data.append("")

        test_data.append(True)
        test_data.append(None)
        if test['results'][0]['test_type'] in ["orchestrated_conversation", "dynamic_discussion", "dynamic_discussion_thread"]:
          report = self.get_report(session_id, 'dynamic',report_only=True)
          test_data.append(report.get('feedback_video_script'))
          test_data.append(report.get('video_script'))
        else:
          report = self.get_report(session_id, 'test',report_only=True)
          test_data.append(report.get('feedback_video_script'))
          test_data.append(report.get('video_script'))



        print(test_data)
        append_to_csv(file_name,test_data)

      print("CSV file written successfully!")
      print(errors)

      return session_ids

    def download_file(file_name, is_drive=True):
    #   from google.colab import files
      import shutil
      if is_drive:
        # Path to file in Google Drive
        gdrive_path = f'/content/drive/MyDrive/Collab Downloads/{file_name}'

        # Copy to /content/
        shutil.copy(gdrive_path, f'/content/{file_name}')

        # Download to your local machine
        files.download(f'/content/{file_name}')
      else:
        files.download(file_name)



    def create_test(self, information, creator_user_id=None, use_anthropic=False, flavour='normal',is_micro=True, previous_session_id=None, custom_prompt=None):
      for _ in range(3):
        try:
          url = f"{self.base_url}/api/v1/tests/get_or_create_test_scenarios_by_site/"
          data = {
              "url": None,
              "mode": "A",
              "access_token": self.token,
              "creator_user_id": creator_user_id,
              "flavour": flavour,
              "is_micro": is_micro,
              "information":json.dumps({'title': "",'data':{'information':information}}),
              "use_anthropic": use_anthropic,
              "previous_session_id": previous_session_id,
              "custom_prompt": custom_prompt

          }

          headers = {
          'Content-Type': 'application/json',
          **self.get_quick_headers()
        }

          response = requests.post(url, data=json.dumps(data), headers=headers)
          print(response.json())

          print(response.json()[0]['test_code'])
          return response.json()
        except Exception as e:
          print(e)
          raise e
          continue


    def get_report(self, session_id, test_type, report_only=False):
      url = f"{self.base_url}/api/v1/test-attempt-sessions/{session_id}/"
      if test_type == 'test':
        url+= 'report-data/'
      elif test_type == 'dynamic':
        url += 'meeting-report-data/'

      headers = {
      'Content-Type': 'application/json',
      'Authorization': f'Basic {auto}'
    }

      response = requests.get(url,headers=self.get_quick_headers())
      print(response.json())
      if response.ok:
        data = response.json()
        if report_only:
          return data['data']
        if test_type == 'test':
          r = {
          'Title': data['data']['title'],
          'description': data['data']['test_description'],
          'question And Answer': data['data']['qa'],
          'skills_graph_data': data['data']['skills_graph_data'],
          'skills_explanation': data['data']['skills_explanation'],
          'feedback_summary': data['data']['feedback_summary'],
          'skill_summary': data['data']['skill_summary'],
          'culture_graph_data': data['data']['culture_graph_data'],
          'culture_skills_explanation': data['data']['culture_skills_explanation'],
          'competency_data': data['data']['competency_data']
        }

        elif test_type == 'dynamic':
          r ={
          'Title': data['data']['title'],
          'description': data['data']['test_description'],
          'objective': data['data']['objective'],

          'question And Answer': data['data']['chat_conversation'],
          'skills_graph_data': data['data']['skills_rating'],
          'skills_explanation': data['data']['skills_explanation'],
          'feedback_summary': data['data']['feedback_summary'],
          'skill_summary': data['data']['skill_summary'],
          'culture_graph_data': data['data']['culture_skills'],
          'culture_skills_explanation': data['data']['culture_skills_explanation'],
          'competency_data': data['data']['competency_data']
        }

        report_data = ''
        for key, value in r.items():
          report_data += f'{key}: {value}\n'
        return report_data

      else:
        raise Exception('Failed to get report data')

    def create_and_attempt_test(self,csv_file,email,password,domain,test_type,file_name):
      uploaded_test = upload_scenario(csv_file,email,password,domain,test_type)
      if not uploaded_test['success']:
        raise Exception(f"Failed to generate all test: {uploaded_test['errors']}")

      test_codes= []
      for value in uploaded_test['file_content'].split('\n'):
        title = value.split(':')[0]
        test_code = value.split(',')[-1].strip()
        print(title, test_code)
        if test_code.startswith('Q'):
          test_codes.append(test_code)

      print(test_codes)

      self.generate_test(test_codes, False,file_name=file_name)


def initialize_csv(file_name, fields=None):
    if fields is None:
        fields = ["Test Code", "TEST TITLE", "Client Name", "Test Type", 
                  "Report Link", "Success", "Error", "Feedback script", "Video Script"]

    file_path = os.path.join('media', file_name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Ensure 'media/' exists

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(fields)


    # Function to append a row to the CSV file
def append_to_csv(file_name, row):
    folder_path = 'media'  # Removed leading slash to keep it relative
    file_path = os.path.join(folder_path, file_name)

    # Ensure the folder exists
    os.makedirs(folder_path, exist_ok=True)

    # Append the row
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(row)
def upload_scenario(myfile, email, password, domain, test_type='static'):
        
        url = f"{base_url}/api/upload-scenarios/"

        # Form data
        data = {
            "email": email,
            "password": password,
            "client_domain_prefix": domain,
            "test_type": test_type
        }

        # File upload
        files = {
            "myfile": myfile  # should be a file-like object or tuple (filename, fileobj, mimetype)
        }

        try:
            response = requests.post(url, data=data, files=files)
            print(response.text)
            response.raise_for_status()  # Raise error for bad responses
            print("✅ Upload successful!")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Upload failed: {e}")
            return {"error": str(e)}