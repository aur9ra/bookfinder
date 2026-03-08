import csv
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class Book(BaseModel):
    book_id: int = Field(alias="Book Id")
    title: str = Field(alias="Title")
    author: str = Field(alias="Author")
    isbn: Optional[str] = Field(alias="ISBN")
    isbn13: Optional[str] = Field(alias="ISBN13")
    my_rating: int = Field(alias="My Rating") # 0 = not yet rated
    average_rating: float = Field(alias="Average Rating")
    pages: Optional[int] = Field(alias="Number of Pages")
    year_published: Optional[int] = Field(alias="Year Published")
    read_count: int = Field(alias="Read Count")

    @field_validator("isbn", "isbn13", mode="before")
    @classmethod
    def clean_isbn_strings(cls, s: str) -> Optional[str]:
        if isinstance(s, str) and s.startswith('="') and s.endswith('"'):
            clean_s = s[2:-1]
            return clean_s if clean_s else None
        return s if s else None

    @field_validator("pages", "year_published", "book_id", "my_rating", "read_count", mode="before")
    @classmethod
    def field_str_to_int(cls, s: str) -> Optional[int]:
        try:
            _s = int(s)
            return _s
        except ValueError:
            return None

    @field_validator("average_rating", mode="before")
    @classmethod
    def field_str_to_float(cls, s: str) -> Optional[float]:
        try:
            _s = float(s)
            return _s
        except ValueError:
            return None

def load_books(path: str) -> List[Book]:
    books = []
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            books.append(Book(**row))
    return books
