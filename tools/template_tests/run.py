import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from regressions import REGRESSIONS


ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "正文"
TMP = ROOT / "tools" / "template_tests" / ".generated"
TMP.mkdir(exist_ok=True)

SUPPORTED_PATHS = {
    key: next(BOOK.glob(f"{key} -*.md"))
    for key in ("01", "02", "03A", "03B", "04", "05A", "05B", "06A", "07", "08")
}
FILES = {key: path.read_text(encoding="utf-8") for key, path in SUPPORTED_PATHS.items()}
BLOCK_PATTERN = re.compile(r"^```c(?:\+\+|pp)\n(.*?)\n```", re.M | re.S)


def find_block(marker, chapter=None):
    matches = [
        (key, match[1])
        for key, page in FILES.items()
        if chapter is None or key == chapter
        for match in BLOCK_PATTERN.finditer(page)
        if marker in match[1]
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one code block for {marker!r}, found {len(matches)}")
    return matches[0]


TESTS = [
    {
        "name": "dijkstra",
        "snippets": ["struct Dijkstra {"],
        "main": r"""
signed main() {
    Dijkstra G(3);
    G.add(1, 2, 3);
    G.add(2, 3, 4);
    G.add(1, 3, 10);
    G.work(1);
    assert(G.getDis(3) == 7);
    return 0;
}
""",
    },
    {
        "name": "bellman_ford",
        "snippets": ["struct BellmanFord {"],
        "main": r"""
signed main() {
    BellmanFord G(3);
    G.add(1, 2, 2);
    G.add(2, 3, -5);
    G.add(1, 3, 10);
    G.work(1);
    assert(G.getDis(3) == -3);
    assert(!G.cantReach(3));
    assert(!G.inNegLoop(3));

    BellmanFord H(7);
    H.add(4, 5, 0);
    H.add(3, 4, 0);
    H.add(2, 3, 100);
    H.add(1, 3, 0);
    H.add(1, 2, 0);
    H.add(2, 2, -1);
    H.add(6, 6, -1);
    H.add(6, 7, 0);
    H.work(1);
    assert(!H.inNegLoop(1) && !H.cantReach(1));
    for (int i = 2; i <= 5; ++i) {
        assert(H.inNegLoop(i) && !H.cantReach(i));
    }
    assert(H.cantReach(6) && !H.inNegLoop(6));
    assert(H.cantReach(7) && !H.inNegLoop(7));

    H.work(6);
    assert(H.cantReach(2) && !H.inNegLoop(2));
    assert(H.inNegLoop(6) && H.inNegLoop(7));

    BellmanFord single(1);
    single.add(1, 1, -1);
    single.work();
    assert(single.inNegLoop(1));
    return 0;
}
""",
    },
    {
        "name": "floyd_struct",
        "snippets": ["struct Floyd {"],
        "main": r"""
signed main() {
    Floyd G(3);
    G.add(1, 2, 1);
    G.add(2, 3, 2);
    G.add(1, 3, 10);
    G.work();
    assert(G.getDis(1, 3) == 3);
    return 0;
}
""",
    },
    {
        "name": "prim",
        "snippets": ["struct Prim {"],
        "main": r"""
signed main() {
    Prim G(3);
    G.add(1, 2, 1);
    G.add(2, 3, 2);
    G.add(1, 3, 5);
    assert(G.work() == 3);
    return 0;
}
""",
    },
    {
        "name": "dsu",
        "snippets": ["struct Kruskal {", "vector<int> fa, p, e, f;"],
        "main": r"""
signed main() {
    DSU d(3);
    Kruskal::DSU nested(3);
    assert(nested.merge(1, 2));
    assert(!d.same(1, 2));
    d.merge(1, 2);
    assert(d.same(1, 2));
    return 0;
}
""",
    },
    {
        "name": "kruskal",
        "snippets": ["struct Kruskal {"],
        "main": r"""
signed main() {
    Kruskal G(3);
    G.add(1, 2, 1);
    G.add(2, 3, 2);
    G.add(1, 3, 5);
    assert(G.work() == 3);
    return 0;
}
""",
    },
    {
        "name": "scc",
        "snippets": ["struct SCC {"],
        "main": r"""
signed main() {
    SCC G(4);
    G.add(1, 2); G.add(2, 1);
    G.add(2, 3);
    G.add(3, 4); G.add(4, 3);
    auto cntData = G.work();
    auto cnt = get<0>(cntData);
    auto adj = get<1>(cntData);
    auto col = get<2>(cntData);
    auto siz = get<3>(cntData);
    assert(cnt == 2);
    assert(col[1] == col[2]);
    assert(col[3] == col[4]);
    assert(col[1] != col[3]);
    return 0;
}
""",
    },
    {
        "name": "edcc",
        "snippets": ["struct EDCC {"],
        "main": r"""
signed main() {
    EDCC G(5);
    G.add(1, 2);
    G.add(1, 2);
    G.add(2, 3);
    G.add(4, 4);
    auto data = G.work();
    const auto &adj = get<1>(data);
    const auto &col = get<2>(data);
    const auto &siz = get<3>(data);
    assert(get<0>(data) == 4);
    assert(col[1] == col[2] && col[2] != col[3]);
    assert(siz[col[1]] == 2);
    assert((adj[col[1]] == vector<int>{col[3]}));
    assert((adj[col[3]] == vector<int>{col[1]}));
    assert(adj[col[4]].empty() && adj[col[5]].empty());
    assert((G.bridge == set<array<int, 2>>{{2, 3}}));
    assert((G.direct == set<array<int, 2>>{{1, 2}, {2, 1}}));
    return 0;
}
""",
    },
    {
        "name": "v_dcc",
        "snippets": ["struct V_DCC {"],
        "main": r"""
signed main() {
    V_DCC G(5);
    G.add(1, 2);
    G.add(1, 2);
    G.add(2, 3);
    G.add(2, 4);
    G.add(5, 5);
    auto data = G.rebuild();
    const auto &adj = data.second;
    assert(G.cnt == 4 && data.first == 9);
    assert(G.point[2] && !G.point[1] && !G.point[5]);
    assert(G.S.empty());
    assert(adj[2].size() == 3 && adj[5].size() == 1);
    for (int i = 1; i <= G.cnt; i++) {
        assert(adj[5 + i] == G.col[i]);
        for (int x : G.col[i]) {
            assert(count(adj[x].begin(), adj[x].end(), 5 + i) == 1);
        }
    }
    assert((adj[adj[5].front()] == vector<int>{5}));
    return 0;
}
""",
    },
    {
        "name": "bipartite",
        "snippets": ["struct BipartiteGraph {"],
        "main": r"""
signed main() {
    BipartiteGraph G(3);
    G.add(1, 2);
    G.add(2, 3);
    assert(G.work());
    G.add(1, 3);
    assert(!G.work());
    return 0;
}
""",
    },
    {
        "name": "topsort",
        "snippets": ["vector<int> topsort("],
        "main": r"""
signed main() {
    vector<vector<int>> adj(6);
    adj[1] = {2, 2};
    adj[2] = {3};
    adj[4] = {3};
    auto order = topsort(adj);
    assert(order.size() == 5);
    vector<int> pos(6);
    for (int i = 0; i < 5; i++) pos[order[i]] = i;
    for (int x = 1; x <= 5; x++) {
        for (int y : adj[x]) assert(pos[x] < pos[y]);
    }
    adj[3] = {2};
    assert((topsort(adj) == vector<int>{1, 4, 5}));
    return 0;
}
""",
    },
    {
        "name": "general_matching",
        "snippets": ["struct MV {"],
        "main": r"""
signed main() {
    MV G(6);
    G.add(1, 2);
    G.add(2, 3);
    G.add(3, 1);
    G.add(2, 4);
    G.add(2, 4);
    G.add(5, 5);
    auto res = G.work();
    assert(res.first == 2);
    assert(res.second.size() == 7 && res.second[0] == 0);
    assert(res.second[1] == 3 && res.second[3] == 1);
    assert(res.second[2] == 4 && res.second[4] == 2);
    assert(res.second[5] == 0 && res.second[6] == 0);
    assert(G.work() == res);
    return 0;
}
""",
    },
    {
        "name": "general_weighted_matching",
        "snippets": ["struct GeneralWeightedMatching {"],
        "main": r"""
signed main() {
    GeneralWeightedMatching G(7);
    G.add(1, 2, 16);
    G.add(2, 3, 9);
    G.add(1, 3, 10);
    G.add(2, 4, 9);
    G.add(2, 4, 1);
    G.add(5, 6, 500000000);
    G.add(6, 7, 0);
    G.add(5, 7, -1);
    G.add(7, 7, 100);
    assert(G.work() == 500000019);
    assert((G.answer() == vector<array<int, 2>>{{1, 3}, {2, 4}, {5, 6}}));
    assert(G.lk[1] == 3 && G.lk[3] == 1);
    assert(G.lk[2] == 4 && G.lk[4] == 2);
    assert(G.lk[5] == 6 && G.lk[6] == 5 && G.lk[7] == 0);
    assert(G.work() == 500000019);
    return 0;
}
""",
    },
    {
        "name": "hungary_match",
        "snippets": ["struct HungaryMatch {"],
        "main": r"""
signed main() {
    HungaryMatch G(2, 2);
    G.add(1, 1);
    G.add(1, 2);
    G.add(2, 2);
    assert(G.work() == 2);
    auto ans = G.answer();
    assert(ans.size() == 2);
    return 0;
}
""",
    },
    {
        "name": "hopcroft_karp",
        "snippets": ["struct HopcroftKarp"],
        "main": r"""
signed main() {
    HopcroftKarp G(5, 6);
    G.add(1, 1);
    G.add(1, 3);
    G.add(2, 2);
    G.add(2, 4);
    G.add(3, 1);
    G.add(3, 2);
    G.add(4, 2);
    G.add(4, 2);
    const vector<array<int, 2>> expected{{1, 3}, {2, 4}, {3, 1}, {4, 2}};
    assert(G.work() == 4 && G.answer() == expected);
    assert(G.work() == 4 && G.answer() == expected);
    assert(G.l[5] == 0 && G.r[5] == 0 && G.r[6] == 0);
    G.add(5, 6);
    assert(G.work() == 5 && G.l[5] == 6 && G.r[6] == 5);
    return 0;
}
""",
    },
    {
        "name": "max_cost_match",
        "snippets": ["struct MaxCostMatch {"],
        "main": r"""
signed main() {
    MaxCostMatch G(2);
    G.add(1, 1, 3);
    G.add(1, 2, 1);
    G.add(2, 1, 2);
    G.add(2, 2, 4);
    assert(G.work() == 7);
    auto leftData = G.answer(2, 2);
    auto left = get<0>(leftData);
    auto right = get<1>(leftData);
    assert(left[1] == 1 && left[2] == 2);
    return 0;
}
""",
    },
    {
        "name": "dag",
        "snippets": ["struct DAG {"],
        "main": r"""
signed main() {
    DAG G(3);
    G.add(1, 2, 3);
    G.add(2, 3, 4);
    G.add(1, 3, 5);
    assert(G.work(1, 3) == 7);
    return 0;
}
""",
    },
    {
        "name": "shortest_path_tree",
        "snippets": ["struct ShortestPathTree : Dijkstra"],
        "main": r"""
signed main() {
    ShortestPathTree G(3);
    G.add(1, 2, 1, 11);
    G.add(2, 3, 2, 22);
    G.add(1, 3, 10, 33);
    G.work(1);
    assert(G.getDis(3) == 3);
    assert(G.getWeightSum() == 3);
    auto ids = G.getEdgeIds();
    sort(ids.begin(), ids.end());
    assert(ids == vector<int>({11, 22}));
    return 0;
}
""",
    },
    {
        "name": "stoer_wagner",
        "snippets": ["struct StoerWagner {"],
        "main": r"""
signed main() {
    StoerWagner G(3);
    G.add(1, 2, 1);
    G.add(2, 3, 1);
    G.add(1, 3, 1);
    assert(G.work() == 2);
    return 0;
}
""",
    },
    {
        "name": "directed_euler",
        "snippets": ["struct DirectedEulerGraph : EulerGraph"],
        "main": r"""
signed main() {
    DirectedEulerGraph G(3);
    G.add(1, 2);
    G.add(2, 3);
    assert(G.hasEulerPath());
    auto path = G.work();
    assert(path == vector<int>({1, 2, 3}));
    DirectedEulerGraph H(4);
    H.add(1, 1); H.add(1, 2); H.add(2, 1);
    H.add(1, 2); H.add(2, 1);
    assert(H.hasEulerPath());
    assert(H.work(2) == vector<int>({2, 1, 1, 2, 1, 2}));
    DirectedEulerGraph disconnected(3);
    disconnected.add(1, 1); disconnected.add(3, 3);
    assert(!disconnected.hasEulerPath());
    return 0;
}
""",
    },
    {
        "name": "undirected_euler",
        "snippets": ["struct UndirectedEulerGraph : EulerGraph"],
        "main": r"""
signed main() {
    UndirectedEulerGraph G(3);
    G.add(1, 2);
    G.add(2, 3);
    assert(G.hasEulerPath());
    auto path = G.work();
    assert(path == (vector<pair<int, int>>{{1, 2}, {2, 3}}));
    UndirectedEulerGraph H(3);
    H.add(2, 2); H.add(2, 3); H.add(2, 3);
    assert(H.hasEulerPath());
    assert(H.work() == (vector<pair<int, int>>{{2, 2}, {2, 3}, {3, 2}}));
    UndirectedEulerGraph disconnected(4);
    disconnected.add(1, 1); disconnected.add(3, 3);
    assert(!disconnected.hasEulerPath());
    return 0;
}
""",
    },
    {
        "name": "difference_constraints",
        "snippets": ["struct DifferenceConstraints {"],
        "main": r"""
signed main() {
    DifferenceConstraints G(2);
    G.add(1, 2, 3);
    G.add(2, 1, -1);
    assert(G.work());
    assert(G.getVal(1) - G.getVal(2) <= 3);
    assert(G.getVal(2) - G.getVal(1) <= -1);
    return 0;
}
""",
    },
    {
        "name": "two_sat",
        "snippets": ["struct TwoSat {"],
        "main": r"""
signed main() {
    TwoSat G(1);
    G.add(0, true, 0, true);
    assert(G.work());
    auto ans = G.answer();
    assert(ans[0] == true);
    auto uniq = G.uniqueAnswer();
    assert(uniq[0] == 1);
    return 0;
}
""",
    },
    {
        "name": "shortest_path_counter",
        "snippets": ["template<class T> constexpr T mypow(T n, int k)", "struct ShortestPathCounter {"],
        "main": r"""
signed main() {
    ShortestPathCounter G(4);
    G.add(1, 2, 1); G.add(2, 1, 1);
    G.add(2, 3, 1); G.add(3, 2, 1);
    G.add(1, 3, 2); G.add(3, 1, 2);
    G.add(1, 4, 1); G.add(4, 1, 1);
    G.add(4, 3, 1); G.add(3, 4, 1);
    G.work(1);
    assert(G.dis[3][0] == 2 && G.num[3][0].val() == 3);
    assert(G.dis[3][1] == 4);
    ShortestPathCounter H(4);
    H.add(1, 3, 5);
    H.add(1, 2, 1);
    H.add(2, 3, 1); H.add(2, 3, 1); H.add(2, 3, 4);
    H.work(1);
    assert(H.dis[3][0] == 2 && H.num[3][0].val() == 2);
    assert(H.dis[3][1] == 5 && H.num[3][1].val() == 2);
    assert(H.dis[4][0] == ShortestPathCounter::INF);
    H.work(3);
    assert(H.dis[1][1] == ShortestPathCounter::INF && H.num[1][1].val() == 0);
    return 0;
}
""",
    },
    {
        "name": "floyd_function",
        "snippets": ["int floyd(vector<vector<int>> dis, int inf)"],
        "main": r"""
signed main() {
    constexpr int inf = 4'000'000'000'000'000'000LL;
    vector<vector<int>> dis(4, vector<int>(4, inf));
    for (int i = 1; i <= 3; ++i) dis[i][i] = 0;
    assert(floyd(dis, inf) == inf);
    dis[1][2] = dis[2][1] = 2'000'000'000LL;
    dis[1][3] = dis[3][1] = 2'000'000'000LL;
    dis[2][3] = dis[3][2] = 2'000'000'000LL;
    assert(floyd(dis, inf) == 6'000'000'000LL);
}
""",
    },
    {
        "name": "undirected_min_cycle",
        "snippets": ["int minCycleBfs("],
        "main": r"""
signed main() {
    vector<vector<int>> g{{}, {2,3}, {1,3}, {1,2}, {}};
    assert(minCycleBfs(g) == 3);
    g[1] = {2};
    g[3] = {2};
    assert(minCycleBfs(g) == -1);
    return 0;
}
""",
    },
    {
        "name": "simple_cycle_counter",
        "snippets": ["struct SimpleCycleCounter {"],
        "main": r"""
signed main() {
    SimpleCycleCounter G(3);
    G.add(0, 1);
    G.add(1, 2);
    G.add(2, 0);
    assert(G.work() == 1);
    return 0;
}
""",
    },
    {
        "name": "cycle_finder",
        "snippets": ["struct CycleFinder {"],
        "main": r"""
signed main() {
    auto check = [](int n, bool directed, vector<pair<int, int>> edges, int size) {
        CycleFinder g(n, directed);
        for (auto e : edges) g.add(e.first, e.second);
        auto res = g.work();
        assert((int)res.first.size() == size && (int)res.second.size() == size);
        assert(set<int>(res.first.begin(), res.first.end()).size() == res.first.size());
        assert(set<int>(res.second.begin(), res.second.end()).size() == res.second.size());
        for (int i = 0; i < size; ++i) {
            auto edge = edges.at(res.second[i] - 1);
            pair<int, int> step{res.first[i], res.first[(i + 1) % size]};
            assert(edge == step || (!directed && edge == make_pair(step.second, step.first)));
        }
        assert(g.work() == res);
    };
    check(4, true, {{2,3}, {3,4}, {4,2}}, 3);
    check(4, true, {{1,2}, {1,3}, {3,4}, {4,2}}, 0);
    check(3, true, {{2,3}, {3,2}}, 2);
    check(3, false, {{2,3}}, 0);
    check(3, false, {{2,3}, {3,2}}, 2);
    check(4, false, {{2,3}, {3,4}, {4,2}}, 3);
    check(3, false, {{2,2}}, 1);
    check(3, true, {{2,2}}, 1);
}
""",
    },
]


TESTS.extend(REGRESSIONS)


def parse_args():
    parser = argparse.ArgumentParser(description="Compile and run template tests.")
    parser.add_argument("--all", action="store_true", help="run all supported tests")
    parser.add_argument("--changed", action="store_true", help="run tests related to changed supported files")
    parser.add_argument("--files", nargs="*", default=[], help="run tests for specific files")
    parser.add_argument("--list", action="store_true", help="list matched tests and exit")
    parser.add_argument("--optimization", choices=("0", "2"), default="2")
    return parser.parse_args()


def run_cmd(cmd, cwd=ROOT, **kwargs):
    proc = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace", cwd=cwd, **kwargs
    )
    return proc.returncode, proc.stdout, proc.stderr


