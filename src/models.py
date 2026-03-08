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

# --- library & search models ---

class RawSearchResult(BaseModel):
    title: str
    author: str
    status: str
    metadata_id: str = Field(default="", description="The unique ID used for availability lookups")
    holds: int = Field(default=0, description="Number of people waiting")
    copies: int = Field(default=0, description="Total number of physical copies")
    branch_codes: List[str] = Field(default_factory=list, description="Codes of branches where this item is available")

class SearchResultSet(BaseModel):
    results: List[RawSearchResult] = Field(description="List of matched books")
    url: str = Field(description="The URL used to perform this search")

class BookToSearch(BaseModel):
    title: str = Field(description="Title of the book")
    author: str = Field(description="Author of the book")
    source: Literal["to_read", "discovery"] = Field(description="Source of the book")
    primary_query: str = Field(description="Primary search string")
    fallback_queries: List[str] = Field(default_factory=list, description="Fallback queries")
    results: List[RawSearchResult] = Field(default_factory=list, description="Raw results found")
    search_url: Optional[str] = Field(default=None, description="Successful search URL")
    searched: bool = Field(default=False, description="Whether this book has been searched")

class BookSearchPlan(BaseModel):
    b1: BookToSearch
    b2: BookToSearch
    b3: BookToSearch
    b4: BookToSearch
    b5: BookToSearch
    b6: BookToSearch
    b7: BookToSearch
    b8: BookToSearch
    b9: BookToSearch
    b10: BookToSearch
    b11: BookToSearch
    b12: BookToSearch
    b13: BookToSearch
    b14: BookToSearch
    b15: BookToSearch

    def get_books(self) -> List[BookToSearch]:
        return [getattr(self, f"b{i}") for i in range(1, 16)]

class TargetedExpansionPlan(BaseModel):
    b1: BookToSearch
    b2: BookToSearch
    b3: BookToSearch
    b4: BookToSearch
    b5: BookToSearch
    b6: BookToSearch
    b7: BookToSearch
    b8: BookToSearch
    b9: BookToSearch
    b10: BookToSearch

    def get_books(self) -> List[BookToSearch]:
        return [getattr(self, f"b{i}") for i in range(1, 11)]

# --- final recommendation models ---

class UserFeedback(BaseModel):
    feedback: str = Field(description="The user's specific critique or direction")
    rejected_titles: List[str] = Field(default_factory=list, description="Titles the user specifically rejected in this turn")

class FinalRecommendation(BaseModel):
    title: str
    author: str
    source_book: str = Field(description="Original search title")
    availability_status: str = Field(description="Library status")
    reasoning: str = Field(description="Why this book was chosen")

class InterpretationResult(BaseModel):
    is_complete: bool = Field(description="True if 3 recommendations found")
    recommendations: List[FinalRecommendation] = Field(default_factory=list, description="Top 3 matches")
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
