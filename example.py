import sys

from paraphrase_agents.config import validate_env
from paraphrase_agents.orchestrator import ParaphraseOrchestrator

def main():
    try:
        validate_env()
    except EnvironmentError as exc:
        print(str(exc))
        sys.exit(1)
    
    # Initialize the orchestrator
    print("Initializing paraphrasing system...")
    orchestrator = ParaphraseOrchestrator(num_agents=3)
    
    # Interactive loop
    print("\nParaphrasing System Ready!")
    print("Enter text to paraphrase (or 'quit' to exit):")
    
    while True:
        try:
            # Get user input
            print("\n" + "="*50)
            text = input("> ").strip()
            
            if text.lower() in ('quit', 'exit', 'q'):
                print("Goodbye!")
                break
                
            if not text:
                print("Please enter some text to paraphrase.")
                continue
                
            # Generate and display paraphrase
            print("\nGenerating paraphrase...")
            result = orchestrator.paraphrase_with_feedback_loop(
                text,
                max_iterations=3,
                target_kld=0.5
            )
            
            # Display results
            print("\n" + "="*50)
            print("ORIGINAL TEXT:")
            print(text)
            print("\nPARAPHRASE:")
            print(result['text'])
            print("\nEVALUATION:")
            print(f"KL-Divergence: {result['evaluation']['kld']:.4f}")
            print(f"Length Ratio: {result['evaluation']['length_ratio']:.2f}")
            print(f"Word Overlap: {result['evaluation']['word_overlap']:.2f}")
            print(f"Overall Score: {result['evaluation']['score']:.2f}/100")
            
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            continue

if __name__ == "__main__":
    main()
