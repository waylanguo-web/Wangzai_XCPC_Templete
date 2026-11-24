"""Regression cases extracted from the chapter Markdown files."""


def case(name, snippets, main="", **options):
    return dict(name=name, snippets=snippets, main=main, **options)


PLANAR = [
    "using ld = long double;",
    "template<class T> struct Point {",
    "T cross(Point<T> a, Point<T> b)",
    "T dot(Point<T> a, Point<T> b)",
    "ld dis(T x1, T y1, T x2, T y2)",
    "Point<T> rotate(Point<T> p1, Point<T> p2)",
    "Point<ld> rotate(Point<ld> p, ld rad)",
    "Point<ld> rotate(Point<ld> a, Point<ld> b, ld rad)",
    "int pointOnLineLeft(Point<T> p",
    "Point<ld> lineIntersection(Line<ld>",
    "pointToLine(Point<ld>",
    "bool pointOnSegment(Point<T> p",
    "pointToSegment(Point<ld>",
    "Line<ld> midSegment(Line<T>",
    "tuple<int, Point<T>, Point<T>> segmentIntersection",
    "bool segmentsIntersect(Line<T>",
]

SPATIAL = [
    "using ld = long double;",
    "struct Point3 {",
    "ld len(P3 p)",
    "bool onLine(P3 p1",
    "bool onPlane(P3 p1",
    "bool pointOnSegment(P3 p",
    "bool pointOnSegmentSide(P3",
    "bool lineParallel(L3",
    "bool planeParallel(Plane",
    "bool same(Plane",
    "bool linePlaneParallel(L3",
    "bool segmentIntersection(L3",
    "pair<bool, P3> lineIntersection(L3",
    "pair<bool, P3> linePlaneCross(L3",
    "pair<bool, L3> planeIntersection(Plane",
    "pair<ld, P3> pointToLine(P3",
    "tuple<ld, P3, P3> lineToLine",
]

