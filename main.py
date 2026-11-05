import sys
from src.rag_pipeline import answer


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else input("Enter your question: ")
    print(answer(query))


if __name__ == "__main__":
    main()