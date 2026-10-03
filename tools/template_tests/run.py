import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "正文"
TMP = ROOT / "tools" / "template_tests" / ".generated"
TMP.mkdir(exist_ok=True)

FILES = {
    "03A": (BOOK / "03A - 图论.md").read_text(encoding="utf-8"),
    "03B": (BOOK / "03B - 图论常见结论及例题.md").read_text(encoding="utf-8"),
}

SUPPORTED_PATHS = {
    "03A": BOOK / "03A - 图论.md",
    "03B": BOOK / "03B - 图论常见结论及例题.md",
}


COMMON = r"""
#include <bits/stdc++.h>
using namespace std;
#define int long long

template<int MOD>
struct Zmod {
    int x;
    Zmod(int v = 0) {
        x = (v % MOD + MOD) % MOD;
    }
    int val() const {
        return x;
    }
    Zmod& operator+=(const Zmod& other) {
        x += other.x;
        if (x >= MOD) x -= MOD;
        return *this;
    }
    friend Zmod operator+(Zmod a, const Zmod& b) {
        return a += b;
    }
};
using Z = Zmod<1000000007>;

"""


def extract_block(marker: str) -> str:
    for text in FILES.values():
        for m in re.finditer(r"```c\+\+\n(.*?)\n```", text, re.S):
            block = m.group(1)
            if marker in block:
                return block
    raise RuntimeError(f"cannot find block containing: {marker}")


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
    return 0;
}
""",
    },
    {
        "name": "spfa",
        "snippets": ["struct SPFA {"],
        "main": r"""