def git_file_list(args):
    code, out, _ = run_cmd([args[0], "-c", "core.quotepath=false", *args[1:]])
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def get_changed_supported_keys():
    files = set()
    files.update(git_file_list(["git", "diff", "--name-only"]))
    files.update(git_file_list(["git", "diff", "--name-only", "--cached"]))
    code, _, _ = run_cmd(["git", "rev-parse", "--verify", "@{upstream}"])
    if code == 0:
        files.update(git_file_list(["git", "diff", "--name-only", "@{upstream}...HEAD"]))

    if any(name.startswith("tools/template_tests/") or name == ".github/workflows/template-tests.yml" for name in files):
        return set(SUPPORTED_PATHS)

    matched = set()
    for raw in files:
        p = (ROOT / raw).resolve()
        for key, path in SUPPORTED_PATHS.items():
            if p == path.resolve():
                matched.add(key)
    return matched


def normalize_input_files(paths):
    matched = set()
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        else:
            p = p.resolve()
        for key, path in SUPPORTED_PATHS.items():
            if p == path.resolve():
                matched.add(key)
    return matched


def test_groups(test):
    groups = {find_block(marker)[0] for marker in test["snippets"]}
    if not test.get("standalone"):
        groups.add("01")
    return groups


def select_tests(args):
    if args.all:
        return TESTS

    target_keys = set()
    if args.changed or (not args.files and not args.all):
        target_keys |= get_changed_supported_keys()
    if args.files:
        target_keys |= normalize_input_files(args.files)

    if not target_keys:
        return []

    return [test for test in TESTS if test_groups(test) & target_keys]


