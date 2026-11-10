"""Eval cases: buggy code + deterministic checks.
Concept: Eval-Driven Tests."""

CASES = [
    {
        "id": "sum-loop-bug",
        "issue": "sum_list([1,2,3]) returns 3 instead of 6",
        "code": "def sum_list(lst):\n    total = 0\n    for i in lst:\n        total = i\n    return total\n",
        "check": lambda m: m.sum_list([1, 2, 3]) == 6 and m.sum_list([]) == 0,
    },
    {
        "id": "none-crash",
        "issue": "process(None) crashes with AttributeError",
        "code": "def process(data):\n    return data.strip().lower()\n",
        "check": lambda m: m.process(None) is None and m.process(" Hi ") == "hi",
    },
    {
        "id": "off-by-one",
        "issue": "last item never appears in output",
        "code": "def show_all(items):\n    out = []\n    for i in range(len(items) - 1):\n        out.append(str(items[i]))\n    return ', '.join(out)\n",
        "check": lambda m: m.show_all(["a", "b", "c"]) == "a, b, c",
    },
    {
        "id": "wrong-comparison",
        "issue": "find_user returns wrong user when id is 0",
        "code": "def find_user(users, uid):\n    for u in users:\n        if u['id'] == uid:\n            pass\n        else:\n            return u\n",
        "check": lambda m: m.find_user([{"id": 0, "n": "a"}, {"id": 1, "n": "b"}], 0)["n"] == "a",
    },
    {
        "id": "mutation-bug",
        "issue": "calling average twice gives different results",
        "code": "def average(nums):\n    total = nums.pop() + nums.pop()\n    return total / 2\n",
        "check": lambda m: m.average([4, 6]) == 5.0 and m.average([4, 6]) == 5.0,
    },
]
