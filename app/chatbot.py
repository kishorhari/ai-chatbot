from typing import Dict, List, Optional

from ollama import chat

try:
    from .config import MODEL_NAME, SYSTEM_PROMPT
except ImportError:
    from config import MODEL_NAME, SYSTEM_PROMPT


class ChatBotError(Exception):
    pass


class ChatBot:
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None) -> None:
        self.model = model or MODEL_NAME
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def ask(self, user_input: str) -> str:
        user_text = user_input.strip()
        if not user_text:
            return ""

        self.messages.append({"role": "user", "content": user_text})

        try:
            response = chat(model=self.model, messages=self.messages)
        except Exception as exc:
            self.messages.pop()
            raise ChatBotError(
                "Unable to reach Ollama. Please make sure Ollama is running and reachable."
            ) from exc

        assistant_reply = response["message"]["content"]
        self.messages.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    def history(self) -> str:
        lines: List[str] = []
        for message in self.messages:
            role = message["role"].capitalize()
            content = message["content"]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def clear(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]
