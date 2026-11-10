"""Example hand-written skill (a template for your own)."""

from skills.loader import Skill

SECURITY_AUDIT = Skill(
    name="security_audit",
    trigger=["security", "injection", "xss", "secret", "vulnerability"],
    prompt="""Perform a security audit of the changed files.
Check: SQL injection, path traversal, hardcoded secrets, unsafe deserialization,
command injection. Rate each finding critical|high|medium|low.""",
)