signed main() {
    SPFA G(3);
    G.add(1, 2, 2);
    G.add(2, 3, -5);
    G.add(1, 3, 10);
    G.work(1);
    assert(G.getDis(3) == -3);
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
        "snippets": ["struct DSU {"],
        "main": r"""
signed main() {
    DSU d(3);
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
    auto [cnt, adj, col, siz] = G.work();
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
    EDCC G(3);
    G.add(1, 2);
    G.add(2, 3);
    auto [cnt, adj, col, siz] = G.work();
    assert(cnt == 3);
    assert(col[1] != col[2] && col[2] != col[3]);
    assert(!G.bridge.empty());
    return 0;
}
""",
    },
    {
        "name": "v_dcc",
        "snippets": ["struct V_DCC {"],
        "main": r"""
signed main() {
    V_DCC G(3);
    G.add(1, 2);
    G.add(2, 3);
    G.work();
    assert(G.point[2]);
    auto [tot, adj] = G.rebuild();
    assert(tot == 3);
    assert(G.pointId[2] != 0);
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
        "name": "forward_star_graph",
        "snippets": ["struct ForwardStarGraph {"],
        "main": r"""
signed main() {
    ForwardStarGraph G(3, 3);
    G.add(1, 2);
    G.add(1, 3);
    G.dfs(1);
    assert(G.siz[1] == 3);
    G.bfs(1);
    assert(G.bfsDep[2] == 2);
    auto [ok, ord] = G.topsort();
    assert(ok);
    return 0;
}
""",
    },
    {
        "name": "general_matching",
        "snippets": ["struct GeneralMatching {"],
        "main": r"""
signed main() {
    GeneralMatching G(3);
    G.add(0, 1);
    G.add(1, 2);
    G.add(0, 2);
    auto [cnt, match] = G.work();
    assert(cnt == 1);
    return 0;
}
""",
    },
    {
        "name": "general_weighted_matching",
        "snippets": ["struct GeneralWeightedMatching {"],
        "main": r"""
signed main() {
    GeneralWeightedMatching G(2);
    G.add(1, 2, 5);
    assert(G.work() == 5);
    auto ans = G.answer();
    assert(ans.size() == 1);
    assert(ans[0][0] == 1 && ans[0][1] == 2);
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
        "snippets": ["struct HopcroftKarp {"],
        "main": r"""
signed main() {
    HopcroftKarp G(2, 2);
    G.add(0, 0);
    G.add(1, 1);
    assert(G.work() == 2);
    auto ans = G.answer();
    assert(ans.size() == 2);
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
    auto [left, right] = G.answer(2, 2);
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
        "snippets": ["struct ShortestPathTree {"],
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
        "snippets": ["struct DirectedEulerGraph {"],
        "main": r"""
signed main() {
    DirectedEulerGraph G(3);
    G.add(1, 2);
    G.add(2, 3);
    assert(G.hasEulerPath());
    auto path = G.work();
    assert(path == vector<int>({1, 2, 3}));
    return 0;
}
""",
    },
    {
        "name": "undirected_euler",
        "snippets": ["struct UndirectedEulerGraph {"],
        "main": r"""
signed main() {
    UndirectedEulerGraph G(3);
    G.add(1, 2);
    G.add(2, 3);
    assert(G.hasEulerPath());
    auto path = G.work();
    assert(path.size() == 2);
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
        "name": "tree_pair_distance_sum",
        "snippets": ["struct TreePairDistanceSum {"],
        "main": r"""
signed main() {
    TreePairDistanceSum G(2);
    G.add(1, 2);
    G.add(2, 3);
    G.add(3, 4);
    assert(G.work() == 4);
    return 0;
}
""",
    },
    {
        "name": "tree_max_connected_block",
        "snippets": ["struct TreeMaxConnectedBlock {"],
        "main": r"""
signed main() {
    TreeMaxConnectedBlock G(3);
    G.setPoint(1, 1);
    G.setPoint(2, 2);
    G.setPoint(3, 3);
    G.add(1, 2, 4);
    G.add(2, 3, 5);
    assert(G.work() == 15);
    return 0;
}
""",
    },
    {
        "name": "shortest_path_counter",
        "snippets": ["struct ShortestPathCounter {"],
        "main": r"""
signed main() {
    ShortestPathCounter G(4);
    G.add(1, 2, 1); G.add(2, 1, 1);
    G.add(2, 3, 1); G.add(3, 2, 1);
    G.add(1, 3, 2); G.add(3, 1, 2);
    G.add(1, 4, 1); G.add(4, 1, 1);
    G.add(4, 3, 1); G.add(3, 4, 1);
    G.work(1);
    assert(G.answer(3).val() == 3);
    return 0;
}
""",
    },
    {
        "name": "triangle_finder",
        "snippets": ["struct TriangleFinder {"],
        "main": r"""
signed main() {
    TriangleFinder G(3);
    G.add(1, 2);
    G.add(2, 3);
    G.add(3, 1);
    auto cyc = G.work();
    assert(cyc.size() == 3);
    return 0;
}
""",
    },
    {
        "name": "directed_min_cycle_counter",
        "snippets": ["struct DirectedMinCycleCounter {"],
        "main": r"""
signed main() {
    DirectedMinCycleCounter G(3, 1000000007);
    G.add(1, 2, 1);
    G.add(2, 3, 1);
    G.add(3, 1, 1);
    auto [len, cnt] = G.work();
    assert(len == 3);
    assert(cnt == 1);
    return 0;
}
""",
    },
    {
        "name": "floyd_function",
        "snippets": ["int floyd(int n) {"],
        "pre": r"""
vector<vector<int>> val, dis;
""",
        "main": r"""
signed main() {
    int n = 3;
    val.assign(n + 1, vector<int>(n + 1, (int)4e18));
    dis.assign(n + 1, vector<int>(n + 1, (int)4e18));
    for (int i = 1; i <= n; ++i) val[i][i] = dis[i][i] = 0;
    auto add = [&](int x, int y, int w) {
        val[x][y] = val[y][x] = dis[x][y] = dis[y][x] = min(dis[x][y], w);
    };
    add(1, 2, 1);
    add(2, 3, 1);
    add(1, 3, 1);
    assert(floyd(n) == 3);
    return 0;
}
""",
    },
    {
        "name": "undirected_min_cycle",
        "snippets": ["struct UndirectedMinCycle {"],
        "main": r"""
signed main() {
    UndirectedMinCycle G(3);
    G.add(1, 2);
    G.add(2, 3);
    G.add(1, 3);
    assert(G.work() == 3);
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
        "name": "simple_cycle_finder",
        "snippets": ["struct SimpleCycleFinder {"],
        "main": r"""
signed main() {
    SimpleCycleFinder G(3);
    G.add(1, 2);
    G.add(2, 3);
    G.add(3, 1);
    auto cyc = G.work();
    assert(cyc.size() == 3);
    return 0;
}
""",
    },
    {
        "name": "directed_cycle_counter",
        "snippets": ["struct DirectedCycleCounter {"],
        "main": r"""
signed main() {
    DirectedCycleCounter G(2);
    G.add(1, 2);
    G.add(2, 1);
    assert(G.work() == 1);
    return 0;
}
""",
    },
    {
        "name": "directed_cycle_finder",
        "snippets": ["struct DirectedCycleFinder {"],
        "main": r"""
signed main() {
    DirectedCycleFinder G(3);
    G.add(1, 2);
    G.add(2, 3);
    G.add(3, 1);
    auto [V, E] = G.work();
    assert(V.size() == 3);
    assert(E.size() == 3);
    return 0;
}
""",
    },
    {
        "name": "undirected_cycle_finder",
        "snippets": ["struct UndirectedCycleFinder {"],
        "main": r"""
signed main() {
    UndirectedCycleFinder G(3);
    G.add(1, 2);
    G.add(2, 3);
    G.add(3, 1);
    auto [V, E] = G.work();
    assert(V.size() == 3);
    assert(E.size() == 3);
    return 0;
}
""",
    },
    {
        "name": "planar_chord_checker",
        "snippets": ["struct TwoSat {", "struct PlanarChordChecker {"],
        "main": r"""
signed main() {
    PlanarChordChecker G(4);
    G.add(1, 3);
    G.add(2, 4);
    auto [ok, ans] = G.work();
    assert(ok);
    assert(ans.size() == 2);
    return 0;
}
""",
    },
]


def parse_args():
    parser = argparse.ArgumentParser(description="Compile and run template tests.")
    parser.add_argument("--all", action="store_true", help="run all supported tests")
    parser.add_argument("--changed", action="store_true", help="run tests related to changed supported files")
    parser.add_argument("--files", nargs="*", default=[], help="run tests for specific files")
    parser.add_argument("--list", action="store_true", help="list matched tests and exit")
    return parser.parse_args()


def run_cmd(cmd, cwd=ROOT):
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


def git_file_list(args):
    code, out, _ = run_cmd(args)
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
    groups = set()
    for marker in test["snippets"]:
        for key, text in FILES.items():
            if marker in text:
                groups.add(key)
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
    parts = [COMMON]
    if test.get("pre"):
        parts.append(test["pre"])
    for marker in test["snippets"]:
        parts.append(extract_block(marker))
        parts.append("\n")
    parts.append(test["main"])
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
    cleanup_generated()

    if args.list:
        print(json.dumps([t["name"] for t in tests], ensure_ascii=False, indent=2))
        return 0

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
                "g++", "-std=gnu++20", "-O2", str(cpp_path), "-o", str(exe_path)
            ])
            item = {"name": test["name"], "compile_ok": code == 0}
            if code != 0:
                item["compile_error"] = err
                results.append(item)
                continue
            code, out, err = run_cmd([str(exe_path)])
            item["run_ok"] = code == 0
            if code != 0:
                item["run_error"] = err or out
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
