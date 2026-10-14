"""
Standard Goods & Services Matcher
=================================
For each customer-supplied goods/services item (separated by ;), finds the
closest MyIPO / IPOS pre-approved standard term in the chosen Nice class and
labels the match: exact, broader, narrower or no match.

Reads the files in the `index` folder made by build_index.py.
The only secret needed is ANTHROPIC_API_KEY.
"""
import json
import os

import numpy as np
import streamlit as st
from anthropic import Anthropic
from fastembed import TextEmbedding

st.set_page_config(page_title="Standard Goods Matcher", layout="wide")

INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index")
MODEL_NAME = "BAAI/bge-small-en-v1.5"
TOP_K = 10


@st.cache_resource
def get_embedding_model():
    return TextEmbedding(model_name=MODEL_NAME)


@st.cache_resource
def get_client():
    return Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


@st.cache_resource(max_entries=6)
def load_class(jurisdiction: str, nice_class: int):
    """Loads one class's terms + embeddings. Returns None if the file is missing."""
    path = os.path.join(INDEX_DIR, f"{jurisdiction.lower()}_class_{nice_class:02d}.npz")
    if not os.path.exists(path):
        return None
    data = np.load(path)
    terms = [str(t) for t in data["texts"]]
    embeddings = data["embeddings"].astype(np.float32)
    return terms, embeddings


def retrieve_candidates(terms, embeddings, query_vec, k=TOP_K):
    query_vec = query_vec / np.linalg.norm(query_vec)
    scores = embeddings @ query_vec
    top = np.argsort(-scores)[:k]
    return [terms[i] for i in top]


JUDGE_PROMPT = """You are helping a trademark agent replace a customer's free-text \
goods/services item with the closest pre-approved standard term, so the filing \
qualifies for a lower fee. The replacement must be copied EXACTLY from the \
candidate list below -- never reworded, never invented.

Customer's item: "{item}"

Candidate standard terms (closest by semantic similarity, same Nice class):
{candidates}

Respond with ONLY a JSON object, no other text, no markdown fences:
{{
  "match": "<verbatim text of the chosen candidate, copied EXACTLY, or null>",
  "classification": "<exact | broader | narrower | no_match>",
  "reasoning": "<one short sentence>"
}}

Rules:
- "exact": the candidate means essentially the same thing as the customer's item.
- "broader": the candidate covers more than the customer's item. Safe to suggest.
- "narrower": the candidate covers less than the customer's item. Still return it, \
but flag it as narrower so the agent can decide -- never silently pick a narrower \
match without flagging it.
- "no_match": none of the candidates are a reasonable substitute. Set "match" to \
null. Never force a bad substitution.
- "match" must be copied character-for-character from the candidate list, or null. \
Never paraphrase.
"""


def judge_with_claude(client, item, candidates):
    prompt = JUDGE_PROMPT.format(
        item=item,
        candidates="\n".join(f"- {c}" for c in candidates),
    )
    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
    except Exception as e:  # network problem, bad JSON, etc.
        return {"match": None, "classification": "no_match",
                "reasoning": f"Could not get a result for this item ({type(e).__name__}). Check it manually."}

    # Safety net: only trust a match that is character-for-character in the candidate list.
    if result.get("match") and result["match"] not in candidates:
        return {"match": None, "classification": "no_match",
                "reasoning": "The suggested wording was not an exact standard term, so it was discarded. Check manually."}
    return result


TAGS = {
    "exact": ("green", "EXACT"),
    "broader": ("blue", "BROADER"),
    "narrower": ("orange", "NARROWER \u2014 check the scope"),
    "no_match": ("red", "NO MATCH \u2014 keep original wording"),
}

st.title("Standard Goods & Services Matcher")
st.caption(
    "Finds the closest MyIPO / IPOS pre-approved term for each item, "
    "so the filing can use the lower standard-term fee."
)

col1, col2 = st.columns(2)
with col1:
    jurisdiction = st.selectbox("Jurisdiction", ["MYIPO", "IPOS"])
with col2:
    nice_class = st.number_input("Nice class", min_value=1, max_value=45, step=1, value=9)

items_text = st.text_area(
    "Customer's goods/services (separate items with ;)",
    height=140,
    placeholder="e.g. smart phone cases; wireless charging pads; bluetooth speakers",
)

if st.button("Find matches", type="primary"):
    items = [i.strip() for i in items_text.split(";") if i.strip()]
    if not items:
        st.warning("Type or paste at least one item first.")
        st.stop()

    loaded = load_class(jurisdiction, int(nice_class))
    if loaded is None:
        st.error(f"No index file found for {jurisdiction} class {int(nice_class)}.")
        st.stop()
    terms, embeddings = loaded

    model = get_embedding_model()
    client = get_client()

    with st.spinner(f"Matching {len(items)} item(s)..."):
        query_vectors = list(model.embed(items))
        results = []
        for item, qv in zip(items, query_vectors):
            candidates = retrieve_candidates(terms, embeddings, np.asarray(qv, dtype=np.float32))
            judged = judge_with_claude(client, item, candidates)
            results.append({"item": item, "candidates": candidates, **judged})

    st.divider()
    for r in results:
        st.markdown(f"**Original:** {r['item']}")
        color, label = TAGS.get(r.get("classification"), ("gray", str(r.get("classification")).upper()))
        if r.get("match"):
            st.markdown(f":{color}[**{label}**] \u2192 `{r['match']}`")
        else:
            st.markdown(f":{color}[**{label}**]")
        if r.get("reasoning"):
            st.caption(r["reasoning"])
        with st.expander("Other terms that were considered"):
            for c in r["candidates"]:
                st.write(f"- {c}")
        st.divider()
