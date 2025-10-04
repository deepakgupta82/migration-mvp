"""
Prompt loader utility for document service.
Loads prompts from JSON files in the prompts directory.
"""
import os
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


# Get the prompts directory path
SERVICE_DIR = Path(__file__).parent.parent
PROMPTS_DIR = SERVICE_DIR / "prompts"


def load_prompt(prompt_id: str) -> Dict[str, Any]:
    """
    Load a prompt from the prompts directory.
    
    Args:
        prompt_id: The ID of the prompt to load (without .json extension)
        
    Returns:
        Dictionary containing prompt data
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
        json.JSONDecodeError: If prompt file is invalid JSON
    """
    prompt_path = PROMPTS_DIR / f"{prompt_id}.json"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_prompt_text(prompt_id: str, variables: Optional[Dict[str, str]] = None) -> str:
    """
    Load a prompt and substitute variables.
    
    Args:
        prompt_id: The ID of the prompt to load
        variables: Dictionary of variable name -> value mappings
        
    Returns:
        Prompt text with variables substituted
    """
    prompt_data = load_prompt(prompt_id)
    text = prompt_data.get("text", "")
    
    if variables:
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            text = text.replace(placeholder, str(var_value))
    
    return text


def list_prompts() -> List[str]:
    """
    List all available prompt IDs.
    
    Returns:
        List of prompt IDs (without .json extension)
    """
    if not PROMPTS_DIR.exists():
        return []
    
    return [
        f.stem for f in PROMPTS_DIR.glob("*.json")
        if f.is_file()
    ]
