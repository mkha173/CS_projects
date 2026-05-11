# Muhammad Saad Khan
# 251309919
import sys

class Heap:
    def __init__(self, keys, n):
        self._INF   = keys[0]
        self._n     = n
        self._size  = n
        self._key  = keys[:]
        self._pos  = list(range(n + 1))
        self._heap = list(range(n + 1))
        for i in range(n // 2, 0, -1):
            self._sift_down(i)

    def _swap(self, i, j):
        id_i, id_j = self._heap[i], self._heap[j]
        self._heap[i], self._heap[j] = id_j, id_i
        self._pos[id_i], self._pos[id_j] = j, i

    def _sift_up(self, i):
        while i > 1:
            p = i // 2
            if self._key[self._heap[p]] > self._key[self._heap[i]]:
                self._swap(i, p)
                i = p
            else:
                break

    def _sift_down(self, i):
        while True:
            smallest = i
            l, r = 2 * i, 2 * i + 1
            if l <= self._size and self._key[self._heap[l]] < self._key[self._heap[smallest]]:
                smallest = l
            if r <= self._size and self._key[self._heap[r]] < self._key[self._heap[smallest]]:
                smallest = r
            if smallest != i:
                self._swap(i, smallest)
                i = smallest
            else:
                break

    def in_heap(self, id):
        return 1 <= id <= self._n and self._pos[id] <= self._size and self._heap[self._pos[id]] == id

    def is_empty(self):
        return self._size == 0

    def min_key(self):
        return self._key[self._heap[1]]

    def min_id(self):
        return self._heap[1]

    def key(self, id):
        return self._key[id]

    def delete_min(self):
        if self._size == 0:
            return None
        min_id = self._heap[1]
        self._swap(1, self._size)
        self._pos[min_id] = 0
        self._size -= 1
        if self._size > 0:
            self._sift_down(1)
        return min_id

    def decrease_key(self, id, new_key):
        if new_key < self._key[id]:
            self._key[id] = new_key
            self._sift_up(self._pos[id])


def read_graph(filename):
    if filename in ('/dev/stdin', '-'):
        import sys as _sys
        lines = _sys.stdin.read().split('\n')
    else:
        with open(filename) as f:
            lines = f.read().split('\n')
    idx = 0
    while idx < len(lines) and lines[idx].strip() == '':
        idx += 1
    n = int(lines[idx].strip()); idx += 1
    adj = [[] for _ in range(n + 1)]
    for line in lines[idx:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        u, v, w = int(parts[0]), int(parts[1]), int(parts[2])
        adj[u].append((v, w))
        adj[v].append((u, w))
    return n, adj


def prim(n, adj, root=1):
    INF = float('inf')
    keys = [INF] * (n + 1)
    keys[root] = 0
    parent = [0] * (n + 1)
    parent[root] = -1
    heap = Heap(keys, n)
    mst_edges = []
    while not heap.is_empty():
        u = heap.delete_min()
        if u != root:
            mst_edges.append((parent[u], u, heap._key[u]))
        for (v, w) in adj[u]:
            if heap.in_heap(v) and w < heap._key[v]:
                parent[v] = u
                heap.decrease_key(v, w)
    return mst_edges


def print_adjacency_list(n, adj):
    print("=" * 60)
    print("ADJACENCY LIST REPRESENTATION")
    print("=" * 60)
    for u in range(1, n + 1):
        neighbors = ", ".join(f"{v}(w={w})" for v, w in sorted(adj[u]))
        print(f"  {u:2d}: [{neighbors}]")
    print()

def print_mst(mst_edges):
    print("=" * 60)
    print("MINIMUM SPANNING TREE EDGES  (Prim's, root = 1)")
    print("=" * 60)
    total = 0
    for (p, c, w) in mst_edges:
        print(f"  ({p}, {c}) : {w}")
        total += w
    print()
    print(f"Total MST weight: {total}")
    print("=" * 60)


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "sssp_graph_medium.txt"
    n, adj = read_graph(filename)
    print_adjacency_list(n, adj)
    mst_edges = prim(n, adj, root=1)
    print_mst(mst_edges)
