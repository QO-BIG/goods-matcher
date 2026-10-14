# Standard Goods & Services Matcher

Internal tool for Quality Oracle. For each goods/services item a customer wants to
protect, it finds the closest **pre-approved standard term** from the MyIPO or IPOS
list, so the trademark filing can use the lower standard-term fee.

## Why it exists
Both MyIPO and IPOS charge a higher fee for a whole class if even one item in that class
is not worded exactly like a pre-approved term. Customers usually write their items in
their own words, so staff had to search for the closest standard term by hand.

## How to use it
1. Open the app link.
2. Choose the jurisdiction (MYIPO or IPOS) and the Nice class.
3. Paste the customer's items, separated by `;`.
4. Click **Find matches**.

Each item gets a tag:
- **EXACT**: the standard term means the same thing.
- **BROADER**: the standard term covers more than the customer asked for. Safe to use.
- **NARROWER**: the standard term covers less. Check the scope before using it.
- **NO MATCH**: keep the customer's original wording.

The suggested term is always copied exactly from the official list. Wording that is not
an exact standard term is discarded by the app, because even a small change in wording
gets flagged as non-standard when filing.

## How it works
1. `build_index.py` (run once on a PC) turns every standard term into a list of numbers
   (an embedding) that captures its meaning, and saves one file per jurisdiction and
   class in the `index` folder.
2. When you click **Find matches**, `app.py` loads the file for the chosen class and
   finds the 10 terms closest in meaning to each item.
3. Claude (model `claude-sonnet-5`) then picks the best of those 10 and labels the match.

There is no database. The embeddings are the files in `index`.

## Files in this repo
- `app.py`: the Streamlit app.
- `requirements.txt`: Python packages Streamlit installs.
- `index/`: 90 files, `myipo_class_01.npz` ... `ipos_class_45.npz`.
- `build_index.py` is not stored here. It is run on a PC when the lists change.

## Secrets
Set in Streamlit Cloud under the app's **Settings → Secrets**. Never put them in GitHub.

```
ANTHROPIC_API_KEY = "sk-ant-..."
```

## When MyIPO or IPOS update their lists
1. Download the new official list.
   - MyIPO: the export on https://onlineapps.myipo.gov.my/tmclass/search_class.php
   - IPOS: the Goods and Services database file from IPOS.
2. Convert it to a CSV with the columns below.
   - `myipo_standard_goods.csv`: `class`, `goods_and_services`
   - `ipos_standard_goods.csv`: `jurisdiction`, `class`, `goods_and_services`, `source`
3. Put both CSVs and `build_index.py` in one folder, delete the old `index` folder, and run
   `pip install fastembed numpy` then `python build_index.py` (use `py` on Windows
   if `python` is not found).
4. Upload the new `index` folder to this repo. The app updates itself.

Lists in use were downloaded in September 2026: MyIPO 136,339 terms (136,152 after
removing exact duplicates), IPOS 117,211 terms.

## Good to know
- The app sleeps if nobody uses it for a while. The next visitor clicks a button to wake it.
- Anyone with the app link can use it, and each use costs a little Anthropic API credit.
- The embedding model is `BAAI/bge-small-en-v1.5`. It downloads automatically.

## Owners and accounts (fill in)
- GitHub account that owns this repo:
- Streamlit account that runs the app:
- Whose Anthropic API key is used:
- Person to ask:
