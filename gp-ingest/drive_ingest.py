from langchain_google_community import GoogleDriveLoader
#from langchain_chroma import Chroma
#from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm
import json
import os
import pickle
import re
import langchain
import io
from langchain_core.documents import Document

langchain.verbose = True

SCOPES = ['https://www.googleapis.com/auth/drive.readonly',
          'https://www.googleapis.com/auth/documents'
          ]
CACHE_FILE = 'google_drive_cache.pkl'
FOLDER_ID = '1uUtOtxon1VdnZ25xjbRTqnDL-IX8q9ZLl7WGCtAsITtS1ZikKmfDxc3ojC2qJ0Jiz7dR58zn'

def get_api_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GDRIVE_REFRESH_TOKEN"],
        client_id=os.environ["GDRIVE_CLIENT_ID"],
        client_secret=os.environ["GDRIVE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES
    )

    creds.refresh(Request())
    #print("Refresh Token: ", creds.refresh_token)
    #print("Client ID: ", creds.client_id)
    #print("Client Secret: ", creds.client_secret)
    return creds

import threading
import time
def alive():
    while True:
        print("I'm still alive")
        time.sleep(15)

#To update the docs periodically

def load_manifest():
    if os.path.exists("manifest.json"):
        return json.load(open("manifest.json"))
    else:
        return {}

def save_manifest(manifest):
    json.dump(manifest, open("manifest.json", "w"))       

def ingest_drive_data(creds):
    print("Authenticating with Google...")
    manifest = load_manifest()
    drive_service = build('drive', 'v3', credentials=creds)
    #result=drive_service.files().list(q=f"'{FOLDER_ID}' in parents and trashed=false", fields="files(id, name, mimeType, modifiedTime)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = list_all_docs(FOLDER_ID, drive_service)
    #print(files)

    changed_files = []
    for file in files:
        file_id = file['id']
        modified_time = file['modifiedTime']
        if file_id not in manifest:
            changed_files.append(file)
        elif manifest[file_id] != modified_time:
            changed_files.append(file)
    #print(changed_files)

    print("Connecting to Google Drive...")

    if not changed_files:
        print('changed_files is empty.')
        return []

    documents = []
    threading.Thread(target=alive, daemon=True).start() 
    for f in changed_files: 
        buff = io.BytesIO()
        downloader = MediaIoBaseDownload(buff, drive_service.files().export_media(fileId=f['id'], mimeType='text/plain'))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        text = buff.getvalue().decode('utf-8')
        doc = Document(page_content=text, metadata={'source': f['name'], 'file_id': f['id']})
        documents.append(doc)
        
    for f in changed_files:
        manifest[f['id']] = f['modifiedTime']

    save_manifest(manifest)
    print(f"Loaded {len(documents)} documents from Google Drive.")
    return documents

split = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=100,
    separators=[
        "\n\n",
        "\n",
        " "
    ])

def get_chunks(creds):
    documents = ingest_drive_data(creds)
    return split.split_documents(documents)

