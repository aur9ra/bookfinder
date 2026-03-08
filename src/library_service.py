from typing import List, Dict
from models import BookToSearch, RawSearchResult, SearchResultSet, RefinedReaderAnalysis, TargetedExpansionPlan, InterpretationResult
from api import search_sfpl, get_detailed_availability
from strands.models.gemini import GeminiModel
from agents import interpret_search_results, targeted_expansion_selection

class LibraryService:
    def __init__(self, locations: List[str], branch_lookup: Dict[str, str]):
        self.locations = locations
        self.branch_lookup = branch_lookup

    async def search_book(self, book: BookToSearch) -> bool:
        """
        Performs a location-first, then wide-net search for a book.
        Updates the book object in-place. Returns True if results were found.
        """
        queries = [book.primary_query] + book.fallback_queries
        
        for q in queries:
            # search with location filters first.
            # why?
            # when including location filters, we see if books are available at those locations,
            # but do not get information for holds
            result_set: SearchResultSet = await search_sfpl(q, self.locations, search_type="smart")
            
            is_available = any(r.status.lower() == 'available' for r in result_set.results)
            
            if not is_available:
                # if the book is not found available at the user-specified locations,
                # search without location to see if any are available to place a hold on at other locations
                result_set = await search_sfpl(q, [], search_type="smart")

            if result_set.results:
                book.search_url = result_set.url
                for r in result_set.results:
                    if r.metadata_id:
                        r.branch_codes = await get_detailed_availability(r.metadata_id)
                
                book.results = result_set.results
                book.searched = True
                return True
        
        book.searched = True
        return False

    def get_status_summary(self, result: RawSearchResult) -> str:
        """Returns a human-readable status string including holds and locations."""
        status_str = result.status
        if result.holds > 0:
            status_str += f" (Holds: {result.holds} on {result.copies} copies)"
        
        # add the branches where the book is available, if possible
        if result.branch_codes:
            preferred = [self.branch_lookup.get(c, c) for c in result.branch_codes if c in self.locations]
            others_count = len([c for c in result.branch_codes if c not in self.locations])
            
            locations_parts = []
            if preferred:
                locations_parts.append(", ".join(preferred))
            if others_count > 0:
                locations_parts.append(f"{others_count} other location(s)")
            
            if locations_parts:
                status_str += f" | At: {'; '.join(locations_parts)}"
        
        return status_str
