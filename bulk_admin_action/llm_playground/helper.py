from datetime import datetime
import os
import shutil
from string import Template
import zipfile

from docx import Document

from coachbots_app.utils.llm import anthropic_completion, gemini_completion


def process_files(df, filename, llm_type='gemini'):
    output_folder = "word_files"
    os.makedirs(output_folder, exist_ok=True)
    org_columns = df.columns
    print("ABX")
    for index, row in df.iterrows():
        row_identifier = f"file-row-{index+1}"
      

        template = Template(row['Prompt'])
        prompt = template.safe_substitute(row)
        print(f"   ➤ Prompt: {prompt}")

        output = gemini_completion(prompt) if llm_type == 'gemini' else anthropic_completion(prompt)
        df.at[index, 'Output'] = output

        doc = Document()
        doc.add_heading(f'Row {index + 1}', level=1)

        for col in df.columns:
            doc.add_paragraph(col, style='Intense Quote')
            doc.add_paragraph(str(df.at[index, col]))

        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in row_identifier[:50])
        doc_path = os.path.join(output_folder, f"{safe_title}.docx")
        doc.save(doc_path)
        print(f"   📄 Saved Word: {safe_title}.docx")


    csv_filename = None

    csv_filename = f"updated_{filename}.csv"
    df.to_csv(csv_filename, index=False)
    print(f"\n💾 CSV saved: {csv_filename}")

    zip_filename = None


    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{filename[:10]}_bundle_{timestamp}.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        if csv_filename:
            zipf.write(csv_filename)
        for root, _, files_list in os.walk(output_folder):
            for file in files_list:
                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=file)
    print(f"📦 ZIP created: {zip_filename}")

    if csv_filename and os.path.exists(csv_filename):
        os.remove(csv_filename)
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    print("🧹 Cleanup complete.")
    
    return zip_filename  # Return ZIP file path