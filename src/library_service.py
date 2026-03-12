from typing import List, Dict
from models import Book, RawSearchResult, SearchResultSet, AvailabilityStatus
from api import search_sfpl, get_detailed_availability

class LibraryService:
    def __init__(self, locations: List[str], branch_lookup: Dict[str, str]):
        self.locations = locations
        self.branch_lookup = branch_lookup

    async def search_book(self, book: Book, status_callback=None) -> bool:
        """
        Performs a location-first, then wide-net search for a book.
        Updates the book object in-place. Returns True if results were found.
        """
        queries = [book.primary_query] + book.fallback_queries
        
        for q in queries:
            if status_callback:
                status_callback("local")
            
            # search with location filters first.
            result_set: SearchResultSet = await search_sfpl(q, self.locations, search_type="smart")
            
            is_available = any(r.status_label.lower() == 'available' for r in result_set.results)
            
            if not is_available:
                if status_callback:
                    status_callback("wide")
                # search without location to see if any are available at other locations
                result_set = await search_sfpl(q, [], search_type="smart")

            if result_set.results:
                book.search_url = result_set.url
                for r in result_set.results:
                    if r.metadata_id:
                        r.branch_codes = await get_detailed_availability(r.metadata_id)
                    
                    # Determine Availability Status
                    is_avail_text = r.status_label.lower() == "available"
                    has_local = any(c in self.locations for c in r.branch_codes)
                    
                    if is_avail_text and has_local:
                        r.availability = AvailabilityStatus.AVAILABLE_LOCAL
                    elif is_avail_text:
                        r.availability = AvailabilityStatus.AVAILABLE_SYSTEM
                    elif "in use" in r.status_label.lower() or r.holds > 0:
                        r.availability = AvailabilityStatus.ON_HOLD
                    else:
                        r.availability = AvailabilityStatus.NOT_AVAILABLE
                
                # set book-level availability based on best available result
                book.availability = AvailabilityStatus.NOT_AVAILABLE
                for status in [AvailabilityStatus.AVAILABLE_LOCAL, AvailabilityStatus.AVAILABLE_SYSTEM, AvailabilityStatus.ON_HOLD]:
                    if any(r.availability == status for r in result_set.results):
                        book.availability = status
                        break

                book.results = result_set.results
                book.searched = True
                return True
        
        book.searched = True
        return False

    def get_status_summary(self, result: RawSearchResult) -> str:
        """Returns a human-readable status string including holds and locations."""
        if result.availability == AvailabilityStatus.ON_HOLD:
            status_str = f"All copies in use (Holds: {result.holds} on {result.copies} copies)"
        else:
            status_str = result.status_label
        
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
