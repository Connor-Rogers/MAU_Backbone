import os
import re
from typing import Dict, Optional, Any
import openai

"""
ModelWithCot.py - A module for using Chain of Thought reasoning with Language Learning Models
"""


class ModelWithCot:
    """A class that implements Chain of Thought reasoning with Language Learning Models."""
    
    def __init__(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """
        Initialize the ModelWithCot.
        
        Args:
            model_name: The name of the model to use
            api_key: API key for the LLM service. If None, tries to get it from environment variables.
        """
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._setup_client()
    
    def _setup_client(self):
        """Set up the client for the LLM API."""
        try:
            
            if not self.api_key:
                raise ValueError("API key not found. Please provide it or set the OPENAI_API_KEY environment variable.")
            
            openai.api_key = self.api_key
            self.client = openai
        except ImportError:
            raise ImportError("OpenAI package not installed. Please install it with 'pip install openai'.")
    
    def _create_cot_prompt(self, question: str) -> str:
        """
        Create a prompt that encourages Chain of Thought reasoning.
        
        Args:
            question: The question to ask the model
            
        Returns:
            A prompt string that encourages CoT reasoning
        """
        return f"""Please solve the following problem step by step, showing your reasoning:

{question}

Let's think through this step by step:"""
    
    def ask(self, question: str, temperature: float = 0.7, max_tokens: int = 1000) -> Dict[str, Any]:
        """
        Ask a question to the model using Chain of Thought prompting.
        
        Args:
            question: The question to ask
            temperature: Controls randomness in the response (0-1)
            max_tokens: Maximum number of tokens in the response
            
        Returns:
            A dictionary containing the full response and extracted answer
        """
        prompt = self._create_cot_prompt(question)
        
        response = self.client.ChatCompletion.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        full_response = response.choices[0].message.content
        
        # Extract the reasoning and final answer
        reasoning = self._extract_reasoning(full_response)
        answer = self._extract_answer(full_response)
        
        return {
            "question": question,
            "full_response": full_response,
            "reasoning": reasoning,
            "answer": answer
        }
    
    def _extract_reasoning(self, response: str) -> str:
        """Extract the reasoning steps from the response."""
        conclusion_indicators = ["therefore", "thus", "so", "hence", "in conclusion"]
        
        for indicator in conclusion_indicators:
            pattern = re.compile(f"(.*?)({indicator}|{indicator.capitalize()})", re.DOTALL)
            match = pattern.search(response)
            if match:
                return match.group(1).strip()
        
        # If no conclusion indicator is found, return everything except the last sentence
        sentences = response.split('.')
        if len(sentences) > 1:
            return '.'.join(sentences[:-1]).strip()
        
        return response
    
    def _extract_answer(self, response: str) -> str:
        """Extract the final answer from the response."""
        conclusion_indicators = ["therefore", "thus", "so", "hence", "in conclusion", "the answer is"]
        
        for indicator in conclusion_indicators:
            pattern = re.compile(f"({indicator}|{indicator.capitalize()})(.+)", re.DOTALL)
            match = pattern.search(response)
            if match:
                return match.group(2).strip()
        
        # If no conclusion indicator is found, return the last sentence
        sentences = response.split('.')
        if sentences:
            return sentences[-1].strip()
        
        return "No clear answer found"

def example_usage():
    """Example usage of the ModelWithCot class."""
    # Initialize the model
    model = ModelWithCot(api_key="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")
    
    # Ask a question
    question = "If a train travels at 120 km/h and covers a distance of 360 km, how long does the journey take?"
    result = model.ask(question)
    
    print(f"Question: {result['question']}")
    print("\nReasoning:")
    print(result['reasoning'])
    print("\nAnswer:")
    print(result['answer'])

if __name__ == "__main__":
    example_usage()