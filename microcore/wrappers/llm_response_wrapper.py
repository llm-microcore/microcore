from typing import Any

from ..types import BadAIAnswer
from ..json_parsing import parse_json
from ..utils import ExtendedString, ConvertableToMessage, extract_number
from ..message_types import Role, AssistantMsg


class LLMResponse(ExtendedString, ConvertableToMessage):
    """
    Response from the Large Language Model.

    If treated as a string, it returns the text generated by the LLM.

    Also, it contains all fields returned by the API accessible as an attributes.

    See fields returned by the OpenAI:

    - https://platform.openai.com/docs/api-reference/completions/object
    - https://platform.openai.com/docs/api-reference/chat/object
    """

    def __new__(cls, string: str, attrs: dict = None):
        attrs = {
            "role": Role.ASSISTANT,
            "content": str(string),
            "gen_duration": None,
            **(attrs or {}),
        }
        obj = ExtendedString.__new__(cls, string, attrs)
        return obj

    def parse_json(
        self, raise_errors: bool = True, required_fields: list[str] = None
    ) -> list | dict | float | int | str:
        return parse_json(self.content, raise_errors, required_fields)

    def parse_number(
        self,
        default=BadAIAnswer,
        position="last",
        dtype: type | str = float,
        rounding: bool = False,
    ) -> int | float | Any:
        return extract_number(self.content, default, position, dtype, rounding)

    def as_message(self) -> AssistantMsg:
        return self.as_assistant
