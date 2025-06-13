from typing import List, Dict, Any
from collections import deque
import random
from collections import defaultdict
import json
from pprint import pprint

Point = Dict[str, float]

def get_random_chain_slice(chains: List[List[Point]], quantity: int) -> List[Point]:
    """
    Randomly pick one chain from the list and return a random slice of 'quantity' points.
    If the selected chain has fewer points than 'quantity', return the full chain.
    """
    if not chains:
        return []

    chain = random.choice(chains)
    if len(chain) <= quantity:
        return chain

    start_index = random.randint(0, len(chain) - quantity)
    return chain[start_index:start_index + quantity]


def build_proximity_graph(
    points: List[Point],
    max_dx: float = 40.0,
    max_dy: float = 25.0
) -> List[List[int]]:
    """
    Return an adjacency list for points: graph[i] is a list of indices j
    such that points[i] is within the given dx/dy of points[j].
    """
    n = len(points)
    graph = [[] for _ in range(n)]
    
    for i in range(n):
        for j in range(i+1, n):
            dx = abs(points[i]['x'] - points[j]['x'])
            dy = abs(points[i]['y'] - points[j]['y'])
            if dx <= max_dx and dy <= max_dy:
                graph[i].append(j)
                graph[j].append(i)
    return graph


def connected_components(graph: List[List[int]]) -> List[List[int]]:
    """
    Return a list of components, each as the list of node-indices in that component.
    """
    seen = set()
    comps = []
    for start in range(len(graph)):
        if start in seen:
            continue
        # BFS/DFS from start
        queue = deque([start])
        comp = []
        seen.add(start)
        while queue:
            u = queue.popleft()
            comp.append(u)
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        comps.append(comp)
    return comps


def get_nearby_chains(
    points: List[Point],
    quantity: int,
    max_dx: float = 40.0,
    max_dy: float = 25.0
) -> List[List[Point]]:
    """
    1. Build the proximity graph on `points`.
    2. Extract all connected components.
    3. Keep only those of size >= quantity.
    4. Return them as lists of point-dicts, each sorted by descending y.
    """
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    
    graph = build_proximity_graph(points, max_dx, max_dy)
    comps = connected_components(graph)
    
    # Filter + convert index-lists to actual point-lists
    valid_chains = []
    for comp in comps:
        if len(comp) >= quantity:
            chain = [points[i] for i in comp]
            # sort chain however you like; we'll do descending Y
            chain.sort(key=lambda p: -p['y'])
            valid_chains.append(chain)
    
    return valid_chains

# new

def find_nearby_chains(
    features: List[Dict[str, Any]],
    desired_length: int,
    desired_category: str
) -> List[List[Dict[str, Any]]]:
    """
    Find all maximal chains of seats such that:
      - areaName, seatCategory and row are identical
      - when sorted by seat number, each adjacent difference <= 2
      - only returns chains whose length is >= desired_length

    Args:
        features: list of feature dicts (each with .properties containing row, number, areaName, seatCategory)
        desired_length: minimum chain length to include

    Returns:
        List of chains, each a list of feature dicts in ascending seat number order
    """
    # 1) Group by (areaName, seatCategory, row)
    groups = defaultdict(list)
    for feat in features:
        p = feat["properties"]
        key = (p["areaName"], p["seatCategory"], int(p["row"]))
        num = int(p["number"])
        groups[key].append((num, feat))

    result = []
    # 2) For each group, sort and build maximal runs
    for key, items in groups.items():
        items.sort(key=lambda x: x[0])
        current_run = [items[0]]  # start the first run
        if not key[1].lower() == desired_category.lower(): continue
        for prev, curr in zip(items, items[1:]):
            prev_num, _ = prev
            curr_num, _ = curr

            # if seats are "nearby", continue the run
            if curr_num - prev_num <= 2:
                current_run.append(curr)
            else:
                # run breaks — check length and reset
                if len(current_run) >= desired_length:
                    # extract just the feature dicts in order
                    result.append([feat for _, feat in current_run])
                current_run = [curr]

        # check the last run
        if len(current_run) >= desired_length:
            result.append([feat for _, feat in current_run])

    return result



