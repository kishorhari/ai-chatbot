try:
    from .chatbot import ChatBot, ChatBotError
except ImportError:
    from chatbot import ChatBot, ChatBotError


def main() -> None:
    bot = ChatBot()
    print("Chat started. Type '/history' to view history, '/clear' to reset, and 'exit' or 'quit' to stop.")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        normalized = user_input.lower()
        if normalized in {"exit", "quit"}:
            print("Goodbye!")
            break

        if normalized == "/history":
            print(bot.history())
            continue

        if normalized == "/clear":
            bot.clear()
            print("Conversation history cleared. System prompt preserved.")
            continue

        try:
            response = bot.ask(user_input)
        except ChatBotError as error:
            print(f"Error: {error}")
            continue

        print(f"Bot: {response}")


if __name__ == "__main__":
    main()

response = chat(
    model="qwen2.5:3b",
    messages=[
        {
            "role": "user",
            "content": "My Name is Hari."
        },
        {
            "role": "assistant",
            "content": "Hello Hari"
        },
        {
            "role": "user",
            "content": "I work on ERPNext"
        },
        {
            "role": "assistant",
            "content": "That's great!"
        },
        {
            "role": "user",
            "content": "What is my name?"
        }
    ]
)

print(response["message"]["content"])