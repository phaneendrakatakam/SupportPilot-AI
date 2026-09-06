"""Controlled V3 support-action layer.

The V2 Gemini tool registry remains read-only. V3 action execution is
implemented separately so that protected state-changing operations can
require explicit backend-enforced human approval.
"""