if __name__ == "__main__":
    # arr2 = [{'x': 310, 'y': 143}, {'x': 273, 'y': 75}, {'x': 237, 'y': 369}, {'x': 455, 'y': 301}, {'x': 310, 'y': 30}, {'x': 92, 'y': 324}, {'x': 201, 'y': 30}, {'x': 310, 'y': 188}, {'x': 201, 'y': 52}, {'x': 310, 'y': 211}, {'x': 201, 'y': 75}, {'x': 165, 'y': 120}, {'x': 310, 'y': 165}, {'x': 382, 'y': 324}, {'x': 273, 'y': 188}, {'x': 382, 'y': 165}, {'x': 310, 'y': 120}, {'x': 165, 'y': 165}, {'x': 201, 'y': 188}, {'x': 273, 'y': 30}, {'x': 237, 'y': 75}, {'x': 201, 'y': 279}, {'x': 237, 'y': 324}, {'x': 201, 'y': 369}, {'x': 455, 'y': 143}, {'x': 237, 'y': 301}, {'x': 165, 'y': 75}, {'x': 92, 'y': 279}, {'x': 273, 'y': 369}, {'x': 237, 'y': 256}, {'x': 128, 'y': 188}, {'x': 165, 'y': 256}, {'x': 382, 'y': 301}, {'x': 237, 'y': 279}, {'x': 310, 'y': 256}, {'x': 310, 'y': 347}, {'x': 310, 'y': 75}, {'x': 310, 'y': 234}, {'x': 455, 'y': 347}, {'x': 165, 'y': 211}, {'x': 201, 'y': 324}, {'x': 92, 'y': 120}, {'x': 201, 'y': 234}, {'x': 273, 'y': 120}, {'x': 128, 'y': 301}, {'x': 237, 'y': 234}, {'x': 237, 'y': 165}, {'x': 92, 'y': 301}, {'x': 310, 'y': 369}, {'x': 92, 'y': 234}, {'x': 128, 'y': 279}, {'x': 273, 'y': 165}, {'x': 201, 'y': 120}, {'x': 455, 'y': 279}, {'x': 273, 'y': 347}, {'x': 455, 'y': 165}, {'x': 237, 'y': 211}, {'x': 201, 'y': 301}, {'x': 92, 'y': 256}, {'x': 201, 'y': 211}, {'x': 455, 'y': 324}, {'x': 165, 'y': 347}, {'x': 455, 'y': 98}, {'x': 92, 'y': 188}, {'x': 273, 'y': 324}, {'x': 165, 'y': 30}, {'x': 310, 'y': 52}, {'x': 455, 'y': 211}, {'x': 165, 'y': 98}, {'x': 201, 'y': 347}, {'x': 201, 'y': 143}, {'x': 92, 'y': 165}, {'x': 237, 'y': 52}, {'x': 455, 'y': 256}, {'x': 128, 'y': 256}, {'x': 92, 'y': 211}, {'x': 455, 'y': 120}, {'x': 273, 'y': 301}, {'x': 128, 'y': 120}, {'x': 128, 'y': 52}, {'x': 310, 'y': 324}, {'x': 165, 'y': 301}, {'x': 165, 'y': 324}, {'x': 273, 'y': 234}, {'x': 237, 'y': 30}, {'x': 455, 'y': 75}, {'x': 273, 'y': 52}, {'x': 382, 'y': 234}, {'x': 273, 'y': 256}, {'x': 201, 'y': 256}, {'x': 455, 'y': 188}, {'x': 92, 'y': 143}, {'x': 382, 'y': 188}, {'x': 128, 'y': 75}, {'x': 165, 'y': 234}, {'x': 128, 'y': 234}, {'x': 310, 'y': 98}, {'x': 128, 'y': 165}, {'x': 165, 'y': 279}, {'x': 273, 'y': 211}, {'x': 128, 'y': 98}, {'x': 237, 'y': 143}, {'x': 201, 'y': 98}, {'x': 382, 'y': 256}, {'x': 382, 'y': 211}, {'x': 237, 'y': 188}, {'x': 310, 'y': 301}, {'x': 273, 'y': 98}, {'x': 310, 'y': 279}, {'x': 128, 'y': 30}, {'x': 128, 'y': 211}, {'x': 237, 'y': 347}, {'x': 165, 'y': 52}, {'x': 273, 'y': 279}, {'x': 382, 'y': 279}, {'x': 165, 'y': 188}, {'x': 201, 'y': 165}, {'x': 382, 'y': 347}, {'x': 273, 'y': 143}, {'x': 165, 'y': 143}, {'x': 455, 'y': 234}, {'x': 128, 'y': 324}, {'x': 128, 'y': 143}]
    # arr3 = [{'x': 237, 'y': 211}, {'x': 310, 'y': 211}, {'x': 382, 'y': 256}, {'x': 128, 'y': 279}, {'x': 310, 'y': 29}, {'x': 128, 'y': 188}, {'x': 201, 'y': 29}, {'x': 128, 'y': 256}, {'x': 165, 'y': 256}, {'x': 165, 'y': 301}, {'x': 237, 'y': 166}, {'x': 201, 'y': 369}, {'x': 273, 'y': 188}, {'x': 237, 'y': 256}, {'x': 455, 'y': 143}, {'x': 237, 'y': 392}, {'x': 273, 'y': 301}, {'x': 273, 'y': 211}, {'x': 382, 'y': 53}, {'x': 310, 'y': 301}, {'x': 310, 'y': 324}, {'x': 273, 'y': 120}, {'x': 237, 'y': 98}, {'x': 273, 'y': 279}, {'x': 92, 'y': 324}, {'x': 455, 'y': 53}, {'x': 455, 'y': 29}, {'x': 455, 'y': 7}, {'x': 237, 'y': 369}, {'x': 382, 'y': 29}, {'x': 310, 'y': 346}, {'x': 201, 'y': 53}, {'x': 273, 'y': 166}, {'x': 382, 'y': 75}, {'x': 346, 'y': 392}, {'x': 237, 'y': 53}, {'x': 128, 'y': 233}, {'x': 165, 'y': 369}, {'x': 201, 'y': 392}, {'x': 128, 'y': 301}, {'x': 273, 'y': 7}, {'x': 346, 'y': 369}, {'x': 128, 'y': 324}, {'x': 273, 'y': 369}, {'x': 165, 'y': 233}, {'x': 237, 'y': 324}, {'x': 237, 'y': 143}, {'x': 273, 'y': 143}, {'x': 237, 'y': 75}, {'x': 237, 'y': 346}, {'x': 165, 'y': 324}, {'x': 165, 'y': 211}, {'x': 237, 'y': 188}, {'x': 165, 'y': 346}, {'x': 165, 'y': 392}, {'x': 237, 'y': 279}, {'x': 273, 'y': 346}, {'x': 310, 'y': 75}, {'x': 310, 'y': 98}, {'x': 273, 'y': 392}, {'x': 273, 'y': 256}, {'x': 128, 'y': 211}, {'x': 310, 'y': 369}, {'x': 201, 'y': 346}, {'x': 92, 'y': 369}, {'x': 92, 'y': 392}, {'x': 165, 'y': 7}, {'x': 92, 'y': 256}, {'x': 237, 'y': 233}, {'x': 273, 'y': 29}, {'x': 237, 'y': 120}, {'x': 273, 'y': 324}, {'x': 128, 'y': 369}, {'x': 92, 'y': 346}, {'x': 310, 'y': 256}, {'x': 201, 'y': 7}, {'x': 455, 'y': 324}, {'x': 382, 'y': 233}, {'x': 92, 'y': 233}, {'x': 165, 'y': 279}, {'x': 310, 'y': 188}, {'x': 92, 'y': 301}, {'x': 128, 'y': 392}, {'x': 310, 'y': 7}, {'x': 455, 'y': 392}, {'x': 310, 'y': 53}, {'x': 310, 'y': 233}, {'x': 310, 'y': 143}, {'x': 310, 'y': 120}, {'x': 310, 'y': 279}, {'x': 165, 'y': 188}, {'x': 310, 'y': 392}, {'x': 128, 'y': 346}, {'x': 237, 'y': 301}, {'x': 310, 'y': 166}, {'x': 92, 'y': 279}, {'x': 273, 'y': 233}, {'x': 382, 'y': 143}, {'x': 382, 'y': 120}, {'x': 382, 'y': 166}, {'x': 455, 'y': 166}, {'x': 455, 'y': 346}, {'x': 455, 'y': 369}, {'x': 455, 'y': 75}, {'x': 455, 'y': 279}, {'x': 455, 'y': 98}, {'x': 455, 'y': 120}, {'x': 455, 'y': 301}]
    
    # chains = get_nearby_chains(arr3, quantity=4)
    # random_slice = get_random_chain_slice(chains, 4)
    # print(random_slice)
    # for i, chain in enumerate(chains, 1):
    #     print(f"Chain {i} (size {len(chain)}):")
    #     for pt in chain:
    #         print("  ", pt)
    with open('./cast/freeSeats.json', 'r') as file:
        data = json.load(file)

        chains = find_nearby_chains(data["features"], 2, 'Category 2')
        # for chain in chains:
        #     chain = random.choice(chains)
        #     nums = [f["properties"]["number"] for f in chain]
        #     print(f"Chain of {len(chain)} seats:", nums)
        # print(chains)
        chain = random.choice(chains)
        nums = [f["properties"]["number"] for f in chain]
        print(f"Chain of {len(chain)} seats:", nums)
        random_chain = get_random_chain_slice(chains, 2)
        pprint(random_chain)
        product_id
        twe25rss = f'UEFA_TWE25RSS_{product_id}_{performance_id}_{seat_map_selection}_{aread_id}_{block_id}_{tariff_id}_{seat_category_id}_{amount}'