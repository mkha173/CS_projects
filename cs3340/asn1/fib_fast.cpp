// Muhammad Saad Khan
// 251309919

#include <iostream>
#include <vector>
using namespace std;

struct BigInt {
    vector<int> d;

    BigInt(long long x = 0) {
        if (x == 0) d.push_back(0);
        while (x > 0) {
            d.push_back(x % 10);
            x /= 10;
        }
    }

    BigInt operator+(const BigInt& other) const {
        BigInt res;
        res.d.clear();
        int carry = 0;
        size_t n = max(d.size(), other.d.size());
        for (size_t i = 0; i < n || carry; i++) {
            int sum = carry;
            if (i < d.size()) sum += d[i];
            if (i < other.d.size()) sum += other.d[i];
            res.d.push_back(sum % 10);
            carry = sum / 10;
        }
        return res;
    }

    void print() const {
        for (int i = d.size() - 1; i >= 0; i--)
            cout << d[i];
    }
};

pair<BigInt, BigInt> fib_fast(int n) {
    if (n == 0) return {BigInt(0), BigInt(0)};
    if (n == 1) return {BigInt(1), BigInt(0)};
    auto prev = fib_fast(n - 1);
    BigInt Fn = prev.first + prev.second;
    return {Fn, prev.first};
}

int main() {
    for (int i = 0; i <= 25; i++) {
        int n = i * 20;
        auto result = fib_fast(n);
        cout << "F(" << n << ") = ";
        result.first.print();
        cout << endl;
    }
    return 0;
}
