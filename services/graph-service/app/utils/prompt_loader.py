"""
Utility for loading prompts from JSON files in the prompts directory
"""
import os
import json
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Get the prompts directory path
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt(prompt_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a prompt by ID from the prompts directory.
    
    Args:
        prompt_id: The prompt ID (filename without .json extension)
        
    Returns:
        Dictionary containing prompt data or None if not found
    """
    try:
        prompt_file = os.path.join(PROMPTS_DIR, f"{prompt_id}.json")
        
        if not os.path.exists(prompt_file):
            logger.warning(f"Prompt file not found: {prompt_file}")
            return None
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_data = json.load(f)
        
        logger.debug(f"Successfully loaded prompt: {prompt_id}")
        return prompt_data
        
    except Exception as e:
        logger.error(f"Failed to load prompt {prompt_id}: {e}")
        return None


def get_prompt_text(prompt_id: str, variables: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Load a prompt and optionally substitute variables.
    
    Args:
        prompt_id: The prompt ID
        variables: Dictionary of variable name -> value for substitution
        
    Returns:
        Prompt text with variables substituted, or None if not found
    """
    prompt_data = load_prompt(prompt_id)
    
    if not prompt_data:
        return None
    
    prompt_text = prompt_data.get("text", "")
    
    # Substitute variables if provided
    if variables:
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            prompt_text = prompt_text.replace(placeholder, str(var_value))
    
    return prompt_text


def list_prompts() -> list:
    """
    List all available prompts in the prompts directory.
    
    Returns:
        List of prompt IDs (filenames without .json extension)
    """
    try:
        if not os.path.exists(PROMPTS_DIR):
            logger.warning(f"Prompts directory not found: {PROMPTS_DIR}")
            return []
        
        prompt_files = [
            f[:-5] for f in os.listdir(PROMPTS_DIR)
            if f.endswith('.json')
        ]
        
        return sorted(prompt_files)
        
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        return []
