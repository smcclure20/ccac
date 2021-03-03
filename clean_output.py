''' Take SMT output and clean it up, trying to remove the clutter and leave
behind only the essential details for why the counter-example works '''

from copy import copy
from fractions import Fraction
from functools import reduce
from model_utils import ModelConfig, ModelDict
from my_solver import extract_vars
import numpy as np
import operator
from scipy.optimize import LinearConstraint, minimize
from typing import Any, Dict, List, Set, Tuple, Union
from z3 import And, ArithRef, AstVector, BoolRef, RatNumRef


def eval_smt(m: ModelDict, a) -> Union[Fraction, bool]:
    if type(a) is AstVector:
        a = And(a)

    decl = str(a.decl())
    children = [eval_smt(m, x) for x in a.children()]

    if len(children) == 0:
        if type(a) is ArithRef:
            return m[str(a)]
        elif type(a) is RatNumRef:
            return a.as_fraction()
        elif str(a.decl()) == "True":
            return True
        elif str(a.decl()) == "False":
            return False
        elif type(a) is BoolRef:
            return m[str(a)]

    if decl == "Not":
        assert(len(a.children()) == 1)
        return not children[0]
    if decl == "And":
        return all(children)
    if decl == "Or":
        return any(children)
    if decl == "Implies":
        assert(len(a.children()) == 2)
        if children[0] is True and children[1] is False:
            return False
        else:
            return True
    if decl == "If":
        assert(len(a.children()) == 3)
        if children[0] is True:
            return children[1]
        else:
            return children[2]
    if decl == "+":
        return sum(children)
    if decl == "-":
        if len(a.children()) == 2:
            return children[0] - children[1]
        elif len(a.children()) == 1:
            return -children[0]
        else:
            assert(False)
    if decl == "*":
        return reduce(operator.mul, children, 1)
    if decl == "/":
        assert(len(children) == 2)
        return children[0] / children[1]
    if decl == "<":
        assert(len(a.children()) == 2)
        return children[0] < children[1]
    if decl == "<=":
        assert(len(a.children()) == 2)
        return children[0] <= children[1]
    if decl == ">":
        assert(len(a.children()) == 2)
        return children[0] > children[1]
    if decl == ">=":
        assert(len(a.children()) == 2)
        return children[0] >= children[1]
    if decl == "==":
        assert(len(a.children()) == 2)
        return children[0] == children[1]
    if decl == "Distinct":
        assert(len(a.children()) == 2)
        return children[0] != children[1]
    print(f"Unrecognized decl {decl} in {str(a)}")
    exit(1)


def anded_constraints(m: ModelDict, a, truth=True, top_level=True) -> List[Any]:
    ''' We'll find a subset of linear inequalities that are satisfied in the
    solution. To simplify computation, we'll only search for "nice" solutions
    within this set. 'a' is an assertion. 'top_level' and 'truth' are internal
    variables and indicate what we expect the truth value of the sub-expression
    to be and whether we are in the top level of recursion respectively '''

    # No point searching for solutions if we are not given a satisfying
    # assignment to begin with
    if top_level:
        assert(eval_smt(m, a))

    if type(a) is AstVector:
        a = And(a)

    decl = str(a.decl())
    if decl in ["<", "<=", ">", ">=", "==", "Distinct"]:
        assert(len(a.children()) == 2)
        x, y = a.children()

        if not truth:
            decl = {
                "<": ">=",
                "<=": ">",
                ">": "<=",
                ">=": "<",
                "==": "Distinct",
                "Distinct": "=="
            }[decl]
        if decl in ["==", "Distinct"]:
            if type(x) is BoolRef or type(y) is BoolRef:
                assert(type(x) is BoolRef and type(y) is BoolRef)
                # It should evaluate to what it evaluated in the original
                # assignment
                return (anded_constraints(m, x, eval_smt(m, x), False)
                        + anded_constraints(m, y, eval_smt(m, y), False))

        if decl == "Distinct":
            # Convert != to either < or >
            if eval_smt(m, x) < eval_smt(m, y):
                return [x < y]
            else:
                return [y < x]

        if not truth:
            if decl == "<":
                return [x < y]
            if decl == "<=":
                return [x <= y]
            if decl == ">":
                return [x > y]
            if decl == ">=":
                return [x >= y]
        return [a]
    # if decl == "If":
    #     assert(len(a.children()) == 3)
    #     c, t, f = a.children()
    #     if eval_smt(m, c):
    #         return children[0] + children[1]
    #     else:
    #         return children[0] + children[2]

    if decl == "Not":
        assert(len(a.children()) == 1)
        return anded_constraints(m, a.children()[0], (not truth), False)
    if decl == "And":
        if truth:
            return sum([anded_constraints(m, x, True, False)
                        for x in a.children()],
                       start=[])
        else:
            for x in a.children():
                if not eval_smt(m, x):
                    # Return just the first one (arbitrary choice). Returning
                    # more causes us to be unnecessarily restrictive
                    return anded_constraints(m, x, False, False)
    if decl == "Or":
        if truth:
            for x in a.children():
                if eval_smt(m, x):
                    # Return just the first one (arbitrary choice). Returning more
                    # causes us to be unnecessarily restrictive
                    return anded_constraints(m, x, True, False)
        else:
            return sum([anded_constraints(m, x, True, False)
                        for x in a.children()],
                       start=[])

    if decl == "Implies":
        assert(len(a.children()) == 2)
        assert(type(eval_smt(m, a.children()[0])) is bool)
        if truth:
            if eval_smt(m, a.children()[0]):
                return anded_constraints(m, a.children()[1], True, False)
            else:
                return anded_constraints(m, a.children()[0], False, False)
        else:
            return (anded_constraints(m, a.children()[0], True, False)
                    + anded_constraints(m, a.children()[1], False, False))
    if type(a) is BoolRef:
        # Must be a boolean variable. We needn't do anything here
        return []
    print(f"Unrecognized decl {decl} in {a}")
    assert(False)


