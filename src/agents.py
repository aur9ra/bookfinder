import json, asyncio
from typing import List
from strands.models.gemini import GeminiModel
from strands.agent.agent import Agent
from models import (
    ReaderAnalysis, RefinedReaderAnalysis, QuestionOption, PreferenceQuestion,
    PreferenceDeterminationPlan, UserAnswer, UserResponseSet, RawSearchResult,
    FinalRecommendation, InterpretationResult, Book, BookSearchPlan,
    TargetedExpansionPlan, UserFeedback
)

def load_prompts():
    with open("prompts.json", "r") as f:
        return json.load(f)

PROMPTS = load_prompts()

def format_feedback(feedback_history: List[UserFeedback]) -> str:
    if not feedback_history:
        return "None"
    return "\n".join([f"- Feedback: {f.feedback} (Blacklisted: {', '.join(f.rejected_titles)})" for f in feedback_history])

async def wide_net_selection(analysis: RefinedReaderAnalysis, to_read: str, rated: str, model) -> BookSearchPlan:
    # select 15 books from to-read list + discoveries
    wide_net_agent = Agent(
        model=model,
        system_prompt=PROMPTS["wide_net_selection"],
        structured_output_model=BookSearchPlan,
        callback_handler=None
    )

    selection_result = await wide_net_agent.invoke_async(
        f"Refined Profile: {analysis.model_dump_json()}\n"
        f"To-Read List: {to_read}\n"
        f"Already Read (Rated) Books: {rated}"
    )
    
    return selection_result.structured_output

async def targeted_expansion_selection(analysis: RefinedReaderAnalysis, previous_searches: List[Book], rated: str, feedback_history: List[UserFeedback], model) -> TargetedExpansionPlan:
    # analyze all previous searches and generate 10 more targeted searches
    previous_titles = ", ".join([f"{b.title} by {b.author}" for b in previous_searches])
    
    expansion_agent = Agent(
        model=model,
        system_prompt=PROMPTS["targeted_expansion_selection"].format(previous_titles=previous_titles),
        structured_output_model=TargetedExpansionPlan,
        callback_handler=None
    )

    expansion_result = await expansion_agent.invoke_async(
        f"Refined Profile: {analysis.model_dump_json()}\n"
        f"User Feedback History: {format_feedback(feedback_history)}\n"
        f"Previous Searches: {previous_titles}\n"
        f"Already Read (Rated) Books: {rated}"
    )
    
    return expansion_result.structured_output

async def interpret_search_results(analysis: RefinedReaderAnalysis, all_searched_books: List[BookToSearch], feedback_history: List[UserFeedback], model) -> InterpretationResult:
    # interpret the raw results
    interpretation_agent = Agent(
        model=model,
        system_prompt=PROMPTS["interpret_search_results"],
        structured_output_model=InterpretationResult,
        callback_handler=None
    )

    interpretation_result = await interpretation_agent.invoke_async(
        f"Reader Profile: {analysis.model_dump_json()}\n"
        f"User Feedback History: {format_feedback(feedback_history)}\n"
        f"All Searched Books and Library Results: {json.dumps([b.model_dump() for b in all_searched_books])}"
    )
    
    return interpretation_result.structured_output

async def preference_determination(analysis: ReaderAnalysis, rated: str, to_read: str, model, previous_analysis: RefinedReaderAnalysis = None) -> PreferenceDeterminationPlan:
    # questions to determine reader preferences
    preferences_questions_agent = Agent(
        model=model,
        system_prompt=PROMPTS["preference_determination"],
        structured_output_model=PreferenceDeterminationPlan,
        callback_handler=None
    )

    context = f"Initial Profile: {analysis.model_dump_json()}\n"
    if previous_analysis:
        context += f"Previous Refined Profile (Incomplete): {previous_analysis.model_dump_json()}\n"
    context += f"Book History: {rated}"

    try:
        preferences_questions_result = await asyncio.wait_for(
            preferences_questions_agent.invoke_async(context),
            timeout=60.0
        )
        plan: PreferenceDeterminationPlan = preferences_questions_result.structured_output
    except asyncio.TimeoutError:
        # Fallback if the model is being slow/unresponsive
        print("\n[DEBUG] Question generation timed out. Retrying with simpler context...")
        preferences_questions_result = await preferences_questions_agent.invoke_async(
            f"Initial Profile: {analysis.model_dump_json()}\nBook History: {rated}"
        )
        plan = preferences_questions_result.structured_output

    return plan

async def analyze_reader(rated, to_read, model) -> ReaderAnalysis:
    # discovery and analysis
    discovery_agent = Agent(
        model=model,
        system_prompt=PROMPTS["analyze_reader"],
        structured_output_model=ReaderAnalysis,
        callback_handler=None
    )

    discovery_result = await discovery_agent.invoke_async(
        (
            f"Identify the themes and genres I enjoy and dislike based on my list of rated books and my list of to-read books."
            f"Rated books: {rated}, To-read list: {to_read}"
        )
    )
    discovery_analysis: ReaderAnalysis = discovery_result.structured_output

    return discovery_analysis

async def refine_analysis(previous_analysis: ReaderAnalysis, plan: PreferenceDeterminationPlan, responses: UserResponseSet, model) -> RefinedReaderAnalysis:
    # refinement based on answers
    refinement_agent = Agent(
        model=model,
        system_prompt=PROMPTS["refine_analysis"],
        structured_output_model=RefinedReaderAnalysis,
        callback_handler=None
    )

    refinement_result = await refinement_agent.invoke_async(
        f"Previous Analysis: {previous_analysis.model_dump_json()}\n"
        f"Questions Asked: {plan.model_dump_json()}\n"
        f"User Responses: {responses.model_dump_json()}"
    )
    
    return refinement_result.structured_output
