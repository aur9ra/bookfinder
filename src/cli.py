from typing import List, Dict
from models import (
    PreferenceDeterminationPlan, UserResponseSet, UserAnswer, SearchSession, 
    BookToSearch, RefinedReaderAnalysis, UserFeedback
)
from library_service import LibraryService

class BookfinderCLI:
    @staticmethod
    def get_user_satisfaction() -> bool:
        while True:
            val = input("\nAre you satisfied with these recommendations? (y/n): ").strip().lower()
            if val in ('y', 'yes'):
                return True
            if val in ('n', 'no'):
                return False
            print("Please enter 'y' or 'n'.")

    @staticmethod
    def get_refinement_input() -> UserFeedback:
        print("\n" + "="*50)
        print("REFINEMENT FEEDBACK")
        print("="*50)
        feedback_text = input("What would you like to change? (e.g., 'too dark', 'already read X', 'more non-fiction'): ").strip()
        
        rejected_input = input("Any specific titles to blacklist? (comma-separated, or leave blank): ").strip()
        rejected_titles = [t.strip() for t in rejected_input.split(',')] if rejected_input else []
        
        return UserFeedback(feedback=feedback_text, rejected_titles=rejected_titles)

    @staticmethod
    def ask_questions(plan: PreferenceDeterminationPlan) -> UserResponseSet:
        answers = []
        print("\n" + "="*50)
        print("READER PREFERENCE SURVEY")
        print("="*50)
        print("Please answer the following questions to help refine your profile.\n")

        for i, question in enumerate(plan.questions, 1):
            print(f"Question {i}: {question.text}")
            
            # display response options
            for j, option in enumerate(question.options, 1):
                print(f"  {j}. {option.label}")
            
            custom_idx = len(question.options) + 1
            print(f"  {custom_idx}. Custom, let me explain myself")
            
            selected_option_ids = []
            custom_explanation = None
            
            while True:
                user_input = input(f"\nSelect options (comma-separated numbers): ").strip()
                
                if not user_input:
                    print("Please provide an answer.")
                    continue
                    
                try:
                    choices = [int(x.strip()) for x in user_input.replace(',', ' ').split()]
                    
                    valid = True
                    current_selected_ids = []
                    is_custom_selected = False
                    
                    for choice in choices:
                        if 1 <= choice < custom_idx:
                            current_selected_ids.append(question.options[choice-1].id)
                        elif choice == custom_idx:
                            is_custom_selected = True
                        else:
                            print(f"Invalid choice: {choice}")
                            valid = False
                            break
                    
                    if not valid:
                        continue
                    
                    if is_custom_selected:
                        custom_explanation = input("Please explain your preference: ").strip()
                    
                    selected_option_ids = current_selected_ids
                    break
                    
                except ValueError:
                    print("Please enter valid numbers.")

            answers.append(UserAnswer(
                question_id=question.id,
                selected_option_ids=selected_option_ids,
                custom_explanation=custom_explanation
            ))
            print("-" * 30)

        return UserResponseSet(answers=answers)

    @staticmethod
    def display_refinement(refined_profile: RefinedReaderAnalysis):
        print(f"\nRefinement Status: {'Complete' if refined_profile.is_complete else 'Incomplete'}")
        print(f"Reasoning: {refined_profile.refinement_reasoning}")
        
        if refined_profile.diversification_goals:
            print("\nDiversification Goals:")
            for goal in refined_profile.diversification_goals:
                print(f"  - {goal}")

    @staticmethod
    def display_search_header(title: str):
        print("\n" + "="*50)
        print(f"{title}")
        print("="*50)

    @staticmethod
    def display_book_results(book: BookToSearch, service: LibraryService):
        print(f"\n--- Searching for: {book.title} by {book.author} ({book.source}) ---")
        
        if book.results:
            for r in book.results:
                print(f"    [{service.get_status_summary(r)}] {r.title} by {r.author}")
            if book.search_url:
                print(f"    Search URL: {book.search_url}")
        elif book.searched:
            print("    (No results found in search)")

    @staticmethod
    def display_final_report(session: SearchSession, service: LibraryService):
        if not session.final_recommendations:
            return

        print("\n" + "="*50)
        print("FINAL RECOMMENDATIONS")
        print("="*50)
        print(f"Status: {'COMPLETE' if session.final_recommendations.is_complete else 'INCOMPLETE'}")
        print(f"Reasoning: {session.final_recommendations.reasoning}")
        
        if session.final_recommendations.is_complete:
            # aggregate all searched books for status/url lookup
            all_searched = session.wide_net_plan.get_books() if session.wide_net_plan else []
            for p in session.expansion_plans:
                all_searched.extend(p.get_books())

            for i, rec in enumerate(session.final_recommendations.recommendations, 1):
                print(f"\n{i}. {rec.title} by {rec.author}")
                print(f"   Original Search: {rec.source_book}")
                
                # fetch detailed status/url from original match
                source_match = next((b for b in all_searched if b.title == rec.source_book), None)
                if source_match:
                    raw_hit = next((r for r in source_match.results if r.title == rec.title), None)
                    if raw_hit:
                        print(f"   Status: {service.get_status_summary(raw_hit)}")
                    if source_match.search_url:
                        print(f"   Search URL: {source_match.search_url}")
                
                print(f"   Why: {rec.reasoning}")
        else:
            print("\nCould not find sufficient high-confidence matches.")
