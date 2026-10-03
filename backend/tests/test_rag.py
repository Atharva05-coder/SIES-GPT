from rag.rag_pipeline import ask_sies_gpt
    
while True:
    user_input = input(
        "\nEnter your question (or 'exit' to quit): "
    )

    if user_input.lower() == "exit":
        break

    result = ask_sies_gpt(user_input)

    print("\nANSWER:")
    print(result["answer"])

    print("\nSOURCES:")

    for source in result["sources"]:

        print(
            f"- {source['filename']} "
            f"(Page {source['page']})"
        )