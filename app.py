
from src.ai_service import AIService


def main():
    print("\n================================")
    print("       AI ASSISTANCE")
    print("================================")
    print("Type 'exit' to quit.\n")

    try:
        assistant = AIService()
    except ValueError as error:
        print(f"Configuration error: {error}")
        return

    conversation = []

    while True:
        question = input("You: ").strip()

        if question.lower() in ("exit", "quit"):
            print("AI Assistant: Goodbye!")
            break

        if not question:
            continue

        conversation.append({
            "role": "user",
            "content": question,
        })

        try:
            answer = assistant.get_response(conversation)
            print(f"\nAI Assistant: {answer}\n")

            conversation.append({
                "role": "assistant",
                "content": answer,
            })

        except Exception as error:
            print(f"\nSomething went wrong: {error}\n")
            conversation.pop()


if __name__ == "__main__":
    main()
