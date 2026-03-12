import json
import os
from typing import Type, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class DataManager:
    def __init__(self):
        pass

    def load(self, path: str, model_class: Type[T]) -> Optional[T]:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return model_class.model_validate(json.load(f))
            except Exception as e:
                print(f"Error loading {path}: {e}")
        return None

    def save(self, path: str, data: BaseModel):
        try:
            with open(path, "w") as f:
                json.dump(data.model_dump(), f, indent=2)
        except Exception as e:
            print(f"Error saving {path}: {e}")
