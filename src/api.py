import httpx
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typing import List
from models import RawSearchResult, SearchResultSet
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# initialize environment
load_dotenv()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(httpx.HTTPError)
)
async def get_detailed_availability(metadata_id: str) -> List[str]:
    """
    Fetches detailed branch-level availability for a specific metadata ID.
    Returns a list of branch codes where the book is currently AVAILABLE.
    """
    if not metadata_id:
        return []
        
    availability_query_url = f"https://gateway.bibliocommons.com/v2/libraries/sfpl/bibs/{metadata_id}/availability"
    query_params = {"locale": "en-US"}
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get(availability_query_url, params=query_params)
            # print(f"    [Availability API] {response.status_code} {availability_query_url}")
            if response.status_code != 200:
                return []
            
            data = response.json()
            bib_items = data.get("entities", {}).get("bibItems", {})
            
            available_branches = []
            for item in bib_items.values():
                if item.get("availability", {}).get("status") == "AVAILABLE":
                    branch_code = item.get("branch", {}).get("code")
                    if branch_code:
                        available_branches.append(branch_code)
            
            return list(set(available_branches))
        except httpx.ReadTimeout:
            # print(f"    [Availability API] Timeout for {metadata_id}, retrying...")
            raise
        except Exception as e:
            # print(f"    [Availability API] Error for {metadata_id}: {e}")
            return []

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(httpx.HTTPError)
)
async def search_sfpl(search, locations: List, search_type="title") -> SearchResultSet:
    """
    Searches the San Francisco Public Library (SFPL) catalog.
    This function parses the HTML returned by the catalog to determine book availability.
    """
    # avlocation filters by the specified branch/location
    # formatcode:(BK ) ensures we only get physical books
    location_query = "|".join(locations) if locations else None
    
    request_uri = "https://sfpl.bibliocommons.com/v2/search"
    params = {
        "query": search,
        "searchType": search_type,
        "locale": "en-US",
        "f_FORMAT": "BK"
    }
    if location_query:
        params["f_STATUS"] = location_query

    # print(f"Searching SFPL for: {search}...")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get(request_uri, params=params)
            # print(f"    [Search API] {response.status_code} {response.url}")
            response.raise_for_status()
            html = response.text
        except httpx.ReadTimeout:
            # print(f"    [Search API] Timeout for {search}, retrying...")
            raise

    soup = BeautifulSoup(html, "html.parser")
    
    results = []
    results_list = soup.select_one("ul.results")
    
    if not results_list:
        return SearchResultSet(results=[], url=str(response.url))
    
    found_items = results_list.select("li.cp-search-result-item")
    
    for item in found_items:
        title_tag = item.select_one(".title-content")
        author_tag = item.select_one(".author-link")
        status_tag = item.select_one(".cp-availability-status")
        
        metadata_id = ""
        # try bib-title link (e.g. /v2/record/S93C2458431)
        title_link = item.select_one("a[data-key='bib-title']")
        if title_link and 'href' in title_link.attrs:
            match = re.search(r'/record/(S\d+C\d+)', title_link['href'])
            if match:
                metadata_id = match.group(1)
        
        # fallback to availability-link (e.g. /v2/availability/S93C2458431)
        if not metadata_id:
            avail_link = item.select_one("a[data-key='bib-availability-link']")
            if avail_link and 'href' in avail_link.attrs:
                match = re.search(r'/availability/(S\d+C\d+)', avail_link['href'])
                if match:
                    metadata_id = match.group(1)

        # extract hold info: "Holds: 4 on 2 copies"
        holds = 0
        copies = 0
        hold_tag = item.select_one(".cp-hold-counts")
        if hold_tag:
            hold_text = hold_tag.get_text(strip=True) # e.g. "Holds: 4 on 2 copies"
            holds_match = re.search(r"Holds:\s*(\d+)", hold_text, re.I)
            copies_match = re.search(r"(\d+)\s*copies", hold_text, re.I)
            
            if holds_match:
                holds = int(holds_match.group(1))
            if copies_match:
                copies = int(copies_match.group(1))

        if title_tag:
            results.append(RawSearchResult(
                title=title_tag.get_text(strip=True),
                author=author_tag.get_text(strip=True) if author_tag else "Unknown",
                status_label=status_tag.get_text(strip=True) if status_tag else "Availability Unknown",
                availability="Not Available", # Default, will be refined in service
                metadata_id=metadata_id,
                holds=holds,
                copies=copies,
                branch_codes=[]
            ))

    return SearchResultSet(results=results, url=str(response.url))
