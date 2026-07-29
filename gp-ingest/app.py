import streamlit as st
import json
from groq import Groq
import os

st.set_page_config(page_title="mrs-vetri")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


st.title("GP Extracted Examples from 26S64's Google Drive")

with st.expander("About"):
    st.markdown("""
    :rainbow[Hello]
    """)
    st.markdown("""This is a General Paper example bank sorted by topic, extracted from the 26S64 C1 GP Google Drive. The bot searches through the drive and compile each example present into documents. The documents will update every 4 days(I hope). 

    You may choose to view the examples collated by topic from the dropdown menu, or use the bot to ask questions, that will give you info based ONLY from information from the google drive. ts basically a worse chatgpt cuz u cant send so many questions at once and it only extracts from the drive. lowkey added it for fun.

    Please understand that some documents may appear relatively empty as there may not be enough content related to such topics, and that the bot is not perfect. Nevertheless, I have faith that it should work alright.""")
    st.markdown("built by hongr")

st.divider()

topic = st.selectbox(
    "Choose a GP Essay Topic: This menu will bring you to a Google Doc that collated all the examples from the drive and sorts them into topics.",
    ("Culture", "Politics", "Education", "Environment",
            "Technology", "Economics", "Society", "Media", "General")
)

index_path = os.path.join(BASE_DIR, "created_google_docs_index.json")
if os.path.exists(index_path):
    with open(os.path.join(BASE_DIR, "created_google_docs_index.json")) as f:
        existing_index = json.load(f)

else: 
    existing_index = {}
topic_data = existing_index.get(topic)

if isinstance(topic_data, dict) and "url" in topic_data:
    st.markdown(f"[View {topic} Examples]({topic_data['url']})")
elif isinstance(topic_data, str):
    # Fallback in case topic_data was saved as a direct string or ID
    url = topic_data if topic_data.startswith("http") else f"https://docs.google.com/document/d/{topic_data}/edit"
    st.markdown(f"[View {topic} Examples]({url})")

else:
    st.info("No examples yet, please wait 3-5 days for the files to automatically update.")

st.divider()
with st.expander("Format of a GP essay"):
      st.markdown("""
###   Intro:
* Hook
* Link to Question
* Dual Perspectives
* 30/70 Stand
* Thesis
---

### Structure of a body paragraph:
* **1. TS = Connector + Keywords + Point + Personal View +  Concept**

Evidently, today the evolution of digitalisation has certainly enhanced human interaction by empowering them with a voice to bring about positive changes.

* **2. Reason 1, Reason 2, Reason 3**

[R1] This is because many dishes are not the product of a single country, but rather the result of centuries of cultural exchange and adaptation across regions.\n
[R2] Consequently, neighbouring nations may contest attempts to brand such dishes as belonging exclusively to one national culture, viewing them as a misrepresentation or appropriation of their own heritage.\n
[R3] These disputes are particularly difficult to resolve because culinary traditions often emerged before modern national boundaries were established, making definitive ownership claims problematic.\n
* **3. Sprinkler effect (to sprinkle keywords in the paragraph)**

As a result, efforts to elevate a country's international profile through contested food heritage may generate diplomatic tensions and cultural rivalries(keywords relevant to your point), suggesting that less contentious methods of preserving and promoting culinary heritage may sometimes be preferable. 
* **4. Examples for reasons (try to give 2, one for each of any two reasons. USE 5W1H when explaining examples)**

In 2008, the head of the Association of Lebanese Industrialists filed a lawsuit against Israel for what he called "food copyright" infringement, after Lebanese producers objected to hummus being marketed and sold in Western stores under the label "Israeli cuisine." The dispute escalated to the point where Lebanon's government formally petitioned the European Union to have hummus classified as a uniquely Lebanese food.
The dispute is especially difficult to resolve on the merits, since hummus can be traced back to the era of Saladin, a 12th-century sultan — centuries before either the state of Israel or Lebanon existed. This makes any claim of exclusive national ownership inherently contestable, since the dish predates the very borders being used to stake the claim.


* **5. Evaluation (Why is the example relevant and what does it show)**

The discord that gazetting culturally important foods can bring about can therefore be significant, especially when the emergence of a food item came from centuries of cultural exchange long before boundaries were drawn. (Links the example to the point, on WHY gastrodiplomacy causes conflict)

* **6. Link (keywords)**
Thus, claiming a country’s culinary heritage to be exclusive internationally can cause friction and cultural resentment, contrary to the intention of raising one’s global standing.
    """)

st.divider()
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

    examples_path = os.path.join(BASE_DIR, "gp_extracted_examples.json")
    if os.path.exists(examples_path):
        with open(os.path.join(BASE_DIR,"gp_extracted_examples.json")) as f:
            examples = json.load(f)

    else:
        examples = []

        keyword = prompt.lower()
        relevant = [e for e in examples if keyword in e.get("extraction", "").lower()][:2]
        context = "\n\n".join([e["extraction"] for e in relevant])


    groq_client = Groq(api_key=os.environ['GROQ_API_KEY'])
    response = groq_client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[
          {"role": "system", "content": f"Your name is Mrs Vetri. You are a General Paper tutor following the Singapore A-Level H1 General Paper syllabus. Only give CONCRETE examples Give the who, what when where, why, how and substantial statitics for each example where possible. Split the who what where when how into separate lines. Only deal with Paper 1 (Essay) Use these examples:\n{context}"},
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
    st.balloons()
      
st.button(
      label = f"{st.session_state.likes} time(s) pressed",
      on_click = increase_likes,   
)
