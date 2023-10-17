'''  '''

from z3 import And, If, Implies, Not

from config import ModelConfig
from pyz3_utils import MySolver
from variables import Variables

NUM_RULES = 50

class Action:
    def __init__(self, cwnd_mult, cwnd_add, rate):
        self.cwnd_mult = cwnd_mult
        self.cwnd_add = cwnd_add
        self.rate = rate

class SignalRange:
    def __init__(self, low, high):
        self.low = low
        self.high = high

class Rule:
    def __init__(self, action, signal_ranges):
        self.action = action
        self.signal_space = signal_ranges

    def matches(self, point):
        pass #TODO: Use this!

class RuleTable:
    def __init__(self, rules):
        self.rules = rules
    
class MAVariables:
    def __init__(self, c: ModelConfig, s: MySolver):
        # TODO: Consider if all of these need to be full variables
        self.last_pkt_rcv_time = [s.Int(f"ma_pkt_rcv_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.last_pkt_snd_time = [s.Int(f"ma_pkt_snd_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.rtt = [s.Int(f"ma_rtt_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.rewma = [s.Real(f"ma_rewma_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.sewma = [s.Real(f"ma_sewma_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.srewma = [s.Real(f"ma_srewma_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.rttr = [s.Real(f"ma_rttr_{n},{t}") for t in range(c.T) for n in range(c.N)]
        self.min_rtt = [s.Int(f"ma_min_rtt_{n},{t}") for t in range(c.T) for n in range(c.N)]
        
        # TODO: We need solver rules that these cannot be overlapping (and that they cover the whole space!) => need defined behavior for if none match
        self.rules = RuleTable([Rule(Action(s.Real(f"ma_rules_cmult{r}"), s.Real(f"ma_rules_cadd{r}"), s.Real(f"ma_rules_rate{r}")),
                                     [SignalRange(s.Real(f"ma_rules_rewma_low_{r}"), s.Real(f"ma_rules_rewma_hi_{r}")), 
                                      SignalRange(s.Real(f"ma_rules_sewma_low_{r}"), s.Real(f"ma_rules_sewma_hi_{r}")), 
                                      SignalRange(s.Real(f"ma_rules_srewma_low_{r}"), s.Real(f"ma_rules_srewma_hi_{r}")), 
                                      SignalRange(s.Real(f"ma_rules_rttr_low_{r}"), s.Real(f"ma_rules_rttr_hi_{r}"))
                                      ]) for r in range(NUM_RULES)])


def cca_ma(self, c: ModelConfig, s: MySolver, v: Variables):
    cv = MAVariables(c, s)

    for rule1 in cv.rules:
        for rule2 in cv.rules:
            s.add(And(rule1.signal_space[0].high <= rule2.signal_space[0].low, rule1.signal_space[0].high < rule2.signal_space[0].low)

    alpha = 1 / 8 # TODO: Check this
    salpha = 1 / 256
    for n in range(c.N):
        for t in range(c.T):
            s.add(cv.last_pkt_recv_time[n][t] == If(v.S_f[n][t-c.R] > v.S_f[n][t-c.R-1], t, cv.last_pkt_rcv_time[n][t-1]))
            s.add(cv.last_pkt_snd_time[n][t] == If(v.A_f[n][t] > v.S_f[n][t-1], t, cv.last_pkt_rcv_time[n][t-1]))
            s.add(cv.min_rtt[n][t] == If(v.S_f))

            for dt in range(c.T):
                if v.S_f[n][t] == v.A_f[n][t-dt]:
                    s.add(cv.rtt[n][t] == dt)
                    break

            if cv.last_pkt_recv_time[n][t] == t:
                s.add(cv.rewma == alpha * (cv.last_pkt_recv_time[n][t] - cv.last_pkt_recv_time[n][t-1]) + (1-alpha) * cv.rewma)
                s.add(cv.sewma == alpha * (cv.last_pkt_snd_time[n][t] - cv.last_pkt_snd_time[n][t-1]) + (1-alpha) * cv.sewma)
                s.add(cv.srewma == salpha * (cv.last_pkt_snd_time[n][t] - cv.last_pkt_snd_time[n][t-1]) + (1-salpha) * cv.srewma)
                s.add(cv.rttr == cv.rtt[n][t] / cv.min_rtt[n][t])


                for rule in self.rules:
                    if (rule[0] <= cv.rewma[n][t] and cv.rewma[n][t] < rule[1]) and (rule[2] <= cv.sewma[n][t] and cv.sewma[n][t] < rule[3]) \
                        and (rule[4] <= cv.srewma[n][t] and cv.srewma[n][t] < rule[5]) and (rule[6] <= cv.rttr[n][t] and cv.rttr[n][t] < rule[7]):
                        break

                # Set the rate and cwnd based on the rule
                s.add(v.c_f[n][t] == rule.action.cwnd_mult * v.c_f[n][t] + rule.action.cwnd_add)
                s.add(v.r_f[n][t] == rule.action.rate)