REGRESSIONS = [
    case("tree_subtree_direction", ["int get_siz(int p, int u)"], r"""
signed main() {
    n = 5;
    for (auto item : {make_pair(1, 2), make_pair(1, 3), make_pair(2, 4), make_pair(2, 5)}) {
        auto u = get<0>(item);
        auto v = get<1>(item);
        g[u].push_back(v);
        g[v].push_back(u);
    }
    dfs(1);
    assert(get_siz(1, 2) == 3 && get_siz(2, 1) == 2);
    assert(get_siz(4, 2) == 4 && get_siz(2, 4) == 1);
    dfs(4);
    assert(siz[4] == n && siz[2] == 4);
    assert(get_siz(1, 2) == 3 && get_siz(2, 1) == 2);
}
"""),
    case("polynomial", [
        "template<class T> constexpr T mypow(T n, int k)",
        "struct Poly : public",
        "void dft(vector<Zmod<P>>",
        "Poly<P> berlekampMassey",
        "linearRecurrence(Poly<P>",
    ], r"""
signed main() {
    auto recurrence = berlekampMassey(Poly<>{0, 1, 1, 2, 3, 5, 8, 13});
    assert(recurrence.size() == 3 && recurrence[0] == 1);
    assert(recurrence[1] == -1 && recurrence[2] == -1);
    assert(linearRecurrence(Poly<>{0, 1}, recurrence, 10) == 55);

    Poly<> p{1, 2, 1};
    auto root = p.sqrt(3);
    assert(root[0] == 1 && root[1] == 1 && root[2] == 0);
    auto cube = Poly<>{1, 1}.pow(3, 4);
    assert(cube[0] == 1 && cube[1] == 3 && cube[2] == 3 && cube[3] == 1);
    auto values = p.eval({0, 1, 2});
    assert(values[0] == 1 && values[1] == 4 && values[2] == 9);

    Poly<> a(130), b(130);
    fill(a.begin(), a.end(), 1);
    fill(b.begin(), b.end(), 1);
    auto product = a * b;
    for (int i = 0; i < 259; ++i) {
        assert(product[i] == min(i + 1, 259 - i));
    }
}
"""),
    case("dinic_reset_against_cuts", ["template<typename T> struct Flow_"], r"""
signed main() {
    mt19937 rng(42);
    for (int trial = 0; trial < 100; ++trial) {
        int n = 2 + rng() % 5;
        Flow flow(n);
        vector<array<int, 3>> edges;
        for (int i = 0; i < 20; ++i) {
            int u = rng() % n, v = rng() % n, w = rng() % 8;
            flow.add(u, v, w);
            edges.push_back({u, v, w});
        }
        int best = LLONG_MAX;
        for (int mask = 1; mask < (1LL << (n - 1)); mask += 2) {
            int cut = 0;
            for (auto item : edges) {
                auto u = get<0>(item);
                auto v = get<1>(item);
                auto w = get<2>(item);
                if ((mask >> u & 1) && !(mask >> v & 1)) cut += w;
            }
            best = min(best, cut);
        }
        assert(flow.work(0, n - 1) == best);
        flow.reset();
        assert(flow.work(0, n - 1) == best);
    }
}
"""),
    case("bezout_program", ["int n, a, ans;"], input="3\n-6 15 9\n", output="3"),
    case("totient_sieve_program", ["void euler(int n)"], input="5\n", output="1 1 2 2 4"),
    case("mobius_count_program", ["void getMu()"], input="1\n3 3 1\n", output="7"),
    case("division_blocks_program", ["j = n / (n / i);"], input="1\n4\n", output="8"),
    case("gauss_program", ["int gauss(){"], input="2\n1 1 3\n1 -1 1\n", output="2.00 1.00"),
    case("cantor_inverse_program", ["void jie_cheng(int n)", "vector<int> kangtuo_inv("],
         output="2 4 5 3 1", rename_main=["void jie_cheng(int n)"]),
    case("point_fixed_decimal", ["const int Knum = 4;"], r"""
signed main() {
    assert(read() == 2147490000LL);
    assert(read() == -12300);
}
""", input="214749 -1.23"),
    case("graph_matching_reuse", ["struct HopcroftKarp {", "struct MaxCostMatch {"], r"""
signed main() {
    HopcroftKarp hk(1, 1);
    hk.add(0, 0);
    assert(hk.work() == 1 && hk.work() == 1);
    MaxCostMatch km(2);
    km.add(1, 1, 0);
    km.add(2, 2, 4);
    assert(km.work() == 4 && km.work() == 4);
    auto leftData = km.answer(2, 2);
    auto left = get<0>(leftData);
    auto right = get<1>(leftData);
    assert(left[1] == 1 && right[1] == 1);
}
"""),
    case("spt_zero_weights", ["struct ShortestPathTree {"], r"""
signed main() {
    ShortestPathTree g(3);
    g.add(1, 2, 0, 0);
    g.add(2, 3, 0, 1);
    g.work();
    assert((g.getEdgeIds() == vector<int>{0, 1}));
    assert(g.getWeightSum() == 0);
}
"""),
    case("mincut_projects", ["template<typename T> struct Flow_", "projects(m);"],
         input="1 2\n1\n1 1 3\n1 1 4\n", output="6"),
    case("gomory_hu", ["template<typename T> struct Flow_", "gomoryHu(Flow &flow"],
         input="5 4\n1 2 5\n1 3 1\n2 3 1\n4 5 2000000000\n4\n1 3\n1 2\n4 5\n1 5\n",
         output="2\n6\n2000000000\n0"),
    case("min_cost_flow", ["struct MinCostFlow {"], r"""
signed main() {
    MinCostFlow f(3);
    f.add(0, 1, 1, -1);
    f.add(0, 1, 1, 2);
    assert((f.flow(0, 1) == pair<int, int>{2, 1}));
    assert((f.flow(0, 0) == pair<int, int>{0, 0}));
    MinCostFlow chain(4);
    chain.add(2, 3, 1, -3);
    chain.add(1, 2, 1, -2);
    chain.add(0, 1, 1, -1);
    assert((chain.flow(0, 3) == pair<int, int>{1, -6}));
}
""", flags=["-ftrapv"]),
    case("wide_mod_and_inverse", ["namespace WideMod {", "int exgcd(int a, int b, int &x",
                                "int getInv(int a, int mod)"], r"""
signed main() {
    assert(WideMod::pow(-2, 3, 13) == 5);
    assert(WideMod::mul(LLONG_MAX - 1, LLONG_MAX - 1, LLONG_MAX) == 1);
    assert(getInv(-2, 9) == 4 && getInv(3, 9) == -1);
}
"""),
    case("exbsgs_large_mod", ["namespace BSGS {"],
         input="9223372036854775807 1 1\n", output="0", flags=["-ftrapv"]),
    case("linear_sieve_bounds", ["bool isprime(int n) {\n    return n >= 2"], r"""
signed main() {
    sieve(10);
    assert(!isprime(-1) && !isprime(0) && !isprime(1) && !isprime(11));
    assert(isprime(7) && !isprime(9));
}
"""),
    case("min25_program", ["namespace min25{"], input="2\n2 998244353\n2 4294967291\n", output="6 6",
         flags=["-Werror=format"]),
    case("factorized_binomial_program", ["int c(int n,int m,int p)"],
         input="6 2 12\n", output="3"),
    case("fenwick_cantor_standalone", ["struct fwt{"], standalone=True, flags=["-ftrapv"],
         input="15\n15 14 13 12 11 10 9 8 7 6 5 4 3 2 1\n", output="972509923"),
    case("wide_matrix", ["bool ok; //"], r"""
signed main() {
    Matrix<4294967291LL> a(1), b(1);
    a[0][0] = 4294967290LL;
    b[0][0] = -1;
    assert((a * a)[0][0] == 1 && (b * b)[0][0] == 1);
    assert(b.inv()[0][0] == a[0][0]);
    assert((b + Matrix<4294967291LL>(1))[0][0] == a[0][0]);
}
""", flags=["-ftrapv"]),
    case("ball_box_program", ["void Stirling2("],
         input="5\n1 3 2\n7 4 3\n10 15 15\n11 3 4\n12 3 2\n",
         output="2\n14\n437893890380859375\n24\n6",
         flags=["-D_GLIBCXX_ASSERTIONS", "-ftrapv"]),
    case("bounded_sum", ["template<class T> constexpr T mypow(T n, int k)", "struct CombZ {",
                         "Z countBoundedSum("], r"""
signed main() {
    assert(countBoundedSum(3, 2, 2).val() == 3);
    assert(countBoundedSum(2, 3, 5).val() == 0);
}
"""),
    case("comb_lookup", ["struct Comb {"], r"""
signed main() {
    Comb c(132);
    assert(c.C(132, 66) == 241200029);
    assert(c.inv(-2) * (c.mod - 2) % c.mod == 1);
}
"""),
    case("geometry_planar", PLANAR + ["ld slope(Point<T>", "template<class T> struct Frac", "Frac<T> slopeEx", "int pointInPolygon(",
              "bool segmentInPolygon(", "vector<Point<T>> staticConvexHull", "struct HullLine {"], r"""
signed main() {
    assert(segmentsIntersect(Line<int>{{0, 0}, {1000000000, 0}},
                             Line<int>{{1, -1000000000}, {1, 1000000000}}));
    assert(slope(Point<int>{0, 0}, Point<int>{2, 1}) == .5L);
    auto fraction = slopeEx(Point<int>{0, 0}, Point<int>{2, 1});
    assert(fraction.val() == .5);
    assert((fraction + fraction).val() == 1 && (fraction - fraction).val() == 0);
    assert((fraction * fraction).val() == .25);
    assert(midSegment(Line<int>{{0, 0}, {1, 0}}).a.x == .5L);
    assert(dis(Point<int>{0, 0}, Point<int>{4000000000LL, 0}) == 4000000000.L);
    assert(abs(rotate({1, 0}, {0, 0}, PI / 2).y - 1) < EPS);
    assert(pointToSegment({1, 0}, {{0, 0}, {0, 0}}).second == 1);
    assert(staticConvexHull(vector<Point<int>>{{1, 1}, {1, 1}, {1, 1}}).size() == 1);
    Point<ld> a{0, 0}, b{.75L * EPS, 0}, c{1.5L * EPS, 0};
    assert(a < b && b < c && a < c);
    vector<Point<ld>> poly{{0, 0}, {4, 0}, {4, 4}, {3, 4}, {3, 1}, {1, 1}, {1, 4}, {0, 4}};
    assert(segmentInPolygon(Line<ld>{{0, 0}, {.5, .5}}, poly));
    assert(!segmentInPolygon(Line<ld>{{0, 3}, {4, 3}}, poly));
    reverse(poly.begin(), poly.end());
    assert(segmentInPolygon(Line<ld>{{0, 0}, {.5, .5}}, poly));
    assert(!segmentInPolygon(Line<ld>{{0, 3}, {4, 3}}, poly));
    ConvexHull hull;
    hull.add({0, 0}); hull.add({2, 0}); hull.add({1, 2});
    assert(hull.isIntersect(1, 0, 1) && hull.isIntersect(1, 0, 2));
    assert(!hull.isIntersect(1, 0, 3));
}
""", flags=["-ftrapv"]),
    case("geometry_circles", PLANAR + ["Point<ld> getPoint(", "circleIntersection(Point<ld>",
                                      "tangent(Point<ld> A, ld Ar"], r"""
signed main() {
    assert(get<0>(circleIntersection({0, 0}, 2, {0, 0}, 2)) == 4);
    auto kindData = circleIntersection({0, 0}, 5, {0, 6}, 5);
    auto kind = get<0>(kindData);
    auto a = get<1>(kindData);
    auto b = get<2>(kindData);
    assert(kind == 3 && a == Point<ld>(-4, 3) && b == Point<ld>(4, 3));
    assert(get<0>(circleIntersection({0, 0}, 2, {4, 0}, 2)) == 2);
    auto countData = tangent({0, 0}, 1, {5, 0}, 2);
    auto count = get<0>(countData);
    auto first = get<1>(countData);
    auto second = get<2>(countData);
    assert(count == 4);
    for (int i = 0; i < count; ++i) {
        assert(abs(dis(first[i], {0, 0}) - 1) < EPS);
        assert(abs(dis(second[i], {5, 0}) - 2) < EPS);
    }
}
"""),
    case("geometry_spatial", SPATIAL, r"""
signed main() {
    L3 x{{0, 0, 0}, {1, 0, 0}}, y{{0, 0, 0}, {0, 1, 0}};
    auto hitData = lineIntersection(y, x);
    auto hit = get<0>(hitData);
    auto point = get<1>(hitData);
    assert(hit && point == P3());
    auto okData = planeIntersection({{0, 0, 0}, {0, 1, 0}, {0, 0, 1}},
                                      {{0, 0, 0}, {1, 0, 0}, {1, 1, 0}});
    auto ok = get<0>(okData);
    auto line = get<1>(okData);
    assert(ok && line.a != line.b && line.a.x == 0 && line.b.x == 0);
    assert(line.a.z == 0 && line.b.z == 0);
    assert(!segmentIntersection1(x, {{2, 0, 0}, {3, 0, 0}}));
    assert(!segmentIntersection1(x, {{1, 0, 0}, {1, 1, 0}}));
    assert(segmentIntersection1(x, {{.5, -1, 0}, {.5, 1, 0}}));
    auto distanceData = lineToLine(x, {{0, 1, 0}, {1, 1, 0}});
    auto distance = get<0>(distanceData);
    auto p = get<1>(distanceData);
    auto q = get<2>(distanceData);
    assert(distance == 1 && dis(p, q) == 1);
}
"""),
]
