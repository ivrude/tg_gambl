import random

def generate_number():
    return random.randint(1, 100)

def evaluate_guess(choice: str, bet: int, first: int, second: int):
    if choice == "менше" and second < first:
        return True, bet * 2, first, second
    elif choice == "більше" and second > first:
        return True, bet * 2, first, second
    elif choice == "рівно" and second == first:
        return True, bet * 10, first, second
    else:
        return False, 0, first, second

