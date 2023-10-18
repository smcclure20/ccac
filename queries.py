from z3 import And, Not, Or

from config import ModelConfig
from model import make_solver
from plot import plot_model
from pyz3_utils import MySolver, run_query
from utils import make_periodic

# RULE_NAMES = ["ma_rules_rewma_low_", ]

class Rule:
    rewma_low = None
    rewma_hi= None
    sewma_low = None
    sewma_hi = None
    srewma_low = None
    srewma_hi = None
    rttr_low = None
    rttr_hi = None
    cmult = None
    cadd = None
    rate = None

    def __str__(self):
        return "rewma:<{:.2f},{:.2f}>; sewma:<{:.2f},{:.2f}>; srewma:<{:.2f},{:.2f}>; rttr:<{:.2f},{:.2f}>; cmult:{}; cadd:{}; rate:{}".format(self.rewma_low, self.rewma_hi, 
                                                                                                             self.sewma_low, self.sewma_hi, 
                                                                                                             self.srewma_low, self.srewma_hi, 
                                                                                                             self.rttr_low, self.rttr_hi,
                                                                                                             self.cmult, self.cadd, self.rate)

def print_rules(model):
    rules = {}
    keys = list(model.keys())
    keys.sort()
    for var in keys:
        if var.startswith("ma_rules") and not(">" in var) and not("<" in var) and not("=" in var):
            rule_num = int(var.split("_")[-1])
            if rule_num not in rules.keys():
                rules[rule_num] = Rule()

            varname = var.split("_")[-2]
            if varname == "hi" or varname == "low":
                varname = var.split("_")[-3] + "_" + varname

            rules[rule_num].__dict__[varname] = model[var].numerator / model[var].denominator   

    for rulenum in rules.keys():
        print(rules[rulenum])


def cca_ma_test(timeout=10):
    '''

    '''
    c = ModelConfig.default()
    c.compose = True
    c.cca = "cca_ma"
    c.T = 10
    # Simplification isn't necessary, but makes the output a bit easier to
    # understand
    c.simplify = False
    s, v, cv = make_solver(c)
    # s.add(v.A_f[0][0] == 0)
    # Consider the no loss case for simplicity
    s.add(v.L[0] == 0)
    # Ask for < 10% utilization. Can be made arbitrarily small
    # s.add(v.S[-1] - v.S[0] > 0.1 * c.C * c.T) 
    # # Ask for worse-cast RTT of 1.5 * Delay for all packets
    # for t in range(c.T):
    #     s.add(cv.rtt[0][t] <= 1.5 * c.R)
    # make_periodic(c, s, v, 2 * c.R) #<- TODO: MAYBE THIS?
    qres = run_query(c, s, v, 500)
    print("Satisfiability:", qres.satisfiable)
    if str(qres.satisfiable) == "sat":
        print_rules(qres.model)
        plot_model(qres.model, c, qres.v)




if __name__ == "__main__":
    cca_ma_test()
