from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# --- reader analysis models ---

class ReaderAnalysis(BaseModel):
    enjoyed_themes: List[str] = Field(description="Themes the reader enjoys based on high ratings")
    enjoyed_genres: List[str] = Field(description="genres the reader enjoys based on high ratings")
    disliked_themes: List[str] = Field(description="Themes the reader dislikes based on low ratings")
    disliked_genres: List[str] = Field(description="genres the reader dislikes based on low ratings")
    reasoning: str = Field(description="An in-depth explanation of why these themes and genres were identified")

class RefinedReaderAnalysis(ReaderAnalysis):
    is_complete: bool = Field(description="True if you have an exhaustive understanding of the reader, False if more questions are needed")
    refinement_reasoning: str = Field(description="Explanation of how the user's answers changed or confirmed the analysis, and why the analysis is or isn't complete")
    diversification_goals: List[str] = Field(default_factory=list, description="Up to 4 high-level goals to ensure recommendations sample across different genres/interests")

# --- question & answer models ---

class QuestionOption(BaseModel):
    id: str = Field(description="Unique ID for this option as a slug")
    label: str = Field(description="Display text")

class PreferenceQuestion(BaseModel):
    id: str = Field(description="Unique ID for the question")
    text: str = Field(description="The question to ask the reader")
    options: List[QuestionOption]
    reasoning: str = Field(description="Why this question is being asked")

class PreferenceDeterminationPlan(BaseModel):
    questions: List[PreferenceQuestion]

class UserAnswer(BaseModel):
    question_id: str = Field(description="ID of the question being answered")
    selected_option_ids: List[str] = Field(description="List of selected option IDs")
    custom_explanation: Optional[str] = Field(default=None, description="Free-text explanation")

class UserResponseSet(BaseModel):
    answers: List[UserAnswer] = Field(description="Set of answers provided by the user")

from enum import Enum

# --- library & search models ---

class AvailabilityStatus(str, Enum):
    AVAILABLE_LOCAL = "Available Local"
    AVAILABLE_SYSTEM = "Available in System"
    ON_HOLD = "On Hold"
    NOT_AVAILABLE = "Not Available"

class RawSearchResult(BaseModel):
    title: str
    author: str
    status_label: str = Field(description="Original status text from library")
    availability: AvailabilityStatus = Field(default=AvailabilityStatus.NOT_AVAILABLE)
    metadata_id: str = Field(default="", description="The unique ID used for availability lookups")
    holds: int = Field(default=0, description="Number of people waiting")
    copies: int = Field(default=0, description="Total number of physical copies")
    branch_codes: List[str] = Field(default_factory=list, description="Codes of branches where this item is available")

class SearchResultSet(BaseModel):
    results: List[RawSearchResult] = Field(description="List of matched books")
    url: str = Field(description="The URL used to perform this search")

class Book(BaseModel):
    search_id: str = Field(description="A unique, URL-friendly identifier (slug) for this book, e.g., 'hitchhikers-guide-to-the-galaxy'")
    title: str = Field(description="Title of the book")
    author: str = Field(description="Author of the book")
    source: Literal["to_read", "discovery"] = Field(description="Source of the book")
    primary_query: str = Field(description="Primary search string")
    fallback_queries: List[str] = Field(default_factory=list, description="Fallback queries")
    availability: AvailabilityStatus = Field(default=AvailabilityStatus.NOT_AVAILABLE, description="Overall availability status")
    results: List[RawSearchResult] = Field(default_factory=list, description="Raw results found", exclude=True)
    search_url: Optional[str] = Field(default=None, description="Successful search URL", exclude=True)
    searched: bool = Field(default=False, description="Whether this book has been searched", exclude=True)

class BookSearchPlan(BaseModel):
    b1: Book
    b2: Book
    b3: Book
    b4: Book
    b5: Book
    b6: Book
    b7: Book
    b8: Book
    b9: Book
    b10: Book
    b11: Book
    b12: Book
    b13: Book
    b14: Book
    b15: Book

    def get_books(self) -> List[Book]:
        return [getattr(self, f"b{i}") for i in range(1, 16)]

class TargetedExpansionPlan(BaseModel):
    b1: Book
    b2: Book
    b3: Book
    b4: Book
    b5: Book
    b6: Book
    b7: Book
    b8: Book
    b9: Book
    b10: Book

    def get_books(self) -> List[Book]:
        return [getattr(self, f"b{i}") for i in range(1, 11)]

# --- final recommendation models ---

class UserFeedback(BaseModel):
    feedback: str = Field(description="The user's specific critique or direction")
    rejected_titles: List[str] = Field(default_factory=list, description="Titles the user specifically rejected in this turn")

class FinalRecommendation(BaseModel):
    search_id: str = Field(description="The search_id of the Book this recommendation is based on")
    title: str
    author: str
    reasoning: str = Field(description="Why this book was chosen")

class LocalRecommendation(FinalRecommendation):
    availability: Literal[AvailabilityStatus.AVAILABLE_LOCAL] = Field(description="Must be AVAILABLE_LOCAL")

class SystemRecommendation(FinalRecommendation):
    availability: Literal[AvailabilityStatus.AVAILABLE_SYSTEM, AvailabilityStatus.ON_HOLD] = Field(description="Must be AVAILABLE_SYSTEM or ON_HOLD")

class InterpretationResult(BaseModel):
    is_complete: bool = Field(description="True if sufficient recommendations found (usually 5 total)")
    local_recommendations: List[LocalRecommendation] = Field(default_factory=list, description="Books available at user's local branches (at least 2 preferred)")
    system_recommendations: List[SystemRecommendation] = Field(default_factory=list, description="Books available elsewhere in the system or on hold")
    reasoning: str = Field(description="Overall interpretation logic")

# --- orchestration / session models ---

class SearchSession(BaseModel):
    reader_profile: Optional[ReaderAnalysis] = None
    refined_profile: Optional[RefinedReaderAnalysis] = None
    questions_plan: Optional[PreferenceDeterminationPlan] = None
    user_responses: Optional[UserResponseSet] = None
    wide_net_plan: Optional[BookSearchPlan] = None
    expansion_plans: List[TargetedExpansionPlan] = Field(default_factory=list)
    final_recommendations: Optional[InterpretationResult] = None
    feedback_history: List[UserFeedback] = Field(default_factory=list)
