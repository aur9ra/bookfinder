from typing import List, Dict, Callable, Any, Coroutine
from models import (
    PreferenceDeterminationPlan, UserResponseSet, UserAnswer, SearchSession, 
    BookToSearch, RefinedReaderAnalysis, UserFeedback
)
from library_service import LibraryService
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

console = Console()

class CLITheme:
    HEADER = "bold deep_sky_blue1"
    SUBHEADER = "bold cyan"
    QUEUED = "grey50"
    SEARCHING = "bold cyan"
    FOUND = "bold green"
    NOT_FOUND = "bold red"
    DIM = "grey50"
    SUCCESS = "green"
    ERROR = "bold red"
    ACCENT = "italic orange1"

class BookfinderCLI:
    @staticmethod
    def get_user_satisfaction() -> bool:
        while True:
            console.print(f"\nAre you satisfied with these recommendations? (y/n): ", end="", style=CLITheme.SUBHEADER)
            val = input().strip().lower()
            if val in ('y', 'yes'):
                return True
            if val in ('n', 'no'):
                return False
            console.print("Please enter 'y' or 'n'.", style=CLITheme.ERROR)

    @staticmethod
    def get_refinement_input() -> UserFeedback:
        BookfinderCLI.display_search_header("REFINEMENT FEEDBACK")
        console.print("What would you like to change? (e.g., 'too dark', 'more non-fiction'): ", end="", style=CLITheme.SUBHEADER)
        feedback_text = input().strip()
        
        console.print("Any specific titles to blacklist? (comma-separated, or leave blank): ", end="", style=CLITheme.SUBHEADER)
        rejected_input = input().strip()
        rejected_titles = [t.strip() for t in rejected_input.split(',')] if rejected_input else []
        
        return UserFeedback(feedback=feedback_text, rejected_titles=rejected_titles)

    @staticmethod
    def ask_questions(plan: PreferenceDeterminationPlan) -> UserResponseSet:
        answers = []
        BookfinderCLI.display_search_header("READER PREFERENCE SURVEY")
        console.print("Please answer the following questions to help refine your profile.\n", style=CLITheme.DIM)

        for i, question in enumerate(plan.questions, 1):
            console.print(f"Question {i}: {question.text}", style=CLITheme.SUBHEADER)
            
            # display response options
            for j, option in enumerate(question.options, 1):
                console.print(f"  {j}. {option.label}")
            
            custom_idx = len(question.options) + 1
            console.print(f"  {custom_idx}. Custom, let me explain myself")
            
            selected_option_ids = []
            custom_explanation = None
            
            while True:
                console.print(f"\nSelect options (comma-separated numbers): ", end="", style=CLITheme.ACCENT)
                user_input = input().strip()
                
                if not user_input:
                    console.print("Please provide an answer.", style=CLITheme.ERROR)
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
                            console.print(f"Invalid choice: {choice}", style=CLITheme.ERROR)
                            valid = False
                            break
                    
                    if not valid:
                        continue
                    
                    if is_custom_selected:
                        console.print("Please explain your preference: ", end="", style=CLITheme.ACCENT)
                        custom_explanation = input().strip()
                    
                    selected_option_ids = current_selected_ids
                    break
                    
                except ValueError:
                    console.print("Please enter valid numbers.", style=CLITheme.ERROR)

            answers.append(UserAnswer(
                question_id=question.id,
                selected_option_ids=selected_option_ids,
                custom_explanation=custom_explanation
            ))
            console.print("-" * 30, style=CLITheme.DIM)

        return UserResponseSet(answers=answers)

    @staticmethod
    def display_refinement(refined_profile: RefinedReaderAnalysis):
        status = "Complete" if refined_profile.is_complete else "Incomplete"
        color = CLITheme.SUCCESS if refined_profile.is_complete else CLITheme.NOT_FOUND
        console.print(f"\nRefinement Status: [{color}]{status}[/]")
        console.print(f"Reasoning: ", end="", style=CLITheme.DIM)
        console.print(refined_profile.refinement_reasoning)
        
        if refined_profile.diversification_goals:
            console.print("\nDiversification Goals:", style=CLITheme.SUBHEADER)
            for goal in refined_profile.diversification_goals:
                console.print(f"  - {goal}", style=CLITheme.ACCENT)

    @staticmethod
    def display_search_header(title: str):
        width = 80
        console.print("\n" + "="*width, style=CLITheme.HEADER)
        console.print(title.center(width), style=CLITheme.HEADER)
        console.print("="*width, style=CLITheme.HEADER)

    @staticmethod
    async def run_search_with_progress(
        books: List[BookToSearch], 
        search_func: Callable[[BookToSearch, Any], Coroutine[Any, Any, bool]],
        service: LibraryService,
        on_step_complete: Callable[[], None]
    ):
        book_statuses = {b.title: f"[{CLITheme.QUEUED}][QUEUED][/]" for b in books}
        book_progress_labels = {b.title: "queued..." for b in books}
        book_results_summary = {b.title: "" for b in books}

        def generate_table():
            table = Table(box=None, show_header=False, pad_edge=False)
            table.add_column("Status", width=15)
            table.add_column("Book")
            
            for b in books:
                status = book_statuses[b.title]
                text = Text()
                text.append(f"{b.title} ", style="bold")
                text.append(f"by {b.author}", style="italic")
                
                summary = book_results_summary[b.title]
                if summary:
                    text.append(f"\n    {summary}", style=CLITheme.DIM)
                else:
                    progress_label = book_progress_labels[b.title]
                    text.append(f"\n    {progress_label}", style=CLITheme.DIM)
                
                table.add_row(status, text)
            return table

        console.print("\nStarting library searches...", style=CLITheme.SUBHEADER)
        with Live(generate_table(), refresh_per_second=4) as live:
            for book in books:
                book_statuses[book.title] = f"[{CLITheme.SEARCHING}][SEARCHING][/]"
                
                def status_cb(phase):
                    if phase == "local":
                        book_progress_labels[book.title] = "searching at your local branch(es)..."
                    elif phase == "wide":
                        book_progress_labels[book.title] = "searching library-wide..."
                    live.update(generate_table())

                book.results = []
                book.search_url = None
                
                await search_func(book, status_cb)
                
                if book.results:
                    book_statuses[book.title] = f"[{CLITheme.FOUND}][FOUND][/]"
                    summary = service.get_status_summary(book.results[0])
                    if len(book.results) > 1:
                        summary += f" (+{len(book.results)-1} more)"
                    book_results_summary[book.title] = summary
                else:
                    book_statuses[book.title] = f"[{CLITheme.NOT_FOUND}][NOT FOUND][/]"
                    book_progress_labels[book.title] = "not found"
                
                on_step_complete()
                live.update(generate_table())

    @staticmethod
    def display_book_results(book: BookToSearch, service: LibraryService):
        console.print(f"\n--- Searching for: {book.title} by {book.author} ({book.source}) ---", style=CLITheme.SUBHEADER)
        
        if book.results:
            for r in book.results:
                console.print(f"    [{service.get_status_summary(r)}] {r.title} by {r.author}")
            if book.search_url:
                console.print(f"    Search URL: {book.search_url}", style=CLITheme.DIM)
        elif book.searched:
            console.print("    (No results found in search)", style=CLITheme.DIM)

    @staticmethod
    def display_final_report(session: SearchSession, service: LibraryService):
        if not session.final_recommendations:
            return

        BookfinderCLI.display_search_header("FINAL RECOMMENDATIONS")
        
        status = "COMPLETE" if session.final_recommendations.is_complete else "INCOMPLETE"
        color = CLITheme.SUCCESS if session.final_recommendations.is_complete else CLITheme.NOT_FOUND
        console.print(f"Status: [{color}]{status}[/]")
        console.print(f"Reasoning: ", end="", style=CLITheme.DIM)
        console.print(session.final_recommendations.reasoning)
        
        if session.final_recommendations.is_complete:
            all_searched = session.wide_net_plan.get_books() if session.wide_net_plan else []
            for p in session.expansion_plans:
                all_searched.extend(p.get_books())

            for i, rec in enumerate(session.final_recommendations.recommendations, 1):
                console.print(f"\n{i}. {rec.title} by {rec.author}", style=CLITheme.SUBHEADER)
                console.print(f"   Original Search: {rec.source_book}", style=CLITheme.DIM)
                
                source_match = next((b for b in all_searched if b.title == rec.source_book), None)
                if source_match:
                    raw_hit = next((r for r in source_match.results if r.title == rec.title), None)
                    if raw_hit:
                        console.print(f"   Status: {service.get_status_summary(raw_hit)}", style=CLITheme.ACCENT)
                    if source_match.search_url:
                        console.print(f"   Search URL: {source_match.search_url}", style=CLITheme.DIM)
                
                console.print(f"   Why: ", end="", style=CLITheme.DIM)
                console.print(rec.reasoning)
        else:
            console.print("\nCould not find sufficient high-confidence matches.", style=CLITheme.ERROR)
