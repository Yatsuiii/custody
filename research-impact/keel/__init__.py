"""Keel: a research program as a typed graph, and what new evidence does to it.

Codename, provisional. The public surface is small on purpose:

    program.load(path)      read a program, or refuse a malformed one
    ingest.ingest(...)      admit or refuse proposed evidence, with reasons
    ledger.replay(log)      rebuild the program from its events
    propagate.evaluate(...) states plus the justification for each
    report.change_report()  what moved, what held still, and why
"""
