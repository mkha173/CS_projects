// Muhammad Saad Khan (251309919)
// cs 3340 asn2

#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <map>

class DisjointSet {
    std::vector<int> parent, rank_;
    int num_sets;
    bool finalized;
    std::vector<int> new_label;
    int total_elements;
public:
    DisjointSet(int n)
        : parent(n+1,0), rank_(n+1,0),
          num_sets(0), finalized(false), total_elements(n) {}

    void make_set(int i) {
        if (finalized) return;
        parent[i] = i; rank_[i] = 0; num_sets++;
    }

    int find_set(int i) {
        if (parent[i] == 0) return 0;
        if (parent[i] != i) parent[i] = find_set(parent[i]);
        return parent[i];
    }

    void union_sets(int i, int j) {
        if (finalized) return;
        int ri = find_set(i), rj = find_set(j);
        if (ri == 0 || rj == 0 || ri == rj) return;
        num_sets--;
        if (rank_[ri] < rank_[rj]) std::swap(ri, rj);
        parent[rj] = ri;
        if (rank_[ri] == rank_[rj]) rank_[ri]++;
    }

    int final_sets() {
        finalized = true;
        std::map<int,int> remap; int counter = 1;
        for (int i = 1; i <= total_elements; i++) {
            if (parent[i] == 0) continue;
            int r = find_set(i);
            if (remap.find(r) == remap.end()) remap[r] = counter++;
        }
        new_label.assign(total_elements+1, 0);
        for (int i = 1; i <= total_elements; i++) {
            if (parent[i] == 0) continue;
            new_label[i] = remap[find_set(i)];
        }
        return num_sets;
    }

    int label(int i) {
        return (i >= 1 && i <= total_elements) ? new_label[i] : 0;
    }
};

int main() {
    std::vector<std::string> img;
    std::string line;
    while (std::getline(std::cin, line)) img.push_back(line);

    int rows = (int)img.size();
    int cols = 0;
    for (auto& r : img) cols = std::max(cols, (int)r.size());
    for (auto& r : img) r.resize(cols, ' ');

    int n = rows * cols;
    auto idx  = [&](int r, int c) { return r * cols + c + 1; };
    auto isP  = [&](int r, int c) {
        return r >= 0 && r < rows && c >= 0 && c < cols && img[r][c] == '+';
    };

    DisjointSet ds(n);
    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++)
            if (isP(r,c)) ds.make_set(idx(r,c));

    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++) {
            if (!isP(r,c)) continue;
            if (isP(r-1,c)) ds.union_sets(idx(r,c), idx(r-1,c));
            if (isP(r,c-1)) ds.union_sets(idx(r,c), idx(r,c-1));
        }

    int K = ds.final_sets();

    std::vector<std::vector<int>> grid(rows, std::vector<int>(cols, 0));
    std::vector<int> sz(K+1, 0);
    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++)
            if (isP(r,c)) {
                int l = ds.label(idx(r,c));
                grid[r][c] = l;
                sz[l]++;
            }

    std::vector<std::pair<int,int>> sizeId;
    for (int i = 1; i <= K; i++) sizeId.push_back({sz[i], i});
    std::sort(sizeId.begin(), sizeId.end(), std::greater<std::pair<int,int>>());

    std::vector<char> ch(K+1, '?');
    for (int k = 0; k < (int)sizeId.size(); k++)
        ch[sizeId[k].second] = (char)('a' + k);

    auto render = [&](int minSz) {
        for (int r = 0; r < rows; r++) {
            for (int c = 0; c < cols; c++) {
                int l = grid[r][c];
                std::cout << (l > 0 && sz[l] > minSz ? ch[l] : ' ');
            }
            std::cout << '\n';
        }
    };

    // ── Output 1: original image ──────────────────────────────────────────────
    std::cout << "================================================================================\n";
    std::cout << "1. INPUT BINARY IMAGE\n";
    std::cout << "================================================================================\n";
    for (auto& row : img) std::cout << row << '\n';
    std::cout << '\n';

    // ── Output 2: all components labelled ────────────────────────────────────
    std::cout << "================================================================================\n";
    std::cout << "2. CONNECTED COMPONENT IMAGE (all components)\n";
    std::cout << "================================================================================\n";
    render(-1);
    std::cout << '\n';

    // ── Output 3: sorted list ─────────────────────────────────────────────────
    std::cout << "================================================================================\n";
    std::cout << "3. COMPONENT LIST (sorted by size, largest first)\n";
    std::cout << "================================================================================\n";
    std::cout << "  label   size\n";
    std::cout << "  -----   ----\n";
    for (auto& [s, id] : sizeId)
        std::cout << "    " << ch[id] << "      " << s << '\n';
    std::cout << "\n  Total components: " << K << '\n';
    std::cout << '\n';

    // ── Output 4: size > 1 ────────────────────────────────────────────────────
    std::cout << "================================================================================\n";
    std::cout << "4. COMPONENTS WITH SIZE > 1\n";
    std::cout << "================================================================================\n";
    render(1);
    std::cout << '\n';

    // ── Output 5: size > 4 ────────────────────────────────────────────────────
    std::cout << "================================================================================\n";
    std::cout << "5. COMPONENTS WITH SIZE > 4\n";
    std::cout << "================================================================================\n";
    render(4);
    std::cout << '\n';

    return 0;
}