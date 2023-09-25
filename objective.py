"""Objective functions"""

import pyomo.environ as pe


def summation(model):
    return pe.summation(model.STUDENTS_IN_SESSION)
