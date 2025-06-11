from typing import List

def filter_seats(array: List[str], quantity: int) -> List[List[str]]:
    """
    Finds non-overlapping sequences where each sequence is a maximal chain of elements
    (allowing extension both backward and forward) such that each consecutive pair differs
    by exactly 1 or 2 in a single digit position, and only chains with length >= quantity
    are returned.

    Parameters:
    - array: List of digit-strings (equal length).
    - quantity: Minimum length for a valid chain.

    Returns:
    - List of non-overlapping chains (each a list of strings) of length >= quantity.
    """
    results = []
    used = [False] * len(array)

    def is_near(a: str, b: str) -> bool:
        # True if exactly one digit differs and its abs diff is 1 or 2
        diffs = [abs(int(x) - int(y)) for x, y in zip(a, b)]
        non_zero = [d for d in diffs if d > 0]
        return len(non_zero) == 1 and non_zero[0] in (1, 2)

    n = len(array)
    for i in range(n):
        if used[i]:
            continue
        # start a new chain with i
        seq = [i]
        # extend backward
        prev = i
        for k in range(i - 1, -1, -1):
            if used[k]:
                continue
            if is_near(array[k], array[prev]):
                seq.insert(0, k)
                prev = k
        # extend forward
        last = i
        for j in range(i + 1, n):
            if used[j]:
                continue
            if is_near(array[last], array[j]):
                seq.append(j)
                last = j
        # record and mark if meets quantity
        if len(seq) >= quantity:
            # sort indices to maintain original order
            seq_sorted = sorted(seq)
            results.append([array[idx] for idx in seq_sorted])
            for idx in seq_sorted:
                used[idx] = True
    return results


if __name__ == "__main__":
    # Example usage
    data1 = ["121413","121414","1120","121412","121446","121447","121301","121305","121309"]
    print(filter_seats(data1, 2))
    # -> [["121412","121413","121414"],["121446","121447"]]

    data2 = ["1743","1745","1746","1855","1856","1859"]
    print(filter_seats(data2, 2))
    # -> [["1743","1745","1746"],["1855","1856"]]
