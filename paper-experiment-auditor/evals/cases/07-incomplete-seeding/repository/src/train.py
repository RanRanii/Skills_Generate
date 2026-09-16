import random


INITIAL_WEIGHT = random.random()


def main() -> None:
    random.seed(42)
    print(INITIAL_WEIGHT)


if __name__ == "__main__":
    main()
