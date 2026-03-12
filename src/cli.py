import difflib
from typing import List, Dict, Callable, Any, Coroutine
from models import (
    PreferenceDeterminationPlan, UserResponseSet, UserAnswer, SearchSession, 
    Book, RefinedReaderAnalysis, UserFeedback, AvailabilityStatus
)
from library_service import LibraryService
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

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
    
    # Availability Colors
    AVAIL_LOCAL = "bold green1"
    AVAIL_SYSTEM = "orange3"
    AVAIL_HOLD = "red3"

class BookfinderCLI:
    console = Console(force_terminal=True)

    @staticmethod
    def get_user_satisfaction() -> bool:
        while True:
            val = Prompt.ask(
                Text("\nAre you satisfied with these recommendations?", style=CLITheme.SUBHEADER),
                choices=["y", "n"],
                default="y"
            ).lower()
            if val in ('y', 'yes'):
                return True
            if val in ('n', 'no'):
                return False

    @staticmethod
    def get_refinement_input() -> UserFeedback:
        BookfinderCLI.display_search_header("REFINEMENT FEEDBACK")
        feedback_text = Prompt.ask(
            Text("What would you like to change? (e.g., 'too dark', 'already read X', 'more non-fiction')", style=CLITheme.SUBHEADER)
        ).strip()
        
        rejected_input = Prompt.ask(
            Text("Any specific titles to blacklist? (comma-separated, or leave blank)", style=CLITheme.SUBHEADER)
        ).strip()
        rejected_titles = [t.strip() for t in rejected_input.split(',')] if rejected_input else []
        
        return UserFeedback(feedback=feedback_text, rejected_titles=rejected_titles)

    @staticmethod
    def ask_questions(plan: PreferenceDeterminationPlan) -> UserResponseSet:
        answers = []
        BookfinderCLI.display_search_header("READER PREFERENCE SURVEY")
        BookfinderCLI.console.print("Please answer the following questions to help refine your profile.\n", style=CLITheme.DIM)

        for i, question in enumerate(plan.questions, 1):
            BookfinderCLI.console.print(f"Question {i}/{len(plan.questions)}: {question.text}", style=CLITheme.SUBHEADER)
            
            # display response options
            for j, option in enumerate(question.options, 1):
                BookfinderCLI.console.print(f"  {j}. {option.label}")
            
            custom_idx = len(question.options) + 1
            BookfinderCLI.console.print(f"  {custom_idx}. Custom, let me explain myself")
            
            while True:
                user_input = Prompt.ask(
                    Text("\nSelect options (comma-separated numbers)", style=CLITheme.ACCENT)
                ).strip()
                
                if not user_input:
                    BookfinderCLI.console.print("Please provide an answer.", style=CLITheme.ERROR)
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
                            BookfinderCLI.console.print(f"Invalid choice: {choice}", style=CLITheme.ERROR)
                            valid = False
                            break
                    
                    if not valid:
                        continue
                    
                    custom_explanation = None
                    if is_custom_selected:
                        custom_explanation = Prompt.ask(
                            Text("Please explain your preference", style=CLITheme.ACCENT)
                        ).strip()
                    
                    selected_option_ids = current_selected_ids
                    break
                    
                except ValueError:
                    BookfinderCLI.console.print("Please enter valid numbers.", style=CLITheme.ERROR)

            answers.append(UserAnswer(
                question_id=question.id,
                selected_option_ids=selected_option_ids,
                custom_explanation=custom_explanation
            ))
            BookfinderCLI.console.print("-" * 30, style=CLITheme.DIM)

        return UserResponseSet(answers=answers)

    @staticmethod
    def display_refinement(refined_profile: RefinedReaderAnalysis):
        status = "Complete" if refined_profile.is_complete else "Incomplete"
        color = CLITheme.SUCCESS if refined_profile.is_complete else CLITheme.NOT_FOUND
        BookfinderCLI.console.print(f"\nRefinement Status: [{color}]{status}[/]")
        BookfinderCLI.console.print(f"[{CLITheme.DIM}]Reasoning:[/] {refined_profile.refinement_reasoning}")
        
        if refined_profile.diversification_goals:
            BookfinderCLI.console.print("\nDiversification Goals:", style=CLITheme.SUBHEADER)
            for goal in refined_profile.diversification_goals:
                BookfinderCLI.console.print(f"  - {goal}", style=CLITheme.ACCENT)

    @staticmethod
    def display_search_header(title: str):
        width = 80
        BookfinderCLI.console.print("\n" + "="*width, style=CLITheme.HEADER)
        BookfinderCLI.console.print(title.center(width), style=CLITheme.HEADER)
        BookfinderCLI.console.print("="*width, style=CLITheme.HEADER)

    @staticmethod
    async def run_search_with_progress(
        books: List[Book], 
        search_func: Callable[[Book, Any], Coroutine[Any, Any, bool]],
        service: LibraryService,
        on_step_complete: Callable[[], None]
    ):
        from models import AvailabilityStatus
        book_statuses = {b.title: f"[{CLITheme.QUEUED}][QUEUED][/]" for b in books}
        book_progress_labels = {b.title: "queued..." for b in books}
        book_results_summary = {b.title: Text() for b in books}

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
                    text.append("\n    ")
                    text.append(summary)
                else:
                    progress_label = book_progress_labels[b.title]
                    text.append(f"\n    {progress_label}", style=CLITheme.DIM)
                
                table.add_row(status, text)
            return table

        BookfinderCLI.console.print("\nStarting library searches...", style=CLITheme.SUBHEADER)
        with Live(generate_table(), refresh_per_second=4, console=BookfinderCLI.console) as live:
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
                    top_res = book.results[0]
                    color = CLITheme.AVAIL_HOLD
                    if top_res.availability == AvailabilityStatus.AVAILABLE_LOCAL:
                        color = CLITheme.AVAIL_LOCAL
                    elif top_res.availability == AvailabilityStatus.AVAILABLE_SYSTEM:
                        color = CLITheme.AVAIL_SYSTEM
                    
                    summary_text = Text(service.get_status_summary(top_res), style=color)
                    if len(book.results) > 1:
                        summary_text.append(f" (+{len(book.results)-1} more)", style=CLITheme.DIM)
                    book_results_summary[book.title] = summary_text
                else:
                    book_statuses[book.title] = f"[{CLITheme.NOT_FOUND}][NOT FOUND][/]"
                    book_progress_labels[book.title] = "not found"
                
                on_step_complete()
                live.update(generate_table())

    @staticmethod
    def display_book_results(book: Book, service: LibraryService):
        BookfinderCLI.console.print(f"\n--- Searching for: {book.title} by {book.author} ({book.source}) ---", style=CLITheme.SUBHEADER)
        
        if book.results:
            for r in book.results:
                BookfinderCLI.console.print(f"    [{service.get_status_summary(r)}] {r.title} by {r.author}")
            if book.search_url:
                BookfinderCLI.console.print(f"    Search URL: {book.search_url}", style=CLITheme.DIM)
        elif book.searched:
            BookfinderCLI.console.print("    (No results found in search)", style=CLITheme.DIM)

    @staticmethod
    def display_final_report(session: SearchSession, service: LibraryService):
        if not session.final_recommendations:
            return

        from models import AvailabilityStatus
        BookfinderCLI.display_search_header("FINAL RECOMMENDATIONS")
        
        status = "COMPLETE" if session.final_recommendations.is_complete else "INCOMPLETE"
        color = CLITheme.SUCCESS if session.final_recommendations.is_complete else CLITheme.NOT_FOUND
        BookfinderCLI.console.print(f"Status: [{color}]{status}[/]")
        BookfinderCLI.console.print(f"[{CLITheme.DIM}]Reasoning:[/] {session.final_recommendations.reasoning}")
        
        if session.final_recommendations.is_complete:
            all_searched = session.wide_net_plan.get_books() if session.wide_net_plan else []
            for p in session.expansion_plans:
                all_searched.extend(p.get_books())

            def normalize(t):
                return t.lower().strip() if t else ""

            search_map = {b.search_id: b for b in all_searched if b.search_id}
            title_map = {normalize(b.title): b for b in all_searched}

            for i, rec in enumerate(session.final_recommendations.recommendations, 1):
                BookfinderCLI.console.print(f"\n{i}. {rec.title} by {rec.author}", style=CLITheme.SUBHEADER)
                
                # 1. try id match first
                source_match = search_map.get(rec.search_id)
                
                # 2. try normalized title match
                if not source_match:
                    source_match = title_map.get(normalize(rec.title))
                
                # 3. fuzzy match fallback
                if not source_match:
                    possible_titles = list(title_map.keys())
                    closest = difflib.get_close_matches(normalize(rec.title), possible_titles, n=1, cutoff=0.6)
                    if closest:
                        source_match = title_map.get(closest[0])
                
                found_status = False
                
                if source_match:
                    if source_match.search_url:
                        BookfinderCLI.console.print(f"   [{CLITheme.DIM}]Search:[/] {source_match.search_url}")

                    norm_rec_title = normalize(rec.title)
                    # find the specific result in the book's search results
                    raw_hit = next((r for r in source_match.results if normalize(r.title) == norm_rec_title), None)
                    
                    if raw_hit:
                        color = CLITheme.AVAIL_HOLD
                        if raw_hit.availability == AvailabilityStatus.AVAILABLE_LOCAL:
                            color = CLITheme.AVAIL_LOCAL
                        elif raw_hit.availability == AvailabilityStatus.AVAILABLE_SYSTEM:
                            color = CLITheme.AVAIL_SYSTEM
                        
                        BookfinderCLI.console.print(f"   [{CLITheme.DIM}]Status:[/] [{color}]{service.get_status_summary(raw_hit)}[/]")
                        found_status = True
                    elif source_match.results:
                        top_res = source_match.results[0]
                        BookfinderCLI.console.print(f"   [{CLITheme.DIM}]Status (Top Result):[/] {service.get_status_summary(top_res)}")
                        found_status = True
                
                if not found_status:
                    # final fallback: manual search link if we couldn't link it to a previous search
                    import urllib.parse
                    query = urllib.parse.quote(f"{rec.title} {rec.author}")
                    manual_link = f"https://sfpl.bibliocommons.com/v2/search?query={query}&searchType=smart"
                    BookfinderCLI.console.print(f"   [{CLITheme.DIM}]Manual Search:[/] {manual_link}")
                    BookfinderCLI.console.print(f"   [{CLITheme.DIM}]Status:[/] Availability Unknown (Link Mismatch)")
                
                BookfinderCLI.console.print(f"   [{CLITheme.DIM}]Why:[/] {rec.reasoning}")
        else:
            BookfinderCLI.console.print("\nCould not find sufficient high-confidence matches.", style=CLITheme.ERROR)
