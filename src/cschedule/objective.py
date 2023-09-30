"""Objective functions for the pyomo model."""

import pyomo.environ as pe


def summation(model):
    """Simple summation"""
    return pe.summation(model.STUDENTS_IN_SESSION)
