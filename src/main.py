import json, os, asyncio
from dotenv import load_dotenv
from csv_parser import load_books
from agents import (
    preference_determination, 
    analyze_reader, 
    refine_analysis,
    wide_net_selection,
    targeted_expansion_selection,
    interpret_search_results
)
from models import (
    ReaderAnalysis, 
    PreferenceDeterminationPlan, 
    UserResponseSet,
    RefinedReaderAnalysis,
    BookSearchPlan,
    TargetedExpansionPlan,
    InterpretationResult,
    SearchSession,
    UserFeedback
)
from strands.models.gemini import GeminiModel
from data_manager import DataManager
from library_service import LibraryService
from cli import BookfinderCLI

def get_model():
    return GeminiModel(
        model_id="gemini-3.1-flash-lite-preview",
        client_args={"api_key": os.getenv("API_KEY")},
        params={
            "thinking_config": {"thinking_level": "high"}
        }
    )

async def run_search_workflow(plan, service: LibraryService, session: SearchSession, dm: DataManager):
    BookfinderCLI.display_search_header("LIBRARY SEARCH STATUS")
    
    for book in plan.get_books():
        # skip if already searched in this session (though with clean slate search results it might not matter,
        # but for session caching we might want to keep the results if we saved them)
        if book.searched and book.results:
            BookfinderCLI.display_book_results(book, service)
            continue

        book.results = []
        book.search_url = None
        
        await service.search_book(book)
        BookfinderCLI.display_book_results(book, service)
        
        # save after each search to avoid data loss
        dm.save("search_session.json", session)

# initialize environment
load_dotenv()

async def main():
    # step 1. initialize
    dm = DataManager()
    books_data = load_books("goodreads_library_export.csv")
    
    try:
        with open("location-slugs/sfpl-location-slugs.json", "r") as f:
            all_location_data = json.load(f)
            # Map every known code to its friendly name for the service to use in reporting
            code_to_name = {ld["code"]: ld["friendly_name"] for ld in all_location_data}
    except FileNotFoundError:
        print("Error: sfpl-location-codes.json not found.")
        return

    try:
        with open("user_settings.json", "r") as f:
            settings = json.load(f)
            user_locations_input = settings.get("locations", [])
            
            locations = []
            for loc_input in user_locations_input:
                matched = False
                for ld in all_location_data:
                    if loc_input.upper() == ld["code"] or \
                       loc_input.upper() == ld["full_name"] or \
                       loc_input.lower() == ld["friendly_name"].lower():
                        locations.append(ld["code"])
                        matched = True
                        break
                if not matched:
                    print(f"Warning: Could not match location: {loc_input}")
            
    except FileNotFoundError:
        locations = []
        print("Warning: user_settings.json not found.")
    
    service = LibraryService(locations, code_to_name)
    
    # step 2. initialize session (Attempt to load from cache)
    session = dm.load("search_session.json", SearchSession) or SearchSession()

    rated_books = [b for b in books_data if b.my_rating > 0]
    to_read_books = [b for b in books_data if b.my_rating == 0]
    rated_str = "\n".join([f"- {b.author}, {b.title} ({b.my_rating}/5)" for b in rated_books])
    to_read_str = "\n".join([f"- {b.author}, {b.title}" for b in to_read_books])

    # step 3. perform initial preference analysis, determine questions to get clearer picture
    if not session.reader_profile or not session.questions_plan:
        print("Running initial analysis and question generation...")
        model = get_model()
        session.reader_profile = await analyze_reader(rated_str, to_read_str, model)
        session.questions_plan = await preference_determination(session.reader_profile, rated_str, to_read_str, model)
        dm.save("search_session.json", session)

    # step 4. ask user
    if not session.user_responses:
        session.user_responses = BookfinderCLI.ask_questions(session.questions_plan)
        dm.save("search_session.json", session)

    # step 5. refine with user responses
    if not session.refined_profile:
        print("Refining reader analysis...")
        session.refined_profile = await refine_analysis(session.reader_profile, session.questions_plan, session.user_responses, get_model())
        dm.save("search_session.json", session)

    BookfinderCLI.display_refinement(session.refined_profile)

    # step 6. search until we have a number of solid reccomendations
    if session.refined_profile.is_complete:
        if not session.wide_net_plan:
            print("\nGenerating wide net search plan (15 books)...")
            session.wide_net_plan = await wide_net_selection(session.refined_profile, to_read_str, rated_str, get_model())
            dm.save("search_session.json", session)

        await run_search_workflow(session.wide_net_plan, service, session, dm)

        while True:
            # aggregate all books for interpretation
            all_searched = session.wide_net_plan.get_books()
            for p in session.expansion_plans:
                all_searched.extend(p.get_books())
            
            print("\nInterpreting search results...")
            session.final_recommendations = await interpret_search_results(session.refined_profile, all_searched, session.feedback_history, get_model())
            dm.save("search_session.json", session)

            BookfinderCLI.display_final_report(session, service)
            
            # have we found a satisfactory number of books, or should we search 10 more
            satisfied = False
            if session.final_recommendations.is_complete:
                satisfied = BookfinderCLI.get_user_satisfaction()
                if satisfied:
                    break
            
            if not satisfied:
                feedback = BookfinderCLI.get_refinement_input()
                session.feedback_history.append(feedback)
                
                print(f"\nResults insufficient or unsatisfied. Expanding search with 10 more books...")
                new_exp = await targeted_expansion_selection(session.refined_profile, all_searched, rated_str, session.feedback_history, get_model())
                session.expansion_plans.append(new_exp)
                await run_search_workflow(new_exp, service, session, dm)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n[FATAL ERROR] The application encountered an unexpected issue: {e}")
        print("Please check your internet connection or try again later.")

