from z3 import And, Not, Or

from config import ModelConfig
from model import make_solver
from plot import plot_model
from pyz3_utils import MySolver, run_query
from utils import make_periodic
from datetime import datetime
import numpy as np

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
        return "rewma:<{:>10.7f},{:>10.7f}>; sewma:<{:>10.7f},{:>10.7f}>; srewma:<{:>10s},{:>10s}>; rttr:<{:>10.7f},{:>10.7f}>; cmult:{:>10s}; cadd:{:>10s}; rate:{:>10s}".format(
                                                                                                             self.rewma_low, self.rewma_hi, 
                                                                                                             self.sewma_low, self.sewma_hi, 
                                                                                                             "{:10.7f}".format(self.srewma_low) if self.srewma_low is not None else str(self.srewma_low),
                                                                                                             "{:10.7f}".format(self.srewma_hi) if self.srewma_hi is not None else str(self.srewma_hi),
                                                                                                             self.rttr_low, self.rttr_hi,
                                                                                                             "{:10.7f}".format(self.cmult) if self.cmult is not None else str(self.cmult),
                                                                                                             "{:10.7f}".format(self.cadd) if self.cadd is not None else str(self.cadd),
                                                                                                             "{:10.7f}".format(self.rate) if self.rate is not None else str(self.rate))

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

def print_signal_state(model, flows, time):
    signal_state = {"rewma": [np.zeros(time) * flows], "sewma": [np.zeros(time) * flows], "srewma": [np.zeros(time) * flows], "rttr": [np.zeros(time) * flows], "rcv": [np.zeros(time) * flows], "snd": [np.zeros(time) * flows]}
    keys = list(model.keys())
    keys.sort()
    for var in keys:
        if (var.startswith("ma_rewma") or var.startswith("ma_sewma") or var.startswith("ma_srewma") or var.startswith("ma_rttr") or var.startswith("ma_pkt")) \
            and not(">" in var) and not("<" in var) and not("=" in var):
            tokens = var.split("_")
            vals = tokens[-1].split(",")
            flow = int(vals[0])
            time = int(vals[1])
            if var.startswith("ma_pkt"):
                signal_state[tokens[2]][flow][time] = model[var].numerator / model[var].denominator
            else:
                signal_state[tokens[1]][flow][time] = model[var].numerator / model[var].denominator

    header_format = "{:5s} " + "{:10s} {:10s} {:10s} {:10s} {:8s} {:8s}" * flows
    print(header_format.format("time", *["f" + str(i) + "_" + k for k in signal_state.keys() for i in range(flows)]))
    for t in range(time):
        row_format = "{:5d} " + "{:<10.7f} {:<10.7f} {:<10.7f} {:<10.7f} {:<8.2f} {:<8.2f}" * flows
        print(row_format.format(t, *[signal_state[signal][flow][t] for signal in signal_state.keys() for flow in range(flows)]))



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
    s.add(v.A_f[0][0] == v.S_f[0][0])
    # Consider the no loss case for simplicity
    s.add(v.L[0] == 0)
    # Ask for < 10% utilization. Can be made arbitrarily small
    s.add(v.S[-1] - v.S[0] > 0.1 * c.C * c.T) 
    # # Ask for worse-cast RTT of 1.5 * Delay for all packets
    # for t in range(c.T):
    #     s.add(cv.rtt[0][t] <= 1.5 * c.R)
    # make_periodic(c, s, v, 2 * c.R) #<- TODO: MAYBE THIS?

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Query Start Time =", current_time)

    qres = run_query(c, s, v, 9000)

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Query End Time =", current_time)

    print("Satisfiability:", qres.satisfiable)
    if str(qres.satisfiable) == "sat":
        print_rules(qres.model)
        print_signal_state(qres.model, c.N, c.T)
        plot_model(qres.model, c, qres.v)




if __name__ == "__main__":
    cca_ma_test()
