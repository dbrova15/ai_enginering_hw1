"""Глобальний one-to-one matching без залежності від порядку елементів."""

from dataclasses import dataclass


@dataclass
class Edge:
    """Ребро залишкової мережі: куди пройти, зворотний індекс, місткість і ціна."""

    target: int
    reverse: int
    capacity: int
    cost: int


def _add(graph: list[list[Edge]], start: int, end: int, cost: int) -> Edge:
    """Додає пряме й зворотне ребра; зворотне дозволяє виправити попередню пару."""
    forward = Edge(end, len(graph[end]), 1, cost)
    backward = Edge(start, len(graph[start]), 0, -cost)
    graph[start].append(forward)
    graph[end].append(backward)
    return forward


def _augment(graph: list[list[Edge]], source: int, sink: int) -> bool:
    """Шукає найдешевший додатковий шлях Bellman–Ford та змінює місткості.

    Від’ємні ціни потрібні для переваги сильних доказів; після кожного шляху
    попередні рішення можуть бути перебудовані через зворотні ребра.
    """
    distances = [float('inf')] * len(graph)
    parents = [None] * len(graph)
    distances[source] = 0
    for _ in range(len(graph) - 1):
        changed = False
        for node, edges in enumerate(graph):
            for index, edge in enumerate(edges):
                candidate = distances[node] + edge.cost
                if edge.capacity and candidate < distances[edge.target]:
                    distances[edge.target] = candidate
                    parents[edge.target] = (node, index)
                    changed = True
        if not changed:
            break
    if parents[sink] is None:
        return False
    node = sink
    while node != source:
        previous, index = parents[node]
        edge = graph[previous][index]
        edge.capacity -= 1
        graph[node][edge.reverse].capacity += 1
        node = previous
    return True


def optimal_pairs(left: int, right: int, candidates: dict[tuple[int, int], int],
                  forbidden: tuple[int, int] | None = None) -> tuple[list, tuple]:
    """Максимізує спочатку число пар, потім суму цілих рівнів доказовості."""
    sink = left + right + 1
    graph = [[] for _ in range(sink + 1)]
    for index in range(left):
        _add(graph, 0, index + 1, 0)
    for index in range(right):
        _add(graph, left + 1 + index, sink, 0)
    edges = {}
    for pair, weight in sorted(candidates.items()):
        if pair != forbidden:
            edges[pair] = _add(graph, pair[0] + 1, left + pair[1] + 1, -weight)
    while _augment(graph, 0, sink):
        pass
    pairs = sorted(pair for pair, edge in edges.items() if edge.capacity == 0)
    return pairs, (len(pairs), sum(candidates[pair] for pair in pairs))


def forced_pairs(left: int, right: int, candidates: dict[tuple[int, int], int]) -> dict:
    """Повертає тільки пари, що існують у кожному оптимальному призначенні.

    Якщо заборона ребра не погіршує оптимум, воно неоднозначне. Таким чином
    рівноцінні варіанти не стають правильними через порядок входу.
    """
    selected, objective = optimal_pairs(left, right, candidates)
    forced, ambiguous = [], []
    for pair in selected:
        _, alternative = optimal_pairs(left, right, candidates, pair)
        (forced if alternative != objective else ambiguous).append(pair)
    fixed_left = {a for a, _ in forced}
    fixed_right = {b for _, b in forced}
    review_edges = [pair for pair in candidates
                    if pair[0] not in fixed_left and pair[1] not in fixed_right]
    return {'pairs': forced, 'review_edges': sorted(review_edges),
            'objective': objective, 'ambiguous_selected': ambiguous}
