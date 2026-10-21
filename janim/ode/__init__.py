"""The ODE stack for the simulations: Tsit5 and ForwardDiff's duals, ported from Julia packages (MIT).

`janim.ode.tsit5` ports OrdinaryDiffEqTsit5 2.1.2 on OrdinaryDiffEqCore 4.12.0
(the adaptive driver, the PI controller, tstops and saveat); `janim.ode.dual`
ports ForwardDiff 1.4.3's forward-mode gradient.
"""

from .tsit5 import ODEProblem, Tsit5, init, solve, step

__all__ = [
    "ODEProblem",
    "Tsit5",
    "init",
    "solve",
    "step",
]
