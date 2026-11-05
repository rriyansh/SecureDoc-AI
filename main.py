from src.rag_pipeline import SecureRAGPipeline

def main():
    print("SecureDoc AI (Basic) - Type 'exit' to quit.")
    pipeline = SecureRAGPipeline()

    while True:
        question = input("\nAsk a question about your documents: ")
        if question.lower() in ["exit", "quit"]:
            break
        answer = pipeline.query(question)
        print(f"\nAnswer: {answer}")

if __name__ == "__main__":
    main()