class LinearVars:
    def __init__(self, vars: Dict[str, float] = {}, constant: float = 0):
        self.vars = vars
        self.constant = constant

    def __add__(self, other):
        vars, constant = copy(self.vars), copy(self.constant)
        for k in other.vars:
            if k in vars:
                vars[k] += other.vars[k]
            else:
                vars[k] = other.vars[k]
        constant += other.constant
        return LinearVars(vars, constant)

    def __mul__(self, factor: float):
        vars, constant = copy(self.vars), copy(self.constant)
        for k in vars:
            vars[k] *= factor
        constant *= factor
        return LinearVars(vars, constant)

    def __str__(self):
        return ' + '.join([f"{self.vars[k]} * {k}" for k in self.vars])\
               + f" + {self.constant}"

    def __eq__(self, other) -> bool:
        return self.vars == other.vars and self.constant == other.constant


def get_linear_vars(expr: Union[ArithRef, RatNumRef])\
        -> LinearVars:
    ''' Given a linear arithmetic expression, return its equivalent that takes
    the form res[1] + sum_i res[0][i][0] * res[0][i][1]'''

    decl = str(expr.decl())
    if decl == "+":
        return sum([get_linear_vars(x) for x in expr.children()],
                   start=LinearVars())
    if decl == "-":
        assert(len(expr.children()) in [1, 2])
        if len(expr.children()) == 2:
            a, b = map(get_linear_vars, expr.children())
            return a + (b * (-1.0))
        else:
            return get_linear_vars(expr.children()[0]) * -1.0
    if decl == "*":
        assert(len(expr.children()) == 2)
        a, b = expr.children()
        if type(a) == ArithRef and type(b) == RatNumRef:
            return get_linear_vars(a) * float(b.as_decimal(100))
        if type(a) == RatNumRef and type(b) == ArithRef:
            return get_linear_vars(b) * float(a.as_decimal(100))
        print(f"Only linear terms allowed. Found {str(expr)}")
        exit(1)
    if type(expr) is ArithRef:
        # It is a single variable, since we have eliminated other cases
        return LinearVars({decl: 1})
    if type(expr) is RatNumRef:
        return LinearVars({}, float(expr.as_decimal(100)))
    print(f"Unrecognized expression {expr}")
    exit(1)


def solver_constraints(constraints: List[Any])\
        -> Tuple[LinearConstraint, List[str]]:
    ''' Given a list of SMT constraints (e.g. those output by
    `anded_constraints`), return the corresponding LinearConstraint object and
    the names of the variables in the order used in LinearConstraint '''

    # First get all the variables
    varss: Set[str] = set().union(*[set(extract_vars(e)) for e in constraints])
    vars: List[str] = list(varss)
    A = np.zeros((len(constraints), len(vars)))
    lb = np.zeros(len(constraints))
    ub = np.zeros(len(constraints))

    for i, cons in enumerate(constraints):
        assert(len(cons.children()) == 2)
        a = get_linear_vars(cons.children()[0])
        b = get_linear_vars(cons.children()[1])

        # Construct the linear part h
        if str(cons.decl()) in [">=", ">", "=="]:
            lin = b + (a * -1.0)
        elif str(cons.decl()) in ["<=", "<"]:
            lin = a + (b * -1.0)
        else:
            assert(False)

        # Put it into the matrix
        for k in lin.vars:
            j = vars.index(k)
            A[i, j] = lin.vars[k]

        # Make the bounds
        if cons.decl == "==":
            lb[i] = -lin.constant
            ub[i] = -lin.constant
        else:
            lb[i] = -float("inf")
            ub[i] = lin.constant

    return (LinearConstraint(A, lb, ub, keep_feasible=True), vars)

def simplify_solution(c: ModelConfig, m: ModelDict, assertions) -> ModelDict:
    constraints, vars_l = solver_constraints(anded_constraints(m, assertions))
    # vars_l = [x for x in m if type(m[x]) is Fraction]
    vars = {k: vars_l.index(k) for k in vars_l}
    init_values = np.asarray([m[v] for v in vars])

    def score(values: np.array) -> float:
        # new_model = copy(m)
        # for k in vars:
        #     new_model[k] = values[vars[k]]
        # if not eval_smt(new_model, assertions):
        #     print("Infeasible")
        #     return c.T * 100
        res = 0
        for t in range(1, c.T):
            res += abs(values[vars[f"tot_inp_{t}"]]
                       - values[vars[f"tot_inp_{t-1}"]])
            res += abs(values[vars[f"tot_out_{t}"]]
                       - values[vars[f"tot_out_{t-1}"]])
        print(res)
        return res

    #soln, _, _ = minimize(score, init_values, constraints=constraints)
    soln, _, _ = minimize(score, init_values)

    res = copy(m)
    for var in vars:
        res[var] = soln[vars[var]]
    return res
