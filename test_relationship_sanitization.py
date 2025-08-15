#!/usr/bin/env python3
"""Test script for relationship sanitization function"""

def sanitize_relationship_type(relationship_type: str) -> str:
    """
    Sanitize relationship type for Neo4j compatibility.
    Neo4j relationship types cannot contain spaces or special characters.
    Converts spaces and special characters to underscores.
    """
    if not relationship_type:
        return "RELATED_TO"
    
    # Convert to uppercase and replace problematic characters
    sanitized = relationship_type.upper()
    # Replace spaces, hyphens, dots, and other special chars with underscores
    sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
    # Remove consecutive underscores
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    
    # Ensure it's not empty and starts with a letter or underscore
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"REL_{sanitized}" if sanitized else "RELATED_TO"
        
    return sanitized

# Test cases from the logs
test_cases = [
    "COMMUNICATES WITH",
    "MAKES API CALLS TO", 
    "HAS ISO CONNECTIVITY WITH",
    "depends on",
    "connected to",
    "processes",
    "hosts",
    "uses",
    "",
    "123starts_with_number",
    "has-dashes",
    "has.dots",
    "has/slashes",
    "has@symbols#",
]

print("Testing relationship type sanitization:")
print("=" * 50)

for test_case in test_cases:
    sanitized = sanitize_relationship_type(test_case)
    print(f"'{test_case}' -> '{sanitized}'")

print("\n" + "=" * 50)
print("All tests completed successfully!")
