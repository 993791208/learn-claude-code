def greet(name: str) -> str:
    """
    Generate a greeting message for the given name.
    
    Args:
        name (str): The name to greet
        
    Returns:
        str: A greeting message in the format "Hello, {name}!"
    """
    return f"Hello, {name}!"

def add_numbers(a: int, b: int) -> int:
    """
    Add two numbers together.
    
    Args:
        a (int): The first number
        b (int): The second number
        
    Returns:
        int: The sum of a and b
    """
    return a + b

def print_message() -> None:
    """
    Main program function that greets the user and demonstrates addition.
    
    This function welcomes the user, asks for their name, greets them,
    and demonstrates the add_numbers function with example values.
    """
    print("Welcome to the program!")
    name = input("Enter your name: ")
    message = greet(name)
    print(message)
    result = add_numbers(5, 3)
    print(f"The sum of 5 and 3 is {result}")


def main() -> None:
    """Main entry point for the program."""
    print_message()


if __name__ == "__main__":
    main()