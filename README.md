# bookfinder

## details

bookfinder takes your Goodreads history and runs it through a series of interactive LLM prompts to determine your core reading preferences. It then automatically cross-references these patterns with the SFPL catalog to find available books at your local branches, allowing you to iterate on the results until you find something you actually want to read.

## this software is "parody"

i made up a bro in my mind who thinks we should replace librarians with the LLM

i thought about how one would do this, and made bookfinder over a weekend.

librarians do amazing work, and they're good at it! however, this problem is decently well suited to an LLM.

LLMs have been trained on every published novel as well as much of our discussion around these novels.
you can also throw your entire goodreads history at an LLM, and it will do a decent job at identifying the patterns in your ratings.

ideally, this software gets more people to go to their libraries! support your public services!

## usage

- create a `.env` file and add your `API_KEY` (Gemini API)
- provide `goodreads_library_export.csv` in the root directory. you can obtain this file from [Goodreads' history export tool](https://www.goodreads.com/review/import).
- configure `user_settings.json` with your preferred library branch codes (e.g., `["G4", "E9"]`).

**setup and run**:

linux/macOS:
```bash
# create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# install dependencies
pip install -r requirements.txt

# start
python3 main.py
```

windows:
```pwsh
# create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# start
python main.py
```

**workflow**:

- **analysis**: the agent analyzes your Goodreads history
- **survey**: you answer 3-5 questions to clarify your preferences
- **search**: the agent performs a "wide net" search of 15 books' availability at your local SFPL branch(es)
- **feedback**: critique the results until you find a few books you like

## todo

- [ ] provide support for searching for books in other languages or translations
- [ ] implement more cities' public library systems
- [ ] implement support for LLM providers with better privacy
