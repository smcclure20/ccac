'''  '''

from z3 import And, If, Implies, Not, Or, AtMost, AtLeast

from config import ModelConfig
from pyz3_utils import MySolver
from variables import Variables

NUM_RULES = 10

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
    
class MAVariables:
    def __init__(self, c: ModelConfig, s: MySolver):
        # TODO: Consider if all of these need to be full variables
        # TODO: Can probably change some of these back to INTs
        self.last_pkt_rcv_time = [[s.Real(f"ma_pkt_rcv_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.last_pkt_snd_time = [[s.Real(f"ma_pkt_snd_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.rtt = [[s.Real(f"ma_rtt_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.rewma = [[s.Real(f"ma_rewma_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.sewma = [[s.Real(f"ma_sewma_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.srewma = [[s.Real(f"ma_srewma_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.rttr = [[s.Real(f"ma_rttr_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.min_rtt = [[s.Real(f"ma_min_rtt_{n},{t}") for t in range(c.T)] for n in range(c.N)]

        self.chosen_cmult = [[s.Real(f"ma_chosen_cmult_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.chosen_cadd = [[s.Real(f"ma_chosen_cadd_{n},{t}") for t in range(c.T)] for n in range(c.N)]
        self.chosen_rate = [[s.Real(f"ma_chosen_rate_{n},{t}") for t in range(c.T)] for n in range(c.N)]

        self.matches = [[[s.Bool(f"ma_matches_{n},{t},{i}") for i in range(NUM_RULES)] for t in range(c.T)] for n in range(c.N)]
        
        self.rules = [Rule(Action(s.Real(f"ma_rules_cmult_{r}"), s.Real(f"ma_rules_cadd_{r}"), s.Real(f"ma_rules_rate_{r}")),
                                     {"rewma": SignalRange(s.Real(f"ma_rules_rewma_low_{r}"), s.Real(f"ma_rules_rewma_hi_{r}")), 
                                      "sewma": SignalRange(s.Real(f"ma_rules_sewma_low_{r}"), s.Real(f"ma_rules_sewma_hi_{r}")), 
                                      "srewma": SignalRange(s.Real(f"ma_rules_srewma_low_{r}"), s.Real(f"ma_rules_srewma_hi_{r}")), 
                                      "rttr": SignalRange(s.Real(f"ma_rules_rttr_low_{r}"), s.Real(f"ma_rules_rttr_hi_{r}"))
                                      }) for r in range(NUM_RULES)]


def cca_ma(c: ModelConfig, s: MySolver, v: Variables) -> MAVariables:
    cv = MAVariables(c, s)

    for rule1 in cv.rules:
        # Enforce on each rule that low < high
        s.add(rule1.signal_space["rewma"].low < rule1.signal_space["rewma"].high)
        s.add(rule1.signal_space["sewma"].low < rule1.signal_space["sewma"].high)
        s.add(rule1.signal_space["srewma"].low < rule1.signal_space["srewma"].high)
        s.add(rule1.signal_space["rttr"].low < rule1.signal_space["rttr"].high)

        s.add(rule1.signal_space["rewma"].low >= 0)
        s.add(rule1.signal_space["sewma"].low >= 0)
        s.add(rule1.signal_space["srewma"].low >= 0)
        s.add(rule1.signal_space["rttr"].low >= 0)
        s.add(rule1.signal_space["rewma"].high >= 0)
        s.add(rule1.signal_space["sewma"].high >= 0)
        s.add(rule1.signal_space["srewma"].high >= 0)
        s.add(rule1.signal_space["rttr"].high >= 0)

        s.add(rule1.action.cwnd_mult >= 0)
        s.add(rule1.action.rate >= 0)

        # Enforce that the rule does not overlap with any other rule (at least one dimension is non-overlapping)
        for rule2 in cv.rules:
            if rule1 == rule2:
                continue
            s.add(Or(Or(rule1.signal_space["rewma"].high <= rule2.signal_space["rewma"].low, rule1.signal_space["rewma"].low >= rule2.signal_space["rewma"].high), 
                     Or(rule1.signal_space["sewma"].high <= rule2.signal_space["sewma"].low, rule1.signal_space["sewma"].low >= rule2.signal_space["sewma"].high), 
                     Or(rule1.signal_space["srewma"].high <= rule2.signal_space["srewma"].low, rule1.signal_space["srewma"].low >= rule2.signal_space["srewma"].high), 
                     Or(rule1.signal_space["rttr"].high <= rule2.signal_space["rttr"].low, rule1.signal_space["rttr"].low >= rule2.signal_space["rttr"].high)))

    alpha = 1 / 8
    salpha = 1 / 256

    for n in range(c.N):
        s.add(cv.last_pkt_rcv_time[n][0] == 0) # One option: don't require this and then it isn't necessarily starting from initial
        s.add(cv.last_pkt_snd_time[n][0] == 0)
        s.add(cv.min_rtt[n][0] == 10000000000)
        s.add(v.c_f[n][0] >= 0)

        for t in range(c.T):
            if t == 0:
                continue
            if t - c.R > 0:
                s.add(cv.last_pkt_rcv_time[n][t] == If((v.S_f[n][t-c.R]) > (v.S_f[n][t-c.R-1]), t, cv.last_pkt_rcv_time[n][t-1]))
            s.add(cv.last_pkt_snd_time[n][t] == If(v.A_f[n][t] > v.A_f[n][t-1], t, cv.last_pkt_rcv_time[n][t-1]))

            # Set the RTT to the time interval necessary for arrival bytes = server bytes (but get the timestamp of the first time the arrival curve had this value)
            for dt in range(t-1):
                s.add(Implies(And(
                                  v.S_f[n][t-c.R] <= v.A_f[n][t-dt], 
                                  v.S_f[n][t-c.R] > v.A_f[n][t-dt-1]), 
                                  cv.rtt[n][t] == t-c.R - (t-dt-1 + (v.S_f[n][t-c.R] - v.A_f[n][t-dt-1]) / (v.A_f[n][t-dt] - v.A_f[n][t-dt-1]))))

            s.add(If(cv.last_pkt_rcv_time[n][t] == t, 
                     cv.min_rtt[n][t] == If(cv.rtt[n][t] < cv.min_rtt[n][t-1], cv.rtt[n][t], cv.min_rtt[n][t-1]),
                     cv.min_rtt[n][t] == cv.min_rtt[n][t-1]))

            # TODO: FOR ALL THESE CHANGES TO STATE BASED ON A PKT BEING RECEIVED, THAT LETS IT DO ANYTHING WHEN THERE ISNT ONE
            # If you received a packet, update signal values and find rule
            # If it's the first packet, set values without weighting
            s.add(If(cv.last_pkt_rcv_time[n][t] == t, 
                     If(cv.last_pkt_rcv_time != 0, 
                        cv.rewma[n][t] == alpha * (cv.last_pkt_rcv_time[n][t] - cv.last_pkt_rcv_time[n][t-1]) + (1-alpha) * cv.rewma[n][t], 
                        cv.rewma[n][t] == cv.last_pkt_rcv_time[n][t] - cv.last_pkt_rcv_time[n][t-1]),
                     cv.rewma[n][t] == cv.rewma[n][t-1]))
            s.add(If(cv.last_pkt_rcv_time[n][t] == t, 
                     If(cv.last_pkt_snd_time != 0, 
                        cv.sewma[n][t] == alpha * (cv.last_pkt_snd_time[n][t] - cv.last_pkt_snd_time[n][t-1]) + (1-alpha) * cv.sewma[n][t],
                        cv.sewma[n][t] == cv.last_pkt_snd_time[n][t] - cv.last_pkt_snd_time[n][t-1]),
                     cv.sewma[n][t] == cv.sewma[n][t-1]))
            s.add(If(cv.last_pkt_rcv_time[n][t] == t,
                     If(cv.last_pkt_rcv_time != 0,
                        cv.srewma[n][t] == salpha * (cv.last_pkt_rcv_time[n][t] - cv.last_pkt_rcv_time[n][t-1]) + (1-salpha) * cv.srewma[n][t],
                        cv.srewma[n][t] == cv.last_pkt_rcv_time[n][t] - cv.last_pkt_rcv_time[n][t-1]),
                     cv.srewma[n][t] == cv.srewma[n][t-1]))
            s.add(If(cv.last_pkt_rcv_time[n][t] == t, 
                     cv.rttr[n][t] == cv.rtt[n][t] / cv.min_rtt[n][t],
                     cv.rttr[n][t] == cv.rttr[n][t-1]))

            # Find the rule that matches the signal values
            for i, rule in enumerate(cv.rules):
                matches = And(
                        cv.last_pkt_rcv_time[n][t] == t,
                        And(cv.rewma[n][t] >= rule.signal_space["rewma"].low, cv.rewma[n][t] < rule.signal_space["rewma"].high),
                        And(cv.sewma[n][t] >= rule.signal_space["sewma"].low, cv.sewma[n][t] < rule.signal_space["sewma"].high),
                        And(cv.srewma[n][t] >= rule.signal_space["srewma"].low, cv.srewma[n][t] < rule.signal_space["srewma"].high),
                        And(cv.rttr[n][t] >= rule.signal_space["rttr"].low, cv.rttr[n][t] < rule.signal_space["rttr"].high)
                    )
                s.add(Implies(
                    matches,
                    And(cv.chosen_cmult[n][t] == rule.action.cwnd_mult, cv.chosen_cadd[n][t] == rule.action.cwnd_add, cv.chosen_rate[n][t] == rule.action.rate)
                ))
                s.add(cv.matches[n][t][i] == matches)

            # Enforce exactly one rule matches
            s.add(If(cv.last_pkt_rcv_time[n][t] == t, And(AtMost(*cv.matches[n][t], 1), AtLeast(*cv.matches[n][t], 1)), AtMost(*cv.matches[n][t], 0)))

            # Set the rate and cwnd based on the rule
            s.add(If(cv.last_pkt_rcv_time[n][t] == t, 
                     If(cv.chosen_cmult[n][t] * v.c_f[n][t-1] + cv.chosen_cadd[n][t] >= 0, 
                        v.c_f[n][t] == cv.chosen_cmult[n][t] * v.c_f[n][t-1] + cv.chosen_cadd[n][t], v.c_f[n][t] == 0),
                       v.c_f[n][t] == v.c_f[n][t-1]))
            s.add(If(cv.last_pkt_rcv_time[n][t] == t, v.r_f[n][t] == cv.chosen_rate[n][t], v.r_f[n][t] == v.r_f[n][t-1]))

    return cv