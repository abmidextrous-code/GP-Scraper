import streamlit as st
import json
from groq import Groq
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

st.title("GP Extracted Examples from 26S64's google drive")
st.markdown("""
:rainbow[Hello]
""")
st.write("This is a General Paper example bank sorted by topic, extracted from the 26S64 C1 GP Google Drive. The bot searches through the drive and compile each example present into documents. The documents will update every 4 days(I hope).")

topic = st.selectbox(
    "Choose a GP Essay Topic: ",
    ("Culture", "Politics", "Education", "Environment",
            "Technology", "Economics", "Society", "Media", "General")
)

with open(os.path.join(BASE_DIR, "created_google_docs_index.json")) as f:
            existing_index = json.load(f)

if topic in existing_index:
        st.markdown(f"[View {topic} Examples]({existing_index[topic]['url']})")
else:
        st.info("No examples yet, please wait 3-5 days for the files to automatically update.")

if "messages" not in st.session_state:
        st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message['role']):
           st.markdown(message["content"])
prompt = st.chat_input("Ask about GP examples (Give me examples on overconsumerism...)")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with open(os.path.join(BASE_DIR,"gp_extracted_examples.json")) as f:
        examples = json.load(f)

        keyword = prompt.lower()
        relevant = [e for e in examples if keyword in e.get("extraction", "").lower()][:5]
        context = "\n\n".join([e["extraction"] for e in relevant])

    groq_client = Groq(api_key=os.environ['GROQ_API_KEY'])
    response = groq_client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[
          {"role": "system", "content": f"You are a General Paper tutor following the Singapore A-Level H1 General Paper syllabus. Use these examples:\n{context}"},
          *st.session_state.messages
          ],
    max_tokens=500
    )
    reply = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
          st.markdown(reply)

if "likes" not in st.session_state:
    st.session_state.likes = 0
def increase_likes():
    st.session_state.likes += 1
      
st.button(
      label = f"{st.session_state.likes} people LOVE this",
      onclick = increase_likes
      onclick = st.balloons()
)

st.subheader("Ask a question about GP examples: ")