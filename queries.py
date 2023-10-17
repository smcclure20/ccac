from z3 import And, Not, Or

from config import ModelConfig
from model import make_solver
from plot import plot_model
from pyz3_utils import MySolver, run_query
from utils import make_periodic


def cca_ma_test(timeout=10):
    '''

    '''
    c = ModelConfig.default()
    c.compose = True
    c.cca = "cca_ma"
    # Simplification isn't necessary, but makes the output a bit easier to
    # understand
    c.simplify = False
    s, v = make_solver(c)
    # Consider the no loss case for simplicity
    # s.add(v.L[0] == 0)
    # Ask for < 10% utilization. Can be made arbitrarily small
    # s.add(v.S[-1] - v.S[0] < 0.1 * c.C * c.T)
    # make_periodic(c, s, v, 2 * c.R)
    qres = run_query(c, s, v, 50)
    print("Satisfiability:", qres.satisfiable)
    if str(qres.satisfiable) == "sat":
        plot_model(qres.model, c, qres.v)



if __name__ == "__main__":
    cca_ma_test()
