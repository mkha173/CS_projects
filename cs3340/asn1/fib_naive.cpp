// Muhammad Saad Khan 
// 251309919

#include <iostream>
using namespace std;

long long fib(int n) {
    if (n == 0) return 0;
    if (n == 1) return 1;
    return fib(n - 1) + fib(n - 2);
}

int main() {
    for (int i = 0; i <= 10; i++) {
        int n = i * 5;
        cout << "F(" << n << ") = " << fib(n) << endl;
    }
    return 0;
}