def build_source(test):
    parts = []
    if not test.get("standalone"):
        _, base = find_block("void solve(){", "01")
        parts.append(base.split("void solve(){", 1)[0])
    if test.get("pre"):
        parts.append(test["pre"])
    for marker in test["snippets"]:
        _, block = find_block(marker)
        if marker in test.get("rename_main", ()):
            block = block.replace("signed main(", "signed example_main(")
        parts.append(block)
    parts.append(test.get("main", ""))
    return "\n".join(parts)


def cleanup_generated():
    for path in TMP.iterdir():
        if path.name == "results.json":
            continue
        if path.is_file():
            path.unlink()


def main():
    args = parse_args()
    tests = select_tests(args)

    # Check if g++ is available
    code, _, err = run_cmd(["g++", "--version"])
    if code != 0:
        print(f"Error: g++ not found or not working. Please install g++.\n{err}", file=sys.stderr)
        return 1

    if args.list:
        print(json.dumps([t["name"] for t in tests], ensure_ascii=False, indent=2))
        return 0

    cleanup_generated()
    if not tests:
        summary = {
            "total": 0,
            "compiled": 0,
            "ran": 0,
            "failed": [],
            "message": "No matched supported template tests.",
        }
        (TMP / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    results = []
    for test in tests:
        cpp_path = TMP / f"{test['name']}.cpp"
        exe_path = TMP / f"{test['name']}.exe"
        try:
            cpp_path.write_text(build_source(test), encoding="utf-8")
            code, out, err = run_cmd([
                "g++", "-std=gnu++14", "-Werror=c++17-extensions", "-Werror=c++20-extensions", f"-O{args.optimization}", *test.get("flags", ()),
                str(cpp_path), "-o", str(exe_path)
            ])
            item = {"name": test["name"], "compile_ok": code == 0}
            if code != 0:
                item["compile_error"] = err
                results.append(item)
                continue
            try:
                code, out, err = run_cmd([str(exe_path)], input=test.get("input", ""), timeout=10)
            except subprocess.TimeoutExpired:
                item.update(run_ok=False, run_error="execution exceeded 10 seconds")
                results.append(item)
                continue
            expected = test.get("output")
            item["run_ok"] = code == 0 and (expected is None or out.split() == expected.split())
            if code == 0 and not item["run_ok"]:
                err = f"expected {expected!r}, got {out!r}"
            if not item["run_ok"]:
                item["run_error"] = err or out
            results.append(item)
        except (OSError, ValueError) as e:
            item = {"name": test["name"], "compile_ok": False, "run_ok": False, "error": str(e)}
            results.append(item)
        finally:
            if cpp_path.exists():
                cpp_path.unlink()
            if exe_path.exists():
                exe_path.unlink()

    summary = {
        "total": len(results),
        "compiled": sum(1 for x in results if x.get("compile_ok")),
        "ran": sum(1 for x in results if x.get("compile_ok") and x.get("run_ok")),
        "failed": [x for x in results if not (x.get("compile_ok") and x.get("run_ok"))],
    }
    (TMP / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