def process_all_chunks(splitted_doc):
    extracted_data=[]

    for i, chunk in enumerate(tqdm(splitted_doc)): # loop thru every doc in spplitted_doc
        try:
            extraction = call_groq_model(chunk.page_content) #passes chunk into call groq function
            
            extracted_data.append({
                "chunk_id": i,
                "source": chunk.metadata.get("source", "Unknown"),
                "extraction": extraction
            }) #formats dictionary with chunk id, source and text output by phi3

            time.sleep(2)
        except Exception as e:
            print(f"Error processing chunk {i}: {e}") # if a single chunk fails, script wont crash completely, but log the rror and move on to next chunk
            
    # Save the processed extractions to a JSON file
    with open("gp_extracted_examples.json", "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=4, ensure_ascii=False)
        
    print("Saved all extracted examples to gp_extracted_examples.json")
    return extracted_data

def push_to_google_doc(extracted_results, creds):
    print("Authentication successful!")
    service = build('docs', 'v1', credentials=creds)

    topics_dict = {
        "Culture": [], "Politics": [], "Education": [], "Environment": [],
        "Technology": [], "Economics": [], "Society": [], "Media": [], "General": []
    }

    topic_re = re.compile(r"Topic:\s*([A-Za-z/ -]+)", re.IGNORECASE)
    title_re = re.compile(r"Title:\s*(.+?)(?=\n|\r|Description:|Context:|\Z)", re.IGNORECASE)

    # --- Step 1: Organize extractions into topics ---
    for item in extracted_results:
        ext_text = item.get("extraction", "")
        chunk_id = item.get("chunk_id")
        source = item.get("source")

        sub_parts = re.split(r"(?=Topic:\s*[A-Za-z/ -]+)", ext_text)

        for part in sub_parts:
            part = part.strip()
            if not part:
                continue

            t_match = topic_re.search(part)
            title_match = title_re.search(part)

            parsed_topic = t_match.group(1).strip().title() if t_match else "General"
            
            if title_match:
                raw_title = title_match.group(1).strip()
                title_text = re.sub(r"[\*\#]", "", raw_title)
                title_text = re.sub(r"\s+", " ", title_text)
            else:
                title_text = ""

            body_lines = []
            for line in part.splitlines():
                clean_line = line.strip()
                # Skip header label prefixes
                if any(clean_line.lower().startswith(prefix) for prefix in ["topic:", "title:", "description:", "context:", "case study:    "]):
                    # If there is text AFTER "Description:" on the same line, keep only the text
                    colon_idx = clean_line.find(":")
                    content_after_colon = clean_line[colon_idx + 1:].strip()
                    if content_after_colon:
                        body_lines.append(content_after_colon)
                else:
                    body_lines.append(clean_line)

            # Deduplicate adjacent duplicate paragraphs if LLM outputted them twice
            cleaned_lines = []
            for line in body_lines:
                if not cleaned_lines or line != cleaned_lines[-1]:
                    cleaned_lines.append(line)

            desc_text = "\n".join(cleaned_lines).strip()

            sub_entry = {
                "chunk_id": chunk_id,
                "source": source,
                "title": title_text,
                "description": desc_text,
            }

            assigned = False
            for key in topics_dict.keys():
                if key.lower() == parsed_topic.lower():
                    topics_dict[key].append(sub_entry)
                    assigned = True
                    break
            if not assigned:
                topics_dict["General"].append(sub_entry)

    # --- Step 2: Create a separate document for each non-empty topic ---
    created_docs_summary = {}

    for topic, entries in topics_dict.items():
        if not entries:
            continue

        doc_title = f"GP Examples - {topic}"
        doc = service.documents().create(body={"title": doc_title}).execute()
        doc_id = doc.get('documentId')

        # Build text content for this topic
        full_text = f"=== {topic.upper()} EXAMPLES ===\n\n"
        for entry in entries:
            full_text += f"[Chunk #{entry['chunk_id']} | Source: {entry['source']}]\n"
            if entry["title"]:
                full_text += f"TITLE: {entry['title']}\n"
            full_text += f"{entry['description']}\n\n" + ("-" * 40) + "\n\n"

        # Push text in a single insertText call
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [{'insertText': {'location': {'index': 1}, 'text': full_text}}]}
        ).execute()

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        created_docs_summary[topic] = {
            "doc_id": doc_id,
            "url": doc_url,
            "count": len(entries)
        }
        print(f"Created '{doc_title}' ({len(entries)} entries): {doc_url}")

    # --- Step 3: Save link directory locally ---
    with open("created_google_docs_index.json", "w", encoding="utf-8") as f:
        json.dump(created_docs_summary, f, indent=4)

    print("\nDone! All topics pushed into separate Google Docs.")
    print("Master index saved to 'created_google_docs_index.json'.")

#Calling the SLM

import time
from groq import Groq

groq_client = Groq(api_key=os.environ['GROQ_API_KEY'])

def call_groq_model(sample_chunk):
    prompt = f"""
    Return ONLY valid JSON.
    You are an expert General Paper (GP) tutor assistant.
    Analyze the text below to extract, construct, and evaluate a concrete, high-level GP essay example or case study.
    
    Classify the example into ONE of these primary topics: [Culture, Politics, Education, Environment, Technology, Economics, Society, Media, General].
    
    Format your output EXACTLY as follows, with no extra intro/outro text:
    
    Topic: <Topic Name>
    Title: <Short, Professional Example Title under 5 words>
    Context: <1-2 sentences explaining the background, context, and key facts/stats (e.g. specific policies, historical background, figures, or geographical scope)>
    Case Study / Concrete Detail: <2-3 sentences detailing the specific actions taken, specific actors involved (e.g., specific leaders, policies, organizations), mechanisms behind the issue>
    You should provide statistical evidence and data to substantiate your evidence where possible.
    
    If the chunk contains "Feedback", strictly DO NOT include it in your output. Only extract relevant GP example content.
    
    Text:
    {sample_chunk}
    """

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800
    )
    return response.choices[0].message.content.strip()

def list_all_docs(folder_id, drive_service):
    stored_result=drive_service.files().list(q=f"'{folder_id}' in parents and trashed=false", fields="files(id, name, mimeType, modifiedTime)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    docs = []
    for file in stored_result['files']:
        if file['mimeType'] == 'application/vnd.google-apps.document':
            docs.append(file)
        elif file['mimeType'] == 'application/vnd.google-apps.folder':
            docs.extend(list_all_docs(file['id'], drive_service))
        else:
            pass
    return docs

if __name__ == '__main__':
    creds = get_api_service()
    # 1. Load the document chunks
    splitted_doc = get_chunks(creds)
    print("Total number of chunks: ", len(splitted_doc))

    # 2. RE-RUN Groq to generate fresh extractions using the updated prompt
    print("Processing chunks with Groq...")
    extracted_results = process_all_chunks(splitted_doc)

    # 3. Push the new results to Google Docs
    print(f"Loaded {len(extracted_results)} extracted examples. Pushing to Google Doc...")
    push_to_google_doc(extracted_results, creds)

    print("Finished successfully!")
